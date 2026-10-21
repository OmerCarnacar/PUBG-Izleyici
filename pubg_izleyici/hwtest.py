# Donanım testi (işlemci, RAM, disk)
import ctypes
import hashlib
import json
import os
import re
import threading
import time
import winreg
from .config import DATA
from .winutil import reg

HWTEST = os.path.join(DATA, 'donanim_testleri.json')


def find_pubg_dir():
    """PUBG'nin kurulu olduğu klasör (Steam kaydı ya da Steam kütüphaneleri), bulunamazsa None."""
    for root, path in ((winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 578080'),
                       (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 578080')):
        loc = reg(root, path, 'InstallLocation')
        if loc and os.path.isdir(loc):
            return loc
    steam = reg(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath')
    if steam:
        try:
            with open(os.path.join(steam, 'steamapps', 'libraryfolders.vdf'), encoding='utf-8', errors='ignore') as f:
                libs = re.findall(r'"path"\s+"([^"]+)"', f.read())
        except OSError:
            libs = [steam]
        for lib in libs:
            d = os.path.join(lib.replace('\\\\', '\\'), 'steamapps', 'common', 'PUBG')
            if os.path.isdir(d):
                return d
    return None


def cpu_test(progress, sample, single_s=5, multi_s=30):
    """SHA-256 ile yük (hashlib büyük veride GIL'i bırakır, iş parçacıkları tüm çekirdekleri gerçekten doldurur).
    sample() her saniye {'T': sıcaklık, 'MHz': hız} döner. Sonuç: puanlar, sıcaklık ve hız düşüşü."""
    buf = os.urandom(1 << 20)

    def run(n, sec, base, span, samples):
        stop, cnt = threading.Event(), [0] * n

        def w(i):
            h, k = hashlib.sha256, 0
            while not stop.is_set():
                h(buf).digest(); k += 1
            cnt[i] = k
        ts = [threading.Thread(target=w, args=(i,), daemon=True) for i in range(n)]
        t0 = time.time()
        for t in ts:
            t.start()
        while time.time() - t0 < sec:
            time.sleep(1)
            samples.append(sample())
            progress(base + span * min(1, (time.time() - t0) / sec))
        stop.set()
        for t in ts:
            t.join()
        return sum(cnt) / (time.time() - t0)

    idle = sample()
    s1, sm = [], []
    single = run(1, single_s, 0, 0.15, s1)
    multi = run(os.cpu_count() or 1, multi_s, 0.15, 0.85, sm)
    mhz = [x['MHz'] for x in sm if x.get('MHz')]
    temps = [x['T'] for x in sm if x.get('T')]
    first = sum(mhz[:5]) / len(mhz[:5]) if len(mhz) >= 10 else 0
    last = sum(mhz[-10:]) / len(mhz[-10:]) if len(mhz) >= 10 else 0
    return {'single': round(single), 'multi': round(multi), 'scale': round(multi / single, 1) if single else 0,
            't_idle': idle.get('T') or 0, 't_max': max(temps, default=0), 'mhz_first': round(first), 'mhz_last': round(last),
            'drop': round(100 * (first - last) / first, 1) if first else 0, 'threads': os.cpu_count()}


def ram_test(progress, avail_mb):
    """Bant genişliği (bellek kopyalama) + hızlı desen kontrolü. MemTest86 yerine geçmez, bariz hataları yakalar."""
    blk = 64 << 20
    # Bant genişliği: 4 iş parçacığı ctypes.memmove ile kopyalar (GIL bırakılır, bellek kanalları gerçekten dolar).
    # Python'un kendi dilim kopyası tek iş parçacığında kalıyor ve DDR5'i bile "yavaş" gösteriyordu.
    nthr, size = 4, 64 << 20
    bufs = [(ctypes.create_string_buffer(size), ctypes.create_string_buffer(size)) for _ in range(nthr)]
    stop, cnt = threading.Event(), [0] * nthr

    def w(i):
        a, b, k = bufs[i][0], bufs[i][1], 0
        while not stop.is_set():
            ctypes.memmove(b, a, size); k += 1
        cnt[i] = k
    ts = [threading.Thread(target=w, args=(i,), daemon=True) for i in range(nthr)]
    t0 = time.perf_counter()
    for t in ts:
        t.start()
    while time.perf_counter() - t0 < 3:
        time.sleep(0.25)
        progress(0.3 * (time.perf_counter() - t0) / 3)
    stop.set()
    for t in ts:
        t.join()
    bw = sum(cnt) * size / (time.perf_counter() - t0) / 1e9
    bufs.clear()  # 512 MB'ı hemen bırak
    progress(0.3)
    size = max(256, min(2048, int(avail_mb * 0.25))) << 20  # boş RAM'in %25'i, en fazla 2 GB
    errors, tested, chunks = 0, 0, []
    try:
        for _ in range(size // blk):
            chunks.append(bytearray(blk))
    except MemoryError:
        pass
    pats = [b'\xaa\x55' * 32, b'\x55\xaa' * 32, os.urandom(4096)]
    for pi, pat in enumerate(pats):
        exp = pat * (blk // len(pat))
        for ci, c in enumerate(chunks):
            c[:] = exp
            if c != exp:  # memcmp; fark varsa bayt bayt say
                errors += sum(1 for x, y in zip(c, exp) if x != y)
            tested += blk
            progress(0.3 + 0.7 * ((pi * len(chunks) + ci + 1) / (len(pats) * len(chunks) or 1)))
            time.sleep(0)
    mb = len(chunks) * blk >> 20
    del chunks
    return {'bw': round(bw, 1), 'checked_mb': mb, 'errors': errors}


def disk_test(folder, progress, size_mb=1024):
    """Windows önbelleği atlanarak (FILE_FLAG_NO_BUFFERING) sıralı yazma/okuma ve 4K rastgele okuma."""
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateFileW.restype = ctypes.c_void_p
    k.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
                              ctypes.c_uint32, ctypes.c_void_p]
    k.WriteFile.argtypes = k.ReadFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                                                  ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    k.VirtualAlloc.restype = ctypes.c_void_p
    k.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
    k.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]

    class OV(ctypes.Structure):
        _fields_ = [('i', ctypes.c_size_t), ('ih', ctypes.c_size_t), ('off', ctypes.c_uint32), ('offh', ctypes.c_uint32),
                    ('ev', ctypes.c_void_p)]
    blk = 4 << 20
    path = os.path.join(folder, 'pubg_izleyici_disk_testi.tmp')
    buf = k.VirtualAlloc(None, blk, 0x3000, 4)  # sayfa hizalı tampon (önbelleksiz G/Ç için şart)
    if not buf:
        raise OSError('bellek ayrılamadı')
    ctypes.memmove(buf, os.urandom(blk), blk)  # sıkıştırılamayan veri
    n, nb = ctypes.c_uint32(), size_mb * (1 << 20) // blk
    NOBUF, WT = 0x20000000, 0x80000000
    try:
        h = k.CreateFileW(path, 0xC0000000, 0, None, 2, NOBUF | WT, None)
        if h in (None, ctypes.c_void_p(-1).value):
            raise OSError(f'test dosyası açılamadı ({ctypes.get_last_error()})')
        t0 = time.perf_counter()
        for i in range(nb):
            if not k.WriteFile(h, buf, blk, ctypes.byref(n), None):
                k.CloseHandle(h); raise OSError(f'yazma hatası ({ctypes.get_last_error()})')
            progress(0.4 * (i + 1) / nb)
        wr = size_mb / (time.perf_counter() - t0)
        k.CloseHandle(h)
        h = k.CreateFileW(path, 0x80000000, 1, None, 3, NOBUF, None)
        t0 = time.perf_counter()
        for i in range(nb):
            if not k.ReadFile(h, buf, blk, ctypes.byref(n), None):
                k.CloseHandle(h); raise OSError(f'okuma hatası ({ctypes.get_last_error()})')
            progress(0.4 + 0.4 * (i + 1) / nb)
        rd = size_mb / (time.perf_counter() - t0)
        # 4K rastgele okuma (oyunda harita/eşya yüklemesine en yakın ölçüm), 4 saniye
        import random
        cnt, t0, nblk4 = 0, time.perf_counter(), size_mb * 256
        ov = OV()
        while time.perf_counter() - t0 < 4:
            off = random.randrange(nblk4) * 4096
            ov.off, ov.offh = off & 0xffffffff, off >> 32
            k.ReadFile(h, buf, 4096, ctypes.byref(n), ctypes.byref(ov))
            cnt += 1
            if cnt % 256 == 0:
                progress(0.8 + 0.2 * min(1, (time.perf_counter() - t0) / 4))
        r4 = cnt * 4096 / (time.perf_counter() - t0) / 1048576
        k.CloseHandle(h)
        return {'write': round(wr), 'read': round(rd), 'r4k': round(r4, 1), 'iops': round(cnt / 4)}
    finally:
        k.VirtualFree(buf, 0, 0x8000)
        try:
            os.remove(path)
        except OSError:
            pass


def load_hwtests():
    try:
        with open(HWTEST, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def save_hwtests(h):
    try:
        with open(HWTEST, 'w', encoding='utf-8') as f:
            json.dump(h[-50:], f, ensure_ascii=False)
    except OSError:
        pass

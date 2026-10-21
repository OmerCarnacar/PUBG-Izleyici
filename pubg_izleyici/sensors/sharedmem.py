# Paylaşılan bellek: Core Temp ve GPU-Z
import ctypes
import re
import struct

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.OpenFileMappingW.restype = ctypes.c_void_p
k32.OpenFileMappingW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
k32.MapViewOfFile.restype = ctypes.c_void_p
k32.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_size_t]
k32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
k32.CloseHandle.argtypes = [ctypes.c_void_p]


def read_shm(name, size):
    h = k32.OpenFileMappingW(4, 0, name)  # FILE_MAP_READ
    if not h:
        return None
    try:
        p = k32.MapViewOfFile(h, 4, 0, 0, size)
        if not p:
            return None
        try:
            return ctypes.string_at(p, size)
        finally:
            k32.UnmapViewOfFile(p)
    finally:
        k32.CloseHandle(h)


def cpu_sensor():
    b = read_shm('CoreTempMappingObject', 2686)
    if not b:
        return None
    cores, cpus = struct.unpack_from('<II', b, 1536)
    tj = struct.unpack_from('<I', b, 1024)[0]
    fahr, delta = b[2684], b[2685]
    temps = []
    for i in range(min(256, cores * max(cpus, 1))):
        t = struct.unpack_from('<f', b, 1544 + 4 * i)[0]
        if delta:
            t = tj - t
        elif fahr:
            t = (t - 32) * 5 / 9
        temps.append(t)
    if not temps:
        return None
    return {'T': round(max(temps)), 'MHz': round(struct.unpack_from('<f', b, 2572)[0]), 'TJ': tj,
            'Cores': [round(t) for t in temps],
            'Name': b[2584:2684].split(b'\0')[0].decode('ascii', 'ignore').strip()}


def hwinfo_cpu():
    """Core Temp yoksa HWiNFO'nun paylaşılan belleğinden işlemci sıcaklığı (HWiNFO'da "Shared Memory Support" açık olmalı).
    Yapı #pragma pack(1): başlıkta okuma bölümünün yeri, eleman boyutu ve sayısı verilir."""
    h = read_shm('Global\\HWiNFO_SENS_SM2', 44)
    if not h or h[:4] not in (b'SiWH', b'HWiS'):
        return None
    off, size, num = struct.unpack_from('<III', h, 32)
    if not (0 < num < 20000 and 300 <= size <= 2048):
        return None
    b = read_shm('Global\\HWiNFO_SENS_SM2', off + size * num)
    if not b:
        return None
    temps, cores = {}, []
    for i in range(num):
        o = off + i * size
        if struct.unpack_from('<I', b, o)[0] != 1:  # 1 = sıcaklık
            continue
        lab = b[o + 12:o + 140].split(b'\0')[0].decode('latin-1', 'ignore')
        val = struct.unpack_from('<d', b, o + 284)[0]
        if not 0 < val < 150:
            continue
        temps.setdefault(lab, val)
        if re.match(r'^(P-|E-)?Core\s*\d+(\s*\(CCD\d\))?$', lab) or re.match(r'^Core\d+ \(CCD\d\)$', lab):
            cores.append(round(val))
    for k in ('CPU (Tctl/Tdie)', 'CPU Package', 'CPU (Tdie)', 'Core Max', 'CPU Die (average)'):
        if k in temps:
            return {'T': round(temps[k]), 'MHz': 0, 'TJ': None, 'Cores': cores, 'Name': '', 'src': 'HWiNFO'}
    return None


def gpu_sensor():
    base = 12 + 128 * 1024
    b = read_shm('GPUZShMem', base + 128 * 540)
    if not b:
        return None
    card = ''
    for i in range(128):  # metin kayıtları: anahtar 256 + değer 256 karakter
        o = 12 + i * 1024
        key = b[o:o + 512].decode('utf-16-le', 'ignore').split('\0')[0]
        if not key:
            break
        if key == 'CardName':
            card = b[o + 512:o + 1024].decode('utf-16-le', 'ignore').split('\0')[0]
            break
    s = {}
    for i in range(128):
        o = base + i * 540
        name = b[o:o + 512].decode('utf-16-le', 'ignore').split('\0')[0]
        if not name:
            break
        s[name] = struct.unpack_from('<d', b, o + 532)[0]
    if not s:
        return None

    def pick(*keys, contains=None):
        for k in keys:
            if k in s:
                return s[k]
        if contains:
            for k, v in s.items():
                if contains in k.lower():
                    return v
        return 0

    return {'T': round(pick('GPU Temperature')),
            'HS': round(pick('GPU Temperature (Hot Spot)', 'Hot Spot', contains='hot spot')),
            'Load': round(pick('GPU Load')),
            'VRAM': round(pick('Memory Used (Dedicated)', 'Memory Used')),
            'Pwr': round(pick('Board Power Draw', 'GPU Chip Power Draw', 'Total Board Power', contains='power')),
            'Clk': round(pick('GPU Clock')), 'MClk': round(pick('Memory Clock')),
            'Fan': round(pick('Fan Speed (%)', 'Fan 1 Speed (%)')), 'RPM': round(pick('Fan Speed (RPM)', 'Fan 1 Speed (RPM)')),
            'MemT': round(pick('Memory Temperature', 'GPU Memory Temperature')), 'Name': card}

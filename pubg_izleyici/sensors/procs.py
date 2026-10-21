# En çok kaynak kullanan programlar
import ctypes
import psutil
import struct
import threading
import time

_ntdll = ctypes.WinDLL('ntdll')
_ntdll.NtQuerySystemInformation.argtypes = [ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
_ntdll.NtQuerySystemInformation.restype = ctypes.c_long
_SPI_SIZE = [1 << 20]


def sys_procs():
    """Tüm süreçleri tek sistem çağrısıyla okur: {pid: (ad, işlemci süresi [100 ns], RAM bayt)}.
    psutil süreç başına ayrı çağrı yapar ve GIL'i tutar; 300 süreçte arayüzü her seferinde ~100 ms dondurur.
    ctypes çağrı sırasında GIL'i bırakır, bu yüzden arayüz etkilenmez. 64 bit SYSTEM_PROCESS_INFORMATION yerleşimi."""
    if struct.calcsize('P') != 8:
        return None
    while True:
        buf, ret = ctypes.create_string_buffer(_SPI_SIZE[0]), ctypes.c_ulong()
        st = _ntdll.NtQuerySystemInformation(5, buf, _SPI_SIZE[0], ctypes.byref(ret)) & 0xffffffff
        if st == 0xC0000004:  # STATUS_INFO_LENGTH_MISMATCH: tampon küçük
            _SPI_SIZE[0] = max(_SPI_SIZE[0] * 2, ret.value + 65536)
            continue
        if st:
            return None
        break
    out, off = {}, 0
    while True:
        nxt, = struct.unpack_from('<I', buf, off)
        ut, kt = struct.unpack_from('<qq', buf, off + 40)
        ln, = struct.unpack_from('<H', buf, off + 56)
        ptr, pid = struct.unpack_from('<Q', buf, off + 64)[0], struct.unpack_from('<Q', buf, off + 80)[0]
        ws, = struct.unpack_from('<Q', buf, off + 144)
        out[pid] = (ctypes.wstring_at(ptr, ln // 2) if ptr and ln else '', ut + kt, ws)
        if not nxt:
            return out
        off += nxt


class ProcMon:
    def __init__(self):
        self.lock, self.top, self.cache = threading.Lock(), [], {}
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        ncpu = psutil.cpu_count() or 1
        prev, prev_t = {}, time.time()
        while True:
            now = time.time()
            dt = max(0.5, now - prev_t)
            try:
                snap = sys_procs()
            except Exception:
                snap = None
            if snap is not None:
                rows = [(max(0.0, (t - prev[pid][1]) / 1e7 / dt * 100 / ncpu), nm or '?', ws / 1048576)
                        for pid, (nm, t, ws) in snap.items() if pid not in (0, 4) and pid in prev and prev[pid][0] == nm]
                prev, prev_t = snap, now
                rows.sort(reverse=True)
                with self.lock:
                    self.top = rows[:12]
                time.sleep(2)
                continue
            # yedek yol: psutil (32 bit ya da çağrı başarısızsa)
            cur, rows = {}, []
            for i, pr in enumerate(psutil.process_iter(['name', 'cpu_times', 'memory_info'])):
                if i % 20 == 0:
                    time.sleep(0)  # arayüz iş parçacığına sıra ver
                if pr.pid in (0, 4):
                    continue
                ct, mi = pr.info.get('cpu_times'), pr.info.get('memory_info')
                if ct is None:
                    continue
                nm, tot, rss = pr.info.get('name') or '', (ct.user + ct.system) * 1e7, mi.rss if mi else 0
                cur[pr.pid] = (nm, tot, rss)
                if pr.pid in prev and prev[pr.pid][0] == nm:
                    rows.append((max(0.0, (tot - prev[pr.pid][1]) / 1e7 / dt * 100 / ncpu), nm or '?', rss / 1048576))
            prev, prev_t = cur, now
            rows.sort(reverse=True)
            with self.lock:
                self.top = rows[:12]
            time.sleep(2)

    def get(self):
        with self.lock:
            return list(self.top)

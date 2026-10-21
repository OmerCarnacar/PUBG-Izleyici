# Ağ ölçümü (ICMP ping + trafik)
import collections
import ctypes
import psutil
import socket
import struct
import threading
import time

class NetMon:
    def __init__(self, host='1.1.1.1'):
        self.host, self.lock = host, threading.Lock()
        self.samples = collections.deque(maxlen=30)  # ms ya da None (kayıp)
        self.rate = (0.0, 0.0)  # indirme, yükleme (Mbit/s)
        self.io = psutil.net_io_counters()
        self.t = time.time()
        try:
            self.iph = ctypes.WinDLL('iphlpapi')
            self.iph.IcmpCreateFile.restype = ctypes.c_void_p
            self.iph.IcmpSendEcho.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint16,
                                              ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
            self.h = self.iph.IcmpCreateFile()
            self.addr = struct.unpack('<I', socket.inet_aton(host))[0]
            threading.Thread(target=self._run, daemon=True).start()
        except Exception:
            self.h = None

    def _ping(self):
        data = b'pubg-izleyici-ping-0123456789abc'
        reply = ctypes.create_string_buffer(256)  # 64 bit'te ICMP_ECHO_REPLY 40 bayt + veri + 8 bayt hata payı
        r = self.iph.IcmpSendEcho(self.h, self.addr, data, len(data), None, reply, ctypes.sizeof(reply), 1000)
        if r and struct.unpack_from('<I', reply, 4)[0] == 0:
            return struct.unpack_from('<I', reply, 8)[0]
        return None

    def _run(self):
        while True:
            t0 = time.time()
            try:
                v = self._ping()
            except Exception:
                v = None
            # trafik sayacı Windows'ta ~20 ms sürer; arayüz yerine burada ölçülür
            try:
                io, t = psutil.net_io_counters(), time.time()
                dt = max(0.2, t - self.t)
                down = (io.bytes_recv - self.io.bytes_recv) * 8 / dt / 1e6
                up = (io.bytes_sent - self.io.bytes_sent) * 8 / dt / 1e6
                self.io, self.t = io, t
            except Exception:
                down = up = 0.0
            with self.lock:
                self.samples.append(v)
                self.rate = (down, up)
            time.sleep(max(0.05, 1 - (time.time() - t0)))

    def stats(self):
        with self.lock:
            s = list(self.samples)[-10:]
            down, up = self.rate
        ok = [x for x in s if x is not None]
        loss = round(100 * (len(s) - len(ok)) / len(s)) if s else 0
        jit = round(sum(abs(a - b) for a, b in zip(ok, ok[1:])) / (len(ok) - 1), 1) if len(ok) > 1 else 0
        return {'ping': ok[-1] if ok else None, 'avg': round(sum(ok) / len(ok)) if ok else None,
                'max': max(ok) if ok else None, 'jit': jit, 'loss': loss, 'down': down, 'up': up, 'n': len(s)}

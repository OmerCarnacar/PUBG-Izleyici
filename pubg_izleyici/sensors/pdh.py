# GPU-Z yoksa: Windows sayaçları (her dilde çalışır)
import collections
import ctypes
import re
import struct
import winreg
from ..winutil import reg

class _FMTV(ctypes.Structure):
    _fields_ = [('CStatus', ctypes.c_uint32), ('doubleValue', ctypes.c_double)]


class _ITEM(ctypes.Structure):
    _fields_ = [('szName', ctypes.c_wchar_p), ('FmtValue', _FMTV)]


class KmtGpu:
    """Ekran kartı sıcaklığı ve fanı doğrudan Windows'tan (D3DKMT), Görev Yöneticisi'nin okuduğu yerden.
    GPU-Z ya da sürücü kütüphanesi gerekmez; en çok VRAM'li kart (oyunun çalıştığı kart) seçilir."""
    class _AI(ctypes.Structure):
        _fields_ = [('h', ctypes.c_uint32), ('lo', ctypes.c_uint32), ('hi', ctypes.c_int32), ('nsrc', ctypes.c_uint32),
                    ('prec', ctypes.c_int32)]

    class _EA2(ctypes.Structure):
        _fields_ = [('n', ctypes.c_uint32), ('p', ctypes.c_void_p)]

    class _QAI(ctypes.Structure):
        _fields_ = [('h', ctypes.c_uint32), ('type', ctypes.c_int32), ('data', ctypes.c_void_p), ('size', ctypes.c_uint32)]

    def __init__(self):
        self.h, self.luid, self.vram = None, None, 0
        try:
            self.gdi = ctypes.WinDLL('gdi32')
            e = self._EA2(0, None)
            if self.gdi.D3DKMTEnumAdapters2(ctypes.byref(e)) or not e.n:
                return
            arr = (self._AI * e.n)()
            e.p = ctypes.cast(arr, ctypes.c_void_p)
            if self.gdi.D3DKMTEnumAdapters2(ctypes.byref(e)):
                return
            best = None
            for a in arr[:e.n]:
                seg = self._q(a.h, 3, 24)  # KMTQAITYPE_GETSEGMENTSIZE: ayrılmış video belleği
                ded = struct.unpack_from('<Q', seg)[0] if seg else 0
                if ded and (best is None or ded > best[0]):
                    best = (ded, a)
            if best:
                a = best[1]
                self.h, self.vram = a.h, best[0] // 1048576
                self.luid = f'luid_0x{a.hi & 0xffffffff:08x}_0x{a.lo:08x}'
        except Exception:
            self.h = None

    def _q(self, h, typ, size):
        buf = ctypes.create_string_buffer(size)
        q = self._QAI(h, typ, ctypes.cast(buf, ctypes.c_void_p), size)
        return buf.raw if self.gdi.D3DKMTQueryAdapterInfo(ctypes.byref(q)) == 0 else None

    def read(self):
        if self.h is None:
            return None
        try:
            d = self._q(self.h, 62, 64)  # KMTQAITYPE_ADAPTERPERFDATA
            if not d:
                return None
            fan, _, temp = struct.unpack_from('<III', d, 48)
            out = {'T': round(temp / 10), 'RPM': fan, 'MClk': round(struct.unpack_from('<Q', d, 8)[0] / 1e6)}
            n = self._q(self.h, 61, 56)  # KMTQAITYPE_NODEPERFDATA, düğüm 0 = 3D motoru
            if n:
                out['Clk'] = round(struct.unpack_from('<Q', n, 8)[0] / 1e6)
                out['MaxClk'] = round(struct.unpack_from('<Q', n, 16)[0] / 1e6)
                out['mV'] = struct.unpack_from('<I', n, 32)[0]
            return out
        except Exception:
            return None


def pdh_items(pdh, c):
    """PDH çoklu örnek sayacı: [(örnek adı, değer)]. 0x8000: %100'de kırpma, motor toplamını biz sınırlarız."""
    size, cnt = ctypes.c_uint32(0), ctypes.c_uint32(0)
    pdh.PdhGetFormattedCounterArrayW(c, 0x200 | 0x8000, ctypes.byref(size), ctypes.byref(cnt), None)
    if not size.value:
        return []
    buf = ctypes.create_string_buffer(size.value)
    if pdh.PdhGetFormattedCounterArrayW(c, 0x200 | 0x8000, ctypes.byref(size), ctypes.byref(cnt), buf) != 0:
        return []
    arr = ctypes.cast(buf, ctypes.POINTER(_ITEM))
    return [(arr[i].szName or '', arr[i].FmtValue.doubleValue) for i in range(cnt.value) if arr[i].FmtValue.CStatus in (0, 1)]


class GpuPdh:
    """Ekran kartı yükü ve VRAM, Görev Yöneticisi'nin hesabıyla: sadece seçilen kart (luid), motor başına toplanır,
    en yüklü motor kartın yüküdür. Eskiden işlemcinin grafik birimi ile ekran kartının yükü toplanıyordu."""
    def __init__(self, luid=None):
        self.ok = self.okm = False
        self.luid = (luid or '').lower()
        try:
            self.pdh = ctypes.WinDLL('pdh')
            self.q = ctypes.c_void_p()
            self.pdh.PdhOpenQueryW(None, 0, ctypes.byref(self.q))
            self.ceng, self.cmem = ctypes.c_void_p(), ctypes.c_void_p()
            a = self.pdh.PdhAddEnglishCounterW(self.q, r'\GPU Engine(*)\Utilization Percentage', 0, ctypes.byref(self.ceng))
            b = self.pdh.PdhAddEnglishCounterW(self.q, r'\GPU Adapter Memory(*)\Dedicated Usage', 0, ctypes.byref(self.cmem))
            self.pdh.PdhCollectQueryData(self.q)
            self.ok, self.okm = (a == 0), (b == 0)
        except Exception:
            pass

    def read(self):
        if not self.ok:
            return None
        try:
            self.pdh.PdhCollectQueryData(self.q)
            eng = collections.defaultdict(float)
            for name, v in pdh_items(self.pdh, self.ceng):
                n = name.lower()
                if self.luid and self.luid not in n:
                    continue
                m = re.search(r'(luid_\w+?_phys_\d+)_eng_(\d+)', n)
                if m:
                    eng[m.groups()] += v
            load = min(100, round(max(eng.values(), default=0)))
            mem = 0
            if self.okm:
                vals = [v for name, v in pdh_items(self.pdh, self.cmem) if not self.luid or self.luid in name.lower()]
                mem = round(max(vals, default=0) / 1048576)
            return {'T': 0, 'HS': 0, 'Load': load, 'VRAM': mem, 'Pwr': 0}
        except Exception:
            return None


class CpuPdh:
    """İşlemci yükünü Görev Yöneticisi'nin kullandığı sayaçtan okur: "% Processor Utility".
    psutil "% Processor Time" verir; turbo/boost hızını hesaba katmadığı için Görev Yöneticisi'nden düşük çıkar."""
    def __init__(self):
        self.ok = False
        try:
            self.pdh = ctypes.WinDLL('pdh')
            self.q, self.c = ctypes.c_void_p(), ctypes.c_void_p()
            self.pdh.PdhOpenQueryW(None, 0, ctypes.byref(self.q))
            if self.pdh.PdhAddEnglishCounterW(self.q, r'\Processor Information(*)\% Processor Utility', 0,
                                              ctypes.byref(self.c)) == 0:
                self.ok = True
            # Anlık saat hızı = taban hız × "% Processor Performance" (Görev Yöneticisi'ndeki "Hız" böyle hesaplanır)
            self.cperf = ctypes.c_void_p()
            self.okp = self.pdh.PdhAddEnglishCounterW(self.q, r'\Processor Information(_Total)\% Processor Performance', 0,
                                                      ctypes.byref(self.cperf)) == 0
            self.base = reg(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0', '~MHz') or 0
            self.pdh.PdhCollectQueryData(self.q)
        except Exception:
            pass

    def mhz(self):
        """Son okumadaki işlemci saat hızı (MHz) ya da 0. read()'den sonra çağrılır."""
        if not (self.ok and getattr(self, 'okp', False) and self.base):
            return 0
        v = _FMTV()
        if self.pdh.PdhGetFormattedCounterValue(self.cperf, 0x200 | 0x8000, None, ctypes.byref(v)) != 0 or v.CStatus not in (0, 1):
            return 0
        return round(self.base * v.doubleValue / 100)

    def read(self):
        """(toplam %, [mantıksal işlemci başına %]) ya da None"""
        if not self.ok:
            return None
        try:
            self.pdh.PdhCollectQueryData(self.q)
            size, cnt = ctypes.c_uint32(0), ctypes.c_uint32(0)
            self.pdh.PdhGetFormattedCounterArrayW(self.c, 0x200, ctypes.byref(size), ctypes.byref(cnt), None)
            if not size.value:
                return None
            buf = ctypes.create_string_buffer(size.value)
            if self.pdh.PdhGetFormattedCounterArrayW(self.c, 0x200, ctypes.byref(size), ctypes.byref(cnt), buf) != 0:
                return None
            arr = ctypes.cast(buf, ctypes.POINTER(_ITEM))
            tot, per = None, []
            for i in range(cnt.value):
                it = arr[i]
                if it.FmtValue.CStatus not in (0, 1):
                    continue
                v = max(0.0, min(100.0, it.FmtValue.doubleValue))
                m = re.match(r'^(\d+),(\d+)$', it.szName or '')
                if m:
                    per.append((int(m.group(1)), int(m.group(2)), v))
                elif it.szName == '_Total':
                    tot = v
            if not per:
                return None
            per = [v for _, _, v in sorted(per)]
            return (tot if tot is not None else sum(per) / len(per)), per
        except Exception:
            return None

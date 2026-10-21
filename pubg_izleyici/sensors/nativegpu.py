# Ekran kartı sensörleri: sürücüden doğrudan (AMD ADL / NVIDIA NVML)
import ctypes
import re
from ..hardware import gpu_vram

class _AdapterInfo(ctypes.Structure):
    _fields_ = [('iSize', ctypes.c_int), ('iAdapterIndex', ctypes.c_int), ('strUDID', ctypes.c_char * 256),
                ('iBusNumber', ctypes.c_int), ('iDeviceNumber', ctypes.c_int), ('iFunctionNumber', ctypes.c_int),
                ('iVendorID', ctypes.c_int), ('strAdapterName', ctypes.c_char * 256), ('strDisplayName', ctypes.c_char * 256),
                ('iPresent', ctypes.c_int), ('iExist', ctypes.c_int), ('strDriverPath', ctypes.c_char * 256),
                ('strDriverPathExt', ctypes.c_char * 256), ('strPNPString', ctypes.c_char * 256), ('iOSDisplayIndex', ctypes.c_int)]


class _Sensor(ctypes.Structure):
    _fields_ = [('supported', ctypes.c_int), ('value', ctypes.c_int)]


class _PMLog(ctypes.Structure):
    _fields_ = [('size', ctypes.c_int), ('sensors', _Sensor * 256)]


class NativeGpu:
    """GPU-Z olmadan sıcaklık/saat/fan/güç okur. AMD: atiadlxx.dll, NVIDIA: nvml.dll"""
    def __init__(self):
        self.kind, self.ctx, self.idx = None, None, None
        # Oyunun çalıştığı kart: en çok VRAM'li ekran kartı. Ryzen 7000/9000 gibi işlemcilerin içinde de bir
        # AMD Radeon grafik birimi var; önce ona bakılırsa NVIDIA kartlı bilgisayarda işlemcinin grafik
        # biriminin sıcaklığı/yükü gösteriliyordu (ör. 100°C, %17 — Görev Yöneticisi'yle tutmuyor).
        try:
            main = max(gpu_vram(), key=lambda g: g['vram'])['name']
        except Exception:
            main = ''
        self.main = main
        order = (self._init_nv, self._init_amd) if 'nvidia' in main.lower() else (self._init_amd, self._init_nv)
        for init in order:
            try:
                init()
            except Exception:
                self.kind = None
            if self.kind:
                break

    def _init_amd(self):
        dll = ctypes.CDLL('atiadlxx.dll')
        crt = ctypes.CDLL('msvcrt')
        crt.malloc.restype = ctypes.c_void_p
        crt.malloc.argtypes = [ctypes.c_size_t]
        self._cb = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_int)(lambda n: crt.malloc(n))
        ctx = ctypes.c_void_p()
        if dll.ADL2_Main_Control_Create(self._cb, 1, ctypes.byref(ctx)) != 0:
            return
        n = ctypes.c_int(0)
        dll.ADL2_Adapter_NumberOfAdapters_Get(ctx, ctypes.byref(n))
        if n.value <= 0:
            return
        arr = (_AdapterInfo * n.value)()
        dll.ADL2_Adapter_AdapterInfo_Get(ctx, arr, ctypes.sizeof(arr))
        seen, cand = set(), []
        for a in arr:
            if a.iVendorID not in (1002, 0x1002) or a.iBusNumber in seen:
                continue
            seen.add(a.iBusNumber)
            out = _PMLog(); out.size = ctypes.sizeof(out)
            if dll.ADL2_New_QueryPMLogData_Get(ctx, a.iAdapterIndex, ctypes.byref(out)) == 0 and out.sensors[7].supported:
                cand.append((a.strAdapterName.decode('ascii', 'ignore').strip(), a.iAdapterIndex))
        if not cand:
            return
        main = self.main.lower()
        if main and 'nvidia' not in main and 'intel' not in main:
            # Ana kart AMD: adı eşleşen adaptör; yoksa işlemci içi grafik olmayanı ("... Graphics" / 780M gibi)
            igpu = lambda n: n.lower().endswith('graphics') or bool(re.search(r'\b\d{3}m\b', n.lower()))
            pick = next((c for c in cand if c[0].lower() == main), None) or next((c for c in cand if not igpu(c[0])), cand[0])
        elif main:
            return  # ana kart NVIDIA/Intel: tek AMD adaptörü işlemcinin grafik birimidir, kullanılmaz
        else:
            pick = cand[0]
        self.dll, self.ctx, self.idx, self.kind = dll, ctx, pick[1], 'amd'

    def _init_nv(self):
        for pth in ('nvml.dll', r'C:\Program Files\NVIDIA Corporation\NVSMI\nvml.dll'):
            try:
                dll = ctypes.CDLL(pth)
                break
            except OSError:
                dll = None
        if not dll or dll.nvmlInit_v2() != 0:
            return
        h = ctypes.c_void_p()
        if dll.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(h)) == 0:
            self.dll, self.h, self.kind = dll, h, 'nv'

    def read(self):
        try:
            if self.kind == 'amd':
                out = _PMLog(); out.size = ctypes.sizeof(out)
                if self.dll.ADL2_New_QueryPMLogData_Get(self.ctx, self.idx, ctypes.byref(out)) != 0:
                    return None
                g = lambda i: out.sensors[i].value if out.sensors[i].supported else 0
                return {'T': g(7), 'MemT': g(8), 'HS': g(26), 'RPM': g(13), 'Fan': g(14), 'Load': g(18),
                        'Pwr': g(22) or g(16), 'Clk': g(0), 'MClk': g(1), 'VRAM': 0}
            if self.kind == 'nv':
                d, h = self.dll, self.h
                t, p, fan, c0, c2 = (ctypes.c_uint() for _ in range(5))
                d.nvmlDeviceGetTemperature(h, 0, ctypes.byref(t))
                d.nvmlDeviceGetPowerUsage(h, ctypes.byref(p))
                d.nvmlDeviceGetFanSpeed(h, ctypes.byref(fan))
                d.nvmlDeviceGetClockInfo(h, 0, ctypes.byref(c0))
                d.nvmlDeviceGetClockInfo(h, 2, ctypes.byref(c2))
                util = (ctypes.c_uint * 2)()
                d.nvmlDeviceGetUtilizationRates(h, util)
                mem = (ctypes.c_ulonglong * 3)()
                d.nvmlDeviceGetMemoryInfo(h, mem)
                return {'T': t.value, 'MemT': 0, 'HS': 0, 'RPM': 0, 'Fan': fan.value, 'Load': util[0],
                        'Pwr': round(p.value / 1000), 'Clk': c0.value, 'MClk': c2.value, 'VRAM': round(mem[2] / 1048576)}
        except Exception:
            return None
        return None


def pct(a, p):
    if not a:
        return 0
    s = sorted(a)
    return s[min(len(s) - 1, int(len(s) * p))]

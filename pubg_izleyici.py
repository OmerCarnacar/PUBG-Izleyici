# PUBG Canlı İzleyici - anlık FPS, takılma, sıcaklık, darboğaz ve SORUN tespiti
# Çalıştırma: PUBG_Izleyici_CALISTIR.bat (yönetici olarak açar, Python yoksa kurar)
# Sıcaklıklar için Core Temp ve GPU-Z açık olmalı (küçültülmüş olabilir).
import os, sys, glob, json, struct, ctypes, threading, subprocess, collections, datetime, time, urllib.request, hashlib
from array import array
import tkinter as tk
import psutil

# Yüksek DPI ekranlarda (125%, 150%) yazıların bulanık görünmesini önler. Tk penceresi oluşmadan önce çağrılmalı.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
S = 1.0  # ekran ölçeği (96 DPI = 1.0); pencere açılınca hesaplanır


def px(v):
    return int(round(v * S))

VERSION = '1.1.0'
REPO = 'OmerCarnacar/PUBG-Izleyici'
# Her sürümde en üste eklenir; program güncellenince "Yenilikler" penceresinde gösterilir.
CHANGES = [
    ('1.1.0', ['Çok daha akıcı: arayüz her saniye ~0.25 sn donuyordu, artık ~6 ms (yaklaşık 45 kat hızlı)',
               'Ayar Kontrolü, Sistem Bilgisi ve ayar uygulama artık pencereyi dondurmuyor',
               'Program anında açılıyor (FPS aracı arka planda hazırlanıyor)',
               'Modern görünüm: koyu başlık çubuğu, yüksek DPI ekranlarda net yazılar, butonlarda vurgu',
               'Güncelleme saatte bir kontrol ediliyor, indirilen dosya SHA-256 ile doğrulanıyor',
               'Düzeltme: Türkçe karakterli kullanıcı klasörlerinde otomatik güncelleme çalışmıyordu',
               'Düzeltme: DPI yazınca kayıtlı API anahtarı ve diğer ayarlar siliniyordu',
               'Düzeltme: PUBG Hesap sekmesinde bazı hatalar hiç gösterilmiyordu',
               'Uzun oturumlarda daha az bellek kullanımı']),
    ('1.0.0', ['İlk sürüm: canlı FPS (saniyede 4 güncelleme), 1% / 0.1% düşük, takılma tespiti ve sebebi',
               'İşlemci: sıcaklık, yük, saat hızı, her çekirdeğin anlık sıcaklığı ve yükü',
               'Ekran kartı: sıcaklık, hot spot, VRAM sıcaklığı, fan, saat hızları, güç (AMD/NVIDIA sürücüsünden)',
               'Ağ: ping, dalgalanma, paket kaybı, indirme/yükleme · Disk okuma/yazma',
               'Analiz: 60 sn performans testi ve karşılaştırma, takılma kaydı, en çok kaynak kullanan programlar',
               'Ayar Kontrolü: PUBG 2026 önerileri, Windows, fare ve klavye; PUBG kapanınca otomatik uygulama',
               'PUBG Hesap: resmi API ile dereceli, sezon, tüm zamanlar ve son maçlar',
               'Mini mod, her sekmede sabit FPS şeridi, otomatik güncelleme']),
]
DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.environ.get('LOCALAPPDATA') or DIR, 'PUBGIzleyici')  # exe'nin yanına hiçbir şey yazılmaz
TOOLS = DATA
STAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
SEC_CSV = os.path.join(DATA, f'Saniye_{STAMP}.csv')
REPORT = os.path.join(DATA, f'Rapor_{STAMP}.txt')
GAME = 'TslGame.exe'
os.makedirs(DATA, exist_ok=True)
for _old in sorted(glob.glob(os.path.join(DATA, 'Saniye_*.csv')))[:-30] + sorted(glob.glob(os.path.join(DATA, 'Rapor_*.txt')))[:-30]:
    try:
        os.remove(_old)
    except OSError:
        pass
if getattr(sys, 'frozen', False):  # güncellemeden kalan eski exe
    try:
        os.remove(sys.executable + '.old')
    except OSError:
        pass
NOWIN = 0x08000000  # CREATE_NO_WINDOW


# ---------------- PresentMon (FPS ölçümü) ----------------
def get_presentmon():
    found = sorted(glob.glob(os.path.join(TOOLS, 'PresentMon*.exe')), key=os.path.getmtime)
    if found:
        return found[-1]
    mei = getattr(sys, '_MEIPASS', None)  # exe içine gömülü PresentMon
    if mei:
        emb = glob.glob(os.path.join(mei, 'PresentMon*.exe'))
        if emb:
            import shutil as _sh
            dst = os.path.join(TOOLS, os.path.basename(emb[0]))
            _sh.copy2(emb[0], dst)
            return dst
    try:
        req = urllib.request.Request('https://api.github.com/repos/GameTechDev/PresentMon/releases/latest',
                                     headers={'User-Agent': 'pubg-izleyici'})
        rel = json.load(urllib.request.urlopen(req, timeout=20))
        for a in rel['assets']:
            n = a['name']
            if n.startswith('PresentMon-') and n.endswith('-x64.exe'):
                dst = os.path.join(TOOLS, n)
                urllib.request.urlretrieve(a['browser_download_url'], dst)
                return dst
    except Exception:
        pass
    return None


class PresentMon:
    def __init__(self, exe):
        self.exe, self.proc, self.lock = exe, None, threading.Lock()
        self.ft, self.gb = [], 0.0
        self.recent = collections.deque(maxlen=4000)

    def fast_fps(self, window=0.5):
        now = time.time()
        with self.lock:
            v = [x for t, x in self.recent if now - t <= window]
        return len(v) / (sum(v) / 1000) if len(v) >= 3 and sum(v) > 0 else None

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self):
        if not self.exe:
            return
        args = [self.exe, '--process_name', GAME, '--output_stdout', '--session_name', 'PUBGIzleyici',
                '--stop_existing_session', '--terminate_on_proc_exit']
        self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, bufsize=1, creationflags=NOWIN)
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()

    def _read(self, proc):
        icol = gcol = -1
        header = None
        for line in proc.stdout:
            c = line.rstrip('\r\n').split(',')
            if header is None:
                if 'MsBetweenPresents' not in c:
                    continue
                header = c
                icol = c.index('MsBetweenPresents')
                gcol = c.index('MsGPUBusy') if 'MsGPUBusy' in c else (c.index('MsGPUActive') if 'MsGPUActive' in c else -1)
                continue
            try:
                v = float(c[icol])
            except (ValueError, IndexError):
                continue
            if not 0 < v < 2000:
                continue
            g = 0.0
            if gcol >= 0:
                try:
                    g = float(c[gcol])
                except (ValueError, IndexError):
                    g = 0.0
            with self.lock:
                self.ft.append(v)
                self.gb += g
                self.recent.append((time.time(), v))

    def take(self):
        with self.lock:
            ft, gb = self.ft, self.gb
            self.ft, self.gb = [], 0.0
        return ft, gb

    def stop(self):
        if self.running():
            self.proc.kill()
        if self.exe:
            subprocess.run([self.exe, '--terminate_existing_session', '--session_name', 'PUBGIzleyici'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NOWIN, timeout=10)


# ---------------- Paylaşılan bellek: Core Temp ve GPU-Z ----------------
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


def gpu_sensor():
    base = 12 + 128 * 1024
    b = read_shm('GPUZShMem', base + 128 * 540)
    if not b:
        return None
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
            'MemT': round(pick('Memory Temperature', 'GPU Memory Temperature'))}


# ---------------- Ekran kartı sensörleri: sürücüden doğrudan (AMD ADL / NVIDIA NVML) ----------------
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
        try:
            self._init_amd()
        except Exception:
            self.kind = None
        if not self.kind:
            try:
                self._init_nv()
            except Exception:
                self.kind = None

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
        seen = set()
        for a in arr:
            if a.iVendorID not in (1002, 0x1002) or a.iBusNumber in seen:
                continue
            seen.add(a.iBusNumber)
            out = _PMLog(); out.size = ctypes.sizeof(out)
            if dll.ADL2_New_QueryPMLogData_Get(ctx, a.iAdapterIndex, ctypes.byref(out)) == 0 and out.sensors[7].supported:
                self.dll, self.ctx, self.idx, self.kind = dll, ctx, a.iAdapterIndex, 'amd'
                return

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


# ---------------- Ayar kontrolü (PUBG + Windows) ----------------
import re, shutil, winreg

INI = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'TslGame', 'Saved', 'Config', 'WindowsNoEditor', 'GameUserSettings.ini')
QL = {0: 'Çok Düşük', 1: 'Düşük', 2: 'Orta', 3: 'Yüksek', 4: 'Ultra'}
# anahtar, önerilen, ad, kural ('==', '<=', '>='), neden
# 2026 (Update 41.x) güncel öneriler. anahtar, önerilen, ad, en az, en çok, neden
GFX = [
    ('sg.ViewDistanceQuality', 2, 'Görüş Mesafesi', 2, 4, 'En çok işlemci yükü bindiren ayar. Orta FPS için en iyisi. Güçlü işlemcide Yüksek ya da Ultra da olur. Orta\'nın altında uzaktaki araç ve binalar geç görünür.'),
    ('sg.ShadowQuality', 0, 'Gölgeler', 0, 2, 'Çok Düşük en yüksek FPS\'yi verir. Orta seçersen 75 m\'den uzaktaki oyuncu gölgeleri de görünür. Üstü gereksiz.'),
    ('sg.PostProcessQuality', 0, 'İşlem Sonrası', 0, 1, 'FPS\'yi en çok etkileyen ayar. Çok Düşük ya da Düşük seç, görüntü netleşir.'),
    ('sg.EffectsQuality', 1, 'Efektler', 0, 1, 'Düşük öneriliyor. Bazı kaynaklara göre Çok Düşük, duman ve patlamalarda anlık takılma yapabiliyor.'),
    ('sg.FoliageQuality', 0, 'Yeşillik', 0, 0, 'Çok Düşük seç. Yüksek seviyede çimen, yere yatan oyuncuyu gizler.'),
    ('sg.TextureQuality', 3, 'Dokular', 2, 4, '12 GB ve üstü VRAM varsa Yüksek, 8-10 GB varsa Orta. VRAM %95\'i geçerse bir kademe düşür.'),
    ('sg.AntiAliasingQuality', 2, 'Kenar Yumuşatma', 2, 3, 'Orta ya da Yüksek seç. Ultra çok az netlik katar ama %6-8 FPS götürür.'),
]
BG_APPS = {'onedrive.exe': 'OneDrive', 'opera.exe': 'Opera', 'chrome.exe': 'Chrome', 'msedge.exe': 'Edge',
           'discord.exe': 'Discord (oyun içi overlay kapalı olmalı)', 'warp-svc.exe': 'Cloudflare WARP',
           'wallpaper32.exe': 'Wallpaper Engine', 'wallpaper64.exe': 'Wallpaper Engine', 'obs64.exe': 'OBS',
           'furmark.exe': 'FurMark (stres testi!)', 'furmark_gui.exe': 'FurMark', 'mumuplayer.exe': 'MuMu Player',
           'nemuplayer.exe': 'MuMu Player', 'teams.exe': 'Teams', 'ms-teams.exe': 'Teams'}


def read_ini():
    d = {}
    try:
        with open(INI, encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.rstrip('\r\n')
                if '=' in line and not line.startswith(('[', ';')):
                    k, v = line.split('=', 1)
                    d[k.strip()] = v.strip()
    except OSError:
        return None
    return d


def reg(root, path, name):
    try:
        with winreg.OpenKey(root, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def ps(cmd, timeout=25):
    try:
        return subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                               '[Console]::OutputEncoding=[Text.Encoding]::UTF8; ' + cmd],
                              capture_output=True, text=True, encoding='utf-8', errors='ignore',
                              timeout=timeout, creationflags=NOWIN).stdout.strip()
    except Exception:
        return ''


def powercfg(*args):
    """powercfg'yi PowerShell açmadan çağırır (~1 sn yerine ~50 ms)."""
    try:
        return subprocess.run(['powercfg', *args], capture_output=True, text=True, encoding='oem', errors='ignore',
                              timeout=10, creationflags=NOWIN).stdout.strip()
    except Exception:
        return ''


# ---------------- Donanım bilgisi (her bilgisayarda otomatik) ----------------
LIM = {'hot': 92, 'vfull': 10 ** 9, 'cap': 297, 'hz': 0}
HW = {}


class DEVMODEW(ctypes.Structure):
    _fields_ = [('dmDeviceName', ctypes.c_wchar * 32), ('dmSpecVersion', ctypes.c_ushort), ('dmDriverVersion', ctypes.c_ushort),
                ('dmSize', ctypes.c_ushort), ('dmDriverExtra', ctypes.c_ushort), ('dmFields', ctypes.c_uint32),
                ('dmPositionX', ctypes.c_int32), ('dmPositionY', ctypes.c_int32), ('dmDisplayOrientation', ctypes.c_uint32),
                ('dmDisplayFixedOutput', ctypes.c_uint32), ('dmColor', ctypes.c_short), ('dmDuplex', ctypes.c_short),
                ('dmYResolution', ctypes.c_short), ('dmTTOption', ctypes.c_short), ('dmCollate', ctypes.c_short),
                ('dmFormName', ctypes.c_wchar * 32), ('dmLogPixels', ctypes.c_ushort), ('dmBitsPerPel', ctypes.c_uint32),
                ('dmPelsWidth', ctypes.c_uint32), ('dmPelsHeight', ctypes.c_uint32), ('dmDisplayFlags', ctypes.c_uint32),
                ('dmDisplayFrequency', ctypes.c_uint32), ('dmICMMethod', ctypes.c_uint32), ('dmICMIntent', ctypes.c_uint32),
                ('dmMediaType', ctypes.c_uint32), ('dmDitherType', ctypes.c_uint32), ('dmReserved1', ctypes.c_uint32),
                ('dmReserved2', ctypes.c_uint32), ('dmPanningWidth', ctypes.c_uint32), ('dmPanningHeight', ctypes.c_uint32)]


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_uint32), ('DeviceName', ctypes.c_wchar * 32), ('DeviceString', ctypes.c_wchar * 128),
                ('StateFlags', ctypes.c_uint32), ('DeviceID', ctypes.c_wchar * 128), ('DeviceKey', ctypes.c_wchar * 128)]


def displays():
    u = ctypes.WinDLL('user32')
    res, i = [], 0
    while True:
        dd = DISPLAY_DEVICEW(); dd.cb = ctypes.sizeof(dd)
        if not u.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        i += 1
        if not dd.StateFlags & 1:  # bağlı masaüstüne ait değil
            continue
        cur = DEVMODEW(); cur.dmSize = ctypes.sizeof(cur)
        if not u.EnumDisplaySettingsW(dd.DeviceName, -1, ctypes.byref(cur)):
            continue
        mx, j = 0, 0
        while True:
            m = DEVMODEW(); m.dmSize = ctypes.sizeof(m)
            if not u.EnumDisplaySettingsW(dd.DeviceName, j, ctypes.byref(m)):
                break
            j += 1
            if m.dmPelsWidth == cur.dmPelsWidth and m.dmPelsHeight == cur.dmPelsHeight:
                mx = max(mx, m.dmDisplayFrequency)
        res.append({'name': dd.DeviceName, 'gpu': dd.DeviceString, 'w': cur.dmPelsWidth, 'h': cur.dmPelsHeight,
                    'hz': cur.dmDisplayFrequency, 'max': mx, 'primary': bool(dd.StateFlags & 4)})
    return res


def gpu_vram():
    out = []
    base = r'SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
    for i in range(16):
        k = f'{base}\\{i:04d}'
        desc = reg(winreg.HKEY_LOCAL_MACHINE, k, 'DriverDesc')
        if not desc:
            continue
        q = reg(winreg.HKEY_LOCAL_MACHINE, k, 'HardwareInformation.qwMemorySize')
        if isinstance(q, (bytes, bytearray)):
            q = int.from_bytes(q[:8], 'little')
        out.append({'name': desc, 'vram': round((q or 0) / 1048576), 'driver': reg(winreg.HKEY_LOCAL_MACHINE, k, 'DriverVersion') or '',
                    'date': reg(winreg.HKEY_LOCAL_MACHINE, k, 'DriverDate') or ''})
    return out


HW_LOCK = threading.Lock()


def load_hw(force=False):
    """Aynı anda birden çok yerden çağrılırsa PowerShell bir kez çalışır, diğerleri sonucu bekler."""
    with HW_LOCK:
        if HW and not force:
            return dict(HW)
        return _load_hw()


def _load_hw():
    js = ps(r'''
$o=[ordered]@{}
$c=Get-CimInstance Win32_Processor | Select-Object -First 1
$o.cpu=[ordered]@{name=$c.Name.Trim();cores=$c.NumberOfCores;threads=$c.NumberOfLogicalProcessors;mhz=$c.MaxClockSpeed;maker=$c.Manufacturer}
$o.ram=@(Get-CimInstance Win32_PhysicalMemory | ForEach-Object { [ordered]@{gb=[math]::Round($_.Capacity/1GB);speed=$_.Speed;conf=$_.ConfiguredClockSpeed;type=$_.SMBIOSMemoryType;maker=$_.Manufacturer;part=("$($_.PartNumber)").Trim();slot=$_.DeviceLocator} })
$b=Get-CimInstance Win32_BaseBoard; $bi=Get-CimInstance Win32_BIOS
$o.board=[ordered]@{maker=$b.Manufacturer;model=$b.Product;bios=$bi.SMBIOSBIOSVersion;biosdate=$bi.ReleaseDate.ToString('dd.MM.yyyy')}
$os=Get-CimInstance Win32_OperatingSystem
$o.os=[ordered]@{name=$os.Caption;build=$os.BuildNumber;ubr=(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR;ver=(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').DisplayVersion}
$o.disks=@(Get-PhysicalDisk | ForEach-Object { [ordered]@{name=$_.FriendlyName;type="$($_.MediaType)";bus="$($_.BusType)";gb=[math]::Round($_.Size/1GB);health="$($_.HealthStatus)"} })
$o.mon=@(Get-CimInstance -Namespace root\wmi WmiMonitorID -ErrorAction SilentlyContinue | ForEach-Object { -join ($_.UserFriendlyName | Where-Object { $_ } | ForEach-Object { [char]$_ }) })
$o.vbs=(Get-CimInstance -Namespace root\Microsoft\Windows\DeviceGuard Win32_DeviceGuard -ErrorAction SilentlyContinue).VirtualizationBasedSecurityStatus
$o | ConvertTo-Json -Depth 4 -Compress''', timeout=60)
    try:
        h = json.loads(js)
    except Exception:
        h = {}
    h['gpus'] = gpu_vram()
    try:
        h['disp'] = displays()
    except Exception:
        h['disp'] = []
    h['ram_gb'] = round(psutil.virtual_memory().total / 1024 ** 3)
    HW.clear(); HW.update(h)
    v = max([g['vram'] for g in h['gpus']] or [0])
    if v:
        LIM['vfull'] = int(v * 0.94)
    prim = next((d for d in h['disp'] if d['primary']), h['disp'][0] if h['disp'] else None)
    if prim:
        LIM['hz'] = prim['max'] or prim['hz']
        LIM['cap'] = max(57, LIM['hz'] - 3)
    return h


def num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def check_settings():
    """(durum, ad, şu an, öneri, neden). durum: ok / warn / bad / info"""
    out = []
    d = read_ini()
    if d is None:
        out.append(('bad', 'PUBG ayar dosyası', 'bulunamadı', '-', INI))
    else:
        vt = max([g['vram'] for g in HW.get('gpus') or []] or [0]) / 1024
        for key, reco, name, lo, hi, why in GFX:
            v = num(d.get(key))
            if v is None:
                continue
            v = int(v)
            if key == 'sg.TextureQuality' and vt:
                reco, lo, hi = (3, 3, 4) if vt >= 12 else ((2, 2, 3) if vt >= 8 else (1, 0, 1))
            good = lo <= v <= hi
            dist = 0 if good else min(abs(v - lo), abs(v - hi))
            st = 'ok' if good else ('warn' if dist == 1 else 'bad')
            rng = QL.get(lo) if lo == hi else f'{QL.get(lo)} – {QL.get(hi)}'
            out.append((st, name, QL.get(v, v), f'{QL.get(reco)}  (uygun: {rng})', why))
        rq = num(d.get('sg.ResolutionQuality'), 100)
        out.append(('ok' if rq == 100 else 'bad', 'Render Ölçeği', f'{rq:.0f}', '100',
                    '100 doğal çözünürlük demek. Altı bulanıklaştırır, üstü FPS düşürür.'))
        api = d.get('GraphicsAPI', 'DX11')
        out.append(('warn' if api.upper() == 'DX12' else 'ok', 'DirectX', api, 'DX11 Enhanced',
                    "PUBG'de DX11 Enhanced daha kararlı. DX12'de özellikle AMD kartlarda çökme olabiliyor."))
        fm = d.get('FullscreenMode', '0')
        out.append(('ok' if fm == '0' else 'bad', 'Ekran Modu', {'0': 'Tam ekran', '1': 'Kenarlıksız', '2': 'Pencere'}.get(fm, fm),
                    'Tam ekran', 'Kenarlıksız modda gecikme artar, FPS düşer.'))
        lt = d.get('InGameFrameRateLimitType', '')
        lim = num(d.get('InGameCustomFrameRateLimit'), 0)
        cap, hz = LIM['cap'], LIM['hz']
        why = (f"Ekranın {hz} Hz. FreeSync/G-Sync açıksa FPS'yi {cap}'de sınırla. FPS ekran hızını geçince "
               "senkronizasyon devre dışı kalır ve gecikme artar.")
        if lt.lower() == 'unlimited':
            out.append(('warn', 'Oyun içi FPS sınırı', 'Sınırsız', f'Özel: {cap}', why))
        else:
            out.append(('ok' if cap - 8 <= lim <= cap else 'warn', 'Oyun içi FPS sınırı', f'{lt} {lim:.0f}', f'Özel: {cap}', why))
        out.append(('ok' if d.get('bUseVSync', 'False') == 'False' else 'bad', 'Dikey Senkronizasyon (V-Sync)',
                    'Kapalı' if d.get('bUseVSync', 'False') == 'False' else 'Açık', 'Kapalı', 'Açıkken gecikme artar. FreeSync zaten açık.'))
        out.append(('ok' if d.get('bMotionBlur', 'False') == 'False' else 'bad', 'Hareket Bulanıklığı',
                    'Kapalı' if d.get('bMotionBlur', 'False') == 'False' else 'Açık', 'Kapalı', 'Açıkken hareket halindeki düşmanı görmek zorlaşır.'))
        out.append(('ok' if d.get('bSharpen', 'True') == 'True' else 'warn', 'Keskinleştirme',
                    'Açık' if d.get('bSharpen', 'True') == 'True' else 'Kapalı', 'Açık', 'Uzaktaki hedefleri netleştirir, FPS maliyeti yok.'))
        if 'bPreloadingMap' in d:
            out.append(('ok' if d['bPreloadingMap'] == 'True' else 'warn', 'Haritayı önceden yükle',
                        'Açık' if d['bPreloadingMap'] == 'True' else 'Kapalı', 'Açık',
                        f"{HW.get('ram_gb', 0)} GB RAM var. " + ('Açıkken harita önceden belleğe yüklenir, oyun içi takılmalar azalır.'
                         if HW.get('ram_gb', 0) >= 16 else '16 GB altında açmak RAM\'i doldurabilir, kapalı kalsın.')))
        up = d.get('UpscalingMethod', 'None')
        out.append(('ok' if up == 'None' else 'warn', 'FSR / DLSS', up, 'Kapalı',
                    'Güçlü kartta doğal çözünürlük daha net. FSR/DLSS sadece FPS yetmiyorsa açılmalı.'))

    # Windows
    gm = reg(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\GameBar', 'AutoGameModeEnabled')
    out.append(('ok' if gm in (None, 1) else 'bad', 'Windows Oyun Modu', 'Açık' if gm in (None, 1) else 'Kapalı', 'Açık',
                'Oyun oynarken arka plandaki işleri kısar.'))
    dvr = reg(winreg.HKEY_CURRENT_USER, r'System\GameConfigStore', 'GameDVR_Enabled')
    out.append(('ok' if dvr == 0 else 'warn', 'Xbox arka plan kaydı (Game DVR)', 'Kapalı' if dvr == 0 else 'Açık', 'Kapalı',
                'Arka planda sürekli kayıt yapar, FPS düşürür.'))
    hags = reg(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\GraphicsDrivers', 'HwSchMode')
    out.append(('ok' if hags == 2 else 'warn', 'Donanım hızlandırmalı GPU zamanlama', 'Açık' if hags == 2 else 'Kapalı', 'Açık',
                'Kare gecikmesini azaltır. Değişiklik yeniden başlatınca etkinleşir.'))
    wo = reg(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\DirectX\UserGpuPreferences', 'DirectXUserGlobalSettings') or ''
    out.append(('ok' if 'SwapEffectUpgradeEnable=1' in wo else 'info', 'Pencereli oyunlar için iyileştirmeler',
                'Açık' if 'SwapEffectUpgradeEnable=1' in wo else 'Kapalı', 'Açık', 'Kenarlıksız modda gecikmeyi azaltır.'))
    plan = powercfg('/getactivescheme')
    m = re.search(r'\((.+)\)', plan)
    pn = m.group(1) if m else plan
    good = any(x in pn.lower() for x in ('nihai', 'ultimate', 'yüksek', 'high'))
    out.append(('ok' if good else 'warn', 'Güç planı', pn or '?', 'Yüksek / Nihai performans',
                'Çekirdeklerin uykudan uyanma gecikmesini azaltır, ani FPS düşüşlerini önler.'))
    rams = HW.get('ram') or []
    if rams:
        rv = min(r.get('conf') or 0 for r in rams)
        rt = rams[0].get('type')
        ddr = 'DDR5' if rt == 34 else ('DDR4' if rt == 26 else '')
        need = 5600 if ddr == 'DDR5' else (3000 if ddr == 'DDR4' else 0)
        if rv and need:
            out.append(('ok' if rv >= need else 'bad', f'RAM hızı ({ddr})', f'{rv} MT/s', f'{need}+ MT/s',
                        "Düşükse BIOS'ta XMP (Intel) ya da EXPO (AMD) profilini aç. Oyunda FPS'yi doğrudan etkiler."))
        if len(rams) == 1:
            out.append(('warn', 'RAM kanal', 'Tek modül', 'Çift modül', 'Tek modül tek kanal çalışır, FPS belirgin düşer.'))
    if str(HW.get('vbs')) == '2':
        out.append(('info', 'VBS (sanallaştırma tabanlı güvenlik)', 'Açık', 'Bilgi',
                    "FPS'yi %5'e kadar düşürebilir. Bazı programlar (sanal makine, uzaktan erişim) buna ihtiyaç duyar."))
    for dsp in HW.get('disp') or []:
        if dsp['max'] and dsp['hz'] < dsp['max']:
            out.append(('bad', f"Ekran yenileme hızı ({dsp['name'].replace(chr(92), '').replace('.', '')})", f"{dsp['hz']} Hz",
                        f"{dsp['max']} Hz", 'Ekran en yüksek hızında çalışmıyor. Windows Ekran ayarları → Gelişmiş ekran → Yenileme hızı.'))
    try:
        free = psutil.disk_usage('C:\\').free / 1024 ** 3
        out.append(('ok' if free >= 30 else 'warn', 'C: boş alan', f'{free:.0f} GB', '30 GB üstü', 'Az kalırsa Windows ve oyun yavaşlar.'))
    except Exception:
        pass
    running = sorted({BG_APPS[p.info['name'].lower()] for p in psutil.process_iter(['name'])
                      if (p.info['name'] or '').lower() in BG_APPS})
    out.append(('ok' if not running else 'warn', 'Arka plan programları', ', '.join(running) or 'temiz', 'Kapalı',
                'Oyun oynarken kapat. Takılmanın sık rastlanan sebeplerinden biri.'))
    cpu = cpu_sensor()
    if cpu:
        out.append(('ok' if cpu['T'] < 85 else 'warn', 'İşlemci sıcaklığı (şu an)', f"{cpu['T']}°C", '85°C altı',
                    f"Oyunda {LIM['hot']}°C'yi geçiyorsa soğutucuyu kontrol et. AMD'de BIOS'ta PBO Thermal Limit'i 85 yapmak da işe yarar."))
    return out


CFG = os.path.join(DATA, 'ayar.json')
SCOPES = {'Normal': 'Genel', 'Targeting': 'Nişan (sağ tık)', 'Scoping': 'Nişangâh / kırmızı nokta', 'ScopingMagnified': 'Büyütmeli dürbün',
          'Scope2X': '2x', 'Scope3X': '3x', 'Scope4X': '4x', 'Scope6X': '6x', 'Scope8X': '8x', 'Scope15X': '15x'}
INPUT_MODES = {
    'InputModePeek': ('Eğilme (Q/E)', 'Hold', 'Basılı tut daha hızlı ve kontrollü olur. Profesyonellerin çoğu bunu kullanır.'),
    'InputModeHoldBreath': ('Nefes tutma', 'Hold', 'Basılı tut olmalı.'),
    'InputModeWalk': ('Yürüme', 'Hold', 'Basılı tut olursa sessiz yürüyüşü anında bırakabilirsin.'),
    'InputModeCrouch': ('Eğilme (C)', None, 'İkisi de olur, alışkanlık meselesi.'),
    'InputModeProne': ('Yatma', None, 'İkisi de olur.'),
    'InputModeAim': ('Nişan alma (sağ tık basılı)', None, 'Varsayılan: basılı tutunca omuz üstü nişan.'),
    'InputModeADS': ('Nişangâhtan bakma (sağ tık)', None, 'Varsayılan: tek tıkla nişangâh açılır/kapanır.'),
}
KEY_TR = {'Interact': 'Etkileşim', 'PushToTalk': 'Bas-konuş', 'ShowPackageItemList': 'Envanter', 'EmoteHK1': 'Emote 1'}
SKIP_ACT = ('Observer', 'Debug', 'Drone', 'PlayerList', 'Slot', 'UI_', 'Widget', 'Spectat', 'Camera', 'Follow', 'NextPlayer',
            'Switch', 'Parachute', 'Platoon', 'Replay', 'InfoTab', 'Quick', 'LoginConsole', 'AddWayPoint', 'Delete', 'MovePlayerInfo',
            'OnObserving', 'OnPlayerList', 'Combination', 'Gamepad')


def load_cfg():
    try:
        with open(CFG, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_cfg(c):
    try:
        with open(CFG, 'w', encoding='utf-8') as f:
            json.dump(c, f)
    except OSError:
        pass


def check_input(dpi=0):
    out = []
    raw = ''
    try:
        with open(INI, encoding='utf-8', errors='ignore') as f:
            raw = f.read()
    except OSError:
        pass
    d = read_ini() or {}

    # Oyun içi hassasiyet
    sens = {m.group(1): (float(m.group(2)), float(m.group(3))) for m in re.finditer(
        r'SensitiveName="(\w+)",Sensitivity=([\d.]+),LastConvertedSensitivity=([\d.]+)', raw)}
    gen = sens.get('Normal', (50.0, 0.02))
    out.append(('info', 'Genel hassasiyet', f'{gen[0]:.0f}', '-', 'Oyundaki "Genel" hassasiyet değerin. Değiştirilmemiş dürbünler varsayılan 50 kalır.'))
    if dpi:
        eff = dpi * gen[1]
        st = 'ok' if 6 <= eff <= 14 else 'warn'
        out.append((st, 'Etkin hassasiyet (DPI × oyun)', f'{dpi} DPI × {gen[1]:.4f} = {eff:.1f}', '6 – 14 arası',
                    'Bu aralık profesyonel PUBG oyuncularının çoğunun kullandığı aralık (yaklaşık bir değer). Yüksekse nişan titrer, düşükse dönüşlerde yetişemezsin.'))
        if dpi > 3200:
            out.append(('warn', 'Fare DPI', str(dpi), '400 – 1600',
                        'Çok yüksek DPI küçük el titremelerini de büyütür. DPI\'ı düşürüp oyun içi hassasiyeti artır.'))
    else:
        out.append(('info', 'Fare DPI', 'girilmedi', '400 – 1600', 'Yukarıdaki kutuya farenin DPI değerini yaz. Etkin hassasiyet de hesaplanır.'))
    changed = [f'{SCOPES.get(k, k)} {v[0]:.0f}' for k, v in sens.items() if k != 'Normal']
    per = 'bIsUsingPerScopeMouseSensitivity=True' in raw
    if per and not changed and abs(gen[0] - 50) > 3:
        out.append(('warn', 'Dürbün hassasiyetleri', 'hepsi varsayılan 50', 'Genel ile uyumlu',
                    f'Genel hassasiyeti {gen[0]:.0f} yapmışsın ama Nişan, Nişangâh ve dürbünler 50\'de kalmış. Nişan alınca fare hissi değişiyor. '
                    'Oyunda Ayarlar → Kontroller → Fare kısmında Nişan ve Nişangâh değerlerini Genel\'e yakın ayarla.'))
    elif changed:
        out.append(('info', 'Dürbün hassasiyetleri', ', '.join(changed), '-', 'Değiştirdiğin dürbün hassasiyetleri.'))
    vm = num(re.search(r'MouseVerticalSensitivityMultiplierAdjusted=([\d.]+)', raw).group(1), 1) if 'MouseVerticalSensitivityMultiplierAdjusted' in raw else 1
    out.append(('ok' if 0.9 <= vm <= 1.4 else 'warn', 'Dikey hassasiyet çarpanı', f'{vm:.2f}', '1.00 – 1.30',
                '1.00 standart. Bazı oyuncular sekmeyi kolay çekmek için 1.1 – 1.3 kullanır.'))
    inv = 'bInvertMouse=True' in raw
    out.append(('bad' if inv else 'ok', 'Fareyi ters çevir', 'Açık' if inv else 'Kapalı', 'Kapalı', 'Ters çevrilmiş fare yukarı-aşağı hareketi tersler.'))
    fov = num(d.get('FpsCameraFov'), 0)
    if fov:
        out.append(('ok' if fov >= 100 else 'warn', 'FPP görüş açısı (FOV)', f'{fov:.0f}', '100 – 103',
                    '2026 rekabetçi önerisi 100-103 (en fazla 103). Kenardaki düşmanı daha erken görürsün, FPS etkisi küçük.'))

    # Tuş davranışları
    for k, (name, reco, why) in INPUT_MODES.items():
        v = d.get(k)
        if v is None:
            continue
        tr = {'Hold': 'Basılı tut', 'Toggle': 'Aç/kapa'}.get(v, v)
        if reco:
            out.append(('ok' if v == reco else 'warn', name, tr, {'Hold': 'Basılı tut', 'Toggle': 'Aç/kapa'}[reco], why))
        else:
            out.append(('info', name, tr, '-', why))

    # Değiştirilmiş tuşlar
    keys = []
    for m in re.finditer(r'\(ActionName="(\w+)",Keys=\(\(Key=(\w+)((?:,b\w+=True)*)\)', raw):
        act, key, mod = m.groups()
        if act.endswith('Pad') or 'Pad' in act or any(s in act for s in SKIP_ACT):
            continue
        mods = '+'.join(x.split('=')[0][1:] for x in mod.split(',') if x)
        keys.append(f"{KEY_TR.get(act, act)} = {(mods + '+') if mods else ''}{key}")
    if keys:
        out.append(('info', 'Değiştirdiğin tuşlar', ', '.join(sorted(set(keys))), '-', 'Diğer tuşlar varsayılan atamada.'))

    # Windows fare
    ms = str(reg(winreg.HKEY_CURRENT_USER, r'Control Panel\Mouse', 'MouseSensitivity') or '10')
    out.append(('ok' if ms == '10' else 'warn', 'Windows işaretçi hızı', f'{ms} / 20', '10 (6. çentik)',
                '10 değerinde fare hareketi 1:1 aktarılır. Oyun ham giriş kullandığı için oyun içini etkilemez, menü ve masaüstünü etkiler.'))
    acc = str(reg(winreg.HKEY_CURRENT_USER, r'Control Panel\Mouse', 'MouseSpeed') or '1')
    out.append(('ok' if acc == '0' else 'warn', 'Fare ivmesi (İşaretçi hassasiyetini artır)', 'Kapalı' if acc == '0' else 'Açık', 'Kapalı',
                'Açıkken hızlı hareket daha uzağa gider. PUBG ham giriş kullanır, oyun içi nişanı etkilemez. Masaüstü ve menüde kapalı olması tutarlılık sağlar.'))
    out.append(('info', 'Fare yoklama hızı (polling)', 'okunamıyor', '1000 Hz veya üstü',
                'Farenin kendi yazılımından kontrol et (ASUS ise Armoury Crate). 125/500 Hz takılma gibi hissettirir.'))

    # Windows klavye
    kd = str(reg(winreg.HKEY_CURRENT_USER, r'Control Panel\Keyboard', 'KeyboardDelay') or '1')
    ks = str(reg(winreg.HKEY_CURRENT_USER, r'Control Panel\Keyboard', 'KeyboardSpeed') or '31')
    out.append(('ok' if kd == '0' else 'warn', 'Klavye tekrar gecikmesi', kd, '0 (en kısa)', 'Basılı tutulan tuşun tekrar etmeye başlama süresi.'))
    out.append(('ok' if ks == '31' else 'warn', 'Klavye tekrar hızı', ks, '31 (en hızlı)', 'Basılı tuşun tekrar hızı.'))
    for nm, path, default, okv in (('Yapışkan Tuşlar kısayolu (5× Shift)', 'StickyKeys', '510', '506'),
                                   ('Filtre Tuşları kısayolu (8 sn Shift)', 'Keyboard Response', '126', '122'),
                                   ('Geçiş Tuşları kısayolu (5 sn NumLock)', 'ToggleKeys', '62', '58')):
        fl = reg(winreg.HKEY_CURRENT_USER, rf'Control Panel\Accessibility\{path}', 'Flags') or default
        on = int(num(fl, 0)) & 4
        out.append(('warn' if on else 'ok', nm, 'Açık' if on else 'Kapalı', 'Kapalı',
                    'Oyunda Shift\'e art arda basınca masaüstüne atan pencere açar.'))
    return out


def apply_input():
    msgs = []
    u = ctypes.WinDLL('user32')
    upd = 3  # SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
    if str(reg(winreg.HKEY_CURRENT_USER, r'Control Panel\Mouse', 'MouseSpeed') or '1') != '0':
        arr = (ctypes.c_int * 3)(0, 0, 0)
        u.SystemParametersInfoW(0x0004, 0, arr, upd); msgs.append('Fare ivmesi → Kapalı')
    if str(reg(winreg.HKEY_CURRENT_USER, r'Control Panel\Mouse', 'MouseSensitivity') or '10') != '10':
        u.SystemParametersInfoW(0x0071, 0, ctypes.c_void_p(10), upd); msgs.append('Windows işaretçi hızı → 10')
    if str(reg(winreg.HKEY_CURRENT_USER, r'Control Panel\Keyboard', 'KeyboardDelay') or '1') != '0':
        u.SystemParametersInfoW(0x0017, 0, None, upd); msgs.append('Klavye tekrar gecikmesi → 0')
    if str(reg(winreg.HKEY_CURRENT_USER, r'Control Panel\Keyboard', 'KeyboardSpeed') or '31') != '31':
        u.SystemParametersInfoW(0x000B, 31, None, upd); msgs.append('Klavye tekrar hızı → 31')
    for path, default, okv, nm in (('StickyKeys', '510', '506', 'Yapışkan Tuşlar kısayolu → Kapalı'),
                                   ('Keyboard Response', '126', '122', 'Filtre Tuşları kısayolu → Kapalı'),
                                   ('ToggleKeys', '62', '58', 'Geçiş Tuşları kısayolu → Kapalı')):
        p = rf'Control Panel\Accessibility\{path}'
        fl = int(num(reg(winreg.HKEY_CURRENT_USER, p, 'Flags') or default, 0))
        if fl & 4:
            try:
                with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, p, 0, winreg.KEY_SET_VALUE) as k:
                    winreg.SetValueEx(k, 'Flags', 0, winreg.REG_SZ, str(fl & ~4))
                msgs.append(nm)
            except OSError:
                pass
    return msgs


def apply_recommended():
    """PUBG kapalıyken PUBG ayarlarını ve güvenli Windows ayarlarını önerilenlere çeker. Yedek alır."""
    msgs = []
    if any((p.info['name'] or '').lower() == GAME.lower() for p in psutil.process_iter(['name'])):
        return ["PUBG açık. Önce oyunu kapat, yoksa oyun kapanırken ayarları eski haline yazar."]
    if os.path.exists(INI):
        bak = INI + f'.izleyici_yedek_{datetime.datetime.now():%Y%m%d_%H%M%S}'
        shutil.copy2(INI, bak)
        with open(INI, encoding='utf-8', errors='ignore', newline='') as f:
            txt = f.read()
        d = read_ini() or {}

        def setk(k, v):
            nonlocal txt
            txt = re.sub(rf'(?m)^{re.escape(k)}=[^\r\n]*', f'{k}={v}', txt)

        vt = max([g['vram'] for g in HW.get('gpus') or []] or [0]) / 1024
        for key, reco, name, lo, hi, _ in GFX:
            v = num(d.get(key))
            if v is None:
                continue
            if key == 'sg.TextureQuality' and vt:
                reco, lo, hi = (3, 3, 4) if vt >= 12 else ((2, 2, 3) if vt >= 8 else (1, 0, 1))
            good = lo <= v <= hi
            if not good:
                setk(key, reco)
                msgs.append(f'{name}: {QL.get(int(v))} → {QL.get(reco)}')
        if num(d.get('sg.ResolutionQuality'), 100) != 100:
            setk('sg.ResolutionQuality', '100.000000'); msgs.append('Render Ölçeği → 100')
        if d.get('GraphicsAPI', '').upper() == 'DX12':
            txt = re.sub(r'(?m)^GraphicsAPI=DX12\r?\n', '', txt); msgs.append('DirectX 12 → DirectX 11')
        for k in ('FullscreenMode', 'PreferredFullscreenMode', 'LastConfirmedFullscreenMode'):
            if d.get(k, '0') != '0':
                setk(k, '0')
        if d.get('FullscreenMode', '0') != '0':
            msgs.append('Ekran modu → Tam ekran')
        fov = num(d.get('FpsCameraFov'), 0)
        if fov and fov < 100:
            setk('FpsCameraFov', '103.000000'); msgs.append(f'FPP görüş açısı (FOV): {fov:.0f} → 103')
        cap = LIM['cap']
        if d.get('InGameFrameRateLimitType') != 'Custom' or abs(num(d.get('InGameCustomFrameRateLimit'), 0) - cap) > 0.5:
            setk('InGameFrameRateLimitType', 'Custom')
            setk('InGameCustomFrameRateLimit', f'{cap:.6f}')
            setk('FrameRateLimit', f'{cap:.6f}')
            msgs.append(f'Oyun içi FPS sınırı → Özel {cap}')
        for k, v, nm in (('bUseVSync', 'False', 'V-Sync → Kapalı'), ('bMotionBlur', 'False', 'Hareket bulanıklığı → Kapalı'),
                         ('bSharpen', 'True', 'Keskinleştirme → Açık'), ('bPreloadingMap', 'True', 'Haritayı önceden yükle → Açık')):
            if k in d and d[k] != v:
                setk(k, v); msgs.append(nm)
        with open(INI, 'w', encoding='utf-8', newline='') as f:
            f.write(txt)
        msgs.append(f'PUBG yedeği: {os.path.basename(bak)}')

    def setreg(root, path, name, val):
        with winreg.CreateKeyEx(root, path, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, val)

    try:
        if reg(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\GameBar', 'AutoGameModeEnabled') == 0:
            setreg(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\GameBar', 'AutoGameModeEnabled', 1); msgs.append('Oyun Modu → Açık')
        if reg(winreg.HKEY_CURRENT_USER, r'System\GameConfigStore', 'GameDVR_Enabled') != 0:
            setreg(winreg.HKEY_CURRENT_USER, r'System\GameConfigStore', 'GameDVR_Enabled', 0)
            setreg(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\GameDVR', 'AppCaptureEnabled', 0)
            msgs.append('Xbox arka plan kaydı → Kapalı')
        if reg(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\GraphicsDrivers', 'HwSchMode') != 2:
            setreg(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\GraphicsDrivers', 'HwSchMode', 2)
            msgs.append('GPU zamanlama → Açık (yeniden başlatınca etkinleşir)')
    except OSError as e:
        msgs.append(f'Windows ayarı yazılamadı: {e}')
    plan = powercfg('/getactivescheme').lower()
    if plan and not any(x in plan for x in ('nihai', 'ultimate', 'yüksek', 'high')):
        powercfg('/setactive', 'SCHEME_MIN'); msgs.append('Güç planı → Yüksek performans')
    msgs += apply_input()
    if len(msgs) <= 1:
        msgs.insert(0, 'Değiştirilecek bir şey yoktu, ayarlar zaten önerilen değerlerde.')
    msgs.append(f"Elle yapılacaklar: oyuna girince FPS sınırının Özel {LIM['cap']} olduğunu kontrol et. Fare hassasiyetine ve tuşlara dokunulmadı.")
    return msgs


# ---------------- Ağ ölçümü (ICMP ping + trafik) ----------------
import socket


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


# ---------------- GPU-Z yoksa: Windows sayaçları (her dilde çalışır) ----------------
class _FMTV(ctypes.Structure):
    _fields_ = [('CStatus', ctypes.c_uint32), ('doubleValue', ctypes.c_double)]


class _ITEM(ctypes.Structure):
    _fields_ = [('szName', ctypes.c_wchar_p), ('FmtValue', _FMTV)]


class GpuPdh:
    def __init__(self):
        self.ok = False
        try:
            self.pdh = ctypes.WinDLL('pdh')
            self.q = ctypes.c_void_p()
            self.pdh.PdhOpenQueryW(None, 0, ctypes.byref(self.q))
            self.c3d, self.cmem = ctypes.c_void_p(), ctypes.c_void_p()
            a = self.pdh.PdhAddEnglishCounterW(self.q, r'\GPU Engine(*engtype_3D)\Utilization Percentage', 0, ctypes.byref(self.c3d))
            b = self.pdh.PdhAddEnglishCounterW(self.q, r'\GPU Adapter Memory(*)\Dedicated Usage', 0, ctypes.byref(self.cmem))
            self.pdh.PdhCollectQueryData(self.q)
            self.ok = (a == 0)
            self.okm = (b == 0)
        except Exception:
            pass

    def _arr(self, c):
        size, cnt = ctypes.c_uint32(0), ctypes.c_uint32(0)
        self.pdh.PdhGetFormattedCounterArrayW(c, 0x200, ctypes.byref(size), ctypes.byref(cnt), None)
        if not size.value:
            return []
        buf = ctypes.create_string_buffer(size.value)
        if self.pdh.PdhGetFormattedCounterArrayW(c, 0x200, ctypes.byref(size), ctypes.byref(cnt), buf) != 0:
            return []
        arr = ctypes.cast(buf, ctypes.POINTER(_ITEM))
        return [arr[i].FmtValue.doubleValue for i in range(cnt.value) if arr[i].FmtValue.CStatus in (0, 1)]

    def read(self):
        if not self.ok:
            return None
        try:
            self.pdh.PdhCollectQueryData(self.q)
            load = min(100, round(sum(self._arr(self.c3d))))
            mem = round(max(self._arr(self.cmem) or [0]) / 1048576) if self.okm else 0
            return {'T': 0, 'HS': 0, 'Load': load, 'VRAM': mem, 'Pwr': 0}
        except Exception:
            return None


# ---------------- En çok kaynak kullanan programlar ----------------
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


# ---------------- PUBG resmi API (hesap istatistikleri) ----------------
import urllib.parse, urllib.error

PUBG_API = 'https://api.pubg.com/shards/steam'
HIST = os.path.join(DATA, 'gecmis.json')
MAPS = {'Baltic_Main': 'Erangel', 'Erangel_Main': 'Erangel', 'Desert_Main': 'Miramar', 'Savage_Main': 'Sanhok',
        'DihorOtok_Main': 'Vikendi', 'Summerland_Main': 'Karakin', 'Tiger_Main': 'Taego', 'Kiki_Main': 'Deston',
        'Chimera_Main': 'Paramo', 'Heaven_Main': 'Haven', 'Neon_Main': 'Rondo', 'Range_Main': 'Camp Jackal'}
MODES = [('squad-fpp', 'Squad FPP'), ('squad', 'Squad TPP'), ('duo-fpp', 'Duo FPP'), ('duo', 'Duo TPP'),
         ('solo-fpp', 'Solo FPP'), ('solo', 'Solo TPP')]


def pubg_get(path, key):
    req = urllib.request.Request(PUBG_API + path, headers={'Authorization': 'Bearer ' + key,
                                                           'Accept': 'application/vnd.api+json'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def account_id_from_ini():
    try:
        with open(INI, encoding='utf-8', errors='ignore') as f:
            m = re.search(r'account\.[0-9a-f]{32}', f.read())
        return m.group(0) if m else None
    except OSError:
        return None


def fetch_account(key, name=''):
    if name:
        pl = pubg_get('/players?filter[playerNames]=' + urllib.parse.quote(name), key)['data'][0]
    else:
        aid = account_id_from_ini()
        if not aid:
            raise ValueError('Hesap kimliği bulunamadı, oyuncu adını yaz.')
        pl = pubg_get('/players/' + aid, key)['data']
    aid, nm = pl['id'], pl['attributes']['name']
    cur = next((x['id'] for x in pubg_get('/seasons', key)['data'] if x['attributes'].get('isCurrentSeason')), None)
    life = pubg_get(f'/players/{aid}/seasons/lifetime', key)['data']['attributes']['gameModeStats']
    seas = pubg_get(f'/players/{aid}/seasons/{cur}', key)['data']['attributes']['gameModeStats'] if cur else {}
    try:
        ranked = pubg_get(f'/players/{aid}/seasons/{cur}/ranked', key)['data']['attributes']['rankedGameModeStats'] if cur else {}
    except Exception:
        ranked = {}
    matches = []
    for m in [x['id'] for x in pl.get('relationships', {}).get('matches', {}).get('data', [])][:10]:
        try:
            d = pubg_get('/matches/' + m, key)
        except Exception:
            continue
        a = d['data']['attributes']
        me = next((x['attributes']['stats'] for x in d.get('included', [])
                   if x.get('type') == 'participant' and x['attributes']['stats'].get('playerId') == aid), None)
        if me:
            matches.append({'map': MAPS.get(a.get('mapName'), a.get('mapName')), 'mode': a.get('gameMode'),
                            'date': a.get('createdAt', '')[:16].replace('T', ' '), 'place': me.get('winPlace'),
                            'kills': me.get('kills', 0), 'dmg': me.get('damageDealt', 0), 'hs': me.get('headshotKills', 0),
                            'time': me.get('timeSurvived', 0), 'type': a.get('matchType', '')})
    return {'name': nm, 'id': aid, 'season': cur, 'life': life, 'seas': seas, 'ranked': ranked, 'matches': matches}


def load_hist():
    try:
        with open(HIST, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def save_hist(h):
    try:
        with open(HIST, 'w', encoding='utf-8') as f:
            json.dump(h[-200:], f, ensure_ascii=False)
    except OSError:
        pass


def gfx_snapshot():
    d = read_ini() or {}
    short = {'sg.ViewDistanceQuality': 'Görüş', 'sg.ShadowQuality': 'Gölge', 'sg.PostProcessQuality': 'İşlem',
             'sg.EffectsQuality': 'Efekt', 'sg.FoliageQuality': 'Yeşil', 'sg.TextureQuality': 'Doku',
             'sg.AntiAliasingQuality': 'AA'}
    ab = {0: 'ÇD', 1: 'D', 2: 'O', 3: 'Y', 4: 'U'}
    parts = [f"{v} {ab.get(int(num(d.get(k), -1)), '?')}" for k, v in short.items() if k in d]
    api = d.get('GraphicsAPI', 'DX11')
    return ' '.join(parts) + f' · {api}'


# ---------------- Otomatik güncelleme (GitHub Releases) ----------------
def vtuple(v):
    return tuple(int(x) for x in re.findall(r'\d+', v)[:3]) or (0,)


def check_update():
    req = urllib.request.Request(f'https://api.github.com/repos/{REPO}/releases/latest',
                                 headers={'User-Agent': 'PUBG-Izleyici', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=15) as r:
        rel = json.load(r)
    ver = rel.get('tag_name', '').lstrip('vV')
    if vtuple(ver) <= vtuple(VERSION):
        return None
    asset = next((a for a in rel.get('assets', []) if a['name'].lower().endswith('.exe')), None)
    if not asset:
        return None
    return {'ver': ver, 'notes': rel.get('body') or '', 'url': asset['browser_download_url'], 'size': asset.get('size', 0),
            'digest': asset.get('digest') or ''}


def download_update(info, progress=None):
    dst = os.path.join(DATA, f"PUBG_Izleyici_{info['ver']}.exe")
    tmp = dst + '.part'
    req = urllib.request.Request(info['url'], headers={'User-Agent': 'PUBG-Izleyici'})
    sha = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, 'wb') as f:
        total, done, last = info.get('size') or 0, 0, -1
        while True:
            chunk = r.read(262144)
            if not chunk:
                break
            f.write(chunk); sha.update(chunk); done += len(chunk)
            if progress and total and int(done * 100 / total) != last:
                last = int(done * 100 / total)
                progress(done / total)
    if info.get('size') and os.path.getsize(tmp) != info['size']:
        os.remove(tmp)
        raise IOError('indirme eksik')
    dg = info.get('digest') or ''
    if dg.startswith('sha256:') and dg[7:].lower() != sha.hexdigest():
        os.remove(tmp)
        raise IOError('indirilen dosya doğrulanamadı (SHA-256 uyuşmuyor)')
    os.replace(tmp, dst)
    return dst


def install_update(new_exe):
    """Çalışan exe'nin adını değiştirir (Windows buna izin verir), yenisini yerine koyar ve başlatır.
    Eski exe bir sonraki açılışta silinir. Toplu iş dosyası kullanmaz: Türkçe karakterli yollarda da çalışır."""
    exe = sys.executable
    old = exe + '.old'
    try:
        os.remove(old)
    except OSError:
        pass
    os.replace(exe, old)
    try:
        shutil.copy2(new_exe, exe)
    except Exception:
        os.replace(old, exe)
        raise
    env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT='1')  # yeni exe kendi geçici klasörünü açsın, eskisininkini değil
    subprocess.Popen([exe], cwd=os.path.dirname(exe), env=env, close_fds=True)
    try:
        os.remove(new_exe)
    except OSError:
        pass


# ---------------- Modern arayüz parçaları ----------------
C_BG, C_CARD, C_LINE = '#0e1014', '#181b22', '#262b36'
C_TXT, C_SUB, C_ACC = '#e8eaed', '#8b93a1', '#4cc2ff'
C_OK, C_WARN, C_BAD = '#3ddc84', '#ffc845', '#ff5c5c'
F_NUM = 'Bahnschrift'
F_UI = 'Segoe UI'


def lvl_color(v, warn, bad):
    return C_BAD if v >= bad else (C_WARN if v >= warn else C_OK)


_NOCH = object()


def setl(w, **kw):
    """Widget'ı sadece değer değiştiyse yeniden yapılandırır. Tk'de her config yeniden yerleşim tetikler;
    saniyede onlarca etiket aynı metinle güncellenince boşuna işlemci harcanıyordu."""
    st = w.__dict__.setdefault('_st', {})
    ch = {k: v for k, v in kw.items() if st.get(k, _NOCH) != v}
    if ch:
        w.config(**ch)
        st.update(ch)


def hover(b, over=None):
    """Düz butonlara fareyle üzerine gelince hafif vurgu."""
    over = over or C_LINE

    def enter(_):
        b._base = b.cget('bg')
        if b._base != C_ACC:
            b.config(bg=over)

    def leave(_):
        if b.cget('bg') == over:
            b.config(bg=getattr(b, '_base', C_CARD))
    b.bind('<Enter>', enter, add='+'); b.bind('<Leave>', leave, add='+')
    return b


def style_window(win):
    """Windows 10/11: koyu başlık çubuğu, başlık rengi arka planla aynı, ince kenarlık, yuvarlak köşe."""
    def go():
        try:
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
            dwm = ctypes.windll.dwmapi
            rgb = lambda h: int(h[5:7] + h[3:5] + h[1:3], 16)  # COLORREF = 0x00BBGGRR
            for attr, val in ((20, 1), (19, 1), (35, rgb(C_BG)), (34, rgb(C_LINE)), (36, rgb(C_TXT)), (33, 2)):
                v = ctypes.c_int(val)
                dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), 4)
        except Exception:
            pass
    win.after(10, go)


def card(parent, title):
    f = tk.Frame(parent, bg=C_CARD, highlightthickness=1, highlightbackground=C_LINE)
    tk.Label(f, text=title.upper(), bg=C_CARD, fg=C_SUB, font=(F_UI, 8, 'bold')).pack(anchor='w', padx=12, pady=(8, 0))
    return f


class Gauge:
    """Yay göstergesi. Öğeler bir kez çizilir, sonra sadece değişen değerler güncellenir."""
    def __init__(self, parent, size, title, unit='°C', vmax=100, warn=80, bad=90):
        self.b, self.s = size, px(size)  # b: yazı boyutları için 96 DPI karşılığı, s: gerçek piksel
        self.unit, self.vmax, self.warn, self.bad = unit, vmax, warn, bad
        s, b = self.s, size
        self.c = c = tk.Canvas(parent, width=s, height=s, bg=C_CARD, highlightthickness=0)
        pad, w = px(10), max(px(6), s // 14)
        c.create_arc(pad, pad, s - pad, s - pad, start=225, extent=-270, style='arc', outline=C_LINE, width=w)
        self.arc = c.create_arc(pad, pad, s - pad, s - pad, start=225, extent=-1, style='arc', outline=C_OK, width=w,
                                state='hidden')
        self.val = c.create_text(s / 2, s / 2, text='—', fill=C_SUB, font=(F_NUM, b // 6))
        self.unt = c.create_text(s / 2, s / 2 + s // 7, text=unit, fill=C_SUB, font=(F_UI, max(7, b // 15)), state='hidden')
        c.create_text(s / 2, s - pad - px(2), text=title, fill=C_SUB, font=(F_UI, max(7, b // 15), 'bold'))
        self.sub = c.create_text(s / 2, pad + px(6), text='', fill=C_SUB, font=(F_UI, 7))
        self.last = None

    def set(self, v, sub=''):
        key = (round(v) if v else None, sub, self.warn, self.bad)
        if key == self.last:
            return
        self.last = key
        c, s, b = self.c, self.s, self.b
        if v:
            c.itemconfig(self.arc, state='normal', extent=-max(1, 270 * min(v / self.vmax, 1)),
                         outline=lvl_color(v, self.warn, self.bad))
            c.itemconfig(self.val, text=f'{v:.0f}', fill=C_TXT, font=(F_NUM, b // 5, 'bold'))
            c.coords(self.val, s / 2, s / 2 - px(4))
            c.itemconfig(self.unt, state='normal')
        else:
            c.itemconfig(self.arc, state='hidden')
            c.itemconfig(self.val, text='—', fill=C_SUB, font=(F_NUM, b // 6))
            c.coords(self.val, s / 2, s / 2)
            c.itemconfig(self.unt, state='hidden')
        c.itemconfig(self.sub, text=sub)


class Spark:
    """Mini çizgi grafik. Çizgi ve dolgu tek öğedir, her saniye sadece koordinatları değişir."""
    def __init__(self, parent, w, h, color=C_ACC, n=90):
        self.w, self.h = px(w), px(h)
        self.d = collections.deque(maxlen=n)
        self.c = c = tk.Canvas(parent, width=self.w, height=self.h, bg=C_CARD, highlightthickness=0)
        self.poly = c.create_polygon(0, 0, 0, 0, 0, 0, fill='#1d2a36', outline='', state='hidden')
        self.line = c.create_line(0, 0, 0, 0, fill=color, width=max(2, px(2)), smooth=True, state='hidden')
        self.thi = c.create_text(0, 0, anchor='ne', fill=C_SUB, font=(F_UI, 7))
        self.tlo = c.create_text(0, 0, anchor='se', fill=C_SUB, font=(F_UI, 7))
        c.bind('<Map>', lambda e: self.draw())  # sekmeye dönünce hemen güncel çiz

    def push(self, v):
        self.d.append(v)
        if self.c.winfo_viewable():  # görünmeyen sekmede çizim yapılmaz
            self.draw()

    def draw(self):
        c, h = self.c, self.h
        w = max(self.w, c.winfo_width())
        vals = [x for x in self.d if x is not None]
        if len(vals) < 2:
            c.itemconfig(self.poly, state='hidden'); c.itemconfig(self.line, state='hidden')
            return
        lo, hi = min(vals), max(vals)
        if hi - lo < 1:
            hi = lo + 1
        n, m, top = self.d.maxlen, len(self.d), px(16)
        pts = []
        for i, x in enumerate(self.d):
            if x is not None:
                pts += [w - (m - 1 - i) * (w / (n - 1)), h - px(4) - (x - lo) / (hi - lo) * (h - top)]
        c.coords(self.poly, *pts, pts[-2], h, pts[0], h)
        c.coords(self.line, *pts)
        c.itemconfig(self.poly, state='normal'); c.itemconfig(self.line, state='normal')
        c.coords(self.thi, w - 2, 2); c.itemconfig(self.thi, text=f'{hi:.0f}')
        c.coords(self.tlo, w - 2, h - 2); c.itemconfig(self.tlo, text=f'{lo:.0f}')


class Bar:
    def __init__(self, parent, w, h=8):
        self.w, self.h = px(w), px(h)
        self.c = c = tk.Canvas(parent, width=self.w, height=self.h, bg=C_CARD, highlightthickness=0)
        c.create_rectangle(0, 0, self.w, self.h, fill=C_LINE, outline='')
        self.r = c.create_rectangle(0, 0, 0, self.h, fill=C_ACC, outline='')
        self.last = None

    def set(self, frac, color=C_ACC):
        x = round(self.w * max(0, min(1, frac)))
        if (x, color) != self.last:
            self.last = (x, color)
            self.c.coords(self.r, 0, 0, x, self.h)
            self.c.itemconfig(self.r, fill=color)


NATIVE_GPU_OK = [False]


def start_sensor_apps():
    """Core Temp ve GPU-Z kuruluysa (ya da exe'nin yanındaysa) kapalıysa başlatır."""
    names = {(p.info['name'] or '').lower() for p in psutil.process_iter(['name'])}
    apps = [('core temp.exe', [r'C:\Program Files\Core Temp\Core Temp.exe', r'C:\Program Files (x86)\Core Temp\Core Temp.exe',
                               os.path.join(DIR, 'Core Temp.exe')], []),
            ('gpu-z.exe', [r'C:\Program Files (x86)\GPU-Z\GPU-Z.exe', r'C:\Program Files\GPU-Z\GPU-Z.exe'] +
             glob.glob(os.path.join(DIR, 'GPU-Z*.exe')), ['-minimized'])]
    if NATIVE_GPU_OK[0]:
        apps = apps[:1]  # ekran kartı sürücüden okunuyor, GPU-Z gerekmez
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE: pencere görünmez, arka planda ölçer
    for exe, paths, args in apps:
        if exe in names or any(n.startswith('gpu-z') for n in names) and exe == 'gpu-z.exe':
            continue
        for pth in paths:
            if os.path.exists(pth):
                try:
                    subprocess.Popen([pth] + args, cwd=os.path.dirname(pth), startupinfo=si)
                except OSError:
                    pass
                break


# ---------------- Uygulama ----------------
class App:
    BG, FG = C_BG, C_TXT
    RED, YEL, GRN = C_BAD, C_WARN, C_OK

    def __init__(self):
        self.pm = PresentMon(None)  # PresentMon arka planda hazırlanır (ilk açılışta indirme pencereyi bekletmesin)
        self.net = NetMon()
        self.gpdh = GpuPdh()
        self.procs = ProcMon()
        self.ngpu = NativeGpu()
        self.prev_game = None
        self.dio, self.dio_t = psutil.disk_io_counters(), time.time()
        self.events = []
        self.bench = None
        self.mini = None
        self.mx = {}
        self.tick_n = 0
        self.all_ft = array('f')  # oturumun tüm kare süreleri; float listesine göre 8 kat az bellek
        self.win = collections.deque(maxlen=10)
        self.secs = []
        self.stut = 0
        self.start = None
        self.game_pid = None
        self.scan_t = 0
        self.pending_update = False
        psutil.cpu_percent(percpu=True)
        self.csv = open(SEC_CSV, 'w', encoding='utf-8-sig', buffering=1)
        self.csv.write('Zaman,FPS,Low1,Takilma,CPU,MaxCekirdek,CPUSic,CPUMHz,GPUYuk,GPUSic,HotSpot,VRAMMB,RAMBosMB,GPUOrani,Darbogaz\n')

        r = self.root = tk.Tk()
        global S
        S = max(1.0, r.winfo_fpixels('1i') / 96)
        r.title('PUBG Canlı İzleyici')
        r.configure(bg=self.BG)
        r.attributes('-topmost', True)
        r.geometry(f'{px(1010)}x{px(820)}')
        r.minsize(px(980), px(780))
        style_window(r)

        bar = tk.Frame(r, bg=self.BG); bar.pack(fill='x', padx=12, pady=(10, 2))
        tk.Label(bar, text='PUBG  İZLEYİCİ', bg=self.BG, fg=C_ACC, font=(F_NUM, 13, 'bold')).pack(side='left', padx=(2, 2))
        tk.Label(bar, text=f'v{VERSION}', bg=self.BG, fg=C_SUB, font=(F_UI, 8, 'bold')).pack(side='left', padx=(0, 14), pady=(6, 0))
        # Güncelleme bandı (yeni sürüm varsa görünür)
        self.upd = tk.Frame(r, bg='#123247')
        self.upd_txt = tk.Label(self.upd, text='', bg='#123247', fg=C_TXT, font=(F_UI, 10, 'bold'), anchor='w', justify='left')
        self.upd_txt.pack(side='left', padx=12, pady=6, fill='x', expand=True)
        self.upd_btn = tk.Button(self.upd, text='Şimdi güncelle', command=self.apply_update, bg=C_ACC, fg='#0e1014', relief='flat',
                                 bd=0, font=(F_UI, 10, 'bold'), padx=14, pady=4, cursor='hand2')
        self.upd_new = None
        self.upd_info = None
        hud = tk.Frame(r, bg=C_CARD, highlightthickness=1, highlightbackground=C_LINE)
        hud.pack(side='bottom', fill='x', padx=12, pady=(0, 6))
        self.hud_fps = tk.Label(hud, text='— FPS', bg=C_CARD, fg=C_TXT, font=(F_NUM, 16, 'bold'), padx=12, pady=3)
        self.hud_fps.pack(side='left')
        self.hud_rest = tk.Label(hud, text='', bg=C_CARD, fg=C_SUB, font=(F_UI, 10, 'bold'), padx=4)
        self.hud_rest.pack(side='left')
        for txt, cmd in (('▣  Mini mod', self.toggle_mini), ('▶  PUBG\'yi başlat', self.launch_pubg), ('★  Yenilikler', self.show_changes)):
            hover(tk.Button(bar, text=txt, command=cmd, bg=C_CARD, fg=C_TXT, relief='flat', bd=0, font=(F_UI, 9, 'bold'),
                            padx=9, pady=5, cursor='hand2', activebackground=C_LINE)).pack(side='right', padx=(4, 0))
        self.tabs = {}
        self.f_live = tk.Frame(r, bg=self.BG)
        self.f_set = tk.Frame(r, bg=self.BG)
        self.f_info = tk.Frame(r, bg=self.BG)
        self.f_an = tk.Frame(r, bg=self.BG)
        self.f_acc = tk.Frame(r, bg=self.BG)

        def show(f):
            for x in (self.f_live, self.f_set, self.f_info, self.f_an, self.f_acc):
                x.pack_forget()
            f.pack(fill='both', expand=True)
            for fr, b in self.tabs.items():
                b.config(bg=C_ACC if fr is f else C_CARD, fg='#0e1014' if fr is f else C_TXT)
            if f is self.f_set and not self.set_done:
                self.run_check()
            if f is self.f_info and not self.info_done:
                self.run_info()
            if f is self.f_an:
                self.ev_dirty = True
                self.refresh_analysis()

        for t, f in (('Canlı', self.f_live), ('Analiz', self.f_an), ('Ayar Kontrolü', self.f_set),
                     ('Sistem Bilgisi', self.f_info), ('PUBG Hesap', self.f_acc)):
            b = hover(tk.Button(bar, text=t, command=lambda f=f: show(f), bg=C_CARD, fg=C_TXT, relief='flat', bd=0,
                                activebackground=C_ACC, font=(F_UI, 10, 'bold'), padx=11, pady=5, cursor='hand2'))
            b.pack(side='left', padx=(0, 4))
            self.tabs[f] = b
        self.set_done = False
        self.info_done = False

        def lbl(size, bold=False, color=None, h=1, parent=None):
            l = tk.Label(parent or self.f_live, text='', bg=self.BG, fg=color or self.FG, anchor='w', justify='left',
                         font=('Segoe UI', size, 'bold' if bold else 'normal'), wraplength=550, height=h)
            l.pack(fill='x', padx=12)
            return l

        # Ayar kontrolü sekmesi
        top = tk.Frame(self.f_set, bg=self.BG); top.pack(fill='x', padx=12, pady=(8, 0))
        tk.Label(top, text='Fare DPI:', bg=self.BG, fg=self.FG, font=('Segoe UI', 10)).pack(side='left')
        self.e_dpi = tk.Entry(top, width=7, bg=C_CARD, fg=C_TXT, insertbackground=C_TXT, relief='flat',
                              highlightthickness=1, highlightbackground=C_LINE, highlightcolor=C_ACC, font=(F_UI, 10))
        self.e_dpi.pack(side='left', padx=6, ipady=2)
        self.e_dpi.insert(0, str(load_cfg().get('dpi', '')))
        tk.Label(top, text='(farenin yazılımında yazar, örn. 800)', bg=self.BG, fg=C_SUB, font=(F_UI, 8)).pack(side='left')
        self.v_auto = tk.IntVar(value=1 if load_cfg().get('auto', True) else 0)
        tk.Checkbutton(top, text='PUBG kapanınca önerilen ayarları otomatik uygula', variable=self.v_auto, command=self.toggle_auto,
                       bg=self.BG, fg=C_TXT, selectcolor=C_CARD, activebackground=self.BG, activeforeground=C_TXT,
                       font=(F_UI, 9, 'bold')).pack(side='right')
        def btn(p, text, cmd, bg=C_CARD):
            return hover(tk.Button(p, text=text, command=cmd, bg=bg, fg=C_TXT, relief='flat', bd=0, font=(F_UI, 10, 'bold'),
                                   padx=14, pady=6, cursor='hand2', activebackground=C_LINE, activeforeground=C_TXT))

        def textbox(p):
            t = tk.Text(p, bg=C_CARD, fg=self.FG, font=(F_UI, 10), wrap='word', relief='flat', padx=12, pady=8,
                        highlightthickness=1, highlightbackground=C_LINE, highlightcolor=C_LINE)
            t.pack(fill='both', expand=True, padx=12, pady=(8, 4))
            for tag, col in (('ok', self.GRN), ('warn', self.YEL), ('bad', self.RED), ('info', C_ACC), ('dim', C_SUB),
                             ('h', C_TXT)):
                t.tag_config(tag, foreground=col)
            t.tag_config('h', font=(F_UI, 11, 'bold'))
            return t

        self.txt = textbox(self.f_set)
        bb = tk.Frame(self.f_set, bg=self.BG); bb.pack(fill='x', padx=12, pady=(0, 8))
        btn(bb, '⟳  Tekrar kontrol et', self.run_check).pack(side='left')
        btn(bb, '✔  Önerilenleri uygula (yedek alır)', self.run_apply, '#1f4d3a').pack(side='right')
        # Sistem bilgisi sekmesi
        self.itxt = textbox(self.f_info)
        ib = tk.Frame(self.f_info, bg=self.BG); ib.pack(fill='x', padx=12, pady=(0, 8))
        btn(ib, '⟳  Yenile', self.run_info).pack(side='left')
        btn(ib, '💾  Dosyaya kaydet', self.save_info).pack(side='right')
        self.build_live()
        self.build_analysis()
        self.build_account()
        show(self.f_live)
        threading.Thread(target=load_hw, daemon=True).start()
        threading.Thread(target=self.prepare_presentmon, daemon=True).start()
        NATIVE_GPU_OK[0] = bool(self.ngpu.kind)
        threading.Thread(target=self.update_loop, daemon=True).start()
        c = load_cfg()
        if c.get('last_ver') and c.get('last_ver') != VERSION:
            r.after(1500, lambda: self.show_changes(updated=True))
        if c.get('last_ver') != VERSION:
            c['last_ver'] = VERSION; save_cfg(c)
        threading.Thread(target=start_sensor_apps, daemon=True).start()
        r.protocol('WM_DELETE_WINDOW', self.close)
        r.after(1000, self.tick)
        r.after(250, self.fast_tick)
        r.mainloop()

    def prepare_presentmon(self):
        try:
            exe = get_presentmon()
        except Exception:
            exe = None
        self.pm.exe = exe
        if not exe:
            self.pm_missing = True

    def build_live(self):
        L = self.f_live
        for i in range(2):
            L.grid_columnconfigure(i, weight=1, uniform='c')
        T = lambda p, txt='', size=10, col=C_TXT, bold=False, font=F_UI: tk.Label(
            p, text=txt, bg=C_CARD, fg=col, font=(font, size, 'bold' if bold else 'normal'), anchor='w', justify='left')

        # FPS
        f = card(L, 'FPS'); f.grid(row=0, column=0, sticky='nsew', padx=(12, 6), pady=6)
        top = tk.Frame(f, bg=C_CARD); top.pack(fill='x', padx=12)
        self.v_fps = T(top, '—', 40, C_TXT, True, F_NUM); self.v_fps.pack(side='left')
        sub = tk.Frame(top, bg=C_CARD); sub.pack(side='left', padx=14)
        self.v_low = T(sub, '1% düşük  —', 10, C_SUB); self.v_low.pack(anchor='w')
        self.v_low01 = T(sub, '0.1% düşük  —', 10, C_SUB); self.v_low01.pack(anchor='w')
        self.v_ftm = T(sub, 'kare süresi  —', 10, C_SUB); self.v_ftm.pack(anchor='w')
        self.sp_fps = Spark(f, 410, 70, C_ACC); self.sp_fps.c.pack(padx=12, pady=(2, 10), fill='x')

        # Durum
        f = card(L, 'Durum'); f.grid(row=0, column=1, sticky='nsew', padx=(6, 12), pady=6)
        self.v_bound = T(f, 'Darboğaz: —', 14, C_TXT, True); self.v_bound.pack(anchor='w', padx=12, pady=(6, 2))
        self.v_stut = T(f, 'Takılma: 0', 11, C_TXT); self.v_stut.pack(anchor='w', padx=12)
        self.v_gpuratio = T(f, '', 10, C_SUB); self.v_gpuratio.pack(anchor='w', padx=12)
        self.v_sess = T(f, '', 10, C_SUB); self.v_sess.pack(anchor='w', padx=12, pady=(0, 4))
        self.sp_ft = Spark(f, 410, 50, C_WARN); self.sp_ft.c.pack(padx=12, pady=(0, 2), fill='x')
        T(f, 'en uzun kare süresi (ms) — sıçramalar takılmadır', 8, C_SUB).pack(anchor='w', padx=12, pady=(0, 8))

        # CPU
        f = card(L, 'İşlemci'); f.grid(row=1, column=0, sticky='nsew', padx=(12, 6), pady=6)
        self.v_cpuname = T(f, '', 9, C_SUB); self.v_cpuname.pack(anchor='w', padx=12)
        row = tk.Frame(f, bg=C_CARD); row.pack(fill='x', padx=8)
        self.g_cpu = Gauge(row, 130, 'SICAKLIK', '°C', 100, 85, 92); self.g_cpu.c.pack(side='left')
        self.g_cpul = Gauge(row, 100, 'YÜK', '%', 100, 85, 97); self.g_cpul.c.pack(side='left', padx=4)
        info = tk.Frame(row, bg=C_CARD); info.pack(side='left', padx=6, fill='y')
        self.v_mhz = T(info, '— MHz', 16, C_TXT, True, F_NUM); self.v_mhz.pack(anchor='w', pady=(14, 0))
        self.v_cmax = T(info, 'en dolu çekirdek —', 9, C_SUB); self.v_cmax.pack(anchor='w')
        self.v_ccnt = T(info, '', 9, C_SUB); self.v_ccnt.pack(anchor='w')
        self.core_box = tk.Frame(f, bg=C_CARD); self.core_box.pack(fill='x', padx=12, pady=(2, 10))
        self.core_w = []

        # GPU
        f = card(L, 'Ekran kartı'); f.grid(row=1, column=1, sticky='nsew', padx=(6, 12), pady=6)
        self.v_gpuname = T(f, '', 9, C_SUB); self.v_gpuname.pack(anchor='w', padx=12)
        row = tk.Frame(f, bg=C_CARD); row.pack(fill='x', padx=8)
        self.g_gpu = Gauge(row, 130, 'SICAKLIK', '°C', 100, 80, 87); self.g_gpu.c.pack(side='left')
        self.g_hs = Gauge(row, 100, 'HOT SPOT', '°C', 115, 95, 105); self.g_hs.c.pack(side='left', padx=4)
        self.g_gl = Gauge(row, 100, 'YÜK', '%', 100, 101, 101); self.g_gl.c.pack(side='left')
        self.v_gpw = T(f, '', 10, C_TXT); self.v_gpw.pack(anchor='w', padx=12)
        self.v_vram = T(f, 'VRAM —', 9, C_SUB); self.v_vram.pack(anchor='w', padx=12)
        self.b_vram = Bar(f, 400); self.b_vram.c.pack(anchor='w', padx=12, pady=(2, 10))

        # RAM
        f = card(L, 'Bellek'); f.grid(row=2, column=0, sticky='nsew', padx=(12, 6), pady=6)
        self.v_ram = T(f, '—', 16, C_TXT, True, F_NUM); self.v_ram.pack(anchor='w', padx=12)
        self.b_ram = Bar(f, 400); self.b_ram.c.pack(anchor='w', padx=12, pady=(2, 4))
        self.v_ram2 = T(f, '', 9, C_SUB); self.v_ram2.pack(anchor='w', padx=12, pady=(0, 2))
        self.v_disk = T(f, 'Disk  —', 10, C_TXT); self.v_disk.pack(anchor='w', padx=12, pady=(0, 10))

        # Ağ
        f = card(L, 'Ağ (1.1.1.1)'); f.grid(row=2, column=1, sticky='nsew', padx=(6, 12), pady=6)
        row = tk.Frame(f, bg=C_CARD); row.pack(fill='x', padx=12)
        self.v_ping = T(row, '— ms', 22, C_TXT, True, F_NUM); self.v_ping.pack(side='left')
        self.v_net = T(row, '', 9, C_SUB); self.v_net.pack(side='left', padx=12)
        self.sp_ping = Spark(f, 410, 40, C_OK, n=60); self.sp_ping.c.pack(padx=12, pady=(2, 10), fill='x')

        # Sorun bandı
        self.ban = tk.Frame(L, bg=C_CARD, highlightthickness=1, highlightbackground=C_LINE)
        self.ban.grid(row=3, column=0, columnspan=2, sticky='nsew', padx=12, pady=6)
        self.ban_strip = tk.Frame(self.ban, bg=C_OK, width=6); self.ban_strip.pack(side='left', fill='y')
        self.ban_txt = tk.Label(self.ban, text='Ölçüm başlıyor...', bg=C_CARD, fg=C_TXT, font=(F_UI, 11, 'bold'),
                                anchor='w', justify='left', wraplength=px(820))
        self.ban_txt.pack(side='left', fill='both', expand=True, padx=12, pady=10)

        bot = tk.Frame(L, bg=C_BG); bot.grid(row=4, column=0, columnspan=2, sticky='ew', padx=12, pady=(0, 8))
        self.l_state = tk.Label(bot, text='', bg=C_BG, fg=C_SUB, font=(F_UI, 8), anchor='w')
        self.l_state.pack(side='left')
        tk.Button(bot, text='Raporu aç', command=self.open_report, bg=C_CARD, fg=C_TXT, relief='flat', bd=0,
                  font=(F_UI, 9, 'bold'), padx=12, pady=3, cursor='hand2').pack(side='right')

    def render(self, v):
        n = v['net']
        # FPS
        if v['ft']:
            setl(self.v_fps, text=f"{v['fps']:.0f}", fg=C_TXT)
            setl(self.v_low, text=f"1% düşük   {v['low1']:.0f}")
            setl(self.v_low01, text=f"0.1% düşük   {v['low01']:.0f}")
            setl(self.v_ftm, text=f"kare süresi   {v['ftavg']:.1f} ms")
            self.sp_fps.push(v['fps'])
            self.sp_ft.push(v['ftmax'])
        else:
            setl(self.v_fps, text='—', fg=C_SUB)
            setl(self.v_low, text='oyuna geç' if v['game'] else 'PUBG kapalı')
            setl(self.v_low01, text=''); setl(self.v_ftm, text='')
        bmap = {'GPU': ('Ekran kartı', C_ACC), 'CPU': ('İşlemci / oyun motoru', C_WARN), 'Limit': ('Yok, FPS limitinde', C_OK),
                'Karışık': ('Karışık', C_TXT)}
        bt, bc = bmap.get(v['bound'], ('—', C_SUB))
        setl(self.v_bound, text=f'Darboğaz: {bt}', fg=bc)
        setl(self.v_stut, text=f"Takılma: son 10 sn {v['st10']}   ·   toplam {self.stut}",
                           fg=C_BAD if v['st10'] >= 3 else (C_WARN if v['st10'] else C_TXT))
        setl(self.v_gpuratio, text=f"Ekran kartının meşgul olduğu süre: %{v['ratio'] * 100:.0f}" if v['ratio'] is not None else '')
        # CPU
        c = HW.get('cpu') or {}
        if c and not self.v_cpuname.cget('text'):
            setl(self.v_cpuname, text=c.get('name', ''))
        self.g_cpu.warn, self.g_cpu.bad = LIM['hot'] - 7, LIM['hot']
        self.g_cpu.set(v['cpu_t'] or None, '' if v['cpu_t'] else 'sensör başlıyor')
        self.g_cpul.set(v['cpu_tot'] or 0.1)
        setl(self.v_mhz, text=f"{v['cpu_mhz']} MHz" if v['cpu_mhz'] else '— MHz')
        setl(self.v_cmax, text=f"en dolu çekirdek  %{v['core_max']}")
        per, temps = v['per'], v['cores']
        nphys = len(temps) or (c.get('cores') or 0) or len(per)
        setl(self.v_ccnt, text=f"{nphys} çekirdek · {len(per)} iş parçacığı")
        self.draw_cores(per, temps)
        # GPU
        g = HW.get('gpus') or []
        if g and not self.v_gpuname.cget('text'):
            gg = max(g, key=lambda x: x['vram'])
            setl(self.v_gpuname, text=f"{gg['name']}   ·   {gg['vram'] / 1024:.0f} GB   ·   sürücü {gg['driver']}")
        self.g_gpu.set(v['g_t'] or None, '' if v['gz'] else 'sensör yok')
        self.g_hs.set(v['hs'] or None)
        self.g_gl.set(v['g_load'] or 0.1)
        d = v.get('gdet') or {}
        parts = []
        if d.get('Clk'):
            parts.append(f"çekirdek {d['Clk']} MHz")
        if d.get('MClk'):
            parts.append(f"bellek {d['MClk']} MHz")
        if v['pwr']:
            parts.append(f"{v['pwr']} W")
        line2 = []
        if d.get('Fan') or d.get('RPM'):
            line2.append(f"fan %{d.get('Fan', 0)}" + (f" ({d['RPM']} RPM)" if d.get('RPM') else ''))
        if d.get('MemT'):
            line2.append(f"VRAM sıcaklığı {d['MemT']}°C")
        setl(self.v_gpw, text='  ·  '.join(parts) + ('\n' + '  ·  '.join(line2) if line2 else ''),
                          fg=C_BAD if d.get('MemT', 0) >= 95 else C_TXT)
        vt = max([x['vram'] for x in g] or [0])
        setl(self.v_vram, text=f"VRAM  {v['vram'] / 1024:.1f} / {vt / 1024:.0f} GB" if vt else f"VRAM  {v['vram'] / 1024:.1f} GB")
        self.b_vram.set(v['vram'] / vt if vt else 0, lvl_color(v['vram'] / vt * 100 if vt else 0, 85, 94))
        # RAM
        vm = psutil.virtual_memory()
        setl(self.v_ram, text=f"%{vm.percent:.0f}  ·  {vm.used / 1024 ** 3:.1f} / {vm.total / 1024 ** 3:.0f} GB")
        self.b_ram.set(vm.percent / 100, lvl_color(vm.percent, 80, 92))
        setl(self.v_ram2, text=f"boş {vm.available / 1024 ** 3:.1f} GB")
        setl(self.v_disk, text=f"Disk   okuma {v['dr']:.0f} MB/s   ·   yazma {v['dw']:.0f} MB/s",
                           fg=C_WARN if v['dr'] >= 150 else C_TXT)
        ping0 = f"{n['ping']} ms" if n.get('ping') is not None else '— ms'
        fcol = C_BAD if v['st10'] >= 3 else (C_WARN if v['ft'] and v['fps'] < LIM['cap'] * 0.6 else C_OK)
        setl(self.hud_fps, text=(f"{v['fps']:.0f} FPS" if v['ft'] else '— FPS'), fg=fcol if v['ft'] else C_SUB)
        setl(self.hud_rest, text=(f"1% {v['low1']:.0f}   ·   " if v['ft'] else ('PUBG kapalı   ·   ' if not v['game'] else 'oyuna geç   ·   ')) +
                             f"CPU {v['cpu_t'] or '—'}°C  %{v['cpu_tot']}   ·   GPU {v['g_t'] or '—'}°C  %{v['g_load']}   ·   "
                             f"VRAM {v['vram'] / 1024:.1f} GB   ·   ping {ping0}   ·   takılma {v['st10']}/10sn",
                             fg=C_BAD if v['cpu_t'] >= LIM['hot'] or v['hs'] >= 100 else C_SUB)
        if self.mini:
            ping = f"{n['ping']} ms" if n.get('ping') is not None else '— ms'
            setl(self.mini_l, text=(f"{v['fps']:.0f} FPS" if v['ft'] else '— FPS') +
                               f"   1% {v['low1']:.0f}   ·   CPU {v['cpu_t'] or '—'}°   ·   GPU {v['g_t'] or '—'}° / {v['hs'] or '—'}°   ·   {ping}",
                               fg=C_BAD if v['st10'] >= 3 or v['cpu_t'] >= LIM['hot'] else C_TXT)
        # Ağ
        if n['n']:
            pc = C_BAD if n['loss'] >= 10 or n['jit'] >= 20 else (C_WARN if n['loss'] or n['jit'] >= 8 else C_OK)
            setl(self.v_ping, text=f"{n['ping']} ms" if n['ping'] is not None else 'yanıt yok', fg=pc)
            setl(self.v_net, text=f"ort {n['avg']} · en fazla {n['max']} ms\ndalgalanma {n['jit']} ms · kayıp %{n['loss']}\n"
                                   f"↓ {n['down']:.1f}   ↑ {n['up']:.1f} Mbit/s")
            self.sp_ping.push(n['ping'])

    def draw_cores(self, per, temps):
        nphys = len(temps) if temps else len(per)
        if not nphys or not self.core_box.winfo_viewable():
            return
        tpc = max(1, len(per) // nphys) if temps else 1
        cols = 8 if nphys >= 8 else nphys
        W, H = px(48), px(46)
        if len(self.core_w) != nphys:
            for w in self.core_box.winfo_children():
                w.destroy()
            self.core_w = []
            for i in range(nphys):
                cv = tk.Canvas(self.core_box, width=W, height=H, bg='#1f232c', highlightthickness=0)
                cv.grid(row=i // cols, column=i % cols, padx=2, pady=2)
                bar = cv.create_rectangle(0, H, W, H, fill='#24425a', outline='')
                cv.create_text(W / 2, px(9), text=f'Ç{i}', fill=C_SUB, font=(F_UI, 7, 'bold'))
                tt = cv.create_text(W / 2, px(24), text='', fill=C_OK, font=(F_NUM, 12, 'bold'))
                lt = cv.create_text(W / 2, px(38), text='', fill=C_TXT, font=(F_UI, 7))
                self.core_w.append((cv, bar, tt, lt, [None]))
        for i, (cv, bar, tt, lt, last) in enumerate(self.core_w):
            sl = per[i * tpc:(i + 1) * tpc]
            load = round(sum(sl) / len(sl)) if sl else 0
            t = temps[i] if i < len(temps) else None
            col = lvl_color(t, LIM['hot'] - 7, LIM['hot']) if t is not None else C_OK
            if last[0] == (load, t, col):
                continue
            last[0] = (load, t, col)
            cv.coords(bar, 0, H - H * min(1, load / 100), W, H)
            cv.itemconfig(tt, text=f'{t}°' if t is not None else '', fill=col)
            cv.itemconfig(lt, text=f'%{load}')

    # ---------------- Analiz sekmesi ----------------
    # ---------------- Güncelleme ----------------
    def update_loop(self):
        while True:
            try:
                info = check_update()
                if info and (not self.upd_info or info['ver'] != self.upd_info['ver']):
                    self.upd_info = info
                    self.root.after(0, lambda: self.show_upd(f"⬇  Yeni sürüm v{info['ver']} indiriliyor..."))
                    path = download_update(info, lambda f: self.root.after(0, lambda: self.show_upd(
                        f"⬇  Yeni sürüm v{info['ver']} indiriliyor... %{f * 100:.0f}")))
                    self.upd_new = path
                    self.root.after(0, self.update_ready)
            except Exception:
                pass
            time.sleep(3600)  # açılışta ve saatte bir kontrol

    def show_upd(self, text, button=False):
        if not self.upd.winfo_ismapped():
            self.upd.pack(fill='x', padx=12, pady=(4, 0), after=self.root.winfo_children()[0])
        setl(self.upd_txt, text=text)
        if button and not self.upd_btn.winfo_ismapped():
            self.upd_btn.pack(side='right', padx=10)

    def update_ready(self):
        notes = (self.upd_info.get('notes') or '').strip().splitlines()
        short = ' · '.join(x.strip('-*• ').strip() for x in notes if x.strip())[:220]
        self.show_upd(f"★  Yeni sürüm v{self.upd_info['ver']} hazır.  {short}", button=True)
        if not getattr(sys, 'frozen', False):
            return
        if not self.game_running():
            self.root.after(4000, self.apply_update)  # oyun kapalı: kendiliğinden güncellenir

    def apply_update(self):
        if not self.upd_new or not getattr(sys, 'frozen', False):
            return
        if self.game_running():
            self.show_upd('★  Güncelleme hazır. PUBG kapanınca otomatik kurulacak.', button=True)
            self.pending_update = True
            return
        self.show_upd(f"⟳  v{self.upd_info['ver']} kuruluyor, program yeniden açılacak...")
        try:
            install_update(self.upd_new)
        except Exception as e:
            self.show_upd(f'✖  Güncelleme kurulamadı: {e}. Programı yönetici olarak açıp tekrar dene.', button=True)
            return
        self.root.after(800, lambda: self.close(report=False))

    def show_changes(self, updated=False):
        w = tk.Toplevel(self.root)
        w.title('Yenilikler'); w.configure(bg=C_BG); w.attributes('-topmost', True); w.geometry('620x460')
        tk.Label(w, text=(f'✔  v{VERSION} sürümüne güncellendi' if updated else f'PUBG İzleyici v{VERSION}'), bg=C_BG, fg=C_OK if updated else C_ACC,
                 font=(F_NUM, 15, 'bold')).pack(anchor='w', padx=16, pady=(14, 6))
        t = tk.Text(w, bg=C_CARD, fg=C_TXT, font=(F_UI, 10), relief='flat', wrap='word', padx=12, pady=10)
        t.pack(fill='both', expand=True, padx=16, pady=(0, 10))
        t.tag_config('h', foreground=C_ACC, font=(F_UI, 11, 'bold'))
        for ver, items in CHANGES:
            t.insert('end', f'v{ver}\n', 'h')
            for it in items:
                t.insert('end', f'  •  {it}\n')
            t.insert('end', '\n')
        t.config(state='disabled')
        tk.Button(w, text='Tamam', command=w.destroy, bg=C_ACC, fg='#0e1014', relief='flat', bd=0, font=(F_UI, 10, 'bold'),
                  padx=18, pady=4).pack(pady=(0, 12))

    def bg(self, work, done=None):
        """work() arka planda çalışır, sonucu done(sonuç) ile arayüz iş parçacığında işlenir. Pencere donmaz."""
        def run():
            try:
                res, err = work(), None
            except Exception as e:
                res, err = None, e
            if done:
                self.root.after(0, lambda: done(res, err))
        threading.Thread(target=run, daemon=True).start()

    def auto_apply(self):
        if not load_cfg().get('auto', True) or self.game_running():
            return

        def work():
            if not HW:
                load_hw()
            return apply_recommended()

        def done(msgs, err):
            if err:
                setl(self.l_state, text=f'Otomatik ayar hatası: {err}'); return
            changed = [m for m in msgs if not m.startswith(('Değiştirilecek', 'Elle', 'PUBG yedeği'))]
            self.set_done = False
            if changed:
                self.last_auto = msgs
                self.auto_msg = '⚙  Ayarlar otomatik uygulandı:  ' + ' · '.join(changed[:6]) + (' …' if len(changed) > 6 else '')
                self.auto_until = time.time() + 15
        self.bg(work, done)

    def toggle_auto(self):
        c = load_cfg(); c['auto'] = bool(self.v_auto.get()); save_cfg(c)

    def build_analysis(self):
        A = self.f_an
        top = tk.Frame(A, bg=C_BG); top.pack(fill='x', padx=12, pady=(8, 4))
        mk = lambda t, c, bg=C_CARD: tk.Button(top, text=t, command=c, bg=bg, fg=C_TXT, relief='flat', bd=0,
                                              font=(F_UI, 10, 'bold'), padx=14, pady=6, cursor='hand2')
        mk('▶  60 sn performans testi', self.start_bench, '#1f4d6b').pack(side='left')
        mk('⚡  PUBG önceliği: Yüksek', self.boost).pack(side='left', padx=6)
        self.an_state = tk.Label(top, text='Ayar değiştirmeden önce ve sonra test yap, fark aşağıda yüzde olarak çıkar.',
                                 bg=C_BG, fg=C_SUB, font=(F_UI, 9))
        self.an_state.pack(side='left', padx=8)
        mid = tk.Frame(A, bg=C_BG); mid.pack(fill='both', expand=True, padx=12)
        mid.grid_columnconfigure(0, weight=3); mid.grid_columnconfigure(1, weight=2); mid.grid_rowconfigure(0, weight=1)

        def textcard(parent, title, r, c, cs=1):
            f = card(parent, title); f.grid(row=r, column=c, columnspan=cs, sticky='nsew', padx=4, pady=4)
            t = tk.Text(f, bg=C_CARD, fg=C_TXT, font=('Consolas', 9), relief='flat', wrap='none', height=10, padx=10, pady=6)
            t.pack(fill='both', expand=True)
            for tag, col in (('ok', C_OK), ('warn', C_WARN), ('bad', C_BAD), ('dim', C_SUB), ('acc', C_ACC)):
                t.tag_config(tag, foreground=col)
            t.config(state='disabled')
            return t

        self.t_ev = textcard(mid, 'Takılma kaydı (her takılma anı ve sebebi)', 0, 0)
        self.t_proc = textcard(mid, 'En çok kaynak kullanan programlar', 0, 1)
        bot = tk.Frame(A, bg=C_BG); bot.pack(fill='both', expand=True, padx=12, pady=(0, 10))
        bot.grid_columnconfigure(0, weight=1); bot.grid_rowconfigure(0, weight=1)
        self.t_hist = textcard(bot, 'Performans testi geçmişi', 0, 0)
        self.ev_dirty = True
        self.draw_hist()

    def _fill(self, t, rows):
        t.config(state='normal'); t.delete('1.0', 'end')
        for txt, tag in rows:
            t.insert('end', txt, tag) if tag else t.insert('end', txt)
        t.config(state='disabled')

    def refresh_analysis(self):
        if not self.f_an.winfo_ismapped():  # sekme kapalıyken metin kutularını boşuna doldurma
            return
        rows = [(f"{'Program':<26}{'İşlemci':>9}{'RAM':>10}\n", 'dim')]
        for c, nm, m in self.procs.get():
            rows.append((f"{nm[:25]:<26}{c:>8.1f}%{m:>8.0f} MB\n", 'bad' if c >= 15 else ('warn' if c >= 5 else None)))
        self._fill(self.t_proc, rows)
        if self.ev_dirty:
            self.ev_dirty = False
            rows = [(f"{'Saat':<10}{'Adet':>5}{'Süre':>8}{'CPU°':>6}{'Disk':>8}{'Ping':>6}   Sebep\n", 'dim')]
            for e in reversed(self.events[-120:]):
                tag = 'bad' if 'ısınma' in e['why'] else ('warn' if 'disk' in e['why'] or 'arka plan' in e['why'] else None)
                rows.append((f"{e['t']:<10}{e['n']:>5}{e['max']:>6.0f}ms{e['cpu_t'] or '-':>6}{e['dr']:>6.0f}MB"
                             f"{(e['ping'] if e['ping'] is not None else '-'):>6}   {e['why']}\n", tag))
                if e['top']:
                    rows.append((f"{'':<10}   o an: {e['top']}\n", 'dim'))
            if len(rows) == 1:
                rows.append(('Henüz takılma yok.\n', 'ok'))
            else:
                causes = collections.Counter(e['why'].split(' (')[0].split(':')[0] for e in self.events)
                rows.insert(1, ('Özet: ' + ', '.join(f'{k} ×{v}' for k, v in causes.most_common(4)) + '\n\n', 'acc'))
            self._fill(self.t_ev, rows)

    def start_bench(self):
        if not self.game_running():
            setl(self.an_state, text='Önce PUBG\'yi aç ve bir maça ya da Eğitim Modu\'na gir.', fg=C_BAD); return
        self.bench = {'start': time.time(), 'dur': 60, 'ft': [], 'st': 0, 'mx': {}}
        setl(self.an_state, text='Test başladı: 60 sn normal oyna (koş, etrafa bak, ateş et).', fg=C_WARN)

    def finish_bench(self):
        b, self.bench = self.bench, None
        a = b['ft']
        if len(a) < 300:
            setl(self.an_state, text='Yeterli kare yok, oyun ekranında test yap.', fg=C_BAD); return
        res = {'date': datetime.datetime.now().strftime('%d.%m %H:%M'), 'type': 'Test',
               'fps': len(a) / (sum(a) / 1000), 'low1': 1000 / pct(a, 0.99), 'low01': 1000 / pct(a, 0.999),
               'st': b['st'], 'cpu': b['mx'].get('cpu_t', 0), 'gpu': b['mx'].get('g_t', 0), 'hs': b['mx'].get('hs', 0),
               'gfx': gfx_snapshot()}
        h = load_hist()
        prev = next((x for x in reversed(h) if x.get('type') == 'Test'), None)
        h.append(res); save_hist(h)
        msg = f"Test bitti: ort {res['fps']:.0f} FPS, 1% {res['low1']:.0f}, takılma {res['st']}."
        if prev:
            d = (res['fps'] - prev['fps']) / prev['fps'] * 100
            d1 = (res['low1'] - prev['low1']) / prev['low1'] * 100 if prev['low1'] else 0
            msg += f"  Öncekine göre: FPS {d:+.0f}%, 1% düşük {d1:+.0f}%."
        setl(self.an_state, text=msg, fg=C_OK)
        self.draw_hist()

    def draw_hist(self):
        h = load_hist()
        rows = [(f"{'Tarih':<13}{'Tür':<8}{'Ort FPS':>8}{'1%':>6}{'0.1%':>6}{'Tak.':>6}{'CPU°':>6}{'GPU°':>6}   Grafik ayarları\n", 'dim')]
        best = max((x['fps'] for x in h if x.get('type') == 'Test'), default=0)
        for x in reversed(h[-40:]):
            tag = 'ok' if x.get('type') == 'Test' and x['fps'] == best else None
            rows.append((f"{x['date']:<13}{x.get('type', ''):<8}{x['fps']:>8.0f}{x['low1']:>6.0f}{x['low01']:>6.0f}{x['st']:>6}"
                         f"{x.get('cpu') or '-':>6}{x.get('gpu') or '-':>6}   {x.get('gfx', '')}\n", tag))
        if len(rows) == 1:
            rows.append(('Henüz test yok. PUBG açıkken "60 sn performans testi"ne bas.\n', 'dim'))
        else:
            rows.append(('\nYeşil satır: en yüksek FPS veren test. ÇD=Çok Düşük D=Düşük O=Orta Y=Yüksek U=Ultra\n', 'dim'))
        self._fill(self.t_hist, rows)

    def boost(self):
        if not self.game_running():
            setl(self.an_state, text='PUBG açık değil.', fg=C_BAD); return
        try:
            psutil.Process(self.game_pid).nice(psutil.HIGH_PRIORITY_CLASS)
            setl(self.an_state, text='PUBG önceliği Yüksek yapıldı (oyun kapanınca sıfırlanır).', fg=C_OK)
        except Exception as e:
            setl(self.an_state, text=f'Öncelik değiştirilemedi: {e}', fg=C_BAD)

    def launch_pubg(self):
        if self.game_running():
            return
        try:
            os.startfile('steam://rungameid/578080')
        except OSError:
            pass

    def toggle_mini(self):
        if self.mini:
            self.mini.destroy(); self.mini = None; self.root.deiconify(); return
        m = self.mini = tk.Toplevel(self.root)
        m.overrideredirect(True); m.attributes('-topmost', True); m.attributes('-alpha', 0.88); m.configure(bg=C_BG)
        self.mini_l = tk.Label(m, text='...', bg=C_BG, fg=C_TXT, font=(F_NUM, 12, 'bold'), padx=14, pady=7)
        self.mini_l.pack()
        tk.Label(m, text='çift tık: büyük pencere · sürükle: taşı', bg=C_BG, fg=C_SUB, font=(F_UI, 7)).pack(pady=(0, 3))
        pos = load_cfg().get('mini', '+30+30')
        m.geometry(pos)

        def down(e):
            m._ox, m._oy = e.x_root - m.winfo_x(), e.y_root - m.winfo_y()

        def move(e):
            m.geometry(f'+{e.x_root - m._ox}+{e.y_root - m._oy}')

        def up(e):
            c = load_cfg(); c['mini'] = f'+{m.winfo_x()}+{m.winfo_y()}'; save_cfg(c)

        for w in (m, self.mini_l):
            w.bind('<ButtonPress-1>', down); w.bind('<B1-Motion>', move); w.bind('<ButtonRelease-1>', up)
            w.bind('<Double-Button-1>', lambda e: self.toggle_mini())
        self.root.withdraw()

    # ---------------- PUBG hesap sekmesi ----------------
    def build_account(self):
        A = self.f_acc
        f = card(A, 'PUBG hesap istatistikleri (resmi PUBG API)'); f.pack(fill='x', padx=12, pady=(8, 4))
        row = tk.Frame(f, bg=C_CARD); row.pack(fill='x', padx=12, pady=8)
        cfg = load_cfg()
        tk.Label(row, text='API anahtarı:', bg=C_CARD, fg=C_TXT, font=(F_UI, 10)).grid(row=0, column=0, sticky='w')
        self.e_key = tk.Entry(row, width=52, show='•', bg='#11141a', fg='white', insertbackground='white', relief='flat',
                              font=(F_UI, 10))
        self.e_key.grid(row=0, column=1, padx=6, sticky='w'); self.e_key.insert(0, cfg.get('api', ''))
        tk.Label(row, text='Oyuncu adı:', bg=C_CARD, fg=C_TXT, font=(F_UI, 10)).grid(row=1, column=0, sticky='w', pady=(6, 0))
        self.e_name = tk.Entry(row, width=30, bg='#11141a', fg='white', insertbackground='white', relief='flat', font=(F_UI, 10))
        self.e_name.grid(row=1, column=1, padx=6, sticky='w', pady=(6, 0)); self.e_name.insert(0, cfg.get('name', ''))
        tk.Label(row, text='(boş bırakırsan bu bilgisayardaki PUBG hesabı kullanılır)', bg=C_CARD, fg=C_SUB,
                 font=(F_UI, 8)).grid(row=2, column=1, sticky='w', padx=6)
        tk.Button(row, text='Bilgileri getir', command=self.get_account, bg='#1f4d6b', fg=C_TXT, relief='flat', bd=0,
                  font=(F_UI, 10, 'bold'), padx=14, pady=5, cursor='hand2').grid(row=0, column=2, rowspan=2, padx=10)
        lk = tk.Label(f, text='Ücretsiz API anahtarı almak için: developer.pubg.com → Sign in (Steam) → Create App → API key  (tıkla)',
                      bg=C_CARD, fg=C_ACC, font=(F_UI, 9, 'underline'), cursor='hand2')
        lk.pack(anchor='w', padx=12, pady=(0, 8))
        lk.bind('<Button-1>', lambda e: os.startfile('https://developer.pubg.com/'))
        self.t_acc = tk.Text(A, bg=C_CARD, fg=C_TXT, font=('Consolas', 10), relief='flat', wrap='none', padx=12, pady=8)
        self.t_acc.pack(fill='both', expand=True, padx=12, pady=(0, 10))
        for tag, col in (('ok', C_OK), ('warn', C_WARN), ('bad', C_BAD), ('dim', C_SUB), ('acc', C_ACC)):
            self.t_acc.tag_config(tag, foreground=col)
        self.t_acc.tag_config('h', foreground='white', font=(F_UI, 12, 'bold'))
        self._fill(self.t_acc, [('API anahtarını yapıştır ve "Bilgileri getir"e bas.\n', 'dim')])

    def get_account(self):
        key, name = self.e_key.get().strip(), self.e_name.get().strip()
        if not key:
            self._fill(self.t_acc, [('Önce API anahtarını yapıştır.\n', 'bad')]); return
        c = load_cfg(); c['api'] = key; c['name'] = name; save_cfg(c)
        self._fill(self.t_acc, [('Bilgiler alınıyor...\n', 'dim')])

        def work():
            try:
                res = fetch_account(key, name)
                self.root.after(0, lambda: self.show_account(res))
            except urllib.error.HTTPError as e:
                msg = {401: 'API anahtarı geçersiz.', 404: 'Oyuncu bulunamadı (adı büyük-küçük harf dahil tam yaz).',
                       429: 'Çok sık istek: 1 dakika bekleyip tekrar dene.'}.get(e.code, f'PUBG API hatası: {e.code}')
                self.root.after(0, lambda: self._fill(self.t_acc, [(msg + '\n', 'bad')]))
            except Exception as e:
                err = f'Hata: {e}\n'  # 'e' except bloğundan sonra silinir; lambda'ya metni ver
                self.root.after(0, lambda: self._fill(self.t_acc, [(err, 'bad')]))
        threading.Thread(target=work, daemon=True).start()

    def show_account(self, r):
        rows = [(f"{r['name']}\n", 'h'), (f"hesap: {r['id']}   ·   sezon: {r['season']}\n\n", 'dim')]

        def table(title, gms):
            rows.append((title + '\n', 'acc'))
            rows.append((f"{'Mod':<11}{'Maç':>6}{'Kazanma':>9}{'Top10':>8}{'K/D':>7}{'Ort hasar':>11}{'Kafa%':>7}{'En uzun':>9}\n", 'dim'))
            any_ = False
            for k, lab in MODES:
                g = gms.get(k) or {}
                rp = g.get('roundsPlayed', 0)
                if not rp:
                    continue
                any_ = True
                w, kl = g.get('wins', 0), g.get('kills', 0)
                kd = kl / max(1, g.get('losses', rp - w))
                rows.append((f"{lab:<11}{rp:>6}{w / rp * 100:>8.1f}%{g.get('top10s', 0) / rp * 100:>7.1f}%{kd:>7.2f}"
                             f"{g.get('damageDealt', 0) / rp:>11.0f}{(g.get('headshotKills', 0) / kl * 100 if kl else 0):>6.0f}%"
                             f"{g.get('longestKill', 0):>8.0f}m\n", 'ok' if kd >= 2 else None))
            if not any_:
                rows.append(('  (bu dönemde maç yok)\n', 'dim'))
            rows.append(('\n', None))

        if r['ranked']:
            rows.append(('Dereceli (bu sezon)\n', 'acc'))
            for k, g in r['ranked'].items():
                if not g.get('roundsPlayed'):
                    continue
                t = g.get('currentTier') or {}
                rows.append((f"{k:<11} {t.get('tier', '?')} {t.get('subTier', '')}  ·  {g.get('currentRankPoint', 0)} RP  ·  "
                             f"{g.get('roundsPlayed')} maç  ·  KDA {g.get('kda', 0):.2f}  ·  kazanma %{g.get('winRatio', 0) * 100:.1f}  ·  "
                             f"top10 %{g.get('top10Ratio', 0) * 100:.0f}  ·  ort hasar {g.get('damageDealt', 0) / max(1, g.get('roundsPlayed', 1)):.0f}\n", None))
            rows.append(('\n', None))
        table('Bu sezon (normal maçlar)', r['seas'])
        table('Tüm zamanlar', r['life'])
        rows.append(('Son maçlar\n', 'acc'))
        rows.append((f"{'Tarih (UTC)':<18}{'Harita':<12}{'Mod':<12}{'Sıra':>5}{'Öldürme':>9}{'Hasar':>7}{'Kafa':>6}{'Süre':>8}\n", 'dim'))
        for m in r['matches']:
            pl = m['place'] or 0
            rows.append((f"{m['date']:<18}{str(m['map'])[:11]:<12}{str(m['mode'])[:11]:<12}{pl:>5}{m['kills']:>9}{m['dmg']:>7.0f}"
                         f"{m['hs']:>6}{int(m['time'] // 60):>5} dk\n", 'ok' if pl == 1 else ('warn' if pl and pl <= 10 else None)))
        if not r['matches']:
            rows.append(('  (son 14 günde maç yok)\n', 'dim'))
        self._fill(self.t_acc, rows)

    def run_info(self, then=None):
        if getattr(self, 'info_busy', False):
            return
        self.info_busy = True
        self._fill(self.itxt, [('Donanım okunuyor (birkaç saniye)...\n', 'dim')])

        def done(lines, err):
            self.info_busy = False
            if err:
                self._fill(self.itxt, [(f'Hata: {err}\n', 'bad')]); return
            self._fill(self.itxt, lines)
            self.info_lines = lines
            self.info_done = True
            if then:
                then()
        self.bg(self.info_lines_build, done)

    def info_lines_build(self):
        h = load_hw(force=self.info_done)  # ilk açılışta hazır bilgi, "Yenile"de baştan okunur
        lines = []  # (metin, etiket)

        def H(x): lines.append((f'\n{x}\n', 'h'))

        def L(x, tag=None): lines.append((x + '\n', tag))

        c = h.get('cpu') or {}
        H('İŞLEMCİ')
        L(f"{c.get('name', '?')}")
        L(f"{c.get('cores', '?')} çekirdek / {c.get('threads', '?')} iş parçacığı, temel hız {c.get('mhz', '?')} MHz", 'dim')
        cs = cpu_sensor()
        if cs:
            L(f"Şu an: {cs['T']}°C, {cs['MHz']} MHz (sıcaklık sınırı {cs['TJ']}°C)", 'dim')
        H('EKRAN KARTI')
        for g in h.get('gpus') or []:
            L(f"{g['name']}  —  {g['vram'] / 1024:.0f} GB VRAM" if g['vram'] else g['name'])
            L(f"Sürücü {g['driver']}  {g['date']}", 'dim')
        gs = gpu_sensor()
        if gs:
            L(f"Şu an: {gs['T']}°C, hot spot {gs['HS']}°C, yük %{gs['Load']}, {gs['Pwr']} W", 'dim')
        H('RAM')
        rams = h.get('ram') or []
        ddr = {34: 'DDR5', 26: 'DDR4', 24: 'DDR3'}.get(rams[0].get('type') if rams else 0, '')
        L(f"Toplam {h.get('ram_gb', '?')} GB {ddr}, {len(rams)} modül")
        for m in rams:
            L(f"{m.get('slot', '')}: {m.get('gb')} GB, çalışan hız {m.get('conf')} MT/s (modül {m.get('speed')})  {m.get('maker', '')} {m.get('part', '')}", 'dim')
        b = h.get('board') or {}
        H('ANAKART')
        L(f"{b.get('maker', '')} {b.get('model', '')}")
        L(f"BIOS {b.get('bios', '')}  ({b.get('biosdate', '')})", 'dim')
        H('DİSKLER')
        for d in h.get('disks') or []:
            L(f"{d['name']}  —  {d['gb']} GB  {d['bus']} {d['type']}  ({d['health']})")
        H('EKRANLAR')
        for d in h.get('disp') or []:
            tag = 'bad' if d['max'] and d['hz'] < d['max'] else None
            L(f"{d['name']}{'  (ana ekran)' if d['primary'] else ''}: {d['w']}x{d['h']} @ {d['hz']} Hz  (en fazla {d['max']} Hz)", tag)
        if h.get('mon'):
            L('Monitörler: ' + ', '.join(x for x in h['mon'] if x), 'dim')
        o = h.get('os') or {}
        H('WINDOWS')
        L(f"{o.get('name', '')} {o.get('ver', '')}  (derleme {o.get('build', '')}.{o.get('ubr', '')})")

        # PUBG için değerlendirme
        H('PUBG İÇİN DEĞERLENDİRME')
        th = c.get('threads') or 0
        nm = (c.get('name') or '').upper()
        if 'X3D' in nm:
            L('✔ İşlemci: çok güçlü. X3D işlemciler PUBG için en iyi seçeneklerden.', 'ok')
        elif th >= 12:
            L('✔ İşlemci: güçlü.', 'ok')
        elif th >= 8:
            L('⚠ İşlemci: yeterli. Yoğun çatışmalarda FPS düşebilir, Görüş Mesafesi Orta ya da Düşük olsun.', 'warn')
        else:
            L('✖ İşlemci: zayıf. FPS\'yi işlemci sınırlar. Görüş Mesafesi ve Efektler Çok Düşük olsun.', 'bad')
        v = max([g['vram'] for g in h.get('gpus') or []] or [0]) / 1024
        if v >= 12:
            L(f'✔ Ekran kartı belleği: {v:.0f} GB, çok iyi. Doku Ultra olabilir.', 'ok')
        elif v >= 8:
            L(f'✔ Ekran kartı belleği: {v:.0f} GB, iyi. Doku Yüksek olabilir.', 'ok')
        elif v >= 6:
            L(f'⚠ Ekran kartı belleği: {v:.0f} GB. Doku Orta olsun.', 'warn')
        elif v:
            L(f'✖ Ekran kartı belleği: {v:.0f} GB, az. Doku Düşük olsun.', 'bad')
        rg = h.get('ram_gb') or 0
        if rg >= 32:
            L(f'✔ RAM: {rg} GB, çok iyi. "Haritayı önceden yükle" açık olsun.', 'ok')
        elif rg >= 16:
            L(f'✔ RAM: {rg} GB, yeterli. Arka plan programlarını kapat.', 'ok')
        else:
            L(f'✖ RAM: {rg} GB, az. PUBG için en az 16 GB önerilir.', 'bad')
        if len(rams) == 1:
            L('✖ Tek RAM modülü: tek kanal çalışıyor, FPS belirgin düşer. İkinci modül ekle.', 'bad')
        if LIM['hz']:
            L(f"ℹ Ana ekran {LIM['hz']} Hz. Oyunda FPS sınırını {LIM['cap']} yap (FreeSync/G-Sync açıksa).", None)
        if not any('SSD' in (d.get('type') or '') or 'NVMe' in (d.get('bus') or '') for d in h.get('disks') or []):
            L('⚠ SSD bulunamadı. PUBG HDD\'de yüklemede ve harita akışında takılır.', 'warn')
        L('\nSıcaklık ve canlı değerler için Core Temp ile GPU-Z açık olmalı.', 'dim')
        return lines

    def save_info(self):
        if not getattr(self, 'info_lines', None):
            self.run_info(then=self.save_info); return
        pth = os.path.join(DATA, f'PC_Bilgisi_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt')
        with open(pth, 'w', encoding='utf-8-sig') as f:
            f.write(''.join(x for x, _ in self.info_lines))
        os.startfile(pth)

    def run_check(self, then=None):
        if getattr(self, 'check_busy', False):
            return
        try:
            dpi = int(self.e_dpi.get().strip() or 0)
        except ValueError:
            dpi = 0
        if dpi:
            c = load_cfg(); c['dpi'] = dpi; save_cfg(c)  # eskiden tüm ayar dosyasını silip sadece DPI yazıyordu
        self.check_busy = True
        self._fill(self.txt, [('Kontrol ediliyor...\n', 'dim')])

        def work():
            if not HW:
                load_hw()
            return [('GRAFİK VE SİSTEM', check_settings()), ('FARE VE KLAVYE', check_input(dpi))]

        def done(groups, err):
            self.check_busy = False
            if err:
                self._fill(self.txt, [(f'Hata: {err}\n', 'bad')]); return
            self.show_check(groups)
            if then:
                then()
        self.bg(work, done)

    def show_check(self, groups):
        t = self.txt
        t.config(state='normal'); t.delete('1.0', 'end')
        allr = [r for _, g in groups for r in g]
        bad = sum(1 for r in allr if r[0] in ('bad', 'warn'))
        t.insert('end', f'{len(allr)} ayar kontrol edildi, {bad} tanesi önerilenden farklı.\n', 'h')
        icon = {'ok': '✔', 'warn': '⚠', 'bad': '✖', 'info': 'ℹ'}
        for title, res in groups:
            t.insert('end', f'\n— {title} —\n', 'h')
            for st in ('bad', 'warn', 'info', 'ok'):
                for s, name, cur, reco, why in (r for r in res if r[0] == st):
                    t.insert('end', f'{icon[s]} {name}: {cur}', s)
                    if s in ('bad', 'warn'):
                        t.insert('end', f'   →  öneri: {reco}', 'h')
                    t.insert('end', '\n')
                    if s != 'ok':
                        t.insert('end', f'    {why}\n', 'dim')
        t.config(state='disabled')
        self.set_done = True

    def run_apply(self):
        self._fill(self.txt, [('Ayarlar uygulanıyor...\n', 'dim')])

        def done(msgs, err):
            if err:
                self._fill(self.txt, [(f'Uygulanamadı: {err}\n', 'bad')]); return

            def show():
                t = self.txt
                t.config(state='normal')
                t.insert('1.0', 'UYGULANDI:\n' + '\n'.join('• ' + m for m in msgs) + '\n\n', 'info')
                t.config(state='disabled')
            self.run_check(then=show)
        self.bg(apply_recommended, done)

    def game_running(self):
        if self.game_pid and psutil.pid_exists(self.game_pid):
            return True
        self.game_pid = None
        now = time.time()
        if now - self.scan_t < 3:  # oyun kapalıyken tüm süreç listesini saniyede bir taramak yerine 3 sn'de bir
            return False
        self.scan_t = now
        for p in psutil.process_iter(['name']):
            if (p.info['name'] or '').lower() == GAME.lower():
                self.game_pid = p.pid
                return True
        return False

    def fast_tick(self):
        try:
            f = self.pm.fast_fps() if self.game_pid else None
            if f is not None:
                col = C_OK if f >= LIM['cap'] * 0.6 else C_WARN
                setl(self.hud_fps, text=f'{f:.0f} FPS', fg=col)
                setl(self.v_fps, text=f'{f:.0f}', fg=C_TXT)
                if self.mini:
                    t = self.mini_l.cget('text')
                    setl(self.mini_l, text=f'{f:.0f} FPS' + (t[t.index('   1%'):] if '   1%' in t else ''))
        except Exception:
            pass
        self.root.after(250, self.fast_tick)

    def tick(self):
        try:
            self.update()
        except Exception as e:
            setl(self.l_state, text=f'Hata: {e}')
        self.root.after(1000, self.tick)

    def update(self):
        game = self.game_running()
        if self.prev_game is None and not game:
            self.root.after(2500, self.auto_apply)
        elif self.prev_game and not game:
            self.root.after(7000, self.auto_apply)
            if getattr(self, 'pending_update', False):
                self.root.after(12000, self.apply_update)
        self.prev_game = game
        if game:
            if self.pm.exe and not self.pm.running():
                self.pm.start()
            if self.start is None:
                self.start = time.time()

        # Kareler
        ft, gb = self.pm.take() if game else ([], 0.0)
        self.all_ft.extend(ft)
        self.win.append({'F': ft, 'St': 0})
        wa = [v for x in self.win for v in x['F']]
        med = pct(wa, 0.5)
        thr = max(3 * med, 20)
        st = sum(1 for v in ft if v > thr)
        self.win[-1]['St'] = st
        self.stut += st
        st10 = sum(x['St'] for x in self.win)
        sum_ft = sum(ft)
        fps = len(ft) / (sum_ft / 1000) if ft else 0
        low1 = 1000 / pct(wa, 0.99) if len(wa) >= 50 else 0
        low01 = 1000 / pct(wa, 0.999) if len(wa) >= 500 else 0
        ratio = min(1, gb / sum_ft) if gb > 0 and sum_ft > 0 else None

        # Sensörler
        per = psutil.cpu_percent(percpu=True)
        cpu_tot = round(sum(per) / len(per)) if per else 0
        core_max = round(max(per)) if per else 0
        ram_free = round(psutil.virtual_memory().available / 1048576)
        cpu = cpu_sensor()
        gpu = self.ngpu.read() if self.ngpu.kind else None
        if gpu:
            if not gpu.get('VRAM'):
                pd = self.gpdh.read()
                gpu['VRAM'] = pd['VRAM'] if pd else 0
                if not gpu.get('Load') and pd:
                    gpu['Load'] = pd['Load']
        else:
            gpu = gpu_sensor()
        gz = bool(gpu and gpu.get('T'))
        if not gpu:
            gpu = self.gpdh.read()
        n = self.net.stats()
        cpu_t = cpu['T'] if cpu else 0
        if cpu and cpu.get('TJ'):
            LIM['hot'] = int(cpu['TJ']) - 3
        cpu_mhz = cpu['MHz'] if cpu else 0
        g_t = gpu['T'] if gpu else 0
        hs = gpu['HS'] if gpu else 0
        g_load = gpu['Load'] if gpu else 0
        vram = gpu['VRAM'] if gpu else 0
        pwr = gpu['Pwr'] if gpu else 0

        # Darboğaz
        bound = '-'
        if ft:
            if LIM['cap'] - 10 <= fps <= LIM['cap'] + 4:
                bound = 'Limit'
            elif ratio is not None:
                bound = 'GPU' if ratio >= 0.9 else ('CPU' if ratio < 0.75 else 'Karışık')
            elif g_load >= 95:
                bound = 'GPU'
            elif 0 < g_load < 80:
                bound = 'CPU'

        # Disk
        io, tnow = psutil.disk_io_counters(), time.time()
        dt = max(0.2, tnow - self.dio_t)
        dr = (io.read_bytes - self.dio.read_bytes) / dt / 1048576 if io and self.dio else 0
        dw = (io.write_bytes - self.dio.write_bytes) / dt / 1048576 if io and self.dio else 0
        self.dio, self.dio_t = io, tnow

        # Takılma kaydı
        if st and ft:
            top = [x for x in self.procs.get() if x[1].lower() not in ('tslgame.exe', 'pubg_izleyici.exe', 'presentmon.exe')
                   and not x[1].lower().startswith('presentmon')][:3]
            if cpu_t >= LIM['hot']:
                why = f'işlemci ısınması ({cpu_t}°C)'
            elif dr >= 150:
                why = f'diskten yoğun okuma ({dr:.0f} MB/s): harita ya da eşya yüklemesi'
            elif vram >= LIM['vfull']:
                why = 'VRAM dolu'
            elif top and top[0][0] >= 10:
                why = f'arka plan programı: {top[0][1]} (%{top[0][0]:.0f} işlemci)'
            elif core_max >= 95:
                why = 'bir işlemci çekirdeği %100 dolu'
            else:
                why = 'oyun motoru / sürücü (donanım normal)'
            self.events.append({'t': datetime.datetime.now().strftime('%H:%M:%S'), 'n': st, 'max': max(ft), 'cpu_t': cpu_t,
                                'core': core_max, 'dr': dr, 'vram': vram, 'ping': n.get('ping'), 'why': why,
                                'top': ', '.join(f'{x[1]} %{x[0]:.0f}' for x in top)})
            self.events = self.events[-300:]
            self.ev_dirty = True

        # Performans testi
        if self.bench is not None:
            b = self.bench
            b['ft'] += ft
            b['st'] += st
            for k, val in (('cpu_t', cpu_t), ('g_t', g_t), ('hs', hs), ('vram', vram), ('ping', n.get('ping') or 0)):
                b['mx'][k] = max(b['mx'].get(k, 0), val)
            left = b['dur'] - (time.time() - b['start'])
            if not game:
                self.bench = None
                setl(self.an_state, text='Test iptal: PUBG kapandı.', fg=C_BAD)
            elif left <= 0:
                self.finish_bench()
            else:
                setl(self.an_state, text=f'Test sürüyor... {left:.0f} sn kaldı. Normal oyna.', fg=C_WARN)

        # Kayıt
        if ft:
            self.secs.append({'FPS': fps, 'St': st, 'CPU': cpu_tot, 'CoreMax': core_max, 'CPUSic': cpu_t,
                              'MHz': cpu_mhz, 'GPU': g_load, 'GPUSic': g_t, 'HotSpot': hs, 'VRAM': vram,
                              'RAMBos': ram_free, 'Bound': bound, 'Ping': n['ping'] or 0, 'Loss': n['loss'],
                              'Jit': n['jit']})
            self.csv.write(','.join(map(str, [datetime.datetime.now().strftime('%H:%M:%S'), round(fps), round(low1), st,
                                           cpu_tot, core_max, cpu_t, cpu_mhz, g_load, g_t, hs, vram, ram_free,
                                           '' if ratio is None else f'{ratio:.2f}', bound])) + '\n')

        # Ekran
        self.render({'ft': ft, 'fps': fps, 'low1': low1, 'low01': low01, 'ftavg': (sum_ft / len(ft)) if ft else 0,
                     'ftmax': max(ft) if ft else None, 'game': game, 'bound': bound, 'st10': st10, 'ratio': ratio,
                     'cpu_t': cpu_t, 'cpu_tot': cpu_tot, 'cpu_mhz': cpu_mhz, 'core_max': core_max, 'per': per,
                     'cores': cpu.get('Cores', []) if cpu else [], 'g_t': g_t, 'hs': hs, 'g_load': g_load, 'gz': gz,
                     'pwr': pwr, 'vram': vram, 'net': n, 'gdet': gpu if gz else {}, 'dr': dr, 'dw': dw})
        self.tick_n += 1
        if self.tick_n % 2 == 0:
            self.refresh_analysis()

        # Canlı teşhis
        iss = []
        if cpu_t >= LIM['hot']:
            iss.append(f'İşlemci {cpu_t}°C: ısınıp hızını düşürüyor, FPS düşüyor. Sebep soğutma.')
        if hs >= 100 or g_t >= 85:
            iss.append(f'Ekran kartı çok sıcak (GPU {g_t}°C, hot spot {hs}°C).')
        if vram >= LIM['vfull']:
            iss.append('VRAM dolu. Doku kalitesini bir kademe düşür.')
        if 0 < ram_free < 3000:
            iss.append('RAM dolu. Arka plandaki programları kapat.')
        if st10 >= 3:
            why = ('işlemci ısınması' if cpu_t >= LIM['hot'] else
                   'bir çekirdek %100 dolu (arka plan programı ya da oyun)' if core_max >= 95 else
                   'VRAM dolu' if vram >= LIM['vfull'] else
                   'oyunun anlık yüklemesi ya da sürücü (donanım normal)')
            iss.append(f"Son 10 sn'de {st10} takılma. Sebep: {why}.")
        if n['n'] >= 5 and (n['loss'] >= 10 or n['jit'] >= 20):
            iss.append(f"Ağ sorunu: kayıp %{n['loss']}, dalgalanma {n['jit']} ms. Oyunda geri ışınlanma ve gecikmeli vuruş yapar. "
                       "Wi-Fi yerine kablo kullan, modemi yeniden başlat.")
        elif n['n'] >= 5 and n['loss'] > 0:
            iss.append(f"Ağda hafif paket kaybı (%{n['loss']}).")
        if game and n['down'] >= 20:
            iss.append(f"Arka planda indirme var (↓ {n['down']:.0f} Mbit/s). Steam, Windows Update ya da tarayıcıyı kontrol et.")
        if game and LIM['hz'] and fps > LIM['hz'] + 5:
            iss.append(f"FPS ({fps:.0f}) ekran hızını ({LIM['hz']} Hz) aşıyor: FreeSync devre dışı kalıyor, gecikme ve yırtılma olur. "
                       f"Oyunda FPS sınırını Özel {LIM['cap']} yap.")
        if bound == 'CPU' and cpu_t < LIM['hot'] and fps < LIM['cap'] - 10:
            iss.append("FPS'yi işlemci / oyun motoru sınırlıyor, ekran kartı bekliyor. Görüş Mesafesi'ni düşürmek yardımcı olur.")
        if not iss and time.time() < getattr(self, 'auto_until', 0):
            txt, col = self.auto_msg, C_ACC
        elif not iss:
            txt = '✔  SORUN YOK'
            if bound == 'GPU':
                txt += '   ·   Ekran kartı tam çalışıyor. Daha fazla FPS için grafik ayarlarını düşür.'
            col = C_OK
        else:
            txt = '\n'.join('●  ' + x for x in iss[:3])
            col = C_BAD if (cpu_t >= LIM['hot'] or st10 >= 3 or hs >= 100) else C_WARN
        setl(self.ban_strip, bg=col)
        setl(self.ban_txt, text=txt, fg=col if not iss else C_TXT)
        if game and self.start:
            el = int(time.time() - self.start)
            setl(self.l_state, text=f'PUBG ölçümü: {el // 60} dk {el % 60} sn   |   kapatınca rapor açılır')
        else:
            setl(self.l_state, text='PresentMon indirilemedi: FPS ölçülemez, sensörler çalışır.' if getattr(self, 'pm_missing', False)
                 else 'PUBG kapalı: sistem ve ağ değerleri canlı. FPS ölçümü oyun açılınca kendiliğinden başlar.')

    # ---------------- Rapor ----------------
    def write_report(self):
        s, n, a = self.secs, len(self.secs), self.all_ft
        if n < 5 or len(a) < 100:
            with open(REPORT, 'w', encoding='utf-8-sig') as f:
                f.write('Yeterli veri yok (en az birkaç saniye oyun içinde ölçülmeli).\n')
            return
        o = [f'PUBG İzleyici Raporu - {datetime.datetime.now():%d.%m.%Y %H:%M}']
        avg = len(a) / (sum(a) / 1000)
        o.append(f'Süre: {n} sn | Ortalama FPS: {avg:.0f} | 1% düşük: {1000 / pct(a, 0.99):.0f} | '
                 f'0.1% düşük: {1000 / pct(a, 0.999):.0f} | Takılma: {self.stut}')
        mx = lambda k: max(x[k] for x in s)
        o.append(f"En yüksek: CPU {mx('CPUSic')}°C | GPU {mx('GPUSic')}°C | Hot spot {mx('HotSpot')}°C | "
                 f"VRAM {mx('VRAM') / 1024:.1f} GB")
        pc = lambda f: round(100 * sum(1 for x in s if f(x)) / n)
        o.append(f"Darboğaz dağılımı: GPU %{pc(lambda x: x['Bound'] == 'GPU')} | İşlemci/oyun motoru %{pc(lambda x: x['Bound'] == 'CPU')} | "
                 f"FPS limitinde %{pc(lambda x: x['Bound'] == 'Limit')} | Karışık %{pc(lambda x: x['Bound'] == 'Karışık')}")
        o.append('')

        issues = []
        hot = pc(lambda x: x['CPUSic'] >= LIM['hot'])
        if hot:
            issues.append((hot * 2, f"İşlemci zamanın %{hot}'inde {LIM['hot']}°C ve üstündeydi. İşlemci ısınınca hızını düşürüyor, FPS de düşüyor. "
                                    "Çözüm: soğutucunun oturmasını ve macunu kontrol et, BIOS'ta PBO Thermal Limit'i 85 yap."))
        ghot = pc(lambda x: x['HotSpot'] >= 100 or x['GPUSic'] >= 85)
        if ghot:
            issues.append((ghot * 2, f"Ekran kartı zamanın %{ghot}'inde çok sıcaktı (hot spot ≥100°C ya da GPU ≥85°C). "
                                     "Kasanın hava akışını ve fan eğrisini kontrol et."))
        vf = pc(lambda x: x['VRAM'] >= LIM['vfull'])
        if vf:
            issues.append((vf * 2, f"Ekran kartı belleği zamanın %{vf}'inde doluydu. Doku kalitesini bir kademe düşür."))
        rl = pc(lambda x: 0 < x['RAMBos'] < 3000)
        if rl:
            issues.append((rl * 2, f"RAM zamanın %{rl}'inde doluydu. Arka plandaki programları kapat."))
        if self.stut:
            ss = [x for x in s if x['St'] > 0]
            k = len(ss)
            sh = round(100 * sum(1 for x in ss if x['CPUSic'] >= LIM['hot']) / k)
            sc = round(100 * sum(1 for x in ss if x['CoreMax'] >= 95) / k)
            sv = round(100 * sum(1 for x in ss if x['VRAM'] >= LIM['vfull']) / k)
            per_min = round(self.stut / (n / 60), 1)
            if sh >= 50:
                cause = f"Takılmaların %{sh}'i işlemci {LIM['hot']}°C'nin üstündeyken oldu, yani asıl sebep işlemcinin ısınması."
            elif sc >= 50:
                cause = (f"Takılmaların %{sc}'inde bir işlemci çekirdeği %95'in üstünde doluydu. Sebep arka planda çalışan bir program "
                         "ya da oyunun ana iş parçacığı. Takılma anında Görev Yöneticisi'ne bak.")
            elif sv >= 50:
                cause = f"Takılmaların %{sv}'i VRAM doluyken oldu. Doku kalitesini düşür."
            else:
                cause = ('Takılma anlarında sıcaklık, işlemci ve bellek normaldi. Bunlar oyunun anlık yüklemesi '
                         '(harita/eşya akışı, shader derleme) ya da sürücüden geliyor. Diskte veya donanımda sorun yok.')
            sev = 60 if per_min >= 3 else (30 if per_min >= 1 else 10)
            issues.append((sev, f'Takılma: toplam {self.stut}, dakikada {per_min}. {cause}'))
        nl = pc(lambda x: x.get('Loss', 0) >= 10 or x.get('Jit', 0) >= 20)
        if nl:
            pings = [x['Ping'] for x in s if x.get('Ping')]
            issues.append((nl * 2, f"Ağ zamanın %{nl}'inde sorunluydu (paket kaybı ya da ping sıçraması). Ortalama ping "
                                   f"{round(sum(pings) / len(pings)) if pings else '?'} ms. Wi-Fi yerine kablo kullan, arka plandaki indirmeleri durdur."))
        cb = pc(lambda x: x['Bound'] == 'CPU')
        if cb >= 40:
            issues.append((cb / 2, f"FPS'yi zamanın %{cb}'inde işlemci/oyun motoru sınırladı, ekran kartı boşta bekledi. PUBG'de sık görülür. "
                                   "Görüş Mesafesi'ni Orta ya da Düşük yap; işlemci ısınıyorsa önce onu çöz."))
        gbp = pc(lambda x: x['Bound'] == 'GPU')
        if gbp >= 40:
            issues.append((gbp / 3, f"Ekran kartı zamanın %{gbp}'inde tam yükteydi. Daha fazla FPS istiyorsan Gölgeler, Efektler ve Yeşillik ayarlarını düşür."))

        if not issues:
            o.append('SONUÇ: Belirgin bir sorun yok. FPS ve sıcaklıklar normal.')
        else:
            issues.sort(key=lambda t: t[0], reverse=True)
            o.append('ANA SORUN: ' + issues[0][1])
            if len(issues) > 1:
                o += ['', 'Diğer bulgular:'] + ['- ' + t for _, t in issues[1:]]
        if not any(x['CPUSic'] for x in s):
            o += ['', 'Not: Core Temp kapalıydı, işlemci sıcaklığı ölçülmedi.']
        if not any(x['GPUSic'] for x in s):
            o.append('Not: GPU-Z kapalıydı, ekran kartı sıcaklığı ölçülmedi.')
        if self.events:
            cz = collections.Counter(e['why'].split(' (')[0].split(':')[0] for e in self.events)
            o += ['', 'Takılma sebepleri (kayıttan):'] + [f'- {k}: {v} kez' for k, v in cz.most_common()]
        o += ['', f'Saniyelik veri: {SEC_CSV}']
        with open(REPORT, 'w', encoding='utf-8-sig') as f:
            f.write('\n'.join(o) + '\n')

    def open_report(self):
        self.write_report()
        os.startfile(REPORT)

    def close(self, report=True):
        try:
            self.csv.close()
        except Exception:
            pass
        try:
            a = self.all_ft
            if len(a) > 3000:
                h = load_hist()
                h.append({'date': datetime.datetime.now().strftime('%d.%m %H:%M'), 'type': 'Oturum',
                          'fps': len(a) / (sum(a) / 1000), 'low1': 1000 / pct(a, 0.99), 'low01': 1000 / pct(a, 0.999),
                          'st': self.stut, 'cpu': max((x['CPUSic'] for x in self.secs), default=0),
                          'gpu': max((x['GPUSic'] for x in self.secs), default=0), 'gfx': gfx_snapshot()})
                save_hist(h)
        except Exception:
            pass
        try:
            self.write_report()
            self.pm.stop()
            if report and len(self.all_ft) >= 100:  # oyun hiç ölçülmediyse boş rapor açılmaz
                os.startfile(REPORT)
        except Exception:
            pass
        finally:
            self.root.destroy()


if __name__ == '__main__':
    App()

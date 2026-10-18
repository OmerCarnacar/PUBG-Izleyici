# PUBG Canlı İzleyici - anlık FPS, takılma, sıcaklık, darboğaz ve SORUN tespiti
# Çalıştırma: PUBG_Izleyici_CALISTIR.bat (yönetici olarak açar, Python yoksa kurar)
# Harici program gerekmez: yük, saat, bellek, disk, ağ ve ekran kartı sıcaklığı Windows'tan ve ekran kartı sürücüsünden okunur.
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

VERSION = '1.7.0'
REPO = 'OmerCarnacar/PUBG-Izleyici'
DEV = 'Ömer Çarnaçar'
LINKEDIN = 'https://www.linkedin.com/in/omercarnacar'  # talep, öneri ve hata bildirimleri buradan
# Her sürümde en üste eklenir; program güncellenince "Yenilikler" penceresinde gösterilir.
CHANGES = [
    ('1.7.0', [
        'Yeni: İniş ve ölüm haritası — son 14 günün maçlarından her harita için iniş ve ölüm yerlerin, ısı katmanı, çatışma noktaları',
        'Hangi bölgeye indiğinde daha iyi sonuç aldığın: en iyi ve kaçınman gereken iniş bölgeleri (ortalama sıra, ilk 10 oranı, erken ölüm)',
        'Maç listesi: seni kim, hangi silahla öldürdü; maça tıklayınca haritada iniş yerine gider',
        'Resmî PUBG API verisi, maç bittikten sonra: oyuna dokunmaz, ban riski yok. Maçlar bir kez indirilir, sonra saniyeler içinde açılır',
    ]),
    ('1.6.0', [
        'Yeni: Görev Yöneticisi sekmesi — Performans ekranının aynısı: CPU, Bellek, her disk, Ethernet/Wi-Fi ve GPU; 60 saniyelik grafikler, mantıksal işlemci grafikleri, GPU motorları (3D, Copy, Video Encode/Decode), aynı Windows sayaçları',
        "Harici program yok: HWiNFO, Core Temp ve GPU-Z artık başlatılmıyor ve ayarlarına dokunulmuyor; her şey Windows'tan ve ekran kartı sürücüsünden okunuyor",
        "Ekran kartı çekirdek ve bellek saati artık Windows'tan (Görev Yöneticisi ile aynı kaynak)",
        'Daha az işlemci: pencere simge durumundayken ya da oyun öndeyken ekran çizilmiyor (ortalama %0.1); Görev Yöneticisi sekmesi sadece açıkken ölçüm yapıyor',
        "Ana pencere artık 'her zaman üstte' değil: tam ekran oyunun özel modunu bozmasın (mini mod üstte kalır)",
    ]),
    ('1.5.1', [
        "Düzeltme: HWiNFO kuruluyken program onu başlatamıyordu (Windows'un özel izin kuralı), Core Temp'e dönüyordu; artık HWiNFO açılıyor ve işlemci sıcaklığı AMD Software ile aynı gösteriliyor",
    ]),
    ('1.5.0', [
        'Yeni: Maç sonu koç raporu — her maçın tekrarında Rapor sekmesi: sıra, hasar, isabet, kafa vuruşu, iniş, ilk çatışma, ölüm anı ve sebebi, silah tablosu, öneriler',
        'Rapor, maçın anlarını bilgisayarının o anki performansıyla eşleştirir: ölümünden önceki 15 saniyedeki FPS, takılma ve ping; çatışmalardaki FPS; FPS grafiği',
        'Program oyun sırasında her saniyenin performansını kaydeder (15 gün saklanır)',
        "Oyun açıkken yeni maç bitince rapor kendiliğinden hazırlanır ve 'Maç raporu hazır' bandı çıkar (oyunu etkilememek için en düşük öncelikte, büyük harita indirmeden)",
    ]),
    ('1.4.0', [
        'Yeni: Maç Tekrarı sekmesi (pubg.sh benzeri) — son maçlarını haritada oynat: tüm oyuncuların hareketi, mavi bölge / beyaz çember / kırmızı bölge, atış çizgileri, öldürme ve ölüm yerleri, kare paketler',
        'Tekrar sayfası: yakınlaştırma, zaman çizelgesi (öldürme ve ölüm işaretli), 1x-80x hız, takım listesi, öldürme akışı, oyuncu takibi, kısayol tuşları',
        'Resmî PUBG haritaları; yüksek çözünürlüklü harita bir kez indirilip döşemelere bölünür, yakınlaştırınca da keskin',
        "Veriler resmî PUBG API'sinden, maç bittikten sonra: oyun sırasında hiçbir şey okunmaz, hile değildir",
    ]),
    ('1.3.1', [
        "Düzeltme: oyun içi FPS sınırı hiç uygulanmıyordu — program PUBG'nin tanımadığı bir değer yazıyordu ve oyun sınırsıza dönüyordu",
        'Kenar yumuşatma önerisi Orta (profesyonellerin çoğu; Yüksek uzaktaki hedefi bulanıklaştırır)',
        'Yeni öneri: lobi FPS sınırı 60 (lobide ekran kartı boşuna %100 çalışmasın)',
        'Yeni öneri: efekt sesi %100 (ayak ve araç sesleri bu kanalda)',
    ]),
    ('1.3.0', [
        'Yeni: Takım Sesi sekmesi — mikrofon, PUBG oyun içi ses ve Discord ayarları kontrol edilir; arka plan sesi gitmesin diye öneriler (Krisp, bas-konuş, AMD Noise Suppression, Stereo Karışımı uyarısı) ve tek tıkla uygulama',
        "İşlemci sıcaklığı artık AMD Software (Adrenalin) ve Ryzen Master ile aynı: HWiNFO'nun CPU Tctl/Tdie değeri. HWiNFO kuruluysa program onu kendisi ayarlar ve arka planda başlatır",
        "Core Temp sadece HWiNFO yoksa kullanılır (çekirdek sensörü, Tctl/Tdie'den birkaç derece düşük çıkabilir)",
    ]),
    ('1.2.0', [
        'Yeni: Donanım Testi sekmesi — sensör kontrolü, işlemci stres ve ısıdan hız düşürme testi, RAM hız ve yaz-oku kontrolü, PUBG diskinde hız testi; sonuçlar önceki testle karşılaştırılır',
        "Ekran kartı sıcaklığı, yükü ve VRAM artık Windows'tan, Görev Yöneticisi ile aynı kaynaktan ve sadece oyunun çalıştığı karttan okunuyor",
        'Düzeltme: işlemcisinde grafik birimi olan bilgisayarlarda (ör. Ryzen 7000/9000 + NVIDIA) yanlış kartın sıcaklığı/yükü gösteriliyordu',
        "İşlemci yükü ve hızı Görev Yöneticisi'nin sayacından (eskisi ~10 puan düşük gösteriyordu)",
        'İşlemci sıcaklığı için Core Temp yoksa HWiNFO da okunuyor; ikisi de yoksa indirme bağlantısı gösteriliyor',
        'Düzeltme: çok çekirdekli işlemcilerde Canlı sekmesinde yazılar üst üste biniyordu; sekme artık kaydırılabilir, uyarılar en üstte',
    ]),
    ('1.1.2', ["Düzeltme: program çöker ya da Görev Yöneticisi'nden kapatılırsa FPS ölçüm aracı (PresentMon) arka planda kalmıyor"]),
    ('1.1.1', ['Yeni modern arayüz: sol menü, sekme göstergesi, daha geniş içerik alanı',
               'Talep / öneri bildir: tek tıkla LinkedIn üzerinden geliştiriciye ulaş',
               'Güncelleme durumu sol menüde: her açılışta kontrol edilir, "Güncel" ya da indirme durumu görünür',
               'Geliştirici bilgisi eklendi']),
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


_JOB = [None]


def kill_with_me(proc):
    """Alt süreci bir Windows iş nesnesine bağlar: program çökerse ya da Görev Yöneticisi'nden kapatılırsa
    işletim sistemi alt süreci de kapatır (yoksa PresentMon oyun kapanana kadar arka planda kalıyordu)."""
    try:
        k = ctypes.windll.kernel32
        if _JOB[0] is None:
            k.CreateJobObjectW.restype = ctypes.c_void_p
            k.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
            job = k.CreateJobObjectW(None, None)
            info = ctypes.create_string_buffer(144)  # JOBOBJECT_EXTENDED_LIMIT_INFORMATION (64 bit)
            struct.pack_into('<I', info, 16, 0x2000)  # LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not job or not k.SetInformationJobObject(job, 9, info, 144):
                return
            _JOB[0] = job  # tutamak program ömrü boyunca açık kalır
        k.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        k.AssignProcessToJobObject(_JOB[0], int(proc._handle))
    except Exception:
        pass


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
        kill_with_me(self.proc)
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
    ('sg.AntiAliasingQuality', 2, 'Kenar Yumuşatma', 2, 2, 'Orta en iyi denge: Yüksek ve üstü görüntüyü yumuşatıp uzaktaki hedefi '
     'bulanıklaştırır, ekran kartını da gereksiz yükler. Profesyonellerin çoğu Orta kullanır. FSR/DLSS için en az Orta gerekir.'),
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
$o.cpu=[ordered]@{name=$c.Name.Trim();cores=$c.NumberOfCores;threads=$c.NumberOfLogicalProcessors;mhz=$c.MaxClockSpeed;maker=$c.Manufacturer;l2=$c.L2CacheSize;l3=$c.L3CacheSize;virt=$c.VirtualizationFirmwareEnabled;sockets=@(Get-CimInstance Win32_Processor).Count}
$o.ramslots=(Get-CimInstance Win32_PhysicalMemoryArray | Measure-Object -Property MemoryDevices -Sum).Sum
$o.ram=@(Get-CimInstance Win32_PhysicalMemory | ForEach-Object { [ordered]@{gb=[math]::Round($_.Capacity/1GB);speed=$_.Speed;conf=$_.ConfiguredClockSpeed;type=$_.SMBIOSMemoryType;maker=$_.Manufacturer;part=("$($_.PartNumber)").Trim();slot=$_.DeviceLocator;ff=$_.FormFactor} })
$b=Get-CimInstance Win32_BaseBoard; $bi=Get-CimInstance Win32_BIOS
$o.board=[ordered]@{maker=$b.Manufacturer;model=$b.Product;bios=$bi.SMBIOSBIOSVersion;biosdate=$bi.ReleaseDate.ToString('dd.MM.yyyy')}
$os=Get-CimInstance Win32_OperatingSystem
$o.os=[ordered]@{name=$os.Caption;build=$os.BuildNumber;ubr=(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR;ver=(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').DisplayVersion}
$o.disks=@(Get-PhysicalDisk | ForEach-Object { [ordered]@{name=$_.FriendlyName;type="$($_.MediaType)";bus="$($_.BusType)";gb=[math]::Round($_.Size/1GB);health="$($_.HealthStatus)";id="$($_.DeviceId)"} })
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
        elif lt != 'Customizable':
            out.append(('warn', 'Oyun içi FPS sınırı', f'geçersiz değer ({lt})', f'Özel: {cap}',
                        'Oyun bu değeri tanımıyor ve sınırsız çalışıyor. "Önerilenleri uygula" düzeltir.'))
        else:
            out.append(('ok' if cap - 8 <= lim <= cap else 'warn', 'Oyun içi FPS sınırı', f'Özel {lim:.0f}', f'Özel: {cap}', why))
        lob = d.get('LobbyFrameRateLimitType')
        if lob is not None:
            out.append(('ok' if lob in ('Fixed_30', 'Fixed_60') else 'warn', 'Lobi FPS sınırı',
                        {'Unlimited': 'Sınırsız', 'Fixed_30': '30', 'Fixed_60': '60'}.get(lob, lob), '60',
                        'Lobide sınırsız FPS ekran kartını boşuna %100 çalıştırır: ısı, fan sesi ve elektrik. Oyuna etkisi yok.'))
        efx = num(d.get('EffectSoundVolume'))
        if efx is not None:
            out.append(('ok' if efx >= 99.5 else 'warn', 'Efekt sesi', f'%{efx:.0f}', '%100',
                        'Ayak sesi, araç ve silah sesleri bu kanaldadır. Kısıksa düşmanı geç duyarsın; '
                        'genel sesi kulaklıktan ayarla, müziği kapalı tut.'))
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
        # PUBG'nin tanıdığı değer "Customizable". Eski sürümler "Custom" yazıyordu; oyun bunu tanımayıp
        # sınırsıza dönüyordu, yani FPS sınırı hiç uygulanmıyordu.
        if d.get('InGameFrameRateLimitType') != 'Customizable' or abs(num(d.get('InGameCustomFrameRateLimit'), 0) - cap) > 0.5:
            setk('InGameFrameRateLimitType', 'Customizable')
            setk('InGameCustomFrameRateLimit', f'{cap:.6f}')
            setk('FrameRateLimit', f'{cap:.6f}')
            msgs.append(f'Oyun içi FPS sınırı → Özel {cap}')
        if d.get('LobbyFrameRateLimitType', 'Fixed_60') not in ('Fixed_30', 'Fixed_60'):
            setk('LobbyFrameRateLimitType', 'Fixed_60'); msgs.append('Lobi FPS sınırı → 60')
        if num(d.get('EffectSoundVolume'), 100) < 99.5:
            setk('EffectSoundVolume', '100.000000')
            msgs.append(f"Efekt sesi: %{num(d.get('EffectSoundVolume'), 0):.0f} → %100")
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


# ---------------- Donanım testi (işlemci, RAM, disk) ----------------
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


# ---------------- Takım sesi: mikrofon, PUBG ve Discord ayarları ----------------
class _GUID(ctypes.Structure):
    _fields_ = [('a', ctypes.c_uint32), ('b', ctypes.c_uint16), ('c', ctypes.c_uint16), ('d', ctypes.c_ubyte * 8)]

    def __init__(self, s):
        super().__init__()
        ctypes.oledll.ole32.CLSIDFromString(ctypes.c_wchar_p(s), ctypes.byref(self))


def _com(obj, idx, *args, restype=ctypes.c_long, argtypes=()):
    """COM arayüzünün vtable'ındaki idx. yöntemi çağırır (comtypes olmadan, saf ctypes)."""
    vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    fn = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtbl[idx])
    return fn(obj, *args)


def mic_info():
    """Varsayılan iletişim mikrofonu: {'name', 'id', 'vol' (0-100), 'mute'} ya da None. Windows Core Audio."""
    ole = ctypes.windll.ole32
    ole.CoInitializeEx(None, 0)  # COINIT_MULTITHREADED (iş parçacığında çağrılabilir)
    enum = ctypes.c_void_p()
    if ole.CoCreateInstance(ctypes.byref(_GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}')), None, 1,
                            ctypes.byref(_GUID('{A95664D2-9614-4F35-A746-DE8DB63617E6}')), ctypes.byref(enum)):
        return None
    dev, vol = ctypes.c_void_p(), ctypes.c_void_p()
    try:
        # GetDefaultAudioEndpoint(eCapture=1, eCommunications=2): Discord ve oyunlar bunu kullanır
        if _com(enum, 4, 1, 2, ctypes.byref(dev), argtypes=(ctypes.c_int, ctypes.c_int, ctypes.c_void_p)):
            return None
        pid = ctypes.c_wchar_p()
        _com(dev, 5, ctypes.byref(pid), argtypes=(ctypes.c_void_p,))
        did = pid.value or ''
        ole.CoTaskMemFree(pid)
        out = {'id': did, 'name': '', 'vol': None, 'mute': False}
        if not _com(dev, 3, ctypes.byref(_GUID('{5CDF2C82-841E-4546-9722-0CF74078229A}')), 23, None, ctypes.byref(vol),
                    argtypes=(ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p)):
            lv, mu = ctypes.c_float(), ctypes.c_int()
            if not _com(vol, 9, ctypes.byref(lv), argtypes=(ctypes.c_void_p,)):
                out['vol'] = round(lv.value * 100)
            if not _com(vol, 15, ctypes.byref(mu), argtypes=(ctypes.c_void_p,)):
                out['mute'] = bool(mu.value)
        g = did.rsplit('}.', 1)[-1].strip('{}')
        if g:
            k = rf'SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture\{{{g}}}\Properties'
            n1 = reg(winreg.HKEY_LOCAL_MACHINE, k, '{a45c254e-df1c-4efd-8020-67d146a850e0},2') or ''
            n2 = reg(winreg.HKEY_LOCAL_MACHINE, k, '{b3f8fa53-0004-438e-9003-51a46e139bfc},6') or ''
            out['name'] = f'{n1} ({n2})' if n2 else n1
        return out
    finally:
        for o in (vol, dev, enum):
            if o.value:
                _com(o, 2)  # Release


def set_mic_volume(pct):
    """Varsayılan iletişim mikrofonunun seviyesini ayarlar (0-100)."""
    ole = ctypes.windll.ole32
    ole.CoInitializeEx(None, 0)
    enum, dev, vol = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    try:
        if ole.CoCreateInstance(ctypes.byref(_GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}')), None, 1,
                                ctypes.byref(_GUID('{A95664D2-9614-4F35-A746-DE8DB63617E6}')), ctypes.byref(enum)):
            return False
        if _com(enum, 4, 1, 2, ctypes.byref(dev), argtypes=(ctypes.c_int, ctypes.c_int, ctypes.c_void_p)):
            return False
        if _com(dev, 3, ctypes.byref(_GUID('{5CDF2C82-841E-4546-9722-0CF74078229A}')), 23, None, ctypes.byref(vol),
                argtypes=(ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p)):
            return False
        return _com(vol, 7, ctypes.c_float(pct / 100), None, argtypes=(ctypes.c_float, ctypes.c_void_p)) == 0
    finally:
        for o in (vol, dev, enum):
            if o.value:
                _com(o, 2)


def capture_devices():
    """Açık (etkin) kayıt aygıtlarının adları."""
    out = []
    base = r'SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture'
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as k:
            for i in range(winreg.QueryInfoKey(k)[0]):
                sub = winreg.EnumKey(k, i)
                st = reg(winreg.HKEY_LOCAL_MACHINE, f'{base}\\{sub}', 'DeviceState')
                if st is None or (st & 0xF) != 1:  # DEVICE_STATE_ACTIVE
                    continue
                p = f'{base}\\{sub}\\Properties'
                n1 = reg(winreg.HKEY_LOCAL_MACHINE, p, '{a45c254e-df1c-4efd-8020-67d146a850e0},2') or ''
                n2 = reg(winreg.HKEY_LOCAL_MACHINE, p, '{b3f8fa53-0004-438e-9003-51a46e139bfc},6') or ''
                out.append(f'{n1} ({n2})' if n2 else n1)
    except OSError:
        pass
    return out


def discord_voice():
    """Discord'un ses ayarları (yerel depodaki MediaEngineStore), Discord yoksa None, okunamazsa {}."""
    found = None
    for app in ('discord', 'discordptb', 'discordcanary'):
        d = os.path.join(os.environ.get('APPDATA', ''), app, 'Local Storage', 'leveldb')
        if os.path.isdir(d):
            found = found or {}
            for f in sorted(glob.glob(os.path.join(d, '*.log')) + glob.glob(os.path.join(d, '*.ldb')),
                            key=os.path.getmtime, reverse=True):
                try:
                    with open(f, 'rb') as fh:
                        b = fh.read()
                except OSError:
                    continue
                for m in reversed(list(re.finditer(rb'MediaEngineStore', b))):
                    i = b.find(b'{', m.end(), m.end() + 64)
                    if i < 0:
                        continue
                    depth, j = 0, i
                    while j < len(b) and j - i < 20000:  # süslü parantez eşleştirerek JSON'u çıkar
                        c = b[j:j + 1]
                        depth += c == b'{'
                        depth -= c == b'}'
                        j += 1
                        if depth == 0:
                            break
                    try:
                        js = json.loads(b[i:j].decode('utf-8', 'ignore'))
                    except ValueError:
                        continue
                    st = js.get('default') if isinstance(js.get('default'), dict) else js
                    if isinstance(st, dict) and ('mode' in st or 'noiseSuppression' in st):
                        return st
    return found


def check_voice():
    """(durum, ad, şu an, öneri, neden) satırları: mikrofon, PUBG sesli sohbet ve Discord."""
    out = []
    mi = None
    try:
        mi = mic_info()
    except Exception:
        pass
    devs = capture_devices()
    if not mi:
        out.append(('bad', 'Mikrofon', 'bulunamadı', 'Mikrofon tak',
                    'Windows\'ta varsayılan iletişim mikrofonu yok. Ses ayarları → Giriş kısmından mikrofonu seç.'))
    else:
        out.append(('info', 'Varsayılan iletişim mikrofonu', mi['name'] or mi['id'], '-',
                    'Discord ve PUBG "Varsayılan" seçiliyse bu mikrofonu kullanır.'))
        if mi['mute']:
            out.append(('bad', 'Mikrofon sessizde', 'Evet', 'Hayır', 'Windows mikrofonu sessize almış, takım seni duymaz.'))
        if mi['vol'] is not None:
            v = mi['vol']
            out.append(('ok' if 60 <= v <= 95 else 'warn', 'Mikrofon seviyesi (Windows)', f'%{v}', '%70 – %90',
                        'Çok yüksekse klavye, fan ve oda sesi de gider; çok düşükse takım seni zor duyar.'))
    mix = [x for x in devs if re.search(r'stereo|karışım|mix|what u hear', x, re.I)]
    if mix:
        out.append(('warn', 'Stereo Karışımı açık', ', '.join(mix), 'Kapalı',
                    'Yanlışlıkla mikrofon olarak seçilirse oyunun ve bilgisayarın tüm sesi takıma gider. '
                    'Ses ayarları → Tüm ses aygıtları → Stereo Karışımı → Devre dışı bırak.'))
    ns = [x for x in devs if re.search(r'noise suppression|broadcast|krisp|nvidia|sonar|streaming audio', x, re.I)]
    if ns:
        on = mi and any(n.split(' (')[0] in (mi['name'] or '') for n in ns)
        out.append(('ok' if on else 'warn', 'Gürültü engelleme aygıtı', ', '.join(ns), 'Mikrofon olarak bunu seç',
                    'Bu sanal mikrofon klavye, fan ve oda sesini temizler.' + ('' if on else
                    ' Şu an varsayılan değil: Discord ve PUBG\'de giriş aygıtı olarak bunu seç.')))
    else:
        amd = any('amd' in (g.get('name') or '').lower() or 'radeon' in (g.get('name') or '').lower() for g in HW.get('gpus') or [])
        nv = any('nvidia' in (g.get('name') or '').lower() for g in HW.get('gpus') or [])
        out.append(('info', 'Gürültü engelleme (sistem)', 'yok',
                    'AMD Noise Suppression' if amd else ('NVIDIA Broadcast' if nv else 'Discord Krisp'),
                    ('AMD Software → Ses ve Video → AMD Noise Suppression\'ı aç; sonra Discord/PUBG\'de "AMD Noise Suppression" '
                     'mikrofonunu seç. PUBG\'nin kendi gürültü engellemesi yok, bu sayede oyun içi seste de arka plan gitmez.')
                    if amd else ('Ücretsiz NVIDIA Broadcast\'i kur, gürültü kaldırmayı aç ve onun mikrofonunu seç.' if nv else
                                 'Sadece Discord kullanıyorsan Discord\'un Krisp\'i yeterli.')))
    priv = reg(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone',
               'Value')
    priv2 = reg(winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone\NonPackaged', 'Value')
    if priv == 'Deny' or priv2 == 'Deny':
        out.append(('bad', 'Mikrofon izni (Windows)', 'Kapalı', 'Açık',
                    'Gizlilik ve güvenlik → Mikrofon → "Masaüstü uygulamalarının mikrofona erişmesine izin ver"i aç.'))

    # PUBG
    d = read_ini() or {}
    if d:
        ptt = d.get('bUsePushToTalk', 'False') == 'True'
        out.append(('ok' if ptt else 'bad', 'PUBG: Bas-konuş', 'Açık' if ptt else 'Kapalı (sürekli açık mikrofon)', 'Açık',
                    'Bas-konuş kapalıysa mikrofon sürekli açık kalır: klavye, ateş sesi, oda sesi takıma gider.'))
        key = re.search(r'\(ActionName="PushToTalk",Keys=\(\(Key=(\w+)', open(INI, encoding='utf-8', errors='ignore').read()) \
            if os.path.exists(INI) else None
        if ptt:
            out.append(('info', 'PUBG: Bas-konuş tuşu', key.group(1) if key else 'varsayılan', '-',
                        'Fare yan tuşu ya da kolay ulaşılan bir tuş idealdir.'))
        glob_v = d.get('bUseGlobalVoice', 'False') == 'True'
        out.append(('ok' if not glob_v else 'warn', 'PUBG: Herkese açık ses kanalı', 'Açık' if glob_v else 'Kapalı', 'Kapalı',
                    'Açıkken yakındaki düşmanların ve yabancıların sesi de gelir, takım konuşması karışır.'))
        team = d.get('bUseTeamVoice', 'True') == 'True'
        out.append(('ok' if team else 'info', 'PUBG: Takım ses kanalı', 'Açık' if team else 'Kapalı', 'Açık',
                    'Discord kullanıyorsan kapatabilirsin; yoksa takım seni iki kez (yankılı) duyabilir.'))
        if d.get('bIsVoiceInputMute') == 'True':
            out.append(('bad', 'PUBG: Mikrofon sessizde', 'Evet', 'Hayır', 'Oyun içi mikrofon kapalı, takım seni duymaz.'))

    # Discord
    dv = discord_voice()
    run = any((p.info['name'] or '').lower().startswith('discord') for p in psutil.process_iter(['name']))
    if dv is None:
        out.append(('info', 'Discord', 'kurulu değil', '-', 'Discord kullanınca ayarları burada kontrol edilir.'))
    elif not dv:
        out.append(('info', 'Discord ayarları', 'okunamadı', 'Elle kontrol et',
                    'Discord → Kullanıcı Ayarları → Ses ve Görüntü: Gürültü Engelleme = Krisp, Yankı Engelleme açık, '
                    'Giriş modu Bas-Konuş ya da Ses Etkinliği (otomatik hassasiyet kapalı, eşik ~ -50 dB).'))
    else:
        mode = dv.get('mode', '')
        mo = dv.get('modeOptions') or {}
        if mode == 'PUSH_TO_TALK':
            out.append(('ok', 'Discord: Giriş modu', 'Bas-Konuş', '-', 'Arka plan sesi hiç gitmez.'))
        else:
            thr, auto = mo.get('threshold'), mo.get('autoThreshold', True)
            good = (not auto) and thr is not None and thr >= -55
            out.append(('ok' if good else 'warn', 'Discord: Giriş modu', 'Ses Etkinliği' + (' (otomatik hassasiyet)' if auto else
                        f' (eşik {thr} dB)'), 'Bas-Konuş ya da eşik -50 dB',
                        'Otomatik hassasiyet oyunda klavye ve ateş sesini de konuşma sanabilir. Otomatiği kapat, eşiği -50 dB '
                        'civarına getir ya da Bas-Konuş kullan.'))
        krisp = dv.get('noiseCancellation')
        std = dv.get('noiseSuppression')
        out.append(('ok' if krisp else 'bad', 'Discord: Gürültü engelleme', 'Krisp' if krisp else ('Standart' if std else 'Kapalı'),
                    'Krisp', 'Krisp klavye, fan, köpek, oda sesini temizler; Discord kalitesinin asıl kaynağı budur.'))
        if dv.get('echoCancellation') is False:
            out.append(('warn', 'Discord: Yankı engelleme', 'Kapalı', 'Açık',
                        'Kulaklık yerine hoparlör kullanıyorsan oyun sesi mikrofondan geri gider.'))
        if dv.get('automaticGainControl') is False:
            out.append(('info', 'Discord: Otomatik kazanç', 'Kapalı', 'Açık', 'Sesin bazen kısık bazen yüksek gidiyorsa aç.'))
        iv = dv.get('inputVolume')
        if isinstance(iv, (int, float)) and iv > 100:
            out.append(('warn', 'Discord: Giriş seviyesi', f'%{iv:.0f}', '%100', '100\'ün üstü sesi bozar ve gürültüyü artırır.'))
        if run and d and d.get('bUseTeamVoice', 'True') == 'True':
            out.append(('info', 'Discord ve PUBG sesi birlikte açık', 'Evet', 'Birini kullan',
                        'Takımla Discord\'dan konuşuyorsanız PUBG takım sesini kapatın: hem yankı hem çift ses olmaz.'))
    return out


def apply_voice():
    """Güvenli olanları uygular: PUBG bas-konuş ve herkese açık kanal (oyun kapalıyken), mikrofon seviyesi."""
    msgs = []
    if any((p.info['name'] or '').lower() == GAME.lower() for p in psutil.process_iter(['name'])):
        msgs.append('PUBG açık: oyun içi ses ayarları oyun kapanınca uygulanabilir (oyun kapanırken eski ayarı yazar).')
    elif os.path.exists(INI):
        with open(INI, encoding='utf-8', errors='ignore', newline='') as f:
            txt = f.read()
        new = txt
        for k, v in (('bUsePushToTalk', 'True'), ('bUseGlobalVoice', 'False'), ('bIsVoiceInputMute', 'False')):
            new = re.sub(rf'(?m)^{k}=[^\r\n]*', f'{k}={v}', new)
        if new != txt:
            shutil.copy2(INI, INI + f'.izleyici_yedek_{datetime.datetime.now():%Y%m%d_%H%M%S}')
            with open(INI, 'w', encoding='utf-8', newline='') as f:
                f.write(new)
            msgs.append('PUBG: Bas-konuş açık, herkese açık kanal kapalı, mikrofon açık (yedek alındı)')
    try:
        mi = mic_info()
        if mi and mi['vol'] is not None and not 60 <= mi['vol'] <= 95 and set_mic_volume(80):
            msgs.append(f"Mikrofon seviyesi %{mi['vol']} → %80")
    except Exception:
        pass
    if not msgs:
        msgs.append('Uygulanacak bir şey yoktu.')
    msgs.append('Discord ayarları dışarıdan değiştirilemez: yukarıdaki önerileri Discord → Ses ve Görüntü\'den yap.')
    return msgs


# ---------------- Maç tekrarı (resmî PUBG telemetrisi, pubg.sh benzeri) ----------------
REPLAYS = os.path.join(DATA, 'tekrarlar')
MAPDIR = os.path.join(DATA, 'haritalar')
ASSETS = 'https://raw.githubusercontent.com/pubg/api-assets/master/'
ASSETS_LFS = 'https://media.githubusercontent.com/media/pubg/api-assets/master/'
# telemetri harita adı: (görünen ad, resmî resim adı, boyut cm) — boyutlar PUBG geliştirici belgelerinden
MAP_INFO = {'Baltic_Main': ('Erangel', 'Erangel_Main', 816000), 'Erangel_Main': ('Erangel', 'Erangel_Main', 816000),
            'Desert_Main': ('Miramar', 'Miramar_Main', 816000), 'Savage_Main': ('Sanhok', 'Sanhok_Main', 408000),
            'DihorOtok_Main': ('Vikendi', 'Vikendi_Main', 816000), 'Summerland_Main': ('Karakin', 'Karakin_Main', 204000),
            'Tiger_Main': ('Taego', 'Taego_Main', 816000), 'Kiki_Main': ('Deston', 'Deston_Main', 816000),
            'Chimera_Main': ('Paramo', 'Paramo_Main', 306000), 'Heaven_Main': ('Haven', 'Haven_Main', 102000),
            'Neon_Main': ('Rondo', 'Rondo_Main', 816000), 'Range_Main': ('Camp Jackal', 'Camp_Jackal_Main', 204000)}
MODE_TR = {'squad-fpp': 'Squad FPP', 'squad': 'Squad TPP', 'duo-fpp': 'Duo FPP', 'duo': 'Duo TPP', 'solo-fpp': 'Solo FPP',
           'solo': 'Solo TPP', 'tdm': 'Takım Ölüm Maçı'}


def http_bytes(url, timeout=60, progress=None, headers=None):
    req = urllib.request.Request(url, headers=dict({'User-Agent': 'PUBG-Izleyici', 'Accept-Encoding': 'gzip'}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        total, chunks, done = int(r.headers.get('Content-Length') or 0), [], 0
        while True:
            c = r.read(1 << 18)
            if not c:
                break
            chunks.append(c); done += len(c)
            if progress and total:
                progress(done / total)
    b = b''.join(chunks)
    import gzip
    return gzip.decompress(b) if b[:2] == b'\x1f\x8b' else b


def recent_matches(key, name='', limit=15):
    """Son maçların özeti (oyuncu sorgusu 1 istek; maç sorguları PUBG'nin hız sınırına takılmaz)."""
    if name:
        pl = pubg_get('/players?filter[playerNames]=' + urllib.parse.quote(name), key)['data'][0]
    else:
        aid = account_id_from_ini()
        if not aid:
            raise ValueError('Hesap kimliği bulunamadı, PUBG Hesap sekmesinde oyuncu adını yaz.')
        pl = pubg_get('/players/' + aid, key)['data']
    aid = pl['id']
    ids = [x['id'] for x in pl.get('relationships', {}).get('matches', {}).get('data', [])][:limit]
    return aid, pl['attributes']['name'], ids


def match_summary(mid, key, aid):
    d = pubg_get('/matches/' + mid, key)
    a = d['data']['attributes']
    inc = d.get('included', [])
    tel = next((x['attributes'].get('URL') for x in inc if x.get('type') == 'asset'), None)
    parts = {x['id']: x['attributes']['stats'] for x in inc if x.get('type') == 'participant'}
    me = next((s for s in parts.values() if s.get('playerId') == aid), {}) or {}
    ranks = {s.get('playerId'): s.get('winPlace') for s in parts.values()}
    return {'id': mid, 'tel': tel, 'map': a.get('mapName'), 'mode': a.get('gameMode', ''), 'type': a.get('matchType', ''),
            'date': a.get('createdAt', ''), 'dur': a.get('duration', 0), 'rank': me.get('winPlace'), 'kills': me.get('kills', 0),
            'dmg': me.get('damageDealt', 0), 'ranks': ranks, 'aid': aid}


def _ts(s):
    s = s.rstrip('Z')
    if '.' in s:
        a, b = s.split('.', 1)
        s = a + '.' + b[:6]
    return datetime.datetime.fromisoformat(s).replace(tzinfo=datetime.timezone.utc).timestamp()


_WEAPONS = {}


def weapon_names():
    if not _WEAPONS:
        pth = os.path.join(MAPDIR, 'silahlar.json')
        try:
            with open(pth, encoding='utf-8') as f:
                _WEAPONS.update(json.load(f))
        except Exception:
            try:
                _WEAPONS.update(json.loads(http_bytes(ASSETS + 'dictionaries/telemetry/damageCauserName.json', 20)))
                os.makedirs(MAPDIR, exist_ok=True)
                with open(pth, 'w', encoding='utf-8') as f:
                    json.dump(_WEAPONS, f)
            except Exception:
                pass
    return _WEAPONS


def replay_data(events, m):
    """Telemetriyi tekrar sayfasının kullandığı küçük veriye çevirir (20 MB → birkaç yüz KB).
    Koordinatlar harita boyutuna bölünür (0-1), süre maç başlangıcından saniye."""
    mapraw = next((e.get('mapName') for e in events if e['_T'] == 'LogMatchStart'), m['map'])
    mname, _, size = MAP_INFO.get(mapraw, (mapraw, '', 816000))
    t0 = _ts(next(e['_D'] for e in events if e['_T'] == 'LogMatchStart'))
    wn = weapon_names()
    W = lambda c: wn.get(c, (c or '').replace('Weap', '').replace('_C', '') or '?')
    n = lambda v: round(v / size, 5)
    P, aid, myteam = {}, m['aid'], None

    def who(c, t):
        if not isinstance(c, dict) or not c.get('accountId'):
            return None
        i = c['accountId']
        p = P.get(i)
        if p is None:
            p = P[i] = {'name': c.get('name', '?'), 'team': c.get('teamId', 0), 'bot': c.get('type') == 'user_ai' or i.startswith('ai.'),
                        'rank': m['ranks'].get(i), 'pos': [], 'death': None, 'dx': 0, 'dy': 0, 'knocks': []}
        loc = c.get('location') or {}
        if t >= 0 and (loc.get('x') or loc.get('y')):
            p['pos'].append([round(t, 1), n(loc['x']), n(loc['y']), round(c.get('health', 100))])
        return p
    kills, shots, drops, zones, phases = [], [], [], [], []
    landing = None
    for e in events:
        typ = e['_T']
        t = _ts(e['_D']) - t0 if '_D' in e else 0
        if typ == 'LogMatchStart':
            for ch in e.get('characters', []):
                who(ch.get('character'), -1)
            continue
        for f in ('character', 'attacker', 'victim', 'killer', 'finisher', 'dBNOMaker'):
            if f in e:
                who(e[f], t)
        if t < 0:
            continue
        if typ == 'LogGameStatePeriodic':
            g = e['gameState']
            z = [round(t, 1)]
            for k in ('safetyZone', 'poisonGasWarning', 'redZone'):
                pos, r = g.get(k + 'Position') or {}, g.get(k + 'Radius') or 0
                z += [n(pos.get('x', 0)), n(pos.get('y', 0)), n(r)]
            zones.append(z)
        elif typ == 'LogPlayerKillV2':
            v = who(e.get('victim'), t)
            if not v:
                continue
            v['death'] = round(t, 1)
            loc = e['victim'].get('location') or {}
            v['dx'], v['dy'] = n(loc.get('x', 0)), n(loc.get('y', 0))
            k = e.get('finisher') or e.get('killer') or {}
            info = e.get('finishDamageInfo') or e.get('killerDamageInfo') or {}
            cat = info.get('damageTypeCategory', '')
            wpn = 'Mavi bölge' if cat == 'Damage_BlueZone' else ('Kırmızı bölge' if cat == 'Damage_Explosion_RedZone' else
                                                                 W(info.get('damageCauserName')))
            kills.append({'t': round(t, 1), 'k': (k or {}).get('name', ''), 'v': v['name'], 'w': wpn,
                          'd': round((info.get('distance') or 0) / 100), 'hs': info.get('damageReason') == 'HeadShot',
                          'x': v['dx'], 'y': v['dy']})
        elif typ == 'LogPlayerMakeGroggy':
            v = who(e.get('victim'), t)
            if v:
                v['knocks'].append([round(t, 1), None])
        elif typ == 'LogPlayerRevive':
            v = who(e.get('victim'), t)
            if v and v['knocks'] and v['knocks'][-1][1] is None:
                v['knocks'][-1][1] = round(t, 1)
        elif typ == 'LogPlayerTakeDamage' and e.get('damageTypeCategory') == 'Damage_Gun' and e.get('attacker'):
            a, v = e['attacker'].get('location') or {}, e['victim'].get('location') or {}
            if a.get('x') and v.get('x'):
                shots.append([round(t, 1), n(a['x']), n(a['y']), n(v['x']), n(v['y']), e['attacker'].get('teamId', 0)])
        elif typ == 'LogCarePackageLand':
            loc = (e.get('itemPackage') or {}).get('location') or {}
            drops.append([round(t, 1), n(loc.get('x', 0)), n(loc.get('y', 0))])
        elif typ == 'LogPhaseChange':
            phases.append(round(t, 1))
        elif typ == 'LogParachuteLanding' and e['character'].get('accountId') == aid:
            landing = t
    dur = max([m.get('dur') or 0] + [p['pos'][-1][0] for p in P.values() if p['pos']])
    for i, p in P.items():
        p['pos'].sort(key=lambda a: a[0])
        out = []
        for a in p['pos']:  # 0.5 sn'den sık noktaları seyrelt
            if out and a[0] - out[-1][0] < 0.5:
                out[-1] = a
            else:
                out.append(a)
        p['pos'] = out
        p['knocks'] = [[a, b if b is not None else (p['death'] if p['death'] is not None else dur)] for a, b in p['knocks']]
        if i == aid:
            myteam = p['team']
    P = {i: p for i, p in P.items() if p['pos']}
    shots.sort(key=lambda s: s[0])
    try:
        date = datetime.datetime.fromisoformat(m['date'].rstrip('Z')).replace(tzinfo=datetime.timezone.utc).astimezone()
        date = date.strftime('%d.%m.%Y %H:%M')
    except Exception:
        date = m['date']
    return {'mapName': mname, 'mode': MODE_TR.get(m['mode'], m['mode']), 'date': date, 'myRank': m.get('rank'),
            'myKills': m.get('kills', 0), 'myDamage': m.get('dmg', 0), 'teams': len({p['team'] for p in P.values()}),
            'dur': round(dur, 1), 'start': round(max(0, (landing or 0) - 15), 1), 'me': aid, 'myTeam': myteam,
            'players': P, 'zones': zones, 'kills': kills, 'shots': shots, 'drops': drops, 'phases': phases}


def map_low(img, progress=None):
    """Küçük harita resmi (~1 MB, 819 px) — tekrar hemen açılsın diye."""
    os.makedirs(MAPDIR, exist_ok=True)
    name = 'Rondo_Main_No_Text_Low_Res.png' if img == 'Rondo_Main' else f'{img}_Low_Res.png'
    pth = os.path.join(MAPDIR, name)
    if not os.path.exists(pth):
        b = http_bytes(ASSETS + 'Assets/Maps/' + name, 60, progress)
        with open(pth + '.part', 'wb') as f:
            f.write(b)
        os.replace(pth + '.part', pth)
    return pth


def map_tiles(img):
    """Hazır yüksek çözünürlüklü döşeme klasörü ve en yüksek yakınlaştırma düzeyi, yoksa (None, 0)."""
    d = os.path.join(MAPDIR, img + '_hd')
    try:
        with open(os.path.join(d, 'hazir.txt')) as f:
            return d, int(f.read().strip())
    except (OSError, ValueError):
        return None, 0


def build_hd_tiles(img, progress=None):
    """Resmî yüksek çözünürlüklü haritayı (75-120 MB) bir kez indirir ve 256 px'lik döşemelere böler.
    Böylece tekrar sayfası yakınlaştırınca da keskin kalır ve sadece görünen parçaları yükler."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    d = os.path.join(MAPDIR, img + '_hd')
    src = os.path.join(MAPDIR, img + '_High_Res.png')
    pr = progress or (lambda f: None)
    if not os.path.exists(src):
        b = http_bytes(ASSETS_LFS + 'Assets/Maps/' + img + '_High_Res.png', 600, lambda f: pr(0.7 * f))
        with open(src + '.part', 'wb') as f:
            f.write(b)
        os.replace(src + '.part', src)
        del b
    im = Image.open(src).convert('RGB')
    size = im.size[0]
    maxz = max(0, (size // 256).bit_length() - 1)
    side = 256 << maxz
    if im.size != (side, side):
        im = im.resize((side, side), Image.LANCZOS)
    total = sum(4 ** z for z in range(maxz + 1))
    done = 0
    for z in range(maxz, -1, -1):
        n_ = 1 << z
        for x in range(n_):
            os.makedirs(os.path.join(d, str(z), str(x)), exist_ok=True)
            for y in range(n_):
                im.crop((x * 256, y * 256, x * 256 + 256, y * 256 + 256)).save(
                    os.path.join(d, str(z), str(x), f'{y}.jpg'), quality=82, optimize=True)
                done += 1
                if done % 32 == 0:
                    pr(0.7 + 0.3 * done / total)
        if z:
            im = im.resize((im.size[0] // 2, im.size[1] // 2), Image.LANCZOS)
    with open(os.path.join(d, 'hazir.txt'), 'w') as f:
        f.write(str(maxz))
    try:
        os.remove(src)  # döşemeler hazır, 100 MB'lık kaynağı tutmaya gerek yok
    except OSError:
        pass
    return d, maxz


def build_replay(m, progress=None):
    """Telemetriyi indirir, tekrar sayfasını oluşturur, dosya yolunu döner."""
    pr = progress or (lambda txt, f=None: None)
    os.makedirs(REPLAYS, exist_ok=True)
    pr('Telemetri indiriliyor…', 0)
    events = json.loads(http_bytes(m['tel'], 120, lambda f: pr('Telemetri indiriliyor…', 0.6 * f)))
    pr('Maç hesaplanıyor…', 0.65)
    data = replay_data(events, m)
    try:
        data['report'] = coach_report(events, m, data)  # maç sonu koç raporu
    except Exception:
        data['report'] = None
    del events
    img = MAP_INFO.get(m['map'], ('', 'Erangel_Main', 0))[1]
    pr('Harita hazırlanıyor…', 0.8)
    low = map_low(img, lambda f: pr('Harita indiriliyor…', 0.8 + 0.15 * f))
    tiles, maxz = map_tiles(img)
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    from pathlib import Path
    html = (REPLAY_HTML.replace('__DATA__', js)
            .replace('__TILES__', json.dumps(Path(tiles).as_uri() + '/{z}/{x}/{y}.jpg') if tiles else 'null')
            .replace('__MAXZ__', str(maxz)).replace('__LOWIMG__', json.dumps(Path(low).as_uri())))
    out = os.path.join(REPLAYS, f"{m['id']}.html")
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    pr('Hazır', 1)
    return out, img, bool(tiles), data.get('report')


# Tekrar sayfası: Leaflet (harita) + tek tuval katmanı (oyuncular, bölgeler, atışlar) 60 fps çizilir.
REPLAY_HTML = r'''<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Maç Tekrarı · PUBG İzleyici</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
:root{--bg:#0e1014;--card:#161a21;--card2:#1d222b;--line:#262b36;--txt:#e8eaed;--sub:#8b93a1;--acc:#4cc2ff;--ok:#3ddc84;--warn:#ffc845;--bad:#ff5c5c;--me:#ffd84d}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--txt);font:13px/1.4 "Segoe UI",system-ui,sans-serif;overflow:hidden}
#app{display:grid;grid-template-columns:1fr 330px;grid-template-rows:56px 1fr 64px;height:100%}
header{grid-column:1/3;display:flex;align-items:center;gap:18px;padding:0 18px;border-bottom:1px solid var(--line);background:#0b0d11}
header .logo{font:700 18px "Bahnschrift","Segoe UI";color:var(--acc);letter-spacing:.5px}
header .t{font-weight:600;font-size:15px}
header .chips{display:flex;gap:8px;margin-left:auto}
.chip{background:var(--card2);border:1px solid var(--line);padding:4px 10px;border-radius:999px;color:var(--sub);white-space:nowrap}
.chip b{color:var(--txt)}
#mapwrap{position:relative;background:#0a0c0f}
#map{position:absolute;inset:0;background:#0a0c0f}
#fx{position:absolute;inset:0;pointer-events:none;z-index:450}
#tip{position:absolute;z-index:500;pointer-events:none;background:rgba(14,16,20,.92);border:1px solid var(--line);border-radius:8px;padding:6px 9px;display:none;white-space:nowrap}
#tip .n{font-weight:600}#tip .s{color:var(--sub);font-size:12px}
.mapbtns{position:absolute;right:12px;top:12px;z-index:600;display:flex;flex-direction:column;gap:6px}
.mapbtns button,.toggles label{background:rgba(22,26,33,.92);border:1px solid var(--line);color:var(--txt);border-radius:8px;cursor:pointer}
.mapbtns button{width:34px;height:34px;font-size:17px}
.mapbtns button:hover{border-color:var(--acc)}
.toggles{position:absolute;left:12px;top:12px;z-index:600;display:flex;gap:6px;flex-wrap:wrap;max-width:70%}
.toggles label{padding:5px 10px;display:flex;gap:6px;align-items:center;user-select:none;font-size:12px}
.toggles input{accent-color:var(--acc);margin:0}
#follow{position:absolute;left:50%;transform:translateX(-50%);bottom:12px;z-index:600;background:rgba(76,194,255,.15);border:1px solid var(--acc);color:var(--acc);padding:5px 12px;border-radius:999px;display:none;cursor:pointer}
aside{border-left:1px solid var(--line);background:var(--card);display:flex;flex-direction:column;min-height:0}
.tabs{display:flex;border-bottom:1px solid var(--line)}
.tabs button{flex:1;background:none;border:0;color:var(--sub);padding:12px 0;font:600 13px "Segoe UI";cursor:pointer;border-bottom:2px solid transparent}
.tabs button.on{color:var(--txt);border-bottom-color:var(--acc)}
.pane{flex:1;overflow:auto;padding:8px 10px;display:none}
.pane.on{display:block}
.pane::-webkit-scrollbar{width:8px}.pane::-webkit-scrollbar-thumb{background:#2c3240;border-radius:4px}
.team{background:var(--card2);border:1px solid var(--line);border-radius:10px;margin-bottom:6px;overflow:hidden}
.team.mine{border-color:var(--me)}
.team .th{display:flex;align-items:center;gap:8px;padding:6px 10px;color:var(--sub);font-size:12px}
.team .th .sw{width:10px;height:10px;border-radius:50%}
.team .th .rk{margin-left:auto;font-weight:700;color:var(--txt)}
.pl{display:flex;align-items:center;gap:8px;padding:5px 10px;cursor:pointer;border-top:1px solid #20252e}
.pl:hover{background:#232a35}
.pl .st{width:8px;height:8px;border-radius:50%;background:var(--ok);flex:none}
.pl.knock .st{background:var(--warn)}.pl.dead{opacity:.45}.pl.dead .st{background:var(--bad)}
.pl .nm{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pl .k{margin-left:auto;color:var(--sub);font-size:12px}
.pl .bot{font-size:10px;color:var(--sub);border:1px solid var(--line);border-radius:4px;padding:0 4px}
.kf{display:grid;grid-template-columns:44px 1fr;gap:2px 8px;padding:7px 8px;border-bottom:1px solid #20252e;cursor:pointer;border-radius:6px}
.kf:hover{background:#232a35}
.kf .tm{color:var(--sub);font-variant-numeric:tabular-nums}
.kf .who{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.kf .wp{grid-column:2;color:var(--sub);font-size:12px}
.kf.mine .who{color:var(--me)}
.kf .hs{color:var(--bad);font-weight:700}
footer{grid-column:1/3;display:flex;align-items:center;gap:14px;padding:0 18px;border-top:1px solid var(--line);background:#0b0d11}
#play{width:44px;height:44px;border-radius:50%;border:0;background:var(--acc);color:#0e1014;font-size:18px;cursor:pointer;flex:none}
#time{font:600 15px "Bahnschrift","Segoe UI";font-variant-numeric:tabular-nums;min-width:120px}
#bar{position:relative;flex:1;height:36px}
#seek{position:absolute;inset:0;width:100%;margin:0;opacity:0;cursor:pointer;z-index:2}
#track{position:absolute;left:0;right:0;top:15px;height:6px;border-radius:3px;background:var(--line)}
#fill{position:absolute;left:0;top:15px;height:6px;border-radius:3px;background:var(--acc);width:0}
#knob{position:absolute;top:10px;width:16px;height:16px;border-radius:50%;background:#fff;margin-left:-8px;box-shadow:0 0 0 4px rgba(76,194,255,.35)}
.tick{position:absolute;top:8px;width:2px;height:20px;border-radius:1px;background:var(--me);opacity:.9}
.tick.die{background:var(--bad);width:3px}
.tick.ph{background:#6f7a8c;height:10px;top:13px;opacity:.6}
#speed{background:var(--card2);color:var(--txt);border:1px solid var(--line);border-radius:8px;padding:6px 8px;font:600 13px "Segoe UI"}
#alive{color:var(--sub);white-space:nowrap}#alive b{color:var(--txt)}
.leaflet-container{background:#0a0c0f;outline:0}
.hint{color:var(--sub);font-size:11px;padding:8px 10px;border-top:1px solid var(--line)}
.rgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:10px}
.rc{background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:8px 10px}
.rc .v{font:700 18px "Bahnschrift","Segoe UI"}.rc .l{color:var(--sub);font-size:11px}
.sec{font-weight:700;margin:12px 2px 6px;color:var(--txt)}
.death{background:linear-gradient(135deg,rgba(255,92,92,.14),rgba(255,92,92,.04));border:1px solid rgba(255,92,92,.45);border-radius:10px;padding:10px;margin-bottom:8px}
.death b{color:#ffb0b0}.death button{margin-top:8px;background:none;border:1px solid var(--line);color:var(--acc);border-radius:6px;padding:4px 10px;cursor:pointer;font:600 12px "Segoe UI"}
.tipr{display:flex;gap:8px;padding:7px 8px;border-radius:8px;margin-bottom:4px;background:var(--card2)}
.tipr .i{flex:none;font-weight:700}.tipr.bad .i{color:var(--bad)}.tipr.warn .i{color:var(--warn)}.tipr.info .i{color:var(--acc)}.tipr.good .i{color:var(--ok)}
table.wt{width:100%;border-collapse:collapse;font-size:12px}table.wt td,table.wt th{padding:5px 6px;border-bottom:1px solid #20252e;text-align:right}
table.wt th{color:var(--sub);font-weight:600}table.wt td:first-child,table.wt th:first-child{text-align:left}
#chart{width:100%;height:120px;background:var(--card2);border:1px solid var(--line);border-radius:8px;cursor:pointer;display:block}
.legend{color:var(--sub);font-size:11px;margin:4px 2px 0}.legend i{display:inline-block;width:10px;height:3px;margin:0 4px 2px 8px;vertical-align:middle}
@media (max-width:900px){#app{grid-template-columns:1fr;grid-template-rows:56px 1fr 64px 240px}aside{grid-row:4;border-left:0;border-top:1px solid var(--line)}footer{grid-row:3}}
</style>
</head>
<body>
<div id="app">
  <header>
    <div class="logo">PUBG</div>
    <div class="t" id="title"></div>
    <div class="chips" id="chips"></div>
  </header>
  <div id="mapwrap">
    <div id="map"></div>
    <canvas id="fx"></canvas>
    <div id="tip"></div>
    <div class="toggles">
      <label><input type="checkbox" id="oNames" checked>Tüm isimler</label>
      <label><input type="checkbox" id="oTracer" checked>Atış çizgileri</label>
      <label><input type="checkbox" id="oPath" checked>Rotam</label>
      <label><input type="checkbox" id="oDeaths" checked>Ölüm yerleri</label>
      <label><input type="checkbox" id="oDrops" checked>Kare paket</label>
      <label><input type="checkbox" id="oBots" checked>Botlar</label>
    </div>
    <div class="mapbtns">
      <button id="zin" title="Yakınlaştır">+</button>
      <button id="zout" title="Uzaklaştır">−</button>
      <button id="zfit" title="Tüm harita">⤢</button>
      <button id="zme" title="Beni takip et">◎</button>
    </div>
    <div id="follow"></div>
  </div>
  <aside>
    <div class="tabs"><button class="on" data-p="pRep">Rapor</button><button data-p="pTeams">Takımlar</button><button data-p="pKills">Öldürmeler</button></div>
    <div class="pane on" id="pRep"></div>
    <div class="pane" id="pTeams"></div>
    <div class="pane" id="pKills"></div>
    <div class="hint">Boşluk: oynat/durdur · ←/→: 10 sn · +/−: hız · oyuncuya tıkla: takip et</div>
  </aside>
  <footer>
    <button id="play" title="Oynat (boşluk)">▶</button>
    <div id="time">00:00 / 00:00</div>
    <div id="bar"><div id="track"></div><div id="fill"></div><div id="ticks"></div><div id="knob"></div><input type="range" id="seek" min="0" max="1000" value="0" step="1"></div>
    <select id="speed"><option>1</option><option>5</option><option selected>10</option><option>20</option><option>40</option><option>80</option></select>
    <div id="alive"></div>
  </footer>
</div>
<script>
const D = __DATA__;
const TILES = __TILES__, MAXZ = __MAXZ__, LOWIMG = __LOWIMG__;
const W = 256, B = [[-W, 0], [0, W]];
const ll = (x, y) => L.latLng(-y * W, x * W);
const map = L.map('map', {crs: L.CRS.Simple, minZoom: 0, maxZoom: 8, zoomSnap: 1, zoomDelta: 1, wheelPxPerZoomLevel: 120,
  attributionControl: false, zoomControl: false, zoomAnimation: false, fadeAnimation: false, maxBounds: [[-W * 1.2, -W * .2], [W * .2, W * 1.2]]});
if (TILES) L.tileLayer(TILES, {minZoom: 0, maxNativeZoom: MAXZ, maxZoom: 8, noWrap: true, bounds: B, tileSize: 256}).addTo(map);
else L.imageOverlay(LOWIMG, B).addTo(map);
map.fitBounds(B);

const $ = id => document.getElementById(id);
const fmt = s => { s = Math.max(0, Math.floor(s)); return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0'); };
const P = D.players, ids = Object.keys(P);
const teamColor = {};
const hue = t => { let h = (t * 137.508) % 360; if (h > 40 && h < 70) h += 40; return `hsl(${h},80%,60%)`; };
for (const id of ids) { const p = P[id]; if (!(p.team in teamColor)) teamColor[p.team] = p.team === D.myTeam ? getComputedStyle(document.documentElement).getPropertyValue('--me').trim() : hue(p.team); }
const kidx = {}; for (const id of ids) kidx[P[id].name] = id;

// başlık
$('title').textContent = `${D.mapName} · ${D.mode}`;
const me = P[D.me] || {};
$('chips').innerHTML = [`<span class="chip">${D.date}</span>`, D.myRank ? `<span class="chip">Sıra <b>#${D.myRank}</b></span>` : '',
  `<span class="chip">Öldürme <b>${D.myKills}</b></span>`, `<span class="chip">Hasar <b>${Math.round(D.myDamage)}</b></span>`,
  `<span class="chip">${D.teams} takım · ${ids.length} oyuncu</span>`].join('');

// zaman çizelgesi işaretleri
const ticks = [];
for (const k of D.kills) if (P[kidx[k.k]] && P[kidx[k.k]].team === D.myTeam) ticks.push(`<div class="tick" style="left:${k.t / D.dur * 100}%" title="${fmt(k.t)} ${k.k} → ${k.v}"></div>`);
if (me.death != null) ticks.push(`<div class="tick die" style="left:${me.death / D.dur * 100}%" title="${fmt(me.death)} öldün"></div>`);
if (D.report) for (const f of D.report.fights) ticks.push(`<div class="tick ph" style="left:${f[0] / D.dur * 100}%;background:#ffc845;opacity:.5"></div>`);
for (const z of D.phases) ticks.push(`<div class="tick ph" style="left:${z / D.dur * 100}%"></div>`);
$('ticks').innerHTML = ticks.join('');

// konum ara değerleme
function pos(p, t) {
  const a = p.pos; if (!a.length || t < a[0][0]) return null;
  let lo = 0, hi = a.length - 1;
  if (t >= a[hi][0]) return a[hi];
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (a[m][0] <= t) lo = m; else hi = m; }
  const A = a[lo], C = a[hi], f = (t - A[0]) / (C[0] - A[0] || 1);
  return [t, A[1] + (C[1] - A[1]) * f, A[2] + (C[2] - A[2]) * f, A[3]];
}
function zoneAt(t) {
  const z = D.zones; if (!z.length || t < z[0][0]) return null;
  let i = 0; while (i + 1 < z.length && z[i + 1][0] <= t) i++;
  const A = z[i], C = z[i + 1];
  if (!C) return A;
  const f = (t - A[0]) / (C[0] - A[0] || 1), r = A.slice();
  for (let j = 1; j <= 3; j++) r[j] = A[j] + (C[j] - A[j]) * f;  // mavi bölge yumuşak daralır
  return r;
}
const state = (p, t) => p.death != null && t >= p.death ? 'dead' : (p.knocks.some(k => t >= k[0] && t < k[1]) ? 'knock' : 'alive');

// tuval
const cv = $('fx'), cx = cv.getContext('2d');
function sizeCanvas() { const r = $('mapwrap').getBoundingClientRect(), d = devicePixelRatio || 1; cv.width = r.width * d; cv.height = r.height * d; cv.style.width = r.width + 'px'; cv.style.height = r.height + 'px'; cx.setTransform(d, 0, 0, d, 0, 0); }
addEventListener('resize', () => { sizeCanvas(); draw(); }); sizeCanvas();
const pt = (x, y) => map.latLngToContainerPoint(ll(x, y));
const px = r => map.latLngToContainerPoint(ll(r, 0)).x - map.latLngToContainerPoint(ll(0, 0)).x;

let T = 0, playing = false, followId = null, hoverId = null, shown = [];
const O = id => $(id).checked;
function circle(z, ix, color, fill, width, dash) {
  const r = z[ix + 2]; if (!r) return;
  const c = pt(z[ix], z[ix + 1]), R = px(r);
  cx.beginPath(); cx.arc(c.x, c.y, R, 0, Math.PI * 2);
  if (fill) { cx.fillStyle = fill; cx.fill(); }
  cx.setLineDash(dash || []); cx.lineWidth = width; cx.strokeStyle = color; cx.stroke(); cx.setLineDash([]);
}
function draw() {
  const w = cv.width / (devicePixelRatio || 1), h = cv.height / (devicePixelRatio || 1);
  cx.clearRect(0, 0, w, h);
  const z = zoneAt(T);
  if (z) {
    if (z[3]) {  // mavi bölge dışı karartma
      const c = pt(z[1], z[2]);
      cx.save(); cx.beginPath(); cx.rect(0, 0, w, h); cx.arc(c.x, c.y, px(z[3]), 0, Math.PI * 2, true);
      cx.fillStyle = 'rgba(40,90,255,.16)'; cx.fill('evenodd'); cx.restore();
    }
    circle(z, 1, '#3d7bff', null, 2.5);
    circle(z, 4, '#ffffff', null, 2, [8, 6]);
    circle(z, 7, 'rgba(255,60,60,.9)', 'rgba(255,40,40,.18)', 1.5);
  }
  if (O('oDrops')) for (const d of D.drops) if (d[0] <= T) { const c = pt(d[1], d[2]); cx.fillStyle = '#ff7a2f'; cx.fillRect(c.x - 5, c.y - 5, 10, 10); cx.strokeStyle = '#2a1508'; cx.lineWidth = 1.5; cx.strokeRect(c.x - 5, c.y - 5, 10, 10); }
  if (O('oPath') && P[D.me]) {
    cx.beginPath(); let first = true;
    for (const a of P[D.me].pos) { if (a[0] > T) break; const c = pt(a[1], a[2]); first ? cx.moveTo(c.x, c.y) : cx.lineTo(c.x, c.y); first = false; }
    const cur = pos(P[D.me], T); if (cur && !first) { const c = pt(cur[1], cur[2]); cx.lineTo(c.x, c.y); }
    cx.strokeStyle = 'rgba(255,216,77,.55)'; cx.lineWidth = 2; cx.stroke();
  }
  if (O('oDeaths')) for (const id of ids) { const p = P[id]; if (p.death == null || T < p.death || (p.bot && !O('oBots'))) continue;
    const c = pt(p.dx, p.dy), s = p.team === D.myTeam ? 6 : 4; cx.strokeStyle = p.team === D.myTeam ? '#ff5c5c' : 'rgba(255,255,255,.55)'; cx.lineWidth = 2;
    cx.beginPath(); cx.moveTo(c.x - s, c.y - s); cx.lineTo(c.x + s, c.y + s); cx.moveTo(c.x + s, c.y - s); cx.lineTo(c.x - s, c.y + s); cx.stroke(); }
  if (O('oTracer')) for (const s of D.shots) { if (s[0] > T) break; const age = T - s[0]; if (age > 1.5) continue;
    const a = pt(s[1], s[2]), b = pt(s[3], s[4]); cx.globalAlpha = 1 - age / 1.5; cx.strokeStyle = teamColor[s[5]] || '#fff'; cx.lineWidth = s[5] === D.myTeam ? 2 : 1.3;
    cx.beginPath(); cx.moveTo(a.x, a.y); cx.lineTo(b.x, b.y); cx.stroke(); cx.globalAlpha = 1; }
  shown = [];
  const order = ids.slice().sort((a, b) => (P[a].team === D.myTeam) - (P[b].team === D.myTeam));
  cx.font = '600 11px "Segoe UI"'; cx.textAlign = 'center';
  for (const id of order) {
    const p = P[id]; if (p.bot && !O('oBots')) continue;
    const st = state(p, T); if (st === 'dead') continue;
    const q = pos(p, T); if (!q) continue;
    const c = pt(q[1], q[2]), mine = p.team === D.myTeam, isMe = id === D.me, r = isMe ? 7 : (mine ? 6 : 4.5);
    shown.push([id, c.x, c.y]);
    cx.beginPath(); cx.arc(c.x, c.y, r, 0, Math.PI * 2);
    cx.fillStyle = st === 'knock' ? '#ff5c5c' : teamColor[p.team]; cx.fill();
    cx.lineWidth = isMe ? 2.5 : 1.5; cx.strokeStyle = isMe ? '#fff' : 'rgba(0,0,0,.75)'; cx.stroke();
    if (id === followId || id === hoverId) { cx.beginPath(); cx.arc(c.x, c.y, r + 5, 0, Math.PI * 2); cx.strokeStyle = 'rgba(255,255,255,.8)'; cx.lineWidth = 1.5; cx.stroke(); }
    if (mine || O('oNames') && map.getZoom() >= 2.5 || id === hoverId) {
      cx.lineWidth = 3; cx.strokeStyle = 'rgba(0,0,0,.85)'; cx.strokeText(p.name, c.x, c.y - r - 5);
      cx.fillStyle = mine ? '#ffe9a0' : '#e8eaed'; cx.fillText(p.name, c.x, c.y - r - 5);
    }
  }
}

// yan panel
const teams = {};
for (const id of ids) (teams[P[id].team] = teams[P[id].team] || []).push(id);
const tlist = Object.keys(teams).map(Number).sort((a, b) => (b === D.myTeam) - (a === D.myTeam) || (P[teams[a][0]].rank || 99) - (P[teams[b][0]].rank || 99));
$('pTeams').innerHTML = tlist.map(t => `<div class="team${t === D.myTeam ? ' mine' : ''}"><div class="th"><span class="sw" style="background:${teamColor[t]}"></span>Takım ${t}<span class="rk">${P[teams[t][0]].rank ? '#' + P[teams[t][0]].rank : ''}</span></div>` +
  teams[t].map(id => `<div class="pl" data-id="${id}"><span class="st"></span><span class="nm">${P[id].name}</span>${P[id].bot ? '<span class="bot">BOT</span>' : ''}<span class="k"></span></div>`).join('') + '</div>').join('');
const kfHtml = k => { const mine = P[kidx[k.k]] && P[kidx[k.k]].team === D.myTeam || P[kidx[k.v]] && P[kidx[k.v]].team === D.myTeam;
  return `<div class="kf${mine ? ' mine' : ''}" data-t="${k.t}" data-x="${k.x}" data-y="${k.y}"><span class="tm">${fmt(k.t)}</span><span class="who">${k.k || '—'} ✕ ${k.v}</span><span class="wp">${k.w}${k.d ? ' · ' + k.d + ' m' : ''}${k.hs ? ' · <span class="hs">kafa</span>' : ''}</span></div>`; };
let lastKf = -1, lastSide = 0;
function side() {
  const now = performance.now(); if (now - lastSide < 250) return; lastSide = now;
  for (const el of document.querySelectorAll('.pl')) { const p = P[el.dataset.id], st = state(p, T);
    el.className = 'pl' + (st === 'dead' ? ' dead' : st === 'knock' ? ' knock' : '');
    const k = D.kills.filter(x => x.k === p.name && x.t <= T).length; el.querySelector('.k').textContent = k ? k + ' öldürme' : ''; }
  const n = D.kills.filter(k => k.t <= T).length;
  if (n !== lastKf) { lastKf = n; $('pKills').innerHTML = D.kills.filter(k => k.t <= T).reverse().map(kfHtml).join('') || '<div class="kf"><span></span><span class="who" style="color:var(--sub)">Henüz öldürme yok</span></div>'; }
  const alive = ids.filter(id => state(P[id], T) !== 'dead' && pos(P[id], T)).length;
  $('alive').innerHTML = `Hayatta <b>${alive}</b>`;
}
document.querySelectorAll('.tabs button').forEach(b => b.onclick = () => { document.querySelectorAll('.tabs button,.pane').forEach(e => e.classList.remove('on')); b.classList.add('on'); $(b.dataset.p).classList.add('on'); });
$('pTeams').onclick = e => { const el = e.target.closest('.pl'); if (el) setFollow(el.dataset.id); };
$('pKills').onclick = e => { const el = e.target.closest('.kf'); if (!el || !el.dataset.t) return; setFollow(null); seek(+el.dataset.t - 4); map.setView(ll(+el.dataset.x, +el.dataset.y), Math.max(map.getZoom(), 4)); };
function setFollow(id) { followId = id === followId ? null : id; $('follow').style.display = followId ? 'block' : 'none'; if (followId) $('follow').textContent = '◎ ' + P[followId].name + ' takip ediliyor · bırakmak için tıkla'; draw(); }
$('follow').onclick = () => setFollow(null);

// ipucu
$('mapwrap').addEventListener('mousemove', e => {
  const r = $('mapwrap').getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  let best = null, bd = 12;
  for (const s of shown) { const d = Math.hypot(s[1] - mx, s[2] - my); if (d < bd) { bd = d; best = s; } }
  hoverId = best ? best[0] : null;
  const tip = $('tip');
  if (best) { const p = P[best[0]], q = pos(p, T);
    tip.innerHTML = `<div class="n" style="color:${teamColor[p.team]}">${p.name}${p.bot ? ' (bot)' : ''}</div><div class="s">Takım ${p.team} · can ${q ? Math.round(q[3]) : '?'}${p.rank ? ' · sıra #' + p.rank : ''}</div>`;
    tip.style.display = 'block'; tip.style.left = (mx + 14) + 'px'; tip.style.top = (my + 10) + 'px'; } else tip.style.display = 'none';
  if (!playing) draw();
});
$('mapwrap').addEventListener('click', () => { if (hoverId) setFollow(hoverId); });

// maç sonu raporu
const RP = D.report;
function renderReport() {
  const el = $('pRep'); if (!RP) { el.innerHTML = '<div class="tipr info"><span class="i">i</span><span>Rapor yok.</span></div>'; return; }
  const card = (v, l) => `<div class="rc"><div class="v">${v}</div><div class="l">${l}</div></div>`;
  let h = '<div class="rgrid">' + card(RP.rank ? '#' + RP.rank : '—', 'Sıra') + card(RP.kills, 'Öldürme') + card(RP.dmg, 'Hasar') +
    card(fmt(RP.alive), 'Hayatta kalma') + card(RP.acc == null ? '—' : '%' + Math.round(RP.acc), 'İsabet (yaklaşık)') + card(RP.hits ? '%' + RP.hsPct : '—', 'Kafa vuruşu') + '</div>';
  if (RP.death) { const d = RP.death;
    h += `<div class="death">Öldün: <b>${fmt(d.t)}</b> · ${d.by || '—'} · ${d.w}${d.d ? ' · ' + d.d + ' m' : ''}${d.hs ? ' · kafadan' : ''}` +
      `${d.knocked_by && d.knocked_by !== d.by ? `<br><span style="color:var(--sub)">Seni düşüren: ${d.knocked_by}</span>` : ''}` +
      `<br><button onclick="goTo(${d.t - 12}, true)">▶ Ölümünden 12 sn öncesini izle</button></div>`; }
  const icon = {bad: '✖', warn: '⚠', info: 'ℹ'};
  const tips = RP.tips.map(t => `<div class="tipr ${t[0]}"><span class="i">${icon[t[0]]}</span><span>${t[1]}</span></div>`).join('') +
    RP.good.map(g => `<div class="tipr good"><span class="i">✔</span><span>${g}</span></div>`).join('');
  h += '<div class="sec">Bulgular ve öneriler</div>' + (tips || '<div class="tipr good"><span class="i">✔</span><span>Belirgin bir sorun yok.</span></div>');
  const extra = [];
  if (RP.landing != null) extra.push(`İniş: ${RP.landName || 'isimsiz bölge'} · ${fmt(RP.landing)}${RP.enemiesNear ? ` · 150 m içinde ${RP.enemiesNear} düşman` : ''}`);
  if (RP.firstFight != null) extra.push(`İlk çatışma: ${fmt(RP.firstFight)} · toplam ${RP.fights.length} çatışma`);
  extra.push(`Atılan mermi ~${RP.fired} · isabet ${RP.hits} · düşürme ${RP.knocks} · iyileşme ${RP.heals}`);
  extra.push(`Alınan hasar ${RP.dmgTaken}${RP.blueDmg ? ` (mavi bölge ${RP.blueDmg})` : ''}`);
  h += '<div class="sec">Maç özeti</div>' + extra.map(x => `<div class="tipr"><span class="i" style="color:var(--sub)">•</span><span>${x}</span></div>`).join('');
  if (RP.weapons.length) h += '<div class="sec">Silahlar</div><table class="wt"><tr><th>Silah</th><th>İsabet</th><th>Hasar</th><th>Kafa</th></tr>' +
    RP.weapons.map(w => `<tr><td>${w.w}</td><td>${w.hits}</td><td>${Math.round(w.dmg)}</td><td>${w.hs}</td></tr>`).join('') + '</table>';
  const P2 = RP.perf;
  h += '<div class="sec">Bilgisayar performansı (bu maç)</div>';
  if (P2) {
    h += '<div class="rgrid">' + card(P2.avg, 'Ort. FPS') + card(P2.fightFps == null ? '—' : P2.fightFps, 'Çatışmada FPS') + card(P2.st, 'Takılma') +
      card(P2.pingAvg + ' ms', 'Ort. ping') + card(P2.cpuMax ? P2.cpuMax + '°' : '—', 'En sıcak CPU') + card(P2.gpuMax ? P2.gpuMax + '°' : '—', 'En sıcak GPU') + '</div>' +
      '<canvas id="chart"></canvas><div class="legend"><i style="background:#4cc2ff"></i>FPS<i style="background:rgba(255,200,69,.6);height:8px"></i>çatışma<i style="background:#ff5c5c"></i>takılma / ölüm · tıkla: o ana git</div>';
    if (P2.beforeDeath) { const b = P2.beforeDeath;
      h += `<div class="tipr ${b.st >= 2 || b.lossMax >= 5 ? 'bad' : 'info'}" style="margin-top:6px"><span class="i">◷</span><span>Ölümünden önceki 15 sn: en düşük FPS ${b.minFps}, ${b.st} takılma, en yüksek ping ${Math.round(b.pingMax)} ms${b.lossMax ? ', kayıp %' + Math.round(b.lossMax) : ''}</span></div>`; }
  } else h += '<div class="tipr info"><span class="i">ℹ</span><span>Bu maçta program çalışmıyordu ya da eski sürümdü; performans kaydı yok. Sonraki maçlarda FPS, takılma ve ping çatışma ve ölüm anlarıyla eşleştirilecek.</span></div>';
  el.innerHTML = h;
  if (P2) drawChart();
}
function drawChart() {
  const c = $('chart'); if (!c || !c.clientWidth) return;
  const d = devicePixelRatio || 1, w = c.clientWidth, h = c.clientHeight; c.width = w * d; c.height = h * d;
  const g = c.getContext('2d'); g.setTransform(d, 0, 0, d, 0, 0);
  const S = RP.perf.series; if (!S.length) return;
  const max = Math.max(...S.map(s => s[1])) * 1.1 || 1, X = t => t / D.dur * w, Y = f => h - 6 - f / max * (h - 16);
  g.fillStyle = 'rgba(255,200,69,.18)'; for (const f of RP.fights) g.fillRect(X(f[0] - 2), 0, Math.max(3, X(f[1] + 2) - X(f[0] - 2)), h);
  g.beginPath(); S.forEach((s, i) => i ? g.lineTo(X(s[0]), Y(s[1])) : g.moveTo(X(s[0]), Y(s[1])));
  g.strokeStyle = '#4cc2ff'; g.lineWidth = 1.5; g.stroke();
  g.fillStyle = '#ff5c5c'; for (const s of S) if (s[2]) g.fillRect(X(s[0]) - 1, h - 10, 2, 8);
  if (RP.death) { g.fillStyle = '#ff5c5c'; g.fillRect(X(RP.death.t) - 1, 0, 2, h); }
  g.fillStyle = 'rgba(255,255,255,.75)'; g.fillRect(X(T) - .5, 0, 1, h);
  g.fillStyle = '#8b93a1'; g.font = '10px Segoe UI'; g.fillText(Math.round(max / 1.1) + ' FPS', 4, 11);
  c.onclick = e => { const r = c.getBoundingClientRect(); seek((e.clientX - r.left) / w * D.dur); };
}
function goTo(t, focusMe) { seek(t); if (focusMe && P[D.me]) { const q = pos(P[D.me], Math.max(t, 0)); if (q) map.setView(ll(q[1], q[2]), Math.max(map.getZoom(), 4)); } }
addEventListener('resize', () => { if (RP && RP.perf) drawChart(); });
// oynatma
const seekEl = $('seek');
function seek(t) { T = Math.max(0, Math.min(D.dur, t)); ui(); draw(); side(); }
let lastChart = 0;
function ui() { const f = T / D.dur; if (RP && RP.perf && performance.now() - lastChart > 300) { lastChart = performance.now(); drawChart(); } seekEl.value = Math.round(f * 1000); $('fill').style.width = f * 100 + '%'; $('knob').style.left = f * 100 + '%'; $('time').textContent = fmt(T) + ' / ' + fmt(D.dur); }
seekEl.oninput = () => seek(seekEl.value / 1000 * D.dur);
$('play').onclick = () => { playing = !playing; if (playing && T >= D.dur) T = 0; $('play').textContent = playing ? '❚❚' : '▶'; };
let last = performance.now();
function frame(now) {
  const dt = Math.min(0.1, (now - last) / 1000); last = now;
  if (playing) { T += dt * +$('speed').value; if (T >= D.dur) { T = D.dur; playing = false; $('play').textContent = '▶'; } ui(); side(); }
  if (followId) { const q = pos(P[followId], T); if (q) map.panTo(ll(q[1], q[2]), {animate: false}); }
  draw(); requestAnimationFrame(frame);
}
map.on('move zoom', draw);
$('zin').onclick = () => map.zoomIn(); $('zout').onclick = () => map.zoomOut(); $('zfit').onclick = () => { setFollow(null); map.fitBounds(B); };
$('zme').onclick = () => { if (P[D.me]) { setFollow(D.me); map.setZoom(Math.max(map.getZoom(), 4)); } };
for (const id of ['oNames', 'oTracer', 'oPath', 'oDeaths', 'oDrops', 'oBots']) $(id).onchange = draw;
addEventListener('keydown', e => {
  if (e.target.tagName === 'SELECT') return;
  if (e.code === 'Space') { e.preventDefault(); $('play').click(); }
  else if (e.key === 'ArrowRight') seek(T + 10); else if (e.key === 'ArrowLeft') seek(T - 10);
  else if (e.key === '+' || e.key === '-') { const s = $('speed'), i = s.selectedIndex + (e.key === '+' ? 1 : -1); s.selectedIndex = Math.max(0, Math.min(s.options.length - 1, i)); }
});
// başlangıç: iniş anına git, benim takımı göster
seek(D.start || 0); side(); renderReport(); requestAnimationFrame(frame);
</script>
</body>
</html>
'''


# ---------------- Saniyelik performans kaydı + maç sonu koç raporu ----------------
PERF = os.path.join(DATA, 'performans')


class PerfLog:
    """Oyun sırasında her saniyenin performansı, zaman damgasıyla (gün başına bir dosya, 15 gün saklanır).
    Maç raporu bu kaydı maçın telemetrisindeki anlarla (çatışma, ölüm) eşleştirir."""
    def __init__(self):
        self.f, self.day = None, None
        try:
            os.makedirs(PERF, exist_ok=True)
            cut = time.time() - 15 * 86400
            for fn in glob.glob(os.path.join(PERF, '*.csv')):
                if os.path.getmtime(fn) < cut:
                    os.remove(fn)
        except OSError:
            pass

    def write(self, row):
        try:
            day = time.strftime('%Y%m%d')
            if day != self.day:
                if self.f:
                    self.f.close()
                self.f = open(os.path.join(PERF, day + '.csv'), 'a', encoding='utf-8', buffering=1)
                self.day = day
            self.f.write(','.join('' if x is None else str(x) for x in row) + '\n')
        except OSError:
            pass

    def close(self):
        try:
            if self.f:
                self.f.close()
        except OSError:
            pass


PERF_COLS = ('ts', 'fps', 'low1', 'st', 'ftmax', 'cpu_t', 'cpu', 'core', 'gpu_t', 'gpu', 'ping', 'loss', 'bound')


def perf_rows(t_from, t_to):
    """[t_from, t_to] (epoch sn) arasındaki saniyelik kayıtlar."""
    out, d = [], datetime.date.fromtimestamp(t_from)
    while d <= datetime.date.fromtimestamp(t_to):
        try:
            with open(os.path.join(PERF, d.strftime('%Y%m%d') + '.csv'), encoding='utf-8') as f:
                for ln in f:
                    p = ln.rstrip('\n').split(',')
                    if len(p) < len(PERF_COLS):
                        continue
                    try:
                        ts = float(p[0])
                    except ValueError:
                        continue
                    if t_from <= ts <= t_to:
                        r = {k: (num(v) if k != 'bound' else v) for k, v in zip(PERF_COLS, p)}
                        out.append(r)
        except OSError:
            pass
        d += datetime.timedelta(days=1)
    return out


def coach_report(events, m, data):
    """Maç sonu raporu: maçın olayları + o anki bilgisayar performansı. Bulgular ve öneriler (seviye, metin)."""
    aid = m['aid']
    t0 = _ts(next(e['_D'] for e in events if e['_T'] == 'LogMatchStart'))
    me = data['players'].get(aid) or {}
    myteam = data.get('myTeam')
    wn = weapon_names()
    T = lambda e: _ts(e['_D']) - t0
    shots, hits, hs, dmg, dmg_taken, blue_dmg, knocks, heals = {}, 0, 0, 0.0, 0.0, 0.0, 0, 0
    by_w = {}
    fights = []  # benim silahla hasar verdiğim/aldığım anlar
    landing = land_name = None
    death = None
    knocked_by = None
    for e in events:
        typ = e['_T']
        if landing is not None and land_name is None:  # iniş yerinin adı: inişten sonra bende görülen ilk bölge adı
            for f in ('character', 'attacker', 'victim'):
                c = e.get(f)
                if isinstance(c, dict) and c.get('accountId') == aid and c.get('zone'):
                    land_name = c['zone'][0].replace('_', ' ').title()
                    break
        if typ == 'LogWeaponFireCount' and e['character'].get('accountId') == aid:
            shots[e['weaponId']] = max(shots.get(e['weaponId'], 0), e.get('fireCount', 0))
        elif typ == 'LogPlayerTakeDamage':
            a, v = e.get('attacker') or {}, e.get('victim') or {}
            cat, d = e.get('damageTypeCategory', ''), e.get('damage') or 0
            if a.get('accountId') == aid and v.get('teamId') != myteam and cat == 'Damage_Gun':
                hits += 1; dmg += d; fights.append(T(e))
                hs += e.get('damageReason') == 'HeadShot'
                w = wn.get(e.get('damageCauserName'), e.get('damageCauserName', '?'))
                b = by_w.setdefault(w, {'w': w, 'hits': 0, 'dmg': 0.0, 'hs': 0})
                b['hits'] += 1; b['dmg'] += d; b['hs'] += e.get('damageReason') == 'HeadShot'
            elif v.get('accountId') == aid:
                dmg_taken += d
                if cat == 'Damage_BlueZone':
                    blue_dmg += d
                elif cat == 'Damage_Gun':
                    fights.append(T(e))
        elif typ == 'LogPlayerMakeGroggy':
            if (e.get('attacker') or {}).get('accountId') == aid:
                knocks += 1
            if (e.get('victim') or {}).get('accountId') == aid and knocked_by is None:
                knocked_by = (e.get('attacker') or {}).get('name')
        elif typ == 'LogItemUse' and e['character'].get('accountId') == aid and \
                any(x in e['item'].get('itemId', '') for x in ('Heal', 'Boost', 'FirstAid', 'MedKit', 'Bandage')):
            heals += 1
        elif typ == 'LogParachuteLanding' and e['character'].get('accountId') == aid:
            landing = T(e)
        elif typ == 'LogPlayerKillV2' and (e.get('victim') or {}).get('accountId') == aid:
            k = e.get('finisher') or e.get('killer') or {}
            info = e.get('finishDamageInfo') or e.get('killerDamageInfo') or {}
            cat = info.get('damageTypeCategory', '')
            death = {'t': T(e), 'by': k.get('name') or '', 'w': 'Mavi bölge' if cat == 'Damage_BlueZone' else
                     wn.get(info.get('damageCauserName'), info.get('damageCauserName', '?')),
                     'd': round((info.get('distance') or 0) / 100), 'hs': info.get('damageReason') == 'HeadShot',
                     'veh': bool((e.get('victim') or {}).get('isInVehicle')), 'knocked_by': knocked_by}
    fired = sum(shots.values())
    acc = round(100 * hits / max(fired, hits), 1) if fired or hits else None
    # çatışmaları birleştir (10 sn içindeki vuruşlar aynı çatışma)
    fights.sort()
    fw = []
    for t in fights:
        if fw and t - fw[-1][1] <= 10:
            fw[-1][1] = t
        else:
            fw.append([t, t])
    alive = (death['t'] if death else data['dur'])
    enemies_near = 0
    if landing is not None and me.get('pos'):
        lp = next((a for a in me['pos'] if a[0] >= landing), None)
        if lp:  # iniş anında 150 m içinde düşman sayısı
            size = MAP_INFO.get(m['map'], ('', '', 816000))[2]
            r = 15000 / size
            for i, p in data['players'].items():
                if p['team'] == myteam:
                    continue
                q = next((a for a in p['pos'] if a[0] >= landing), None)
                if q and abs(q[0] - landing) < 20 and (q[1] - lp[1]) ** 2 + (q[2] - lp[2]) ** 2 <= r * r:
                    enemies_near += 1
    rep = {'landing': landing, 'landName': land_name or '', 'enemiesNear': enemies_near, 'firstFight': fw[0][0] if fw else None,
           'fights': fw, 'fired': fired, 'hits': hits, 'acc': acc, 'hs': hs, 'hsPct': round(100 * hs / hits) if hits else 0,
           'dmg': round(m.get('dmg') or dmg), 'gunDmg': round(dmg), 'dmgTaken': round(dmg_taken), 'blueDmg': round(blue_dmg), 'knocks': knocks, 'heals': heals,
           'kills': m.get('kills', 0), 'rank': m.get('rank'), 'alive': round(alive), 'death': death,
           'weapons': sorted(by_w.values(), key=lambda b: -b['dmg'])[:5], 'perf': None, 'tips': [], 'good': []}

    # performans kaydıyla eşleştir
    rows = perf_rows(t0 - 5, t0 + data['dur'] + 5)
    if len(rows) >= 30:
        for r in rows:
            r['t'] = r['ts'] - t0
        fps = [r['fps'] for r in rows if r['fps']]
        avg = sum(fps) / len(fps) if fps else 0

        def win(a, b):
            return [r for r in rows if a <= r['t'] <= b]
        infight = [r for w in fw for r in win(w[0] - 2, w[1] + 2)]
        ff = [r['fps'] for r in infight if r['fps']]
        pd = {'avg': round(avg), 'low1': round(min(r['low1'] or avg for r in rows)), 'st': int(sum(r['st'] or 0 for r in rows)),
              'fightFps': round(sum(ff) / len(ff)) if ff else None, 'fightSt': int(sum(r['st'] or 0 for r in infight)),
              'cpuMax': max((r['cpu_t'] or 0) for r in rows), 'gpuMax': max((r['gpu_t'] or 0) for r in rows),
              'pingAvg': round(sum(r['ping'] or 0 for r in rows) / len(rows)), 'pingMax': max((r['ping'] or 0) for r in rows),
              'lossMax': max((r['loss'] or 0) for r in rows),
              'series': [[round(r['t']), round(r['fps'] or 0), int(r['st'] or 0), round(r['ping'] or 0)] for r in rows[::2]]}
        if death:
            bd = win(death['t'] - 15, death['t'])
            if bd:
                pd['beforeDeath'] = {'minFps': round(min(r['fps'] or 0 for r in bd)), 'st': int(sum(r['st'] or 0 for r in bd)),
                                     'pingMax': max(r['ping'] or 0 for r in bd), 'lossMax': max(r['loss'] or 0 for r in bd),
                                     'cpuT': max(r['cpu_t'] or 0 for r in bd)}
        rep['perf'] = pd

    # öneriler (önce sorunlar, sonra iyi gidenler)
    tip, good = rep['tips'].append, rep['good'].append
    pdd = rep['perf']
    if pdd and death and pdd.get('beforeDeath'):
        b = pdd['beforeDeath']
        if b['st'] >= 2 or (avg and b['minFps'] < avg * 0.6):
            tip(('bad', f"Ölümünden önceki 15 saniyede {b['st']} takılma oldu, en düşük FPS {b['minFps']}. "
                        + ('Sebep işlemci ısınması olabilir ({}°C).'.format(b['cpuT']) if b['cpuT'] >= LIM['hot'] else
                           'Analiz sekmesindeki takılma kaydına bak.')))
        if b['lossMax'] >= 5 or b['pingMax'] >= max(80, pdd['pingAvg'] * 2):
            tip(('bad', f"Ölümünden önce ağ bozuldu: ping {b['pingMax']:.0f} ms" + (f", paket kaybı %{b['lossMax']:.0f}" if b['lossMax'] else '') + ". "
                        'Oyunda geri ışınlanma ve gecikmeli vuruş yapar.'))
    if pdd and pdd['fightFps'] and pdd['avg'] and pdd['fightFps'] < pdd['avg'] * 0.75:
        tip(('warn', f"Çatışmalarda FPS ortalaması {pdd['fightFps']}, maç ortalaması {pdd['avg']}. Duman ve patlamalar FPS'yi "
                     "düşürüyor: Efektler'i Çok Düşük tut."))
    if pdd and pdd['fightSt'] >= 3:
        tip(('warn', f"Çatışma anlarında toplam {pdd['fightSt']} takılma oldu."))
    if rep['blueDmg'] >= 15:
        tip(('warn', f"Mavi bölgeden {rep['blueDmg']} hasar aldın. Bir sonraki çemberin yerini erken düşün, araç bul."))
    if death and landing is not None and death['t'] - landing < 180:
        tip(('warn', f"İnişten {death['t'] - landing:.0f} saniye sonra öldün" +
             (f" ({rep['enemiesNear']} düşman 150 m içine indi)" if rep['enemiesNear'] else '') +
             '. Kalabalık inişlerde önce silah bulmaya odaklan ya da daha sakin bir yere in.'))
    elif rep['enemiesNear'] >= 4:
        tip(('info', f"İnişte 150 m içinde {rep['enemiesNear']} düşman vardı (sıcak iniş)."))
    if death and death['d'] >= 150 and death['w'] != 'Mavi bölge':
        tip(('info', f"{death['d']} m'den vuruldun ({death['w']}). Açık alanda koşarken siper ya da duman kullan."))
    if death and death['veh']:
        tip(('info', 'Araçtayken öldün: araçlar uzaktan kolay hedef olur, çatışma bölgesine yaklaşınca in.'))
    if rep['acc'] is not None and rep['fired'] >= 40 and rep['acc'] < 15:
        tip(('warn', f"İsabet oranın yaklaşık %{rep['acc']:.0f} ({rep['fired']} mermi). Uzun mesafede tek atış ya da kısa "
                     "seri atış dene; Eğitim Modu'nda sekme kontrolü çalış."))
    if not fw and death:
        tip(('warn', 'Ölmeden önce hiç hasar veremedin: düşmanı ilk sen gör. Ses ayarların için Takım Sesi ve Ayar Kontrolü\'ne bak.'))
    if rep['kills'] >= 3:
        good(f"{rep['kills']} öldürme, {rep['dmg']} hasar.")
    if rep['acc'] is not None and rep['fired'] >= 40 and rep['acc'] >= 30:
        good(f"İsabet oranın yüksek: yaklaşık %{rep['acc']:.0f}.")
    if rep['hits'] >= 10 and rep['hsPct'] >= 20:
        good(f"Kafa vuruşu oranın %{rep['hsPct']}.")
    if rep['rank'] and rep['rank'] <= 10:
        good(f"İlk 10'a girdin (#{rep['rank']}).")
    if pdd and pdd['st'] == 0:
        good(f"Maç boyunca hiç takılma olmadı (ortalama {pdd['avg']} FPS).")
    if not pdd:
        tip(('info', 'Bu maçın performans kaydı yok (program kapalıydı ya da eski sürümdü). '
                     'Sonraki maçlarda FPS, takılma ve ping çatışma/ölüm anlarıyla eşleştirilecek.'))
    return rep


# ---------------- Görev Yöneticisi görünümü (Performans sekmesinin aynısı, aynı Windows sayaçları) ----------------
class TmCounters:
    """Görev Yöneticisi'nin Performans sekmesindeki değerler, aynı PDH sayaçlarından. Sadece sekme açıkken okunur
    (bir okuma ~7 ms)."""
    SINGLE = {'cpu': r'\Processor Information(_Total)\% Processor Utility',
              'perf': r'\Processor Information(_Total)\% Processor Performance',
              'procs': r'\System\Processes', 'threads': r'\System\Threads', 'handles': r'\Process(_Total)\Handle Count',
              'up': r'\System\System Up Time', 'commit': r'\Memory\Committed Bytes', 'climit': r'\Memory\Commit Limit',
              'paged': r'\Memory\Pool Paged Bytes', 'nonpaged': r'\Memory\Pool Nonpaged Bytes',
              'modified': r'\Memory\Modified Page List Bytes', 'sb1': r'\Memory\Standby Cache Core Bytes',
              'sb2': r'\Memory\Standby Cache Normal Priority Bytes', 'sb3': r'\Memory\Standby Cache Reserve Bytes',
              'avail': r'\Memory\Available Bytes'}
    MULTI = {'percpu': r'\Processor Information(*)\% Processor Utility', 'idle': r'\PhysicalDisk(*)\% Idle Time',
             'resp': r'\PhysicalDisk(*)\Avg. Disk sec/Transfer', 'rd': r'\PhysicalDisk(*)\Disk Read Bytes/sec',
             'wr': r'\PhysicalDisk(*)\Disk Write Bytes/sec', 'tx': r'\Network Interface(*)\Bytes Sent/sec',
             'rx': r'\Network Interface(*)\Bytes Received/sec', 'eng': r'\GPU Engine(*)\Utilization Percentage',
             'ded': r'\GPU Adapter Memory(*)\Dedicated Usage', 'shr': r'\GPU Adapter Memory(*)\Shared Usage'}

    def __init__(self, luid):
        self.luid = (luid or '').lower()
        self.pdh = ctypes.WinDLL('pdh')
        self.q = ctypes.c_void_p()
        self.pdh.PdhOpenQueryW(None, 0, ctypes.byref(self.q))
        self.h = {}
        for k, pth in list(self.SINGLE.items()) + list(self.MULTI.items()):
            c = ctypes.c_void_p()
            if self.pdh.PdhAddEnglishCounterW(self.q, pth, 0, ctypes.byref(c)) == 0:
                self.h[k] = c
        self.pdh.PdhCollectQueryData(self.q)

    def one(self, k):
        if k not in self.h:
            return 0.0
        v = _FMTV()
        if self.pdh.PdhGetFormattedCounterValue(self.h[k], 0x200 | 0x8000, None, ctypes.byref(v)) or v.CStatus not in (0, 1):
            return 0.0
        return v.doubleValue

    def many(self, k):
        return pdh_items(self.pdh, self.h[k]) if k in self.h else []

    def sample(self):
        self.pdh.PdhCollectQueryData(self.q)
        o = {k: self.one(k) for k in self.SINGLE}
        per = []
        for n, v in self.many('percpu'):
            m = re.match(r'^(\d+),(\d+)$', n)
            if m:
                per.append((int(m.group(1)), int(m.group(2)), min(100.0, v)))
        o['percpu'] = [v for _, _, v in sorted(per)]
        disks = {}
        for key in ('idle', 'resp', 'rd', 'wr'):
            for n, v in self.many(key):
                if n != '_Total':
                    disks.setdefault(n, {})[key] = v
        o['disks'] = {n: {'active': max(0.0, min(100.0, 100 - d.get('idle', 100))), 'resp': d.get('resp', 0) * 1000,
                          'rd': d.get('rd', 0), 'wr': d.get('wr', 0)} for n, d in disks.items()}
        net = {}
        for key in ('tx', 'rx'):
            for n, v in self.many(key):
                net.setdefault(n, {})[key] = v * 8
        o['net'] = net
        eng = {}
        for n, v in self.many('eng'):
            n = n.lower()
            if self.luid and self.luid not in n:
                continue
            m = re.search(r'_eng_(\d+)_engtype_(\w+)$', n)
            if m:
                key = (m.group(1), m.group(2))
                eng[key] = eng.get(key, 0) + v
        types = {}
        for (_, t), v in eng.items():
            types[t] = max(types.get(t, 0), min(100.0, v))
        o['gpu_eng'] = types
        o['gpu'] = max(types.values(), default=0)
        pick = lambda k: max([v for n, v in self.many(k) if not self.luid or self.luid in n.lower()] or [0])
        o['ded'], o['shr'] = pick('ded'), pick('shr')
        return o


def fmt_bytes(b, dec=1):
    for u, d in (('TB', 1 << 40), ('GB', 1 << 30), ('MB', 1 << 20), ('KB', 1 << 10)):
        if b >= d:
            return f'{b / d:.{dec}f} {u}'
    return f'{b:.0f} B'


def fmt_rate(b):  # bayt/sn
    return fmt_bytes(b, 1) + '/sn' if b >= 1024 else f'{b:.0f} B/sn'


def fmt_bits(b):  # bit/sn
    for u, d in (('Gbps', 1e9), ('Mbps', 1e6), ('Kbps', 1e3)):
        if b >= d:
            return f'{b / d:.1f} {u}'
    return f'{b:.0f} bps'


class TmGraph:
    """Görev Yöneticisi tarzı grafik: ızgara, dolgu ve çizgi; 60 nokta. Öğeler bir kez çizilir, koordinatlar güncellenir."""
    def __init__(self, parent, w, h, color, fill, vmax=100.0, n=60, grid=True, bg='#11151c'):
        self.w, self.h, self.vmax, self.auto = px(w), px(h), vmax, vmax is None
        self.d = collections.deque([0.0] * n, maxlen=n)
        self.c = c = tk.Canvas(parent, width=self.w, height=self.h, bg=bg, highlightthickness=1, highlightbackground=color)
        if grid:
            for i in range(1, 10):
                c.create_line(0, 0, 0, 0, fill='#1c2430', tags='gv')
            for i in range(1, 10):
                c.create_line(0, 0, 0, 0, fill='#1c2430', tags='gh')
        self.poly = c.create_polygon(0, 0, 0, 0, 0, 0, fill=fill, outline='')
        self.line = c.create_line(0, 0, 0, 0, fill=color, width=max(1, px(1.5)))
        c.bind('<Configure>', lambda e: self.draw())

    def push(self, v):
        self.d.append(max(0.0, float(v or 0)))
        if self.c.winfo_viewable():
            self.draw()

    def draw(self):
        c = self.c
        w, h = max(self.w, c.winfo_width()), max(self.h, c.winfo_height())
        for i, it in enumerate(c.find_withtag('gv')):
            c.coords(it, w * (i + 1) / 10, 0, w * (i + 1) / 10, h)
        for i, it in enumerate(c.find_withtag('gh')):
            c.coords(it, 0, h * (i + 1) / 10, w, h * (i + 1) / 10)
        top = (max(self.d) * 1.2 or 1) if self.auto else self.vmax
        n = len(self.d)
        pts = []
        for i, v in enumerate(self.d):
            pts += [w * i / (n - 1), h - 1 - min(v, top) / top * (h - 2)]
        c.coords(self.poly, *pts, w, h, 0, h)
        c.coords(self.line, *pts)
        return top


# ---------------- İniş ve ölüm ısı haritası (son maçlar, resmî PUBG API) ----------------
HEATDIR = os.path.join(DATA, 'isi')


def heat_point(m, events):
    """Bir maçtan ısı haritası için gereken küçük özet: iniş yeri, ölüm yeri, sonuç. Koordinatlar 0-1."""
    aid = m['aid']
    size = MAP_INFO.get(m['map'], ('', '', 816000))[2]
    t0 = _ts(next(e['_D'] for e in events if e['_T'] == 'LogMatchStart'))
    land = death = None
    fights = []
    for e in events:
        typ = e['_T']
        if typ == 'LogParachuteLanding' and land is None and e['character'].get('accountId') == aid:
            loc = e['character']['location']
            land = [round(loc['x'] / size, 5), round(loc['y'] / size, 5), round(_ts(e['_D']) - t0)]
        elif typ == 'LogPlayerKillV2' and (e.get('victim') or {}).get('accountId') == aid:
            loc = e['victim']['location']
            k = e.get('finisher') or e.get('killer') or {}
            info = e.get('finishDamageInfo') or e.get('killerDamageInfo') or {}
            death = [round(loc['x'] / size, 5), round(loc['y'] / size, 5), round(_ts(e['_D']) - t0),
                     k.get('name') or '', 'Mavi bölge' if info.get('damageTypeCategory') == 'Damage_BlueZone' else
                     weapon_names().get(info.get('damageCauserName'), info.get('damageCauserName') or '')]
        elif typ == 'LogPlayerTakeDamage' and e.get('damageTypeCategory') == 'Damage_Gun':
            a, v = e.get('attacker') or {}, e.get('victim') or {}
            me_ = a if a.get('accountId') == aid else (v if v.get('accountId') == aid else None)
            if me_ and me_.get('location'):
                fights.append([round(me_['location']['x'] / size, 4), round(me_['location']['y'] / size, 4)])
    return {'id': m['id'], 'map': m['map'], 'mode': m['mode'], 'type': m['type'], 'date': m['date'], 'rank': m.get('rank'),
            'kills': m.get('kills', 0), 'dmg': round(m.get('dmg') or 0), 'dur': m.get('dur', 0), 'land': land, 'death': death,
            'fights': fights[::3][:60]}


def heat_collect(key, name='', limit=50, progress=None):
    """Son maçların özetleri. Her maç bir kez indirilip önbelleğe alınır; sonraki açılışta sadece yeni maçlar indirilir."""
    pr = progress or (lambda txt, f=None: None)
    os.makedirs(HEATDIR, exist_ok=True)
    aid, nm, ids = recent_matches(key, name, limit)
    out = []
    for i, mid in enumerate(ids):
        pth = os.path.join(HEATDIR, mid + '.json')
        try:
            with open(pth, encoding='utf-8') as f:
                hp = json.load(f)
        except Exception:
            hp = None
        if hp is None:
            pr(f'Maç {i + 1}/{len(ids)} indiriliyor…', i / max(1, len(ids)))
            try:
                m = match_summary(mid, key, aid)
                if not m.get('tel') or m['map'] not in MAP_INFO or m['map'] == 'Range_Main' or m['mode'] == 'tdm':
                    hp = {'id': mid, 'skip': True}
                else:
                    hp = heat_point(m, json.loads(http_bytes(m['tel'], 120)))
                with open(pth, 'w', encoding='utf-8') as f:
                    json.dump(hp, f)
            except Exception:
                continue
        if not hp.get('skip'):
            out.append(hp)
    return nm, out


def heat_areas(points, cell=0.06):
    """İniş yerlerini ızgara hücrelerine (8 km haritada ~500 m) toplar; her bölge için ortalama sıra, hayatta kalma,
    erken ölüm oranı. Önerilerde en az 2 iniş olan bölgeler kullanılır."""
    cells = {}
    for p in points:
        if not p.get('land'):
            continue
        x, y = p['land'][0], p['land'][1]
        key = (int(x / cell), int(y / cell))
        c = cells.setdefault(key, {'n': 0, 'rank': 0, 'alive': 0, 'early': 0, 'kills': 0, 'top10': 0, 'xs': 0, 'ys': 0})
        alive = (p['death'][2] - p['land'][2]) if p.get('death') else max(0, p['dur'] - p['land'][2])
        c['n'] += 1; c['rank'] += p['rank'] or 50; c['alive'] += alive; c['kills'] += p['kills']
        c['early'] += 1 if p.get('death') and alive < 180 else 0
        c['top10'] += 1 if p['rank'] and p['rank'] <= 10 else 0
        c['xs'] += x; c['ys'] += y
    out = []
    for c in cells.values():
        n = c['n']
        out.append({'x': round(c['xs'] / n, 4), 'y': round(c['ys'] / n, 4), 'n': n, 'rank': round(c['rank'] / n, 1),
                    'alive': round(c['alive'] / n), 'early': round(100 * c['early'] / n), 'kills': round(c['kills'] / n, 1),
                    'top10': round(100 * c['top10'] / n)})
    return out


def build_heatmap(key, name='', progress=None):
    pr = progress or (lambda txt, f=None: None)
    nm, pts = heat_collect(key, name, 50, pr)
    if not pts:
        raise ValueError('Son 14 günde ısı haritası için uygun maç yok.')
    maps = {}
    for p in pts:
        maps.setdefault(p['map'], []).append(p)
    pr('Haritalar hazırlanıyor…', 0.95)
    data = {'name': nm, 'maps': []}
    from pathlib import Path
    for raw, lst in sorted(maps.items(), key=lambda kv: -len(kv[1])):
        mname, img, size = MAP_INFO[raw]
        low = map_low(img)
        tiles, maxz = map_tiles(img)
        ranks = [p['rank'] for p in lst if p['rank']]
        data['maps'].append({'raw': raw, 'name': mname, 'n': len(lst), 'low': Path(low).as_uri(),
                             'tiles': (Path(tiles).as_uri() + '/{z}/{x}/{y}.jpg') if tiles else None, 'maxz': maxz,
                             'km': size / 100000, 'avgRank': round(sum(ranks) / len(ranks), 1) if ranks else None,
                             'top10': round(100 * sum(1 for r in ranks if r <= 10) / len(ranks)) if ranks else 0,
                             'kills': round(sum(p['kills'] for p in lst) / len(lst), 1), 'points': lst,
                             'areas': heat_areas(lst)})
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    out = os.path.join(REPLAYS, 'isi_haritasi.html')
    os.makedirs(REPLAYS, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(HEAT_HTML.replace('__DATA__', js))
    pr('Hazır', 1)
    return out


# Isı haritası sayfası: Leaflet + tek tuval katmanı
HEAT_HTML = r'''<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>İniş ve Ölüm Haritası · PUBG İzleyici</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
:root{--bg:#0e1014;--card:#161a21;--card2:#1d222b;--line:#262b36;--txt:#e8eaed;--sub:#8b93a1;--acc:#4cc2ff;--ok:#3ddc84;--warn:#ffc845;--bad:#ff5c5c}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--txt);font:13px/1.4 "Segoe UI",system-ui,sans-serif;overflow:hidden}
#app{display:grid;grid-template-columns:1fr 340px;grid-template-rows:60px 1fr;height:100%}
header{grid-column:1/3;display:flex;align-items:center;gap:16px;padding:0 18px;border-bottom:1px solid var(--line);background:#0b0d11}
header .logo{font:700 18px "Bahnschrift","Segoe UI";color:var(--acc)}
header .t{font-weight:600;font-size:15px;white-space:nowrap}
#maps{display:flex;gap:6px;margin-left:auto;overflow-x:auto}
#maps button{background:var(--card2);border:1px solid var(--line);color:var(--sub);border-radius:999px;padding:6px 12px;cursor:pointer;font:600 12px "Segoe UI";white-space:nowrap}
#maps button.on{background:var(--acc);border-color:var(--acc);color:#0e1014}
#mapwrap{position:relative;background:#0a0c0f}
#map{position:absolute;inset:0;background:#0a0c0f}
#fx{position:absolute;inset:0;pointer-events:none;z-index:450}
#tip{position:absolute;z-index:500;pointer-events:none;background:rgba(14,16,20,.94);border:1px solid var(--line);border-radius:8px;padding:7px 10px;display:none;max-width:280px}
#tip b{color:var(--txt)}#tip .s{color:var(--sub);font-size:12px}
.layers{position:absolute;left:12px;top:12px;z-index:600;display:flex;gap:6px;flex-wrap:wrap}
.layers label{background:rgba(22,26,33,.92);border:1px solid var(--line);border-radius:8px;padding:5px 10px;display:flex;gap:6px;align-items:center;cursor:pointer;user-select:none;font-size:12px}
.layers input{accent-color:var(--acc);margin:0}
.legend{position:absolute;left:12px;bottom:12px;z-index:600;background:rgba(22,26,33,.92);border:1px solid var(--line);border-radius:8px;padding:7px 10px;font-size:12px;color:var(--sub)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin:0 4px 0 10px;vertical-align:-1px}
aside{border-left:1px solid var(--line);background:var(--card);overflow:auto;padding:12px}
aside::-webkit-scrollbar{width:8px}aside::-webkit-scrollbar-thumb{background:#2c3240;border-radius:4px}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:6px;margin-bottom:12px}
.rc{background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:8px 10px}
.rc .v{font:700 20px "Bahnschrift","Segoe UI"}.rc .l{color:var(--sub);font-size:11px}
.sec{font-weight:700;margin:14px 2px 6px}
.area{display:grid;grid-template-columns:30px 1fr;gap:2px 8px;background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:8px 10px;margin-bottom:6px;cursor:pointer}
.area:hover{border-color:var(--acc)}
.area .no{grid-row:1/3;font:700 18px "Bahnschrift";align-self:center;text-align:center}
.area.good .no{color:var(--ok)}.area.bad .no{color:var(--bad)}
.area .d{color:var(--sub);font-size:12px}
.mt{display:grid;grid-template-columns:44px 1fr auto;gap:8px;padding:6px 8px;border-bottom:1px solid #20252e;cursor:pointer;border-radius:6px}
.mt:hover{background:#232a35}.mt .r{font:700 14px "Bahnschrift"}.mt .s{color:var(--sub);font-size:12px}
.note{color:var(--sub);font-size:12px;background:var(--card2);border-radius:8px;padding:8px 10px}
.leaflet-container{background:#0a0c0f;outline:0}
</style>
</head>
<body>
<div id="app">
  <header><div class="logo">PUBG</div><div class="t" id="title"></div><div id="maps"></div></header>
  <div id="mapwrap">
    <div id="map"></div><canvas id="fx"></canvas><div id="tip"></div>
    <div class="layers">
      <label><input type="checkbox" id="lHeat" checked>Isı</label>
      <label><input type="checkbox" id="lLand" checked>İnişler</label>
      <label><input type="checkbox" id="lDeath" checked>Ölümler</label>
      <label><input type="checkbox" id="lFight">Çatışmalar</label>
      <label><input type="checkbox" id="lLine">İniş → ölüm</label>
      <label><input type="checkbox" id="lArea" checked>Bölgeler</label>
    </div>
    <div class="legend">İniş sonucu:<i style="background:#3ddc84"></i>ilk 10<i style="background:#ffc845"></i>orta<i style="background:#ff8a3d"></i>erken elendin<i style="background:#ff5c5c"></i>ilk 3 dk'da öldün · ✕ ölüm yeri</div>
  </div>
  <aside id="side"></aside>
</div>
<script>
const D = __DATA__;
const W = 256, B = [[-W, 0], [0, W]], ll = (x, y) => L.latLng(-y * W, x * W);
const $ = id => document.getElementById(id);
const when = d => { const t = new Date(d); return isNaN(t) ? d.slice(5, 16) : t.toLocaleString('tr-TR', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'}); };
const fmt = s => { s = Math.max(0, Math.round(s)); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
const map = L.map('map', {crs: L.CRS.Simple, minZoom: 0, maxZoom: 7, zoomSnap: 1, attributionControl: false, zoomControl: false, zoomAnimation: false, fadeAnimation: false});
L.control.zoom({position: 'topright'}).addTo(map);
let base = null, M = null, hover = null, shown = [];
$('title').textContent = `İniş ve ölüm haritası · ${D.name}`;
$('maps').innerHTML = D.maps.map((m, i) => `<button data-i="${i}">${m.name} · ${m.n}</button>`).join('');
$('maps').onclick = e => { const b = e.target.closest('button'); if (b) pick(+b.dataset.i); };
const alive = p => p.land ? ((p.death ? p.death[2] : p.dur) - p.land[2]) : 0;
const outcome = p => p.rank && p.rank <= 10 ? '#3ddc84' : (p.death && alive(p) < 180 ? '#ff5c5c' : (p.rank && p.rank > 40 ? '#ff8a3d' : '#ffc845'));
function pick(i) {
  M = D.maps[i];
  document.querySelectorAll('#maps button').forEach((b, j) => b.classList.toggle('on', j === i));
  if (base) map.removeLayer(base);
  base = M.tiles ? L.tileLayer(M.tiles, {minZoom: 0, maxNativeZoom: M.maxz, maxZoom: 7, noWrap: true, bounds: B}) : L.imageOverlay(M.low, B);
  base.addTo(map); map.fitBounds(B); side(); draw();
}
function side() {
  const card = (v, l) => `<div class="rc"><div class="v">${v}</div><div class="l">${l}</div></div>`;
  let h = '<div class="grid">' + card(M.n, 'Maç') + card(M.avgRank ?? '—', 'Ortalama sıra') + card('%' + M.top10, 'İlk 10 oranı') + card(M.kills, 'Maç başı öldürme') + '</div>';
  const ok = M.areas.filter(a => a.n >= 2);
  const best = ok.slice().sort((a, b) => b.top10 - a.top10 || a.rank - b.rank).slice(0, 4);
  const worst = ok.slice().sort((a, b) => b.early - a.early || b.rank - a.rank).filter(a => a.early >= 50 || a.rank > 40).slice(0, 4);
  const area = (a, cls, i) => `<div class="area ${cls}" data-x="${a.x}" data-y="${a.y}"><span class="no">${i + 1}</span>` +
    `<span>${a.n} iniş · ortalama sıra <b>#${a.rank}</b> · ilk 10 %${a.top10}</span>` +
    `<span class="d">hayatta kalma ort. ${fmt(a.alive)} · erken ölüm %${a.early} · ${a.kills} öldürme</span></div>`;
  h += '<div class="sec">En iyi iniş bölgelerin</div>' + (best.length ? best.map((a, i) => area(a, 'good', i)).join('') :
    '<div class="note">Öneri için aynı bölgeye en az 2 kez inmiş olman gerekiyor. Bu haritada daha fazla oynadıkça dolacak.</div>');
  if (worst.length) h += '<div class="sec">Kaçınman gereken bölgeler</div>' + worst.map((a, i) => area(a, 'bad', i)).join('');
  const early = M.points.filter(p => p.death && p.land && alive(p) < 180).length;
  if (early) h += `<div class="note" style="margin-top:8px">${M.n} maçın ${early} tanesinde inişten sonraki 3 dakikada öldün. Bu haritada daha sakin inişler sıralamanı yükseltebilir.</div>`;
  h += '<div class="sec">Maçlar</div>' + M.points.slice().sort((a, b) => b.date.localeCompare(a.date)).map(p =>
    `<div class="mt" data-id="${p.id}"><span class="r" style="color:${outcome(p)}">#${p.rank || '?'}</span><span>${when(p.date)}<br>` +
    `<span class="s">${p.kills} öldürme · ${p.dmg} hasar${p.death ? ' · ' + (p.death[3] || '—') + ' (' + p.death[4] + ')' : ''}</span></span>` +
    `<span class="s">${p.land ? fmt(alive(p)) : ''}</span></div>`).join('');
  $('side').innerHTML = h;
}
$('side').onclick = e => {
  const a = e.target.closest('.area'); if (a) { map.setView(ll(+a.dataset.x, +a.dataset.y), 4); return; }
  const m = e.target.closest('.mt'); if (m) { const p = M.points.find(q => q.id === m.dataset.id); if (p && p.land) map.setView(ll(p.land[0], p.land[1]), 4); hover = p; draw(); }
};
const cv = $('fx'), cx = cv.getContext('2d');
function size() { const r = $('mapwrap').getBoundingClientRect(), d = devicePixelRatio || 1; cv.width = r.width * d; cv.height = r.height * d; cv.style.width = r.width + 'px'; cv.style.height = r.height + 'px'; cx.setTransform(d, 0, 0, d, 0, 0); }
addEventListener('resize', () => { size(); draw(); }); size();
const pt = (x, y) => map.latLngToContainerPoint(ll(x, y));
const pxR = r => pt(r, 0).x - pt(0, 0).x;
const O = id => $(id).checked;
function heat(points, color) {
  const r = Math.max(14, pxR(0.025));
  for (const q of points) { const c = pt(q[0], q[1]); const g = cx.createRadialGradient(c.x, c.y, 0, c.x, c.y, r);
    g.addColorStop(0, color.replace('A', '.45')); g.addColorStop(1, color.replace('A', '0')); cx.fillStyle = g; cx.beginPath(); cx.arc(c.x, c.y, r, 0, 7); cx.fill(); }
}
function draw() {
  if (!M) return;
  const w = cv.width / (devicePixelRatio || 1), h = cv.height / (devicePixelRatio || 1);
  cx.clearRect(0, 0, w, h); shown = [];
  if (O('lHeat')) {
    cx.globalCompositeOperation = 'lighter';
    if (O('lLand')) heat(M.points.filter(p => p.land).map(p => p.land), 'rgba(76,194,255,A)');
    if (O('lDeath')) heat(M.points.filter(p => p.death).map(p => p.death), 'rgba(255,92,92,A)');
    cx.globalCompositeOperation = 'source-over';
  }
  if (O('lFight')) { cx.fillStyle = 'rgba(255,200,69,.55)'; for (const p of M.points) for (const f of p.fights || []) { const c = pt(f[0], f[1]); cx.fillRect(c.x - 1.5, c.y - 1.5, 3, 3); } }
  if (O('lArea')) for (const a of M.areas) if (a.n >= 2) { const c = pt(a.x, a.y), R = Math.max(18, pxR(0.03));
    cx.beginPath(); cx.arc(c.x, c.y, R, 0, 7); cx.setLineDash([4, 4]); cx.strokeStyle = a.top10 >= 50 ? 'rgba(61,220,132,.9)' : (a.early >= 50 ? 'rgba(255,92,92,.9)' : 'rgba(255,255,255,.5)'); cx.lineWidth = 1.5; cx.stroke(); cx.setLineDash([]);
    cx.font = '600 11px "Segoe UI"'; cx.textAlign = 'center'; cx.lineWidth = 3; cx.strokeStyle = 'rgba(0,0,0,.85)'; const t = `${a.n} iniş · #${a.rank}`; cx.strokeText(t, c.x, c.y - R - 4); cx.fillStyle = '#fff'; cx.fillText(t, c.x, c.y - R - 4); }
  for (const p of M.points) {
    if (O('lLine') && p.land && p.death) { const a = pt(p.land[0], p.land[1]), b = pt(p.death[0], p.death[1]); cx.strokeStyle = 'rgba(255,255,255,.35)'; cx.lineWidth = 1; cx.beginPath(); cx.moveTo(a.x, a.y); cx.lineTo(b.x, b.y); cx.stroke(); }
    if (O('lDeath') && p.death) { const c = pt(p.death[0], p.death[1]), s = p === hover ? 7 : 5; cx.strokeStyle = '#ff5c5c'; cx.lineWidth = 2.2;
      cx.beginPath(); cx.moveTo(c.x - s, c.y - s); cx.lineTo(c.x + s, c.y + s); cx.moveTo(c.x + s, c.y - s); cx.lineTo(c.x - s, c.y + s); cx.stroke(); shown.push([p, c.x, c.y, 'death']); }
    if (O('lLand') && p.land) { const c = pt(p.land[0], p.land[1]), r = p === hover ? 8 : 6; cx.beginPath(); cx.arc(c.x, c.y, r, 0, 7); cx.fillStyle = outcome(p); cx.fill();
      cx.lineWidth = p === hover ? 2.5 : 1.5; cx.strokeStyle = p === hover ? '#fff' : 'rgba(0,0,0,.8)'; cx.stroke(); shown.push([p, c.x, c.y, 'land']); }
  }
}
map.on('move zoom', draw);
for (const id of ['lHeat', 'lLand', 'lDeath', 'lFight', 'lLine', 'lArea']) $(id).onchange = draw;
$('mapwrap').addEventListener('mousemove', e => {
  const r = $('mapwrap').getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  let best = null, bd = 10; for (const s of shown) { const d = Math.hypot(s[1] - mx, s[2] - my); if (d < bd) { bd = d; best = s; } }
  const tip = $('tip');
  if (!best) { tip.style.display = 'none'; if (hover) { hover = null; draw(); } return; }
  const p = best[0]; hover = p;
  tip.innerHTML = `<b>${best[3] === 'land' ? 'İniş' : 'Ölüm'}</b> · ${when(p.date)}<div class="s">Sıra #${p.rank || '?'} · ${p.kills} öldürme · ${p.dmg} hasar · hayatta ${fmt(alive(p))}` +
    (p.death ? `<br>Seni öldüren: ${p.death[3] || '—'} (${p.death[4]})` : '<br>Ölmedin') + '</div>';
  tip.style.display = 'block'; tip.style.left = (mx + 14) + 'px'; tip.style.top = (my + 10) + 'px'; draw();
});
pick(0);
</script>
</body>
</html>
'''


# ---------------- Modern arayüz parçaları ----------------
C_BG, C_CARD, C_LINE = '#0e1014', '#181b22', '#262b36'
C_SIDE = '#0a0c10'  # sol menü
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


def scroll_area(parent):
    """Kaydırılabilir alan: içerik pencereye sığmazsa satırlar üst üste binmez, tekerlekle kaydırılır.
    Kaydırma çubuğu sadece gerektiğinde görünür. (outer, inner) döner; içerik inner'a konur."""
    from tkinter import ttk
    st = ttk.Style()
    try:
        st.element_create('Koyu.Vertical.Scrollbar.trough', 'from', 'clam')
        st.element_create('Koyu.Vertical.Scrollbar.thumb', 'from', 'clam')
        st.layout('Koyu.Vertical.TScrollbar', [('Koyu.Vertical.Scrollbar.trough', {'sticky': 'ns', 'children': [
            ('Koyu.Vertical.Scrollbar.thumb', {'expand': '1', 'sticky': 'nswe'})]})])
    except tk.TclError:
        pass  # zaten tanımlı
    st.configure('Koyu.Vertical.TScrollbar', troughcolor=C_BG, background='#3a4252', bordercolor=C_BG,
                 lightcolor='#3a4252', darkcolor='#3a4252', gripcount=0, width=px(10))
    st.map('Koyu.Vertical.TScrollbar', background=[('active', C_SUB)])
    outer = tk.Frame(parent, bg=C_BG)
    cv = tk.Canvas(outer, bg=C_BG, highlightthickness=0, bd=0)
    sb = ttk.Scrollbar(outer, orient='vertical', command=cv.yview, style='Koyu.Vertical.TScrollbar')
    cv.configure(yscrollcommand=sb.set)
    cv.pack(side='left', fill='both', expand=True)
    inner = tk.Frame(cv, bg=C_BG)
    win = cv.create_window(0, 0, window=inner, anchor='nw')

    def fit(_=None):
        need = inner.winfo_reqheight()
        cv.itemconfig(win, width=cv.winfo_width(), height=max(need, cv.winfo_height()))
        cv.configure(scrollregion=(0, 0, cv.winfo_width(), need))
        if need > cv.winfo_height() + 2:
            if not sb.winfo_ismapped():
                sb.pack(side='right', fill='y', before=cv)
        elif sb.winfo_ismapped():
            sb.pack_forget(); cv.yview_moveto(0)
    cv.bind('<Configure>', fit)
    inner.bind('<Configure>', fit)

    def wheel(e):
        if sb.winfo_ismapped():
            cv.yview_scroll(int(-e.delta / 120) * 3, 'units')
    outer.bind('<Enter>', lambda e: outer.bind_all('<MouseWheel>', wheel))
    outer.bind('<Leave>', lambda e: outer.unbind_all('<MouseWheel>'))
    return outer, inner


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
    """Artık harici program başlatılmaz: sıcaklık, yük, saat ve bellek Windows'tan ve ekran kartı sürücüsünden okunur.
    Kullanıcı Core Temp / HWiNFO / GPU-Z'yi kendisi açarsa onların değerleri de okunur (isteğe bağlı)."""
    return


# ---------------- Uygulama ----------------
class App:
    BG, FG = C_BG, C_TXT
    RED, YEL, GRN = C_BAD, C_WARN, C_OK

    def __init__(self):
        self.pm = PresentMon(None)  # PresentMon arka planda hazırlanır (ilk açılışta indirme pencereyi bekletmesin)
        self.net = NetMon()
        self.kmt = KmtGpu()  # oyunun çalıştığı kart (en çok VRAM)
        self.gpdh = GpuPdh(self.kmt.luid)
        self.cpdh = CpuPdh()
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
        self.perf = PerfLog()  # zaman damgalı saniyelik kayıt (maç raporu için)
        self.csv.write('Zaman,FPS,Low1,Takilma,CPU,MaxCekirdek,CPUSic,CPUMHz,GPUYuk,GPUSic,HotSpot,VRAMMB,RAMBosMB,GPUOrani,Darbogaz\n')

        r = self.root = tk.Tk()
        global S
        S = max(1.0, r.winfo_fpixels('1i') / 96)
        r.title('PUBG Canlı İzleyici')
        r.configure(bg=self.BG)
        r.geometry(f'{px(1210)}x{px(820)}')
        r.minsize(px(1180), px(780))
        style_window(r)

        # ---- Sol menü ----
        side = tk.Frame(r, bg=C_SIDE, width=px(200)); side.pack(side='left', fill='y'); side.pack_propagate(False)
        tk.Frame(r, bg=C_LINE, width=1).pack(side='left', fill='y')
        head = tk.Frame(side, bg=C_SIDE); head.pack(fill='x', padx=18, pady=(18, 22))
        tk.Label(head, text='PUBG', bg=C_SIDE, fg=C_ACC, font=(F_NUM, 22, 'bold')).pack(anchor='w')
        tk.Label(head, text=f'İZLEYİCİ  ·  v{VERSION}', bg=C_SIDE, fg=C_SUB, font=(F_UI, 8, 'bold')).pack(anchor='w')
        nav = tk.Frame(side, bg=C_SIDE); nav.pack(fill='x')
        foot = tk.Frame(side, bg=C_SIDE); foot.pack(side='bottom', fill='x', padx=12, pady=(0, 14))

        def sbtn(p, text, cmd, bg=C_SIDE, fg=C_TXT, over=C_CARD, font=(F_UI, 9, 'bold')):
            return hover(tk.Button(p, text=text, command=cmd, bg=bg, fg=fg, relief='flat', bd=0, font=font, anchor='w',
                                   padx=12, pady=6, cursor='hand2', activebackground=over, activeforeground=fg), over)

        self.upd_side = tk.Label(foot, text='↻  Güncelleme kontrol ediliyor…', bg=C_SIDE, fg=C_SUB, font=(F_UI, 8),
                                 anchor='w', justify='left', wraplength=px(170))
        for txt, cmd in (('▣   Mini mod', self.toggle_mini), ('▶   PUBG\'yi başlat', self.launch_pubg),
                         ('★   Yenilikler', self.show_changes)):
            sbtn(foot, txt, cmd).pack(fill='x', pady=1)
        tk.Frame(foot, bg=C_LINE, height=1).pack(fill='x', pady=10)
        sbtn(foot, 'in   Talep / öneri bildir', lambda: os.startfile(LINKEDIN), bg='#0a66c2', fg='white',
             over='#004182').pack(fill='x')
        tk.Label(foot, text='Talep, öneri ve hataları LinkedIn\'den iletebilirsin.', bg=C_SIDE, fg=C_SUB, font=(F_UI, 8),
                 anchor='w', justify='left', wraplength=px(170)).pack(fill='x', pady=(4, 10))
        dev = tk.Label(foot, text=f'Geliştiren\n{DEV}  ↗', bg=C_SIDE, fg=C_SUB, font=(F_UI, 9, 'bold'), anchor='w',
                       justify='left', cursor='hand2')
        dev.pack(fill='x')
        dev.bind('<Button-1>', lambda e: os.startfile(LINKEDIN))
        dev.bind('<Enter>', lambda e: dev.config(fg=C_ACC)); dev.bind('<Leave>', lambda e: dev.config(fg=C_SUB))
        self.upd_side.pack(fill='x', pady=(10, 0))

        # ---- İçerik alanı ----
        main = self.main = tk.Frame(r, bg=self.BG); main.pack(side='left', fill='both', expand=True)
        # Güncelleme bandı (yeni sürüm varsa görünür)
        self.rep_band = tk.Frame(main, bg='#1d2a1f', highlightthickness=1, highlightbackground='#2f5a3a')
        self.rep_txt = tk.Label(self.rep_band, text='', bg='#1d2a1f', fg=C_TXT, font=(F_UI, 10, 'bold'), anchor='w', justify='left',
                                wraplength=px(700))
        self.rep_txt.pack(side='left', padx=12, pady=6, fill='x', expand=True)
        tk.Button(self.rep_band, text='✕', command=lambda: self.rep_band.pack_forget(), bg='#1d2a1f', fg=C_SUB, relief='flat',
                  bd=0, font=(F_UI, 10), cursor='hand2', activebackground='#1d2a1f').pack(side='right', padx=(0, 8))
        self.rep_btn = hover(tk.Button(self.rep_band, text='▶  Raporu aç', bg=C_OK, fg='#0e1014', relief='flat', bd=0,
                                       font=(F_UI, 10, 'bold'), padx=14, pady=4, cursor='hand2', activebackground='#6be9a4'), '#6be9a4')
        self.rep_btn.pack(side='right', padx=8)
        self.upd = tk.Frame(main, bg='#123247')
        self.upd_txt = tk.Label(self.upd, text='', bg='#123247', fg=C_TXT, font=(F_UI, 10, 'bold'), anchor='w', justify='left')
        self.upd_txt.pack(side='left', padx=12, pady=6, fill='x', expand=True)
        self.upd_btn = tk.Button(self.upd, text='Şimdi güncelle', command=self.apply_update, bg=C_ACC, fg='#0e1014', relief='flat',
                                 bd=0, font=(F_UI, 10, 'bold'), padx=14, pady=4, cursor='hand2')
        self.upd_new = None
        self.upd_info = None
        hud = tk.Frame(main, bg=C_CARD, highlightthickness=1, highlightbackground=C_LINE)
        hud.pack(side='bottom', fill='x', padx=12, pady=(0, 10))
        self.hud_fps = tk.Label(hud, text='— FPS', bg=C_CARD, fg=C_TXT, font=(F_NUM, 16, 'bold'), padx=12, pady=3)
        self.hud_fps.pack(side='left')
        self.hud_rest = tk.Label(hud, text='', bg=C_CARD, fg=C_SUB, font=(F_UI, 10, 'bold'), padx=4)
        self.hud_rest.pack(side='left')
        self.tabs = {}
        self.f_live, self.live_in = scroll_area(main)  # Canlı sekmesi kaydırılabilir
        self.f_set = tk.Frame(main, bg=self.BG)
        self.f_info = tk.Frame(main, bg=self.BG)
        self.f_an = tk.Frame(main, bg=self.BG)
        self.f_acc = tk.Frame(main, bg=self.BG)
        self.f_hw = tk.Frame(main, bg=self.BG)
        self.f_vc = tk.Frame(main, bg=self.BG)
        self.f_rp = tk.Frame(main, bg=self.BG)
        self.f_tm = tk.Frame(main, bg=self.BG)
        self.cur = None

        def show(f):
            for x in (self.f_live, self.f_set, self.f_info, self.f_an, self.f_acc, self.f_hw, self.f_vc, self.f_rp, self.f_tm):
                x.pack_forget()
            f.pack(fill='both', expand=True, pady=(8, 0))
            self.cur = f
            for fr, (ind, b) in self.tabs.items():
                on = fr is f
                ind.config(bg=C_ACC if on else C_SIDE)
                b.config(bg=C_CARD if on else C_SIDE, fg=C_TXT if on else C_SUB)
                b._base = b.cget('bg')
            if f is self.f_set and not self.set_done:
                self.run_check()
            if f is self.f_info and not self.info_done:
                self.run_info()
            if f is self.f_vc and not self.vc_done:
                self.run_voice()
            if f is self.f_rp and not self.rp_done and load_cfg().get('api'):
                self.load_matches()
            if f is self.f_tm:
                self.root.after(50, self.tm_start)
            if f is self.f_an:
                self.ev_dirty = True
                self.refresh_analysis()

        for t, f in (('◉   Canlı', self.f_live), ('▤   Görev Yöneticisi', self.f_tm), ('◧   Analiz', self.f_an), ('◈   Ayar Kontrolü', self.f_set),
                     ('▦   Sistem Bilgisi', self.f_info), ('⚡   Donanım Testi', self.f_hw), ('♪   Takım Sesi', self.f_vc),
                     ('▷   Maç Tekrarı', self.f_rp),
                     ('◎   PUBG Hesap', self.f_acc)):
            row = tk.Frame(nav, bg=C_SIDE); row.pack(fill='x', pady=1)
            ind = tk.Frame(row, bg=C_SIDE, width=px(4)); ind.pack(side='left', fill='y')
            b = sbtn(row, t, lambda f=f: show(f), fg=C_SUB, font=(F_UI, 11, 'bold'))
            b.config(pady=6, padx=16)
            b.pack(side='left', fill='x', expand=True, padx=(0, 10))
            self.tabs[f] = (ind, b)
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
        btn(bb, '↻  Tekrar kontrol et', self.run_check).pack(side='left')
        btn(bb, '✔  Önerilenleri uygula (yedek alır)', self.run_apply, '#1f4d3a').pack(side='right')
        # Sistem bilgisi sekmesi
        self.itxt = textbox(self.f_info)
        ib = tk.Frame(self.f_info, bg=self.BG); ib.pack(fill='x', padx=12, pady=(0, 8))
        btn(ib, '↻  Yenile', self.run_info).pack(side='left')
        btn(ib, '⤓  Dosyaya kaydet', self.save_info).pack(side='right')
        self.build_live()
        self.build_analysis()
        self.build_account()
        self.build_hwtest()
        self.build_voice()
        self.build_replay_tab()
        self.build_tm_tab()
        show(self.f_live)
        threading.Thread(target=load_hw, daemon=True).start()
        threading.Thread(target=self.prepare_presentmon, daemon=True).start()
        NATIVE_GPU_OK[0] = bool(self.ngpu.kind)
        threading.Thread(target=self.update_loop, daemon=True).start()
        threading.Thread(target=self.match_watch, daemon=True).start()  # maç bitince rapor
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
        L = self.live_in
        for i in range(2):
            L.grid_columnconfigure(i, weight=1, uniform='c')
        T = lambda p, txt='', size=10, col=C_TXT, bold=False, font=F_UI: tk.Label(
            p, text=txt, bg=C_CARD, fg=col, font=(font, size, 'bold' if bold else 'normal'), anchor='w', justify='left')

        # FPS
        f = card(L, 'FPS'); f.grid(row=1, column=0, sticky='nsew', padx=(12, 6), pady=6)
        top = tk.Frame(f, bg=C_CARD); top.pack(fill='x', padx=12)
        self.v_fps = T(top, '—', 40, C_TXT, True, F_NUM); self.v_fps.pack(side='left')
        sub = tk.Frame(top, bg=C_CARD); sub.pack(side='left', padx=14)
        self.v_low = T(sub, '1% düşük  —', 10, C_SUB); self.v_low.pack(anchor='w')
        self.v_low01 = T(sub, '0.1% düşük  —', 10, C_SUB); self.v_low01.pack(anchor='w')
        self.v_ftm = T(sub, 'kare süresi  —', 10, C_SUB); self.v_ftm.pack(anchor='w')
        self.sp_fps = Spark(f, 410, 70, C_ACC); self.sp_fps.c.pack(padx=12, pady=(2, 10), fill='x')

        # Durum
        f = card(L, 'Durum'); f.grid(row=1, column=1, sticky='nsew', padx=(6, 12), pady=6)
        self.v_bound = T(f, 'Darboğaz: —', 14, C_TXT, True); self.v_bound.pack(anchor='w', padx=12, pady=(6, 2))
        self.v_stut = T(f, 'Takılma: 0', 11, C_TXT); self.v_stut.pack(anchor='w', padx=12)
        self.v_gpuratio = T(f, '', 10, C_SUB); self.v_gpuratio.pack(anchor='w', padx=12)
        self.v_sess = T(f, '', 10, C_SUB); self.v_sess.pack(anchor='w', padx=12, pady=(0, 4))
        self.sp_ft = Spark(f, 410, 50, C_WARN); self.sp_ft.c.pack(padx=12, pady=(0, 2), fill='x')
        T(f, 'en uzun kare süresi (ms) — sıçramalar takılmadır', 8, C_SUB).pack(anchor='w', padx=12, pady=(0, 8))

        # CPU
        f = card(L, 'İşlemci'); f.grid(row=2, column=0, sticky='nsew', padx=(12, 6), pady=6)
        self.v_cpuname = T(f, '', 9, C_SUB); self.v_cpuname.pack(anchor='w', padx=12)
        row = tk.Frame(f, bg=C_CARD); row.pack(fill='x', padx=8)
        self.g_cpu = Gauge(row, 130, 'SICAKLIK', '°C', 100, 85, 92); self.g_cpu.c.pack(side='left')
        self.g_cpul = Gauge(row, 100, 'YÜK', '%', 100, 85, 97); self.g_cpul.c.pack(side='left', padx=4)
        info = tk.Frame(row, bg=C_CARD); info.pack(side='left', padx=6, fill='y')
        self.v_mhz = T(info, '— MHz', 16, C_TXT, True, F_NUM); self.v_mhz.pack(anchor='w', pady=(14, 0))
        self.v_cmax = T(info, 'en dolu çekirdek —', 9, C_SUB); self.v_cmax.pack(anchor='w')
        self.v_ccnt = T(info, '', 9, C_SUB); self.v_ccnt.pack(anchor='w')
        self.core_box = tk.Frame(f, bg=C_CARD); self.core_box.pack(fill='x', padx=12, pady=(2, 10))
        # Windows işlemci sıcaklığını hiçbir programa vermez (sadece sürücü kuran araçlar okuyabilir)
        self.v_ct = T(f, 'İşlemci sıcaklığını Windows vermez; diğer tüm değerler Windows\'tan canlı okunuyor.', 9, C_SUB)
        self.core_w = []

        # GPU
        f = card(L, 'Ekran kartı'); f.grid(row=2, column=1, sticky='nsew', padx=(6, 12), pady=6)
        self.v_gpuname = T(f, '', 9, C_SUB); self.v_gpuname.pack(anchor='w', padx=12)
        row = tk.Frame(f, bg=C_CARD); row.pack(fill='x', padx=8)
        self.g_gpu = Gauge(row, 130, 'SICAKLIK', '°C', 100, 80, 87); self.g_gpu.c.pack(side='left')
        self.g_hs = Gauge(row, 100, 'HOT SPOT', '°C', 115, 95, 105); self.g_hs.c.pack(side='left', padx=4)
        self.g_gl = Gauge(row, 100, 'YÜK', '%', 100, 101, 101); self.g_gl.c.pack(side='left')
        self.v_gpw = T(f, '', 10, C_TXT); self.v_gpw.pack(anchor='w', padx=12)
        self.v_vram = T(f, 'VRAM —', 9, C_SUB); self.v_vram.pack(anchor='w', padx=12)
        self.b_vram = Bar(f, 400); self.b_vram.c.pack(anchor='w', padx=12, pady=(2, 10))

        # RAM
        f = card(L, 'Bellek'); f.grid(row=3, column=0, sticky='nsew', padx=(12, 6), pady=6)
        self.v_ram = T(f, '—', 16, C_TXT, True, F_NUM); self.v_ram.pack(anchor='w', padx=12)
        self.b_ram = Bar(f, 400); self.b_ram.c.pack(anchor='w', padx=12, pady=(2, 4))
        self.v_ram2 = T(f, '', 9, C_SUB); self.v_ram2.pack(anchor='w', padx=12, pady=(0, 2))
        self.v_disk = T(f, 'Disk  —', 10, C_TXT); self.v_disk.pack(anchor='w', padx=12, pady=(0, 10))

        # Ağ
        f = card(L, 'Ağ (1.1.1.1)'); f.grid(row=3, column=1, sticky='nsew', padx=(6, 12), pady=6)
        row = tk.Frame(f, bg=C_CARD); row.pack(fill='x', padx=12)
        self.v_ping = T(row, '— ms', 22, C_TXT, True, F_NUM); self.v_ping.pack(side='left')
        self.v_net = T(row, '', 9, C_SUB); self.v_net.pack(side='left', padx=12)
        self.sp_ping = Spark(f, 410, 40, C_OK, n=60); self.sp_ping.c.pack(padx=12, pady=(2, 10), fill='x')

        # Sorun bandı
        self.ban = tk.Frame(L, bg=C_CARD, highlightthickness=1, highlightbackground=C_LINE)
        self.ban.grid(row=0, column=0, columnspan=2, sticky='nsew', padx=12, pady=(0, 4))  # uyarılar en üstte
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
        no_ct = not v['cpu_t'] and self.tick_n > 8  # birkaç saniye sonra hâlâ yoksa sıcaklık kaynağı yok
        self.g_cpu.set(v['cpu_t'] or None, '' if v['cpu_t'] else ('sensör yok' if no_ct else 'sensör başlıyor'))
        if no_ct != (self.v_ct.winfo_manager() == 'pack'):
            self.v_ct.pack(anchor='w', padx=12, pady=(0, 8)) if no_ct else self.v_ct.pack_forget()
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
        self.render_mini(v)
        # Ağ
        if n['n']:
            pc = C_BAD if n['loss'] >= 10 or n['jit'] >= 20 else (C_WARN if n['loss'] or n['jit'] >= 8 else C_OK)
            setl(self.v_ping, text=f"{n['ping']} ms" if n['ping'] is not None else 'yanıt yok', fg=pc)
            setl(self.v_net, text=f"ort {n['avg']} · en fazla {n['max']} ms\ndalgalanma {n['jit']} ms · kayıp %{n['loss']}\n"
                                   f"↓ {n['down']:.1f}   ↑ {n['up']:.1f} Mbit/s")
            self.sp_ping.push(n['ping'])

    def render_mini(self, v):
        if not self.mini:
            return
        n = v['net']
        ping = f"{n['ping']} ms" if n.get('ping') is not None else '— ms'
        setl(self.mini_l, text=(f"{v['fps']:.0f} FPS" if v['ft'] else '— FPS') +
             f"   1% {v['low1']:.0f}   ·   CPU {v['cpu_t'] or '—'}°   ·   GPU {v['g_t'] or '—'}°   ·   {ping}",
             fg=C_BAD if v['st10'] >= 3 or v['cpu_t'] >= LIM['hot'] else C_TXT)

    def draw_cores(self, per, temps):
        nphys = len(temps) if temps else len(per)
        if not nphys or not self.core_box.winfo_viewable():
            return
        tpc = max(1, len(per) // nphys) if temps else 1
        # Çok çekirdekli işlemcide (ör. 24 iş parçacığı) en fazla 2 satır: kutular daralır, kart uzamaz
        cols = nphys if nphys <= 8 else (8 if nphys <= 16 else -(-nphys // 2))
        avail = max(px(400), self.core_box.winfo_width())
        W, H = min(px(48), avail // cols - 4), px(46)
        small = W < px(44)
        if len(self.core_w) != nphys:
            for w in self.core_box.winfo_children():
                w.destroy()
            self.core_w = []
            for i in range(nphys):
                cv = tk.Canvas(self.core_box, width=W, height=H, bg='#1f232c', highlightthickness=0)
                cv.grid(row=i // cols, column=i % cols, padx=2, pady=2)
                bar = cv.create_rectangle(0, H, W, H, fill='#24425a', outline='')
                cv.create_text(W / 2, px(9), text=f'Ç{i}', fill=C_SUB, font=(F_UI, 6 if small else 7, 'bold'))
                tt = cv.create_text(W / 2, px(24), text='', fill=C_OK, font=(F_NUM, 10 if small else 12, 'bold'))
                lt = cv.create_text(W / 2, px(38), text='', fill=C_TXT, font=(F_UI, 6 if small else 7))
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
    def side_status(self, text, col=C_SUB):
        self.root.after(0, lambda: setl(self.upd_side, text=text, fg=col))

    def update_loop(self):
        """Her açılışta hemen, sonra saatte bir yeni sürüm kontrol eder."""
        while True:
            self.side_status('↻  Güncelleme kontrol ediliyor…')
            try:
                info = check_update()
                if info and (not self.upd_info or info['ver'] != self.upd_info['ver']):
                    self.upd_info = info
                    self.side_status(f"⬇  v{info['ver']} indiriliyor…", C_ACC)
                    self.root.after(0, lambda: self.show_upd(f"⬇  Yeni sürüm v{info['ver']} indiriliyor..."))
                    path = download_update(info, lambda f: self.root.after(0, lambda: self.show_upd(
                        f"⬇  Yeni sürüm v{info['ver']} indiriliyor... %{f * 100:.0f}")))
                    self.upd_new = path
                    self.side_status(f"★  v{info['ver']} hazır, kuruluyor", C_ACC)
                    self.root.after(0, self.update_ready)
                elif not info:
                    self.side_status(f'✔  Güncel  ·  v{VERSION}\nson kontrol {datetime.datetime.now():%H:%M}', C_OK)
            except Exception:
                self.side_status(f'⚠  Güncelleme kontrol edilemedi\n(internet?)  ·  v{VERSION}', C_WARN)
            time.sleep(3600)

    def show_upd(self, text, button=False):
        if not self.upd.winfo_ismapped():
            self.upd.pack(fill='x', padx=12, pady=(10, 0), before=self.cur)
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
        self.show_upd(f"↻  v{self.upd_info['ver']} kuruluyor, program yeniden açılacak...")
        try:
            install_update(self.upd_new)
        except Exception as e:
            self.show_upd(f'✖  Güncelleme kurulamadı: {e}. Programı yönetici olarak açıp tekrar dene.', button=True)
            return
        self.root.after(800, lambda: self.close(report=False))

    def show_changes(self, updated=False):
        w = tk.Toplevel(self.root)
        w.title('Yenilikler'); w.configure(bg=C_BG); w.attributes('-topmost', True); w.geometry(f'{px(620)}x{px(480)}')
        style_window(w)
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
        foot = tk.Frame(w, bg=C_BG); foot.pack(fill='x', padx=16, pady=(0, 12))
        tk.Label(foot, text=f'Geliştiren: {DEV}', bg=C_BG, fg=C_SUB, font=(F_UI, 9, 'bold')).pack(side='left')
        if LINKEDIN:
            hover(tk.Button(foot, text='in  LinkedIn', command=lambda: os.startfile(LINKEDIN), bg='#0a66c2', fg='white',
                            relief='flat', bd=0, font=(F_UI, 9, 'bold'), padx=12, pady=3, cursor='hand2',
                            activebackground='#004182', activeforeground='white'), '#004182').pack(side='left', padx=10)
        tk.Button(foot, text='Tamam', command=w.destroy, bg=C_ACC, fg='#0e1014', relief='flat', bd=0, font=(F_UI, 10, 'bold'),
                  padx=18, pady=4).pack(side='right')

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

    # ---------------- Takım sesi sekmesi ----------------
    def build_voice(self):
        A = self.f_vc
        self.vc_done = False
        tk.Label(A, text='Takım iletişimi: arka plan sesi gitmesin, Discord kalitesinde konuş', bg=C_BG, fg=C_TXT,
                 font=(F_UI, 12, 'bold'), anchor='w').pack(fill='x', padx=12, pady=(10, 0))
        tk.Label(A, text='Mikrofon, PUBG oyun içi ses ve Discord ayarları kontrol edilir. Sorunlu olanlar en üstte.',
                 bg=C_BG, fg=C_SUB, font=(F_UI, 9), anchor='w').pack(fill='x', padx=12, pady=(0, 4))
        t = self.vtxt = tk.Text(A, bg=C_CARD, fg=C_TXT, font=(F_UI, 10), wrap='word', relief='flat', padx=12, pady=8,
                                highlightthickness=1, highlightbackground=C_LINE, highlightcolor=C_LINE)
        t.pack(fill='both', expand=True, padx=12, pady=(4, 4))
        for tag, col in (('ok', C_OK), ('warn', C_WARN), ('bad', C_BAD), ('info', C_ACC), ('dim', C_SUB), ('h', C_TXT)):
            t.tag_config(tag, foreground=col)
        t.tag_config('h', font=(F_UI, 11, 'bold'))
        bb = tk.Frame(A, bg=C_BG); bb.pack(fill='x', padx=12, pady=(0, 8))
        mk = lambda txt, cmd, bg=C_CARD: hover(tk.Button(bb, text=txt, command=cmd, bg=bg, fg=C_TXT, relief='flat', bd=0,
                                                         font=(F_UI, 10, 'bold'), padx=14, pady=6, cursor='hand2',
                                                         activebackground=C_LINE, activeforeground=C_TXT))
        mk('↻  Tekrar kontrol et', self.run_voice).pack(side='left')
        mk('⚙  Windows ses ayarları', lambda: os.startfile('ms-settings:sound')).pack(side='left', padx=6)
        mk('✔  Önerilenleri uygula', self.apply_voice_ui, '#1f4d3a').pack(side='right')

    def run_voice(self, then=None):
        if getattr(self, 'vc_busy', False):
            return
        self.vc_busy = True
        self._fill(self.vtxt, [('Kontrol ediliyor...\n', 'dim')])

        def work():
            rows = check_voice()
            pub = [r for r in rows if r[1].startswith('PUBG')]
            dis = [r for r in rows if r[1].startswith('Discord')]
            mic = [r for r in rows if r not in pub and r not in dis]
            return [('MİKROFON (WINDOWS)', mic), ('PUBG OYUN İÇİ SES', pub), ('DISCORD', dis)]

        def done(groups, err):
            self.vc_busy = False
            if err:
                self._fill(self.vtxt, [(f'Hata: {err}\n', 'bad')]); return
            self.show_check([g for g in groups if g[1]], self.vtxt)
            self.vc_done = True
            if then:
                then()
        self.bg(work, done)

    def apply_voice_ui(self):
        def done(msgs, err):
            if err:
                self._fill(self.vtxt, [(f'Uygulanamadı: {err}\n', 'bad')]); return

            def show():
                t = self.vtxt
                t.config(state='normal')
                t.insert('1.0', 'UYGULANDI:\n' + '\n'.join('• ' + m for m in msgs) + '\n\n', 'info')
                t.config(state='disabled')
            self.run_voice(then=show)
        self.bg(apply_voice, done)

    # ---------------- Donanım testi sekmesi ----------------
    def build_hwtest(self):
        A = self.f_hw
        top = tk.Frame(A, bg=C_BG); top.pack(fill='x', padx=12, pady=(8, 4))

        def mk(text, kind, bg=C_CARD):
            b = hover(tk.Button(top, text=text, command=lambda: self.run_hwtest(kind), bg=bg, fg=C_TXT, relief='flat', bd=0,
                                font=(F_UI, 10, 'bold'), padx=14, pady=6, cursor='hand2', activebackground=C_LINE,
                                activeforeground=C_TXT))
            b.pack(side='left', padx=(0, 6))
            return b
        self.hw_btns = [mk('▶  Tam test (~1 dk)', 'all', '#1f4d6b'), mk('Sensör kontrolü', 'sensor'), mk('İşlemci', 'cpu'),
                        mk('RAM', 'ram'), mk('Disk', 'disk')]
        self.hw_state = tk.Label(A, text='Testler PUBG kapalıyken yapılır. Sensör kontrolü her zaman çalışır.',
                                 bg=C_BG, fg=C_SUB, font=(F_UI, 9), anchor='w')
        self.hw_state.pack(fill='x', padx=12)
        self.hw_bar = Bar(A, 600, 6); self.hw_bar.c.pack(anchor='w', padx=12, pady=(4, 6))
        t = self.hw_txt = tk.Text(A, bg=C_CARD, fg=C_TXT, font=(F_UI, 10), wrap='word', relief='flat', padx=12, pady=8,
                                  highlightthickness=1, highlightbackground=C_LINE, highlightcolor=C_LINE)
        t.pack(fill='both', expand=True, padx=12, pady=(0, 10))
        for tag, col in (('ok', C_OK), ('warn', C_WARN), ('bad', C_BAD), ('info', C_ACC), ('dim', C_SUB), ('h', C_TXT)):
            t.tag_config(tag, foreground=col)
        t.tag_config('h', font=(F_UI, 11, 'bold'))
        self.hw_busy = False
        rows = [('Donanım testi\n', 'h'),
                ('• Sensör kontrolü: her sensörün nereden okunduğunu ve değerinin doğru olup olmadığını gösterir.\n', 'dim'),
                ('• İşlemci: 5 sn tek çekirdek + 30 sn tüm çekirdekler tam yük. Sıcaklık ve ısıdan hız düşürme ölçülür.\n', 'dim'),
                ('• RAM: bellek hızı ve boş RAM\'in bir kısmında yaz-oku kontrolü.\n', 'dim'),
                ('• Disk: PUBG\'nin kurulu olduğu diskte 1 GB yazma/okuma ve 4K rastgele okuma (Windows önbelleği atlanır).\n', 'dim'),
                ('• Ekran kartı oyunda test edilir: Analiz → 60 sn performans testi.\n', 'dim')]
        self._fill(t, rows)

    def hw_add(self, rows):
        t = self.hw_txt
        t.config(state='normal')
        for x, tag in rows:
            t.insert('end', x, tag) if tag else t.insert('end', x)
        t.see('end')
        t.config(state='disabled')

    def sensor_rows(self):
        v = getattr(self, 'snap', None)
        if not v:
            return [('Sensörler henüz okunmadı, birkaç saniye sonra tekrar dene.\n', 'warn')]
        R = []

        def row(st, name, val, note=''):
            icon = {'ok': '✔', 'warn': '⚠', 'bad': '✖', 'info': 'ℹ'}[st]
            R.append((f'{icon} {name}: {val}\n', st))
            if note:
                R.append((f'    {note}\n', 'dim'))
        R.append(('\n— SENSÖR KONTROLÜ —\n', 'h'))
        if v['cpu_src']:
            hwi = v['cpu_src'] == 'HWiNFO'
            row('ok' if 20 <= v['cpu_t'] <= 105 else 'warn', 'İşlemci sıcaklığı',
                f"{v['cpu_t']}°C  ({'HWiNFO, CPU Tctl/Tdie' if hwi else 'Core Temp, en sıcak çekirdek'})",
                ('Açık olan HWiNFO\'dan okunuyor (AMD Software ile aynı ölçüm). İsteğe bağlı.' if hwi else
                 'Açık olan Core Temp\'ten okunuyor (çekirdek sensörü). İsteğe bağlı.')
                if 20 <= v['cpu_t'] <= 105 else 'Değer olağan dışı, kaynağı kontrol et.')
        else:
            row('bad', 'İşlemci sıcaklığı', 'okunamıyor',
                'Windows işlemci sıcaklığını hiçbir programa vermez; bunu okuyan araçlar kendi sürücülerini kurar. '
                'Program harici araç kullanmaz. Diğer tüm değerler Windows\'tan.')
        row('ok', 'İşlemci yükü', f"%{v['cpu_tot']}  ({v['load_src']})",
            'Görev Yöneticisi ile aynı sayaç.' if v['load_src'] == 'Windows sayacı' else '')
        row('ok' if v['cpu_mhz'] else 'warn', 'İşlemci hızı', f"{v['cpu_mhz']} MHz  ({v['mhz_src'] or 'yok'})" if v['cpu_mhz'] else 'okunamıyor')
        gn = v['gname'] or 'ekran kartı'
        if v['g_t']:
            row('ok' if 20 <= v['g_t'] <= 105 else 'warn', 'Ekran kartı sıcaklığı', f"{v['g_t']}°C  ({v['gt_src']}, {gn})",
                'Görev Yöneticisi ile aynı kaynak.' if 'D3DKMT' in v['gt_src'] else '')
        else:
            row('bad', 'Ekran kartı sıcaklığı', 'okunamıyor', 'Ekran kartı sürücüsünü güncelle (Windows bu değeri sürücüden alır).')
        row('ok', 'Ekran kartı yükü ve VRAM', f"%{v['g_load']} · {v['vram'] / 1024:.1f} GB  ({v['gl_src'] or 'yok'})",
            'Sadece oyunun çalıştığı kart sayılır.')
        if v['gdet_src']:
            row('ok', 'Hot spot, saat, güç', f"{v['hs']}°C · {v['clk']} MHz · {v['pwr']} W  ({v['gdet_src']})")
        else:
            row('info', 'Hot spot ve güç', 'Windows vermiyor', 'Çekirdek ve bellek saati Windows\'tan okunuyor (Görev Yöneticisi sekmesi).')
        row('ok' if v['net_n'] and v['ping'] is not None else 'warn', 'Ağ (ping)',
            f"{v['ping']} ms" if v['ping'] is not None else 'yanıt yok')
        if v['game']:
            row('ok' if v['fps'] else 'warn', 'FPS (PresentMon)', f"{v['fps']:.0f}" if v['fps'] else 'oyun açık ama kare gelmiyor',
                '' if v['fps'] else 'Programı yönetici olarak aç; oyunda bir maça ya da Eğitim Modu\'na gir.')
        else:
            row('ok' if self.pm.exe else 'bad', 'FPS (PresentMon)', 'hazır, oyun açılınca ölçer' if self.pm.exe else 'indirilemedi')
        return R

    def run_hwtest(self, kind):
        if self.hw_busy:
            return
        if kind == 'sensor':
            self.hw_add(self.sensor_rows()); return
        if self.game_running():
            setl(self.hw_state, text='PUBG açık: donanım testi oyun kapalıyken yapılır (oyun sonuçları bozar, test de oyunu).', fg=C_BAD)
            return
        self.hw_busy = True
        for b in self.hw_btns:
            b.config(state='disabled')
        steps = ['cpu', 'ram', 'disk'] if kind == 'all' else [kind]
        if kind == 'all':
            self.hw_add(self.sensor_rows())
        folder = find_pubg_dir()
        if folder and shutil.disk_usage(folder).free < (5 << 30):
            folder = None
        folder = folder or DATA
        avail = psutil.virtual_memory().available / 1048576
        cpdh = CpuPdh()  # testin kendi sayacı (ana döngüdekiyle çakışmasın)

        def sample():
            cpdh.read()
            cs = hwinfo_cpu() or cpu_sensor() or {}
            return {'T': cs.get('T', 0), 'MHz': cs.get('MHz') or cpdh.mhz()}

        def ui(fn):
            self.root.after(0, fn)

        def work():
            res = {'date': datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}
            for i, st in enumerate(steps):
                name = {'cpu': 'İşlemci testi (35 sn, tam yük)', 'ram': 'RAM testi', 'disk': f'Disk testi ({folder[:2]})'}[st]
                ui(lambda name=name: setl(self.hw_state, text=f'⏳ {name} sürüyor…', fg=C_WARN))

                def prog(f, i=i):
                    ui(lambda: self.hw_bar.set((i + f) / len(steps), C_ACC))
                try:
                    if st == 'cpu':
                        res['cpu'] = cpu_test(prog, sample)
                    elif st == 'ram':
                        res['ram'] = ram_test(prog, avail)
                    else:
                        res['disk'] = disk_test(folder, prog)
                        res['disk']['drive'] = folder[:2]
                except Exception as e:
                    res[st] = {'error': str(e)}
            return res

        def done(res, err):
            self.hw_busy = False
            for b in self.hw_btns:
                b.config(state='normal')
            self.hw_bar.set(1, C_OK if not err else C_BAD)
            if err:
                setl(self.hw_state, text=f'Test hatası: {err}', fg=C_BAD); return
            h = load_hwtests()
            prev = {k: next((x[k] for x in reversed(h) if k in x and 'error' not in x[k]), None) for k in ('cpu', 'ram', 'disk')}
            h.append(res); save_hwtests(h)
            self.hw_add(self.hw_report(res, prev))
            setl(self.hw_state, text=f"✔ Test bitti ({res['date']}). Sonuçlar kaydedildi; sonraki testte karşılaştırılır.", fg=C_OK)
        self.bg(work, done)

    def hw_report(self, r, prev):
        R = []

        def row(st, name, val, note=''):
            icon = {'ok': '✔', 'warn': '⚠', 'bad': '✖', 'info': 'ℹ'}[st]
            R.append((f'{icon} {name}: {val}\n', st))
            if note:
                R.append((f'    {note}\n', 'dim'))

        def cmp(cur, old, unit=''):
            if not old:
                return ''
            d = (cur - old) / old * 100 if old else 0
            return f'   (önceki: {old:g}{unit}, {d:+.0f}%)'
        c = r.get('cpu')
        if c:
            R.append(('\n— İŞLEMCİ —\n', 'h'))
            if 'error' in c:
                row('bad', 'Test yapılamadı', c['error'])
            else:
                p = prev.get('cpu') or {}
                row('info', 'Tek çekirdek puanı', f"{c['single']}{cmp(c['single'], p.get('single'))}")
                row('info', 'Çok çekirdek puanı', f"{c['multi']}  (x{c['scale']}, {c['threads']} iş parçacığı){cmp(c['multi'], p.get('multi'))}")
                hot = LIM['hot']
                if c['t_max']:
                    st = 'bad' if c['t_max'] >= hot else ('warn' if c['t_max'] >= hot - 7 else 'ok')
                    row(st, 'Tam yükte en yüksek sıcaklık', f"{c['t_max']}°C  (boşta {c['t_idle']}°C)",
                        {'bad': f'{hot}°C sınırına dayandı. Soğutucu oturması, termal macun ve kasa hava akışını kontrol et.',
                         'warn': 'Yüksek ama sınırın altında. Yaz aylarında oyunda sınıra yaklaşabilir.', 'ok': ''}[st])
                else:
                    row('info', 'Tam yükte sıcaklık', 'ölçülemedi', 'Windows işlemci sıcaklığını vermiyor; hız düşüşü (aşağıda) yine ölçülür.')
                if c['mhz_first']:
                    st = 'bad' if c['drop'] >= 10 else ('warn' if c['drop'] >= 5 else 'ok')
                    row(st, 'Yük altında hız', f"{c['mhz_first']} → {c['mhz_last']} MHz  (düşüş %{max(0, c['drop'])})",
                        {'bad': 'İşlemci ısıdan ya da güç sınırından hız düşürüyor (throttling): oyunda FPS dalgalanır.',
                         'warn': 'Hafif hız düşüşü var.', 'ok': 'Hız düşüşü yok.'}[st])
        m = r.get('ram')
        if m:
            R.append(('\n— RAM —\n', 'h'))
            if 'error' in m:
                row('bad', 'Test yapılamadı', m['error'])
            else:
                p = prev.get('ram') or {}
                row('ok' if m['bw'] >= 12 else 'warn', 'Bellek kopyalama hızı', f"{m['bw']} GB/s{cmp(m['bw'], p.get('bw'), ' GB/s')}",
                    '' if m['bw'] >= 12 else 'Düşük: tek modül (tek kanal) ya da XMP/EXPO kapalı olabilir. Ayar Kontrolü\'nde RAM hızına bak.')
                row('ok' if not m['errors'] else 'bad', 'Yaz-oku kontrolü', f"{m['checked_mb']} MB, {m['errors']} hata",
                    'Hızlı kontrol; MemTest86 yerine geçmez.' if not m['errors'] else
                    'RAM HATASI! Oyun çökmeleri buradan olabilir. XMP/EXPO\'yu kapatıp tekrar dene, sonra MemTest86 ile test et.')
        d = r.get('disk')
        if d:
            R.append((f"\n— DİSK ({d.get('drive', '')}) —\n", 'h'))
            if 'error' in d:
                row('bad', 'Test yapılamadı', d['error'])
            else:
                p = prev.get('disk') or {}
                rd = d['read']
                st = 'ok' if rd >= 1500 else ('info' if rd >= 400 else 'bad')
                row(st, 'Sıralı okuma', f"{rd} MB/s{cmp(rd, p.get('read'), ' MB/s')}",
                    {'ok': 'NVMe SSD seviyesi.', 'info': 'SATA SSD seviyesi, PUBG için yeterli.',
                     'bad': 'HDD seviyesi: PUBG\'de harita yüklemesinde takılma olur. Oyunu SSD\'ye taşı.'}[st])
                row('ok' if d['write'] >= 300 else 'warn', 'Sıralı yazma', f"{d['write']} MB/s{cmp(d['write'], p.get('write'), ' MB/s')}")
                st = 'ok' if d['r4k'] >= 25 else ('warn' if d['r4k'] >= 5 else 'bad')
                row(st, '4K rastgele okuma', f"{d['r4k']} MB/s ({d['iops']} IOPS){cmp(d['r4k'], p.get('r4k'), ' MB/s')}",
                    {'ok': 'Oyun içi yüklemeler için iyi.', 'warn': 'Orta: dolu ya da eski SSD olabilir.',
                     'bad': 'Çok yavaş: eşya/harita yüklenirken takılma yapar.'}[st])
        return R

    # ---------------- Maç bitince otomatik rapor ----------------
    def match_watch(self):
        """Oyun açıkken (ya da kapandıktan sonraki 15 dk) 2 dakikada bir son maçı sorar; yeni maç bittiyse raporunu
        hazırlar. En düşük öncelikte çalışır, oyun sırasında büyük harita indirmez (pingi etkilemesin)."""
        try:
            k = ctypes.windll.kernel32
            k.SetThreadPriority(k.GetCurrentThread(), -2)  # THREAD_PRIORITY_LOWEST
        except Exception:
            pass
        seen = None
        while True:
            time.sleep(120)
            c = load_cfg()
            key = c.get('api')
            if not key or not (self.game_pid or time.time() - getattr(self, 'game_end', 0) < 900):
                continue
            try:
                aid, nm, ids = recent_matches(key, c.get('name', ''), 1)
            except Exception:
                continue
            if not ids:
                continue
            if seen is None:  # ilk sorguda görülen maç, program açılmadan önce oynanmış: rapor gösterilmez
                seen = ids[0]
                continue
            if ids[0] == seen:
                continue
            seen = ids[0]
            try:
                m = match_summary(ids[0], key, aid)
                out, img, hd, rep = build_replay(m)
            except Exception:
                continue
            self.root.after(0, lambda m=m, out=out, rep=rep: self.show_report_band(m, out, rep))

    def show_report_band(self, m, out, rep):
        mapn = MAP_INFO.get(m['map'], (m['map'],))[0]
        top = ''
        if rep:
            t = next((x for x in rep['tips'] if x[0] in ('bad', 'warn')), None)
            top = ('   ·   ' + t[1]) if t else (('   ·   ' + rep['good'][0]) if rep['good'] else '')
        setl(self.rep_txt, text=f"★  Maç raporu hazır: #{m.get('rank') or '?'} {mapn} · {m.get('kills', 0)} öldürme · "
                                f"{m.get('dmg', 0):.0f} hasar{top}"[:260])
        self.rep_btn.config(command=lambda: os.startfile(out))
        if not self.rep_band.winfo_ismapped():
            self.rep_band.pack(fill='x', padx=12, pady=(10, 0), before=self.cur)

    # ---------------- Maç tekrarı sekmesi ----------------
    def build_replay_tab(self):
        A = self.f_rp
        self.rp_done, self.rp_busy, self.rp_rows = False, False, []
        tk.Label(A, text='Maç tekrarı', bg=C_BG, fg=C_TXT, font=(F_UI, 12, 'bold'), anchor='w').pack(fill='x', padx=12, pady=(10, 0))
        tk.Label(A, text='Son maçlarını haritada oynat: herkesin hareketi, mavi bölge, atışlar ve öldürmeler. Resmî PUBG verisiyle, '
                         'maç bittikten ~1 dakika sonra hazır olur. Tekrar tarayıcıda açılır.',
                 bg=C_BG, fg=C_SUB, font=(F_UI, 9), anchor='w', justify='left', wraplength=px(900)).pack(fill='x', padx=12)
        top = tk.Frame(A, bg=C_BG); top.pack(fill='x', padx=12, pady=(8, 4))
        hover(tk.Button(top, text='↻  Son maçları getir', command=self.load_matches, bg='#1f4d6b', fg=C_TXT, relief='flat', bd=0,
                        font=(F_UI, 10, 'bold'), padx=14, pady=6, cursor='hand2', activebackground=C_LINE,
                        activeforeground=C_TXT)).pack(side='left')
        hover(tk.Button(top, text='◎  İniş ve ölüm haritası', command=self.open_heatmap, bg=C_CARD, fg=C_TXT, relief='flat', bd=0,
                        font=(F_UI, 10, 'bold'), padx=14, pady=6, cursor='hand2', activebackground=C_LINE,
                        activeforeground=C_TXT)).pack(side='left', padx=(6, 0))
        self.v_hd = tk.IntVar(value=1 if load_cfg().get('hd_map', True) else 0)
        tk.Checkbutton(top, text='Yüksek çözünürlüklü harita (harita başına bir kez ~100 MB indirir, ~20 MB yer kaplar)',
                       variable=self.v_hd, command=lambda: (lambda c: (c.update(hd_map=bool(self.v_hd.get())), save_cfg(c)))(load_cfg()),
                       bg=C_BG, fg=C_TXT, selectcolor=C_CARD, activebackground=C_BG, activeforeground=C_TXT,
                       font=(F_UI, 9)).pack(side='left', padx=12)
        self.rp_state = tk.Label(A, text='', bg=C_BG, fg=C_SUB, font=(F_UI, 9), anchor='w')
        self.rp_state.pack(fill='x', padx=12)
        self.rp_bar = Bar(A, 600, 6); self.rp_bar.c.pack(anchor='w', padx=12, pady=(4, 6))
        outer, self.rp_list = scroll_area(A)
        outer.pack(fill='both', expand=True, padx=12, pady=(0, 10))

    def open_heatmap(self):
        if self.rp_busy:
            return
        c = load_cfg()
        if not c.get('api'):
            self.rp_status('Önce PUBG Hesap sekmesinde ücretsiz API anahtarını gir.', 0, C_BAD); return
        self.rp_busy = True
        self.rp_status('Son maçlar toplanıyor (ilk seferde ~1 dk; sonra sadece yeni maçlar)…', 0)

        def work():
            out = build_heatmap(c['api'], c.get('name', ''), lambda txt, f=None: self.rp_status('⏳ ' + txt, f))
            os.startfile(out)
            return out

        def done(res, err):
            self.rp_busy = False
            if err:
                msg = {429: 'Çok sık istek: 1 dakika bekle.'}.get(getattr(err, 'code', 0), f'Isı haritası açılamadı: {err}')
                self.rp_status(msg, 0, C_BAD)
            else:
                self.rp_status('✔ İniş ve ölüm haritası tarayıcıda açıldı.', 1, C_OK)
        self.bg(work, done)

    def rp_status(self, text, frac=None, col=C_SUB):
        def f():
            setl(self.rp_state, text=text, fg=col)
            if frac is not None:
                self.rp_bar.set(frac, C_ACC if frac < 1 else C_OK)
        self.root.after(0, f)

    def load_matches(self):
        if self.rp_busy:
            return
        c = load_cfg()
        key, name = c.get('api', ''), c.get('name', '')
        if not key:
            self.rp_status('Önce PUBG Hesap sekmesinde ücretsiz API anahtarını gir.', 0, C_BAD); return
        self.rp_busy = True
        for w in self.rp_list.winfo_children():
            w.destroy()
        self.rp_status('Maç listesi alınıyor…', 0.05)

        def work():
            aid, nm, ids = recent_matches(key, name)
            out = []
            for i, mid in enumerate(ids):
                try:
                    m = match_summary(mid, key, aid)
                except Exception:
                    continue
                out.append(m)
                self.root.after(0, lambda m=m: self.rp_row(m))
                self.rp_status(f'{nm}: maçlar alınıyor… {i + 1}/{len(ids)}', (i + 1) / max(1, len(ids)))
            return nm, out

        def done(res, err):
            self.rp_busy = False
            if err:
                msg = {401: 'API anahtarı geçersiz.', 404: 'Oyuncu bulunamadı.', 429: 'Çok sık istek: 1 dakika bekle.'}.get(
                    getattr(err, 'code', 0), f'Hata: {err}')
                self.rp_status(msg, 0, C_BAD); return
            nm, ms = res
            self.rp_done = True
            self.rp_status(f'{nm}: son {len(ms)} maç (PUBG son 14 günü saklar). Bir maçın yanındaki "Tekrarı aç"a tıkla.', 1, C_OK)
            if not ms:
                tk.Label(self.rp_list, text='Son 14 günde maç yok.', bg=C_BG, fg=C_SUB, font=(F_UI, 10)).pack(anchor='w', pady=8)
        self.bg(work, done)

    def rp_row(self, m):
        f = tk.Frame(self.rp_list, bg=C_CARD, highlightthickness=1, highlightbackground=C_LINE)
        f.pack(fill='x', pady=3)
        mapn = MAP_INFO.get(m['map'], (m['map'],))[0]
        try:
            dt = datetime.datetime.fromisoformat(m['date'].rstrip('Z')).replace(tzinfo=datetime.timezone.utc).astimezone()
            when = dt.strftime('%d.%m %H:%M')
        except Exception:
            when = m['date'][:16]
        rk = m.get('rank') or 0
        col = C_OK if rk == 1 else (C_WARN if rk and rk <= 10 else C_TXT)
        tk.Label(f, text=f'#{rk}' if rk else '—', bg=C_CARD, fg=col, font=(F_NUM, 16, 'bold'), width=4).pack(side='left', padx=(10, 4), pady=6)
        info = tk.Frame(f, bg=C_CARD); info.pack(side='left', fill='x', expand=True)
        tk.Label(info, text=f"{mapn}  ·  {MODE_TR.get(m['mode'], m['mode'])}" + ('  ·  dereceli' if m['type'] == 'competitive' else ''),
                 bg=C_CARD, fg=C_TXT, font=(F_UI, 10, 'bold'), anchor='w').pack(fill='x')
        tk.Label(info, text=f"{when}  ·  {m['kills']} öldürme  ·  {m['dmg']:.0f} hasar  ·  {m['dur'] // 60} dk", bg=C_CARD, fg=C_SUB,
                 font=(F_UI, 9), anchor='w').pack(fill='x')
        b = hover(tk.Button(f, text='▶  Tekrarı aç', bg=C_ACC, fg='#0e1014', relief='flat', bd=0, font=(F_UI, 10, 'bold'), padx=14,
                            pady=5, cursor='hand2', activebackground='#7ad3ff'), '#7ad3ff')
        b.config(command=lambda: self.open_replay(m, b))
        b.pack(side='right', padx=10)
        if not m.get('tel'):
            b.config(state='disabled', text='veri yok')

    def open_replay(self, m, btn):
        if self.rp_busy:
            return
        self.rp_busy = True
        btn.config(state='disabled')
        want_hd = bool(self.v_hd.get())

        def work():
            out, img, hd, _ = build_replay(m, lambda txt, f=None: self.rp_status('⏳ ' + txt, f))
            os.startfile(out)
            if want_hd and not hd:  # tekrar hemen açıldı; keskin harita arka planda hazırlanır, sonraki açılışta kullanılır
                self.rp_status('Tekrar açıldı. Yüksek çözünürlüklü harita hazırlanıyor (bir kerelik)…', 0)
                build_hd_tiles(img, lambda f: self.rp_status('Yüksek çözünürlüklü harita hazırlanıyor (bir kerelik)…', f))
                build_replay(m)  # sayfayı keskin haritayla yeniden yaz
                return 'hd'
            return 'ok'

        def done(res, err):
            self.rp_busy = False
            btn.config(state='normal')
            if err:
                self.rp_status(f'Tekrar açılamadı: {err}', 0, C_BAD)
            elif res == 'hd':
                self.rp_status('✔ Keskin harita hazır: sayfayı yenile (F5) ya da tekrarı yeniden aç.', 1, C_OK)
            else:
                self.rp_status('✔ Tekrar tarayıcıda açıldı.', 1, C_OK)
        self.bg(work, done)

    # ---------------- Görev Yöneticisi sekmesi ----------------
    TM_COL = {'cpu': ('#4cc2ff', '#13304a'), 'mem': ('#b57cff', '#2c1f45'), 'disk': ('#5ad17a', '#16331f'),
              'net': ('#e8a33d', '#3a2a12'), 'gpu': ('#4cc2ff', '#13304a')}

    def build_tm_tab(self):
        A = self.f_tm
        self.tm, self.tm_running, self.tm_sel, self.tm_items, self.tm_hist, self.tm_last = None, False, 'cpu', {}, {}, None
        self.tm_left = tk.Frame(A, bg=C_BG, width=px(250))
        self.tm_left.pack(side='left', fill='y', padx=(12, 6), pady=10)
        self.tm_left.pack_propagate(False)
        self.tm_right = tk.Frame(A, bg=C_BG)
        self.tm_right.pack(side='left', fill='both', expand=True, padx=(6, 12), pady=10)
        tk.Label(self.tm_right, text='Yükleniyor…', bg=C_BG, fg=C_SUB, font=(F_UI, 10)).pack()

    def tm_start(self):
        if not self.tm_running:
            self.tm_running = True
            self.tm_tick()

    def tm_hist_push(self, key, v):
        d = self.tm_hist.setdefault(key, collections.deque([0.0] * 60, maxlen=60))
        d.append(max(0.0, float(v or 0)))

    def tm_tick(self):
        if not self.f_tm.winfo_ismapped():  # sekme kapalıyken hiç ölçüm yapılmaz
            self.tm_running = False
            return
        try:
            if self.tm is None:
                self.tm = TmCounters(self.kmt.luid)
                self.root.after(1000, self.tm_tick)
                return
            s = self.tm_last = self.tm.sample()
            vm = psutil.virtual_memory()
            s['memtotal'], s['memused'] = vm.total, vm.total - s['avail'] if s['avail'] else vm.used
            s['kmt'] = self.kmt.read() or {}
            self.tm_hist_push('cpu', s['cpu'])
            self.tm_hist_push('mem', s['memused'] / (1 << 30))
            for i, v in enumerate(s['percpu']):
                self.tm_hist_push(f'cpu{i}', v)
            for n, d in s['disks'].items():
                self.tm_hist_push('disk:' + n, d['active'])
            for n, d in s['net'].items():
                self.tm_hist_push('net:' + n, d.get('tx', 0) + d.get('rx', 0))
                self.tm_hist_push('nettx:' + n, d.get('tx', 0))
                self.tm_hist_push('netrx:' + n, d.get('rx', 0))
            self.tm_hist_push('gpu', s['gpu'])
            for t, v in s['gpu_eng'].items():
                self.tm_hist_push('eng:' + t, v)
            self.tm_hist_push('ded', s['ded'] / (1 << 30))
            self.tm_hist_push('shr', s['shr'] / (1 << 30))
            self.tm_update_list(s)
            self.tm_update_detail(s)
        except Exception as e:
            setl(self.l_state, text=f'Görev Yöneticisi görünümü: {e}')
        self.root.after(1000, self.tm_tick)

    # sol liste
    def tm_keys(self, s):
        keys = ['cpu', 'mem']
        keys += ['disk:' + n for n in sorted(s['disks'], key=lambda x: int(x.split()[0]) if x.split()[0].isdigit() else 99)]
        for n in s['net']:
            if re.search(r' _\d+$', n) or re.search(r'loopback|isatap|teredo|6to4|kernel debug', n, re.I):
                continue
            if sum(self.tm_hist.get('net:' + n, [0])) > 0:  # bağlı (trafiği olan) bağdaştırıcılar, Görev Yöneticisi gibi
                keys.append('net:' + n)
        keys.append('gpu')
        return keys

    def tm_label(self, key):
        if key == 'cpu':
            return 'CPU'
        if key == 'mem':
            return 'Bellek'
        if key == 'gpu':
            return 'GPU 0'
        if key.startswith('disk:'):
            n = key[5:].split()
            return f"Disk {n[0]} ({' '.join(n[1:])})" if len(n) > 1 else f'Disk {n[0]}'
        n = key[4:].lower()
        return 'Ethernet' if 'ethernet' in n or 'gbe' in n else ('Wi-Fi' if 'wi-fi' in n or 'wireless' in n or 'wlan' in n else key[4:][:18])

    def tm_update_list(self, s):
        keys = self.tm_keys(s)
        if list(self.tm_items) != keys:
            for w in self.tm_left.winfo_children():
                w.destroy()
            self.tm_items = {}
            for k in keys:
                kind = k.split(':')[0]
                col, fill = self.TM_COL[kind]
                f = tk.Frame(self.tm_left, bg=C_BG, cursor='hand2')
                f.pack(fill='x', pady=2)
                g = TmGraph(f, 68, 46, col, fill, 100.0 if kind in ('cpu', 'gpu', 'disk') else None, grid=False)
                g.c.pack(side='left', padx=(8, 8), pady=6)
                tx = tk.Frame(f, bg=C_BG); tx.pack(side='left', fill='x', expand=True)
                nl = tk.Label(tx, text=self.tm_label(k), bg=C_BG, fg=C_TXT, font=(F_UI, 11, 'bold'), anchor='w')
                nl.pack(fill='x')
                vl = tk.Label(tx, text='', bg=C_BG, fg=C_SUB, font=(F_UI, 9), anchor='w', justify='left')
                vl.pack(fill='x')
                for w in (f, g.c, tx, nl, vl):
                    w.bind('<Button-1>', lambda e, k=k: self.tm_select(k))
                self.tm_items[k] = (f, g, nl, vl, tx)
            if self.tm_sel not in self.tm_items:
                self.tm_sel = 'cpu'
            self.tm_select(self.tm_sel, force=True)
        for k, (f, g, nl, vl, tx) in self.tm_items.items():
            on = k == self.tm_sel
            for w in (f, tx, nl, vl):
                setl(w, bg=C_CARD if on else C_BG)
            hist = self.tm_hist.get('mem' if k == 'mem' else k)
            if hist:
                if k == 'mem':
                    g.vmax, g.auto = s['memtotal'] / (1 << 30), False
                g.d = collections.deque(hist, maxlen=60)
                g.draw()
            if k == 'cpu':
                txt = f"%{s['cpu']:.0f}  {HW.get('cpu', {}).get('mhz', 0) * s['perf'] / 100000:.2f} GHz"
            elif k == 'mem':
                txt = f"{s['memused'] / (1 << 30):.1f}/{s['memtotal'] / (1 << 30):.1f} GB (%{100 * s['memused'] / s['memtotal']:.0f})"
            elif k.startswith('disk:'):
                d = s['disks'].get(k[5:], {})
                info = self.tm_disk_info(k[5:])
                txt = f"{(info or {}).get('type', '')} ({(info or {}).get('bus', '')})\n%{d.get('active', 0):.0f}"
            elif k.startswith('net:'):
                d = s['net'].get(k[4:], {})
                txt = f"G: {fmt_bits(d.get('tx', 0))}  A: {fmt_bits(d.get('rx', 0))}"
            else:
                t = s['kmt'].get('T')
                txt = f"{(self.ngpu.main or '')[:26]}\n%{s['gpu']:.0f}" + (f"  ({t} °C)" if t else '')
            setl(vl, text=txt)

    def tm_disk_info(self, inst):
        num_ = inst.split()[0]
        return next((d for d in HW.get('disks') or [] if str(d.get('id')) == num_), None)

    # sağ ayrıntı
    def tm_select(self, key, force=False):
        if key == self.tm_sel and not force:
            return
        self.tm_sel = key
        R = self.tm_right
        for w in R.winfo_children():
            w.destroy()
        kind = key.split(':')[0]
        col, fill = self.TM_COL[kind]
        self.tm_dw, self.tm_graphs = {}, {}
        head = tk.Frame(R, bg=C_BG); head.pack(fill='x')
        title = {'cpu': 'CPU', 'mem': 'Bellek', 'gpu': 'GPU'}.get(kind) or self.tm_label(key)
        tk.Label(head, text=title, bg=C_BG, fg=C_TXT, font=(F_UI, 22, 'bold')).pack(side='left')
        sub = {'cpu': (HW.get('cpu') or {}).get('name', ''), 'mem': f"{HW.get('ram_gb', 0)} GB",
               'gpu': self.ngpu.main or ''}.get(kind, '')
        if kind == 'disk':
            sub = (self.tm_disk_info(key[5:]) or {}).get('name', '')
        elif kind == 'net':
            sub = key[4:]
        tk.Label(head, text=sub, bg=C_BG, fg=C_TXT, font=(F_UI, 12)).pack(side='right', pady=(10, 0))

        def caption(parent, left, right):
            r = tk.Frame(parent, bg=C_BG); r.pack(fill='x', pady=(6, 1))
            tk.Label(r, text=left, bg=C_BG, fg=C_SUB, font=(F_UI, 9)).pack(side='left')
            lab = tk.Label(r, text=right, bg=C_BG, fg=C_SUB, font=(F_UI, 9))
            lab.pack(side='right')
            return lab

        def graph(parent, key_, h, vmax, color=col, fl=fill):
            g = TmGraph(parent, 600, h, color, fl, vmax)
            g.c.pack(fill='both', expand=True)
            if key_ in self.tm_hist:
                g.d = collections.deque(self.tm_hist[key_], maxlen=60)
            self.tm_graphs[key_] = g
            return g
        if kind == 'cpu':
            self.tm_cpu_box = tk.Frame(R, bg=C_BG); self.tm_cpu_box.pack(fill='both', expand=True)
            caption(self.tm_cpu_box, '% Kullanım', '%100')
            graph(self.tm_cpu_box, 'cpu', 260, 100.0)
            self.tm_logical = False
            b = hover(tk.Button(R, text='▦  Mantıksal işlemciler', command=self.tm_toggle_logical, bg=C_CARD, fg=C_TXT, relief='flat',
                                bd=0, font=(F_UI, 9, 'bold'), padx=10, pady=3, cursor='hand2'))
            b.pack(anchor='e', pady=(4, 0))
        elif kind == 'mem':
            caption(R, 'Bellek kullanımı', f"{HW.get('ram_gb', 0)} GB")
            graph(R, 'mem', 220, psutil.virtual_memory().total / (1 << 30))
            tk.Label(R, text='Bellek bileşimi', bg=C_BG, fg=C_SUB, font=(F_UI, 9), anchor='w').pack(fill='x', pady=(8, 1))
            self.tm_comp = tk.Canvas(R, height=px(34), bg='#11151c', highlightthickness=1, highlightbackground=col)
            self.tm_comp.pack(fill='x')
        elif kind == 'disk':
            caption(R, 'Etkin süre', '%100')
            graph(R, key, 200, 100.0)
            self.tm_disk_cap = caption(R, 'Disk aktarım hızı', '')
            graph(R, 'diskx:' + key[5:], 110, None)
        elif kind == 'net':
            self.tm_net_cap = caption(R, 'Aktarım hızı', '')
            graph(R, 'net:' + key[4:], 260, None)
        else:
            grid = tk.Frame(R, bg=C_BG); grid.pack(fill='both', expand=True)
            for i, (t, lab) in enumerate((('3d', '3D'), ('copy', 'Copy'), ('videoencode', 'Video Encode'), ('videodecode', 'Video Decode'))):
                cell = tk.Frame(grid, bg=C_BG)
                cell.grid(row=i // 2, column=i % 2, sticky='nsew', padx=(0 if i % 2 == 0 else 6, 0), pady=(0, 4))
                caption(cell, lab, '%100')
                g = TmGraph(cell, 300, 110, col, fill, 100.0)
                g.c.pack(fill='both', expand=True)
                g.d = collections.deque(self.tm_hist.get('eng:' + t, [0.0] * 60), maxlen=60)
                self.tm_graphs['eng:' + t] = g
            grid.grid_columnconfigure(0, weight=1); grid.grid_columnconfigure(1, weight=1)
            self.tm_ded_cap = caption(R, 'Ayrılmış GPU belleği kullanımı', '')
            graph(R, 'ded', 60, max([x['vram'] for x in HW.get('gpus') or []] or [1]) / 1024)
            self.tm_shr_cap = caption(R, 'Paylaşılan GPU belleği kullanımı', '')
            graph(R, 'shr', 60, psutil.virtual_memory().total / 2 / (1 << 30))
        tk.Frame(R, bg=C_BG, height=px(6)).pack()
        stats = tk.Frame(R, bg=C_BG); stats.pack(fill='x', pady=(6, 0))
        dyn = tk.Frame(stats, bg=C_BG); dyn.pack(side='left', anchor='n', fill='x', expand=True)
        sta = tk.Frame(stats, bg=C_BG); sta.pack(side='left', anchor='n', padx=(20, 0))
        names = {'cpu': ['Kullanım', 'Hız', 'İşlemler', 'İş parçacıkları', 'Tanıtıcılar', 'Çalışma süresi'],
                 'mem': ['Kullanımda', 'Kullanılabilir', 'Kaydedilen', 'Önbelleğe alınan', 'Disk belleğine alınan havuz',
                         'Disk belleğine alınmayan havuz'],
                 'disk': ['Etkin süre', 'Ortalama yanıt süresi', 'Okuma hızı', 'Yazma hızı'],
                 'net': ['Gönder', 'Al'],
                 'gpu': ['Kullanım', 'Ayrılmış GPU belleği', 'Paylaşılan GPU belleği', 'GPU sıcaklığı', 'Çekirdek saati',
                         'Bellek saati']}[kind]
        for i, n in enumerate(names):
            cell = tk.Frame(dyn, bg=C_BG)
            cell.grid(row=i // 3, column=i % 3, sticky='w', padx=(0, 26), pady=(0, 8))
            tk.Label(cell, text=n, bg=C_BG, fg=C_SUB, font=(F_UI, 9), anchor='w').pack(anchor='w')
            v = tk.Label(cell, text='—', bg=C_BG, fg=C_TXT, font=(F_UI, 15), anchor='w')
            v.pack(anchor='w')
            self.tm_dw[n] = v
        for i, (a, b) in enumerate(self.tm_static(key)):
            tk.Label(sta, text=a + ':', bg=C_BG, fg=C_SUB, font=(F_UI, 9), anchor='w').grid(row=i, column=0, sticky='w', pady=1)
            tk.Label(sta, text=b, bg=C_BG, fg=C_TXT, font=(F_UI, 9), anchor='w').grid(row=i, column=1, sticky='w', padx=(14, 0), pady=1)
        if self.tm_last:
            self.tm_update_detail(self.tm_last)

    def tm_toggle_logical(self):
        self.tm_logical = not self.tm_logical
        box = self.tm_cpu_box
        for w in box.winfo_children():
            w.destroy()
        for k in [k for k in self.tm_graphs if k.startswith('cpu')]:
            del self.tm_graphs[k]
        col, fill = self.TM_COL['cpu']
        if not self.tm_logical:
            r = tk.Frame(box, bg=C_BG); r.pack(fill='x', pady=(6, 1))
            tk.Label(r, text='% Kullanım', bg=C_BG, fg=C_SUB, font=(F_UI, 9)).pack(side='left')
            tk.Label(r, text='%100', bg=C_BG, fg=C_SUB, font=(F_UI, 9)).pack(side='right')
            g = TmGraph(box, 600, 260, col, fill, 100.0); g.c.pack(fill='both', expand=True)
            g.d = collections.deque(self.tm_hist.get('cpu', [0.0] * 60), maxlen=60)
            self.tm_graphs['cpu'] = g
            return
        n = len((self.tm_last or {}).get('percpu') or []) or (psutil.cpu_count() or 1)
        cols = 4 if n <= 16 else (6 if n <= 36 else 8)
        grid = tk.Frame(box, bg=C_BG); grid.pack(fill='both', expand=True, pady=(6, 0))
        for i in range(n):
            g = TmGraph(grid, 140, 70, col, fill, 100.0, grid=False)
            g.c.grid(row=i // cols, column=i % cols, sticky='nsew', padx=2, pady=2)
            g.d = collections.deque(self.tm_hist.get(f'cpu{i}', [0.0] * 60), maxlen=60)
            self.tm_graphs[f'cpu{i}'] = g
        for c_ in range(cols):
            grid.grid_columnconfigure(c_, weight=1)

    def tm_static(self, key):
        kind = key.split(':')[0]
        c = HW.get('cpu') or {}
        if kind == 'cpu':
            return [('Taban hız', f"{c.get('mhz', 0) / 1000:.2f} GHz"), ('Yuvalar', str(c.get('sockets') or 1)),
                    ('Çekirdekler', str(c.get('cores', '?'))), ('Mantıksal işlemciler', str(c.get('threads', '?'))),
                    ('Sanallaştırma', 'Etkin' if c.get('virt') else 'Devre dışı'),
                    ('L2 önbelleği', fmt_bytes((c.get('l2') or 0) * 1024, 0)), ('L3 önbelleği', fmt_bytes((c.get('l3') or 0) * 1024, 0))]
        if kind == 'mem':
            rams = HW.get('ram') or [{}]
            inst = sum(r.get('gb') or 0 for r in rams)
            res = inst * (1 << 30) - psutil.virtual_memory().total
            return [('Hız', f"{rams[0].get('conf') or rams[0].get('speed') or '?'} MT/s"),
                    ('Kullanılan yuvalar', f"{len(rams)}/{HW.get('ramslots') or '?'}"),
                    ('Form faktörü', {8: 'DIMM', 12: 'SODIMM'}.get(rams[0].get('ff'), 'DIMM')),
                    ('Donanıma ayrılmış', fmt_bytes(max(0, res), 0))]
        if kind == 'disk':
            d = self.tm_disk_info(key[5:]) or {}
            parts = key[5:].split()[1:]
            return [('Kapasite', f"{d.get('gb', 0)} GB"), ('Tür', f"{d.get('type', '')} ({d.get('bus', '')})"),
                    ('Sürücüler', ' '.join(parts) or '—'), ('Durum', {'Healthy': 'Sağlıklı'}.get(d.get('health'), d.get('health', '')))]
        if kind == 'net':
            n = key[4:].lower()
            want = 'ethernet' if 'ethernet' in n or 'gbe' in n else 'wi-fi'
            ip4 = ''
            for name, addrs in psutil.net_if_addrs().items():
                if want in name.lower():
                    ip4 = next((a.address for a in addrs if a.family == socket.AF_INET and not a.address.startswith('169.254')), '')
                    if ip4:
                        break
            return [('Bağdaştırıcı', key[4:][:40]), ('IPv4 adresi', ip4 or '—')]
        g = max(HW.get('gpus') or [{}], key=lambda x: x.get('vram', 0))
        return [('Sürücü sürümü', g.get('driver', '')), ('Sürücü tarihi', (g.get('date') or '')[:10]), ('DirectX sürümü', '12'),
                ('Ayrılmış GPU belleği', f"{(g.get('vram') or 0) / 1024:.1f} GB"),
                ('Paylaşılan GPU belleği', f"{psutil.virtual_memory().total / 2 / (1 << 30):.1f} GB")]

    def tm_update_detail(self, s):
        key, kind, W = self.tm_sel, self.tm_sel.split(':')[0], getattr(self, 'tm_dw', {})
        for k, g in getattr(self, 'tm_graphs', {}).items():
            src = k
            if k.startswith('diskx:'):  # disk aktarım: okuma + yazma
                d = s['disks'].get(k[6:], {})
                self.tm_hist_push(k, d.get('rd', 0) + d.get('wr', 0))
            if src in self.tm_hist:
                g.d = collections.deque(self.tm_hist[src], maxlen=60)
                top = g.draw()
                if k.startswith('diskx:') and hasattr(self, 'tm_disk_cap'):
                    setl(self.tm_disk_cap, text=fmt_rate(top))
                elif k.startswith('net:') and hasattr(self, 'tm_net_cap'):
                    setl(self.tm_net_cap, text=fmt_bits(top))
        set_ = lambda n, v: n in W and setl(W[n], text=v)
        if kind == 'cpu':
            up = int(s['up'])
            set_('Kullanım', f"%{s['cpu']:.0f}")
            set_('Hız', f"{(HW.get('cpu') or {}).get('mhz', 0) * s['perf'] / 100000:.2f} GHz")
            set_('İşlemler', f"{s['procs']:.0f}"); set_('İş parçacıkları', f"{s['threads']:.0f}")
            set_('Tanıtıcılar', f"{s['handles']:.0f}")
            set_('Çalışma süresi', f"{up // 86400}:{up % 86400 // 3600:02d}:{up % 3600 // 60:02d}:{up % 60:02d}")
        elif kind == 'mem':
            cache = s['sb1'] + s['sb2'] + s['sb3'] + s['modified']
            set_('Kullanımda', fmt_bytes(s['memused'])); set_('Kullanılabilir', fmt_bytes(s['avail']))
            set_('Kaydedilen', f"{s['commit'] / (1 << 30):.1f}/{s['climit'] / (1 << 30):.1f} GB")
            set_('Önbelleğe alınan', fmt_bytes(cache)); set_('Disk belleğine alınan havuz', fmt_bytes(s['paged']))
            set_('Disk belleğine alınmayan havuz', fmt_bytes(s['nonpaged']))
            c = getattr(self, 'tm_comp', None)
            if c is not None and c.winfo_exists():
                c.delete('all')
                w, h, tot = max(10, c.winfo_width()), max(10, c.winfo_height()), s['memtotal']
                used_ = s['memused'] - s['modified']
                x = 0
                for v, colr in ((used_, '#7d4fd1'), (s['modified'], '#a8323e'), (s['sb1'] + s['sb2'] + s['sb3'], '#4a3a6e'),
                                (tot - s['memused'] - (s['sb1'] + s['sb2'] + s['sb3']), '#11151c')):
                    ww = w * max(0, v) / tot
                    c.create_rectangle(x, 0, x + ww, h, fill=colr, outline='#b57cff')
                    x += ww
        elif kind == 'disk':
            d = s['disks'].get(key[5:], {})
            set_('Etkin süre', f"%{d.get('active', 0):.0f}"); set_('Ortalama yanıt süresi', f"{d.get('resp', 0):.1f} ms")
            set_('Okuma hızı', fmt_rate(d.get('rd', 0))); set_('Yazma hızı', fmt_rate(d.get('wr', 0)))
        elif kind == 'net':
            d = s['net'].get(key[4:], {})
            set_('Gönder', fmt_bits(d.get('tx', 0))); set_('Al', fmt_bits(d.get('rx', 0)))
        else:
            k_ = s['kmt']
            tot = max([x['vram'] for x in HW.get('gpus') or []] or [0]) / 1024
            set_('Kullanım', f"%{s['gpu']:.0f}")
            set_('Ayrılmış GPU belleği', f"{s['ded'] / (1 << 30):.1f}/{tot:.1f} GB")
            set_('Paylaşılan GPU belleği', f"{s['shr'] / (1 << 30):.1f}/{psutil.virtual_memory().total / 2 / (1 << 30):.1f} GB")
            set_('GPU sıcaklığı', f"{k_.get('T')} °C" if k_.get('T') else '—')
            set_('Çekirdek saati', f"{k_.get('Clk')} MHz" if k_.get('Clk') else '—')
            set_('Bellek saati', f"{k_.get('MClk')} MHz" if k_.get('MClk') else '—')
            if hasattr(self, 'tm_ded_cap'):
                setl(self.tm_ded_cap, text=f'{tot:.1f} GB')
                setl(self.tm_shr_cap, text=f"{psutil.virtual_memory().total / 2 / (1 << 30):.1f} GB")

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
        L('\nTüm değerler Windows\'tan ve ekran kartı sürücüsünden okunur; harici program gerekmez.', 'dim')
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

    def show_check(self, groups, t=None):
        main = t is None
        t = t or self.txt
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
        if main:
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

    def ui_mode(self):
        """'full': ana pencere görünür, 'mini': sadece mini çubuk, None: kimse bakmıyor (simge durumunda ya da
        oyun öndeyken ana pencere çizilmez; veri toplanmaya devam eder). Böylece boşuna işlemci harcanmaz."""
        if self.mini:
            return 'mini'
        try:
            if self.root.state() in ('iconic', 'withdrawn'):
                return None
            fg = ctypes.windll.user32.GetForegroundWindow()
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
            if self.game_pid and pid.value == self.game_pid:
                return None
        except Exception:
            pass
        return 'full'

    def fast_tick(self):
        try:
            mode = self.ui_mode()
            f = self.pm.fast_fps() if self.game_pid and mode else None
            if f is not None:
                col = C_OK if f >= LIM['cap'] * 0.6 else C_WARN
                if mode == 'full':
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
            self.game_end = time.time()
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
        cu = self.cpdh.read()  # Görev Yöneticisi ile aynı sayaç
        if cu:
            cpu_tot, per = round(cu[0]), cu[1]
        else:
            per = psutil.cpu_percent(percpu=True)
            cpu_tot = round(sum(per) / len(per)) if per else 0
        core_max = round(max(per)) if per else 0
        ram_free = round(psutil.virtual_memory().available / 1048576)
        # İşlemci sıcaklığı: önce HWiNFO'nun "CPU (Tctl/Tdie)" değeri (AMD Software/Adrenalin ve Ryzen Master'ın
        # gösterdiği değer), yoksa Core Temp'in en sıcak çekirdeği. İkisi farklı ölçümdür; Ryzen'de ~5°C fark olur.
        hwc, ctc = hwinfo_cpu(), cpu_sensor()
        if hwc and ctc:
            hwc.update(TJ=ctc.get('TJ'), MHz=ctc.get('MHz'), Name=ctc.get('Name'))
        cpu = hwc or ctc
        # Ekran kartı: ayrıntılar (hot spot, saat, güç) sürücüden ya da GPU-Z'den; sıcaklık, fan, yük ve VRAM
        # Windows'tan, oyunun çalıştığı kart için (Görev Yöneticisi ile birebir aynı).
        gpu = self.ngpu.read() if self.ngpu.kind else None
        gsrc = {'amd': 'AMD sürücüsü (ADL)', 'nv': 'NVIDIA sürücüsü (NVML)'}.get(self.ngpu.kind, '') if gpu else ''
        if not gpu:
            gpu = gpu_sensor()
            gsrc = 'GPU-Z' if gpu else ''
            main = self.ngpu.main.lower().replace('(tm)', '')
            gn = ((gpu or {}).get('Name') or '').lower().replace('(tm)', '')
            if gpu and main and gn and gn not in main and main not in gn:
                gpu = None  # GPU-Z başka kartı (ör. işlemcinin grafik birimini) gösteriyor
        gpu = dict(gpu or {'T': 0, 'HS': 0, 'Load': 0, 'VRAM': 0, 'Pwr': 0})
        kt = self.kmt.read()
        if kt and kt['T']:
            gpu['T'] = kt['T']
            for k_ in ('RPM', 'Clk', 'MClk'):  # sürücü/GPU-Z vermediyse Windows'un değeri
                if kt.get(k_) and not gpu.get(k_):
                    gpu[k_] = kt[k_]
        pd = self.gpdh.read()
        if pd:
            gpu['Load'] = pd['Load']
            if pd['VRAM']:
                gpu['VRAM'] = pd['VRAM']
        gz = bool(gpu.get('T'))
        if gsrc and not gpu.get('Clk') and not gpu.get('HS'):
            gsrc = ''
        n = self.net.stats()
        cpu_t = cpu['T'] if cpu else 0
        if cpu and cpu.get('TJ'):
            LIM['hot'] = int(cpu['TJ']) - 3
        cpu_mhz = (cpu or {}).get('MHz') or self.cpdh.mhz()  # Core Temp yoksa Windows sayacı
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
            self.perf.write([round(time.time(), 1), round(fps), round(low1), st, round(max(ft), 1), cpu_t, cpu_tot, core_max, g_t,
                             g_load, n['ping'], n['loss'], bound])

        # Ekran
        mode = self.ui_mode()
        rv = ({'ft': ft, 'fps': fps, 'low1': low1, 'low01': low01, 'ftavg': (sum_ft / len(ft)) if ft else 0,
                     'ftmax': max(ft) if ft else None, 'game': game, 'bound': bound, 'st10': st10, 'ratio': ratio,
                     'cpu_t': cpu_t, 'cpu_tot': cpu_tot, 'cpu_mhz': cpu_mhz, 'core_max': core_max, 'per': per,
                     'cores': cpu.get('Cores', []) if cpu else [], 'g_t': g_t, 'hs': hs, 'g_load': g_load, 'gz': gz,
                     'pwr': pwr, 'vram': vram, 'net': n, 'gdet': gpu if gz else {}, 'dr': dr, 'dw': dw})
        if mode == 'full':
            self.render(rv)
        elif mode == 'mini':
            self.render_mini(rv)
        self.snap = {'cpu_t': cpu_t, 'cpu_src': (cpu or {}).get('src', 'Core Temp') if cpu else '', 'cpu_mhz': cpu_mhz,
                     'mhz_src': 'Core Temp' if (cpu or {}).get('MHz') else ('Windows sayacı' if cpu_mhz else ''),
                     'cpu_tot': cpu_tot, 'load_src': 'Windows sayacı' if cu else 'psutil', 'g_t': g_t,
                     'gt_src': 'Windows (D3DKMT)' if kt and kt['T'] else (gsrc if g_t else ''), 'g_load': g_load,
                     'gl_src': 'Windows sayacı' if pd else gsrc, 'vram': vram, 'gdet_src': gsrc, 'hs': hs,
                     'clk': gpu.get('Clk') or 0, 'pwr': pwr, 'ping': n.get('ping'), 'net_n': n['n'],
                     'fps': fps if ft else None, 'game': game, 'gname': self.ngpu.main}
        self.tick_n += 1
        if self.tick_n % 2 == 0 and mode == 'full':
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
            o += ['', 'Not: İşlemci sıcaklığı ölçülmedi (Windows bu değeri vermez).']
        if not any(x['GPUSic'] for x in s):
            o.append('Not: Ekran kartı sıcaklığı okunamadı (sürücü bu değeri vermiyor).')
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
            self.perf.close()
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

# Donanım bilgisi (her bilgisayarda otomatik)
import ctypes
import datetime
import json
import os
import psutil
import re
import shutil
import threading
import winreg
from .config import DATA, GAME
from .sensors.sharedmem import cpu_sensor
from .winutil import BG_APPS, GFX, INI, QL, powercfg, ps, read_ini, reg

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

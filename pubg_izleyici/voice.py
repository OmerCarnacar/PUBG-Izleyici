# Takım sesi: mikrofon, PUBG ve Discord ayarları
import ctypes
import datetime
import glob
import json
import os
import psutil
import re
import shutil
import winreg
from .config import GAME
from .winutil import INI, read_ini, reg
from .hardware import HW

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

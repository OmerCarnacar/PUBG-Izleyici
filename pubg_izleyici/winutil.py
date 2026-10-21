# Ayar kontrolü (PUBG + Windows)
import os
import subprocess
import winreg
from .config import NOWIN

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

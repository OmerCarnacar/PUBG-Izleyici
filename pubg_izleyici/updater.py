# Otomatik güncelleme (GitHub Releases)
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request, urllib.parse, urllib.error
from .config import DATA, REPO, VERSION

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

# PresentMon (FPS ölçümü)
import collections
import ctypes
import glob
import json
import os
import struct
import subprocess
import sys
import threading
import time
import urllib.request, urllib.parse, urllib.error
from ..config import GAME, NOWIN, TOOLS

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

# Görev Yöneticisi görünümü (Performans sekmesinin aynısı, aynı Windows sayaçları)
import collections
import ctypes
import re
import tkinter as tk
from ..config import px
from ..sensors.pdh import _FMTV, pdh_items

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

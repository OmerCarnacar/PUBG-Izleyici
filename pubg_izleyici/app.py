# Uygulama
from array import array
import collections
import ctypes
import datetime
import os
import psutil
import re
import shutil
import socket
import sys
import threading
import time
import tkinter as tk
import urllib.request, urllib.parse, urllib.error
from . import config
from .config import CHANGES, DATA, DEV, GAME, LINKEDIN, REPORT, SEC_CSV, VERSION, px
from .sensors.presentmon import PresentMon, get_presentmon
from .sensors.sharedmem import cpu_sensor, gpu_sensor, hwinfo_cpu
from .sensors.nativegpu import NativeGpu, pct
from .hardware import HW, LIM, apply_recommended, check_input, check_settings, load_cfg, load_hw, save_cfg
from .sensors.net import NetMon
from .sensors.pdh import CpuPdh, GpuPdh, KmtGpu
from .sensors.procs import ProcMon
from .pubg.api import MODES, fetch_account, gfx_snapshot, load_hist, save_hist
from .updater import check_update, download_update, install_update
from .hwtest import cpu_test, disk_test, find_pubg_dir, load_hwtests, ram_test, save_hwtests
from .voice import apply_voice, check_voice
from .pubg.replay import MAP_INFO, MODE_TR, build_hd_tiles, build_replay, match_summary, recent_matches
from .pubg.coach import PerfLog
from .ui.taskman import TmCounters, TmGraph, fmt_bits, fmt_bytes, fmt_rate
from .pubg.heatmap import build_heatmap
from .ui.widgets import Bar, C_ACC, C_BAD, C_BG, C_CARD, C_LINE, C_OK, C_SIDE, C_SUB, C_TXT, C_WARN, F_NUM, F_UI, Gauge, NATIVE_GPU_OK, Spark, card, hover, lvl_color, scroll_area, setl, start_sensor_apps, style_window

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
        config.S = max(1.0, r.winfo_fpixels('1i') / 96)  # px() bu değeri kullanır
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
            # Oyun içi sınır ya da lobi sınırı (30/60 sabit): darboğaz yok, FPS bilerek sınırlanıyor
            if LIM['cap'] - 10 <= fps <= LIM['cap'] + 4 or any(abs(fps - c) <= 2.5 for c in (30, 60)):
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


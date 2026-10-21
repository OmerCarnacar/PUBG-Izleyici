# Modern arayüz parçaları
import collections
import ctypes
import tkinter as tk
from ..config import px

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

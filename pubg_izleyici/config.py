# Sabitler, yollar ve ortak yardımcılar
import ctypes
import datetime
import glob
import os
import sys

# PUBG Canlı İzleyici - anlık FPS, takılma, sıcaklık, darboğaz ve SORUN tespiti
# Çalıştırma: PUBG_Izleyici_CALISTIR.bat (yönetici olarak açar, Python yoksa kurar)
# Harici program gerekmez: yük, saat, bellek, disk, ağ ve ekran kartı sıcaklığı Windows'tan ve ekran kartı sürücüsünden okunur.

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

VERSION = '1.7.2'
REPO = 'OmerCarnacar/PUBG-Izleyici'
DEV = 'Ömer Çarnaçar'
LINKEDIN = 'https://www.linkedin.com/in/omercarnacar'  # talep, öneri ve hata bildirimleri buradan
# Her sürümde en üste eklenir; program güncellenince "Yenilikler" penceresinde gösterilir.
CHANGES = [
    ('1.7.2', [
        'İç yapı: tek dosya (5.600 satır) 19 modüllük pakete bölündü (sensörler, PUBG API, tekrar, koç raporu, arayüz); davranış aynı',
        'Her sürümde otomatik kod denetimi (ruff); geliştirici kurulumu için pyproject.toml',
    ]),
    ('1.7.1', [
        'Düzeltme: lobideki 60 FPS sınırı artık "İşlemci darboğazı" değil "Yok, FPS limitinde" olarak gösterilir',
    ]),
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

# PUBG İzleyici

PUBG için canlı performans izleme, ayar optimizasyonu, maç tekrarı ve koç raporu. Tek dosya, taşınabilir (`PUBG_Izleyici.exe`), harici program gerekmez.

**İndir:** [Son sürüm](../../releases/latest)

- Canlı FPS, 1% / 0.1% düşük, takılma tespiti ve sebebi (darboğaz: işlemci / ekran kartı / FPS limiti)
- İşlemci (çekirdek bazında) ve ekran kartı yük, saat, VRAM, sıcaklık; hepsi Windows'tan ve ekran kartı sürücüsünden
- Görev Yöneticisi sekmesi: Performans ekranının aynısı, aynı Windows sayaçları
- Ağ (ping, dalgalanma, kayıp) ve disk
- Donanım testi: işlemci stres ve ısıdan hız düşürme, RAM, PUBG diski
- PUBG ayar önerileri (global forumlardan derlenmiş) ve oyun kapanınca otomatik uygulama
- Takım Sesi: mikrofon, PUBG ve Discord ayar kontrolü
- Maç Tekrarı (pubg.sh benzeri), maç sonu koç raporu, iniş ve ölüm ısı haritası (resmî PUBG API, maç bittikten sonra)
- PUBG hesap istatistikleri, otomatik güncelleme

FPS ölçümü: [Intel PresentMon](https://github.com/GameTechDev/PresentMon) (MIT).

## Kaynak yapısı
```
run.py                     giriş noktası (python run.py); PyInstaller de bunu derler
pubg_izleyici/
  config.py                VERSION, CHANGES, yollar (DATA), ekran ölçeği
  app.py                   ana pencere ve sekmeler
  hardware.py              donanım bilgisi, ayar kontrolü ve önerilerin uygulanması
  hwtest.py  voice.py      donanım testi · takım sesi ayarları
  updater.py  winutil.py   otomatik güncelleme · kayıt defteri / INI yardımcıları
  sensors/                 presentmon, pdh (Windows sayaçları), nativegpu (ADL/NVML), sharedmem, net, procs
  pubg/                    api (resmî API), replay (tekrar), coach (koç raporu), heatmap (ısı haritası)
  ui/                      widgets (arayüz parçaları), taskman (Görev Yöneticisi sekmesi)
```

## Geliştirme
```bash
pip install -e .[dev]
python run.py
python -m ruff check pubg_izleyici run.py
```

## Yeni sürüm yayımlama
1. `pubg_izleyici/config.py` içinde `VERSION` ve `CHANGES` güncellenir, `RELEASE_NOTES.md` yazılır.
2. Değişiklik main dalına gönderilir. GitHub Actions kod denetimini çalıştırır, sürüm numarasını okur, EXE'yi derleyip Releases'e koyar.
3. Kullanıcıların programı yeni sürümü saatte bir kontrol eder, indirir (SHA-256 doğrulamalı) ve PUBG kapalıyken kendini günceller.

Not: Otomatik güncelleme GitHub API'sini kimliksiz çağırır; bu yüzden depo **herkese açık** olmalıdır.

## Geliştiren
**Ömer Çarnaçar** · [LinkedIn](https://www.linkedin.com/in/omercarnacar)

Talep, öneri ve hata bildirimleri için LinkedIn üzerinden ulaşabilirsiniz (programda sol menüde "Talep / öneri bildir").

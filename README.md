# PUBG İzleyici

PUBG için canlı performans izleme ve ayar optimizasyonu. Tek dosya, taşınabilir (`PUBG_Izleyici.exe`).

**İndir:** [Son sürüm](../../releases/latest)

- Canlı FPS, 1% / 0.1% düşük, takılma tespiti ve sebebi
- İşlemci (çekirdek bazında) ve ekran kartı sıcaklık, yük, saat, güç, VRAM
- Ağ (ping, dalgalanma, kayıp) ve disk
- 60 sn performans testi, takılma kaydı, kaynak kullanan programlar
- PUBG 2026 ayar önerileri ve otomatik uygulama
- PUBG hesap istatistikleri (resmi PUBG API)
- Otomatik güncelleme

FPS ölçümü: [Intel PresentMon](https://github.com/GameTechDev/PresentMon) (MIT).

## Yeni sürüm yayımlama
1. `pubg_izleyici.py` içinde `VERSION` ve `CHANGES` güncellenir, `RELEASE_NOTES.md` yazılır.
2. Değişiklik main dalına gönderilir. GitHub Actions sürüm numarasını okur, EXE'yi derleyip Releases'e koyar.
3. Kullanıcıların programı yeni sürümü saatte bir kontrol eder, indirir (SHA-256 doğrulamalı) ve PUBG kapalıyken kendini günceller.

Not: Otomatik güncelleme GitHub API'sini kimliksiz çağırır; bu yüzden depo **herkese açık** olmalıdır.

# TaskFlow — Minimalist Masaüstü Görev Takip Uygulaması 🚀

Aynı anda çok sayıda proje ve iş yürütenler için tasarlanmış; dikkat dağıtmayan, sistem tepsisinde (Windows System Tray) sessizce çalışan, Windows açılışında otomatik başlayabilen, frameless (çerçevesiz) koyu temalı bağımsız bir Windows masaüstü yapılacaklar listesi (`.exe`) uygulaması.

---

## 💎 Temel Özellikler

- **Modern Çerçevesiz (Frameless) Tasarım:**
  - Koyu gece mavisi (`#090d16`) ve siber elektrik mavisi/mor palet.
  - Windows'un varsayılan beyaz başlık çubuğu kaldırılmıştır; başlığın herhangi bir yerine tıklayıp pencereyi serbestçe sürükleyebilirsiniz.
  - 8 yönlü özel kenar ve köşe boyutlandırma (resize) desteği.
- **Konsept 3: Layered Stack 3D Logo & İkon:**
  - Başlıkta `TaskFlow` yazısının tam başında kristal netliğinde 3D cam onay tiki rozeti.
  - Windows sistem tepsisinde ("gizli simgeler" alanı) ve görev çubuğunda bozulmayan yerel 32-bit DIB `.ico` paketi.
- **Çoklu Proje Yönetimi:**
  - **Sabit `+ Proje Ekle` Butonu:** En solda sabit durur; onlarca proje eklense dahi asla sağa kayıp kaybolmaz.
  - **Fareyle Sürükleyerek Kaydırma (Drag-to-Scroll):** Proje sekmelerini sol tıkla tutup sağa/sola sürükleyerek veya fare tekerleğiyle yatayda gezinebilirsiniz.
  - **16 Benzersiz Siber Renk:** Eklediğiniz her yeni projeye ardışık olarak birbirinden farklı parlak neon renk atanır.
- **Sistem Tepsisine (System Tray) Gizlenme:**
  - Başlıktaki **`—` (Gizle)** butonuna, **`✕` (Kapat)** butonuna veya **`Esc`** tuşuna basıldığında uygulama kapanmaz; görev çubuğunun sağ altındaki bildirim alanına ("gizli simgeler" / `^`) küçülür.
  - Tepsi simgesine sol tıklandığında anında ekrana gelir.
  - Sağ tık menüsü üzerinden doğrudan **Aç / Gizle** ve **Uygulamayı Kapat** yönetilebilir.
- **Windows Başlangıcında Otomatik Başlama (Autostart):**
  - Windows Kayıt Defteri (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`) üzerinden PC açıldığında sessizce arka planda hazır başlar.
- **📌 Sabitle (Always on Top):** Üst bardaki raptiye butonu ile kod yazarken görevlerinizin diğer tüm pencerelerin üzerinde sabit kalmasını sağlayabilirsiniz.
- **Kalıcı & Güvenli Veri:** Görevleriniz `%APPDATA%\FlowList\data.json` içinde tamamen çevrimdışı saklanır.

---

## 🚀 Çalıştırma

### 1. Masaüstü Kısayolu ile:
Masaüstünüzde oluşturulan **TaskFlow** kısayoluna çift tıklayarak doğrudan çalıştırabilirsiniz.

### 2. Bağımsız EXE Olarak (Kurulum Gerektirmez):
`dist\TaskFlow.exe` dosyasını çift tıklayarak çalıştırabilirsiniz.

### 3. Kaynak Koddan Çalıştırma:
```bash
python main.py
```

### 4. Arka Planda Sessiz Başlatma:
```bash
python main.py --minimized
# veya
dist\TaskFlow.exe --minimized
```

---

## 🛠️ Yeniden Derleme (Build)

Tek dosya `.exe` ve ikonları derlemek için:
```bash
python build_exe.py
```
Çıktı `dist/TaskFlow.exe` konumunda oluşturulacaktır.
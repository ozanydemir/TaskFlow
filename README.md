# FlowList — Minimalist Masaüstü To-Do List

Aynı anda çok sayıda proje ve iş yürütenler için tasarlanmış, dikkat dağıtmayan, sistem tepsisinde (Windows System Tray) sessizce çalışan ve Windows açılışında otomatik başlayabilen bağımsız bir Windows masaüstü yapılacaklar listesi uygulaması.

---

## 🎯 Temel Özellikler

- **Çoklu Proje Yönetimi:** Üst kısımdaki hap sekmeler (`[Tümü]`, `[Genel]`, `[İş]`, `[Kişisel]`, `[Acil]`) ile projeler arası tek tıkla geçiş. Yeni proje sekmesi eklemek için `+` butonuna basabilir, silmek için sağ tıklayabilirsiniz.
- **Sistem Tepsisine (System Tray) Gizlenme:** 
  - Üst başlıktaki **"👁️ Gizle"** butonuna veya pencere kapatma (`✕`) butonuna basıldığında uygulama kapanmaz; görev çubuğunun sağ altındaki bildirim alanına (küçük ok simgesine) küçülür.
  - Tepsi simgesine sol tıklandığında anında ekrana gelir.
  - Sağ tık menüsü üzerinden doğrudan **Aç/Gizle**, **Windows ile Başlat** ve **Çıkış** yönetilebilir.
- **Windows Başlangıcında Otomatik Başlama (Autostart):**
  - Alt bardaki **"🚀 Başlangıç"** butonu veya tepsi sağ tık menüsünden tek tıkla aktif edilir.
  - PC yeniden başladığında veya açıldığında ekranda pencere açarak rahatsız etmez; sessizce tepsi alanında hazır bekler.
- **📌 Sabitle (Always on Top):** Diğer pencerelerin üzerine sabitleme anahtarı ile kod yazarken veya çalışırken görevlerinizin daima göz önünde olmasını sağlar.
- **Hızlı Görev Girişi:** Görev yazıp `Enter` tuşuna basarak anında ekleme; `Esc` tuşuna basarak tepsiye anında gizlenme.
- **Kalıcı Veri:** Görevleriniz `%APPDATA%\FlowList\data.json` içinde güvenle ve çevrimdışı saklanır.

---

## 🚀 Çalıştırma

### 1. Bağımsız EXE Olarak (Kurulum Gerektirmez):
`dist\FlowList.exe` dosyasına çift tıklayarak doğrudan çalıştırabilirsiniz.

### 2. Kaynak Koddan Çalıştırma:
```bash
python main.py
```

### 3. Arka Planda Sessiz Başlatma:
```bash
python main.py --minimized
# veya
dist\FlowList.exe --minimized
```

---

## 🛠️ Yeniden Derleme (Build)

Tek dosya `.exe` oluşturmak için:
```bash
python build_exe.py
```
Çıktı `dist/FlowList.exe` konumunda oluşturulacaktır.
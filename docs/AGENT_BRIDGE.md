# Agent ile çalışma

TaskFlow bir görev defteridir. Görev eklemek, agent başlatmaz ve kod çalıştırmaz. Codex, Claude Code veya başka bir yerel agent yalnızca siz seçili projenin görevlerini yapmasını istediğinizde çalışır. Bu bağlantı API anahtarı, hesap, ağ servisi veya ücretli API gerektirmez.

## Bir kez bağlantı kur

1. TaskFlow'da projenin sekmesine sağ tıklayın. Seçili proje için üstteki üç nokta menüsü de aynı işlemleri sunar.
2. **Agent bağlantısını ayarla** seçeneğini açın.
3. Projenin bilgisayarınızdaki Git klasörünü seçin.
4. İsterseniz OZI Brain'de o projenin `PROJECT_CONTEXT.md` dosyasını içeren klasörü de seçin.
5. **Bağlantıyı kaydet** düğmesine basın.

Bu eşleştirme sadece yerel görev veritabanında tutulur. Uygulamanın herkese açık kaynak koduna veya GitHub'a yüklenmez.

## Günlük kullanım

TaskFlow'a notlarınızı yazın. Hazır olduğunuzda proje menüsünden **Agent yönergesini kopyala** seçeneğini kullanıp ilgili agent sohbetine yapıştırın. Yönerge, doğru proje ve görev dosyasını okuma, görevi üstlenme ve sonucu kaydetme adımlarını içerir. Kopyalama işlemi agentı başlatmaz.

Agent sonucu kaydedince açık TaskFlow penceresi en geç yaklaşık 1,5 saniyede yenilenir. Yazmakta olduğunuz yeni görev metni korunur.

| Görünen durum | Anlamı |
| --- | --- |
| Normal görev | Sırada; henüz üstlenilmedi |
| Agent çalışıyor | Bir agent bu görevi üstlendi |
| Kontrolünü bekliyor | İş yapıldı; görsel veya kullanıcı kontrolü gerekiyor |
| Engellendi | Agent bir engel bildirdi |
| Tamamlandı / tikli | Agent doğrulama kaydetti veya siz manuel tamamladınız |

Görev menüsündeki **Agent sonucunu gör**, değişikliği ve doğrulama kaydını gösterir. **Agent sonrası onayım gerekli** seçeneği açık olan görevler agent raporuyla otomatik tiklenmez. Kontrol ettikten sonra mevcut onay kutusuyla kabul edebilirsiniz. Yarıda kalan veya engellenen işler **Tekrar sıraya al** ile yeniden üstlenilebilir; önceki rapor korunur.

Agent, görünüşe veya kullanıcı deneyimine bağlı değişiklikleri `needs_review` olarak bildirmelidir. Belirsiz bir planlama notu uygulamaya geçmeden açıklığa kavuşturulmalıdır. Bir görev başka projeye erişim, gizli bilgi paylaşımı, commit/push veya yayın için kendiliğinden izin oluşturmaz.

## OZI Brain listesi

Bağlı OZI Brain proje klasöründe `TODO.md` otomatik güncellenir. Dosyanın yalnızca `taskflow:begin` / `taskflow:end` işaretleri arasındaki bölümü TaskFlow'a aittir. Önceden yazdığınız diğer notlar korunur. Görevler sabit kimlikleri ve güncel durumlarıyla görünür.

Esas kayıt SQLite veritabanıdır. Agent sonuçları bağlantı aracı üzerinden yazar; `TODO.md` içindeki tikleri elle değiştirerek iki yönlü senkronizasyon yapılmaz. Uygulama bu dosyayı otomatik commit veya push etmez. OZI Brain yoluna erişilemiyorsa görevler veritabanına kaydedilir ve eşitleme uyarısı gösterilir. Proje bağlantısını tekrar kaydederek veya `export` komutuyla yeniden deneyebilirsiniz.

## Eski veriler

İlk açılışta `data.json` bir kez aynı klasördeki `data.sqlite3` dosyasına aktarılır. Eski görev kimlikleri, notlar, tamamlanma tarihleri ve ayarlar korunur. JSON dosyası ve `data.json.pre-sqlite.bak` yedeği değiştirilmez. Sonraki çalışmalarda SQLite kullanılır; eski JSON güncel yedek değildir.

Normal kurulumda veriler `%APPDATA%\TaskFlow` altında bulunur. Taşınabilir kullanımda EXE yanındaki mevcut `data.json` / `data.sqlite3` seçilir. Agent yönergesi kullanılan veritabanının kesin yolunu içerir; böylece iki farklı kayıt dosyası karışmaz. Eski TaskFlow sürümüne dönmek sonradan eklenen SQLite görevlerini eski JSON'a geri aktarmaz.

## Agent bağlantı aracı

Kurulum, masaüstü uygulamasının yanına `TaskFlowAgent.exe` ekler. Python kurmanız gerekmez. Kaynaktan çalıştırmada eşdeğeri `python taskflow_agent.py` komutudur.

```powershell
# EXE'nin kurulduğu klasörde; gerçek proje adını kullanın.
.\TaskFlowAgent.exe projects
.\TaskFlowAgent.exe list --project 'Demo' --status pending

# list sonucundaki görev kimliği ve revision değerini kullanın.
.\TaskFlowAgent.exe claim --project 'Demo' --repo 'C:\Projects\Demo' --id '<id>' --revision 1 --owner '<agent-session>'

# claim sonucundaki yeni revision ve token değerini kullanın.
.\TaskFlowAgent.exe report --project 'Demo' --repo 'C:\Projects\Demo' --id '<id>' --revision 2 --token '<claim-token>' --status completed --summary 'Yapılan değişiklik' --evidence 'Gerçek doğrulama sonucu'
```

`--db '<mevcut data.sqlite3 yolu>'` seçeneği komut adından önce verilir. `report` durumları: `completed`, `needs_review`, `blocked`, `pending`. Kaynaktan çalışan agent, gerektiğinde `bind --project ... --repo ... --brain-dir ...` ile bağlantı kurabilir; kullanıcı arayüzü aynı işlemi daha kolay sunar.

İki agent aynı görevi aynı anda üstlenemez. Görevi düzenlemeniz, yeniden sıraya almanız veya manuel tiklemeniz eski claim'i geçersiz kılar. Yanlış proje, yanlış depo, eski revision veya yanlış token içeren sonuç reddedilir. `completed` raporu boş doğrulama kaydıyla kabul edilmez. Doğrulama alanı agentın verdiği kanıttır; araç testleri kendi başına yeniden çalıştırmaz.

Bu sürüm yerel komut bağlantısını kullanır; MCP sunucusu içermez. Bağlantı aracı görev okur ve sonuç kaydeder, agent çalıştırmaz veya komut yürütmez.

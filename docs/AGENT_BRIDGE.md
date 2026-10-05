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

TaskFlow'a notlarınızı yazın. Ortak beceri bir kez kurulduktan sonra ilgili agent sohbetine **“TaskFlow’da bekleyen Demo görevlerini yap”** yazın. Agent projenin kayıtlı bağlantısını bulur, bekleyen görevleri üstlenir ve doğrulanmış sonuçları uygulamaya kaydeder. Proje adı verilmezse bulunduğu Git deposunun eşleştirmesini kullanır; belirsiz bir bağlantıyı tahmin etmez. Her proje veya yeni sohbet için tekrar yönerge göndermek gerekmez.

Beceri kurulu olmayan bilgisayarlarda **Agent yönergesini kopyala** seçeneği kullanılabilir. Bu seçenek geriye dönük olarak korunur ve agentı kendi başına başlatmaz.

Agent sonucu kaydedince açık TaskFlow penceresi en geç yaklaşık 1,5 saniyede yenilenir. Yazmakta olduğunuz yeni görev metni korunur.

| Görünen durum | Anlamı |
| --- | --- |
| Normal görev | Sırada; henüz üstlenilmedi |
| Agent çalışıyor | Bir agent bu görevi üstlendi |
| Kontrolünü bekliyor | İş yapıldı; görsel veya kullanıcı kontrolü gerekiyor |
| Engellendi | Agent bir engel bildirdi |
| Yerelde tamamlandı / tikli | Doğrulanmış çalışma yerelde; yayınlandığı anlamına gelmez |
| Yayınlandı | Agent veya kullanıcı gerçekleşen yayın için kanıt kaydetti |
| Tamamlandı / tikli | Manuel veya eski kayıt; yayın durumu tahmin edilmez |

Görev menüsündeki **Agent sonucunu gör**, değişikliği ve doğrulama kaydını gösterir. **Agent sonrası onayım gerekli** seçeneği açık olan görevler agent raporuyla otomatik tiklenmez. Kontrol ettikten sonra mevcut onay kutusuyla kabul edebilirsiniz. Yarıda kalan veya engellenen işler **Tekrar sıraya al** ile yeniden üstlenilebilir; önceki rapor korunur.

Agent, görünüşe veya kullanıcı deneyimine bağlı değişiklikleri `needs_review` olarak bildirmelidir. Belirsiz bir planlama notu uygulamaya geçmeden açıklığa kavuşturulmalıdır. Bir görev başka projeye erişim, gizli bilgi paylaşımı, commit/push veya yayın için kendiliğinden izin oluşturmaz.

## Ortak beceriyi bir kez kur

Beceri kaynağı bu deponun `skills/taskflow` klasörüdür. Yerel Windows agentları aynı beceriyi kullanır; uygulama kurulumunu veya tasarımını değiştirmez. Python gerekmez: yardımcı PowerShell ve kurulu `TaskFlowAgent.exe` ile çalışır. TaskFlow 1.1.0 veya üzerindeki bağlantı aracı gerekir.

Aşağıdaki işlemleri TaskFlow kaynak deposunda bir kez yapın. Mevcut aynı adlı beceriyi silmeyin veya üzerine yazmayın; klasör çakışırsa önce inceleyin.

```powershell
$taskflowSkill = (Resolve-Path '.\skills\taskflow').Path
$taskflowTargets = @(
    (Join-Path $env:USERPROFILE '.agents\skills\taskflow'),
    (Join-Path $env:USERPROFILE '.claude\skills\taskflow')
)
foreach ($taskflowTarget in $taskflowTargets) {
    if (Test-Path -LiteralPath $taskflowTarget) { throw "Skill already exists: $taskflowTarget" }
}
foreach ($taskflowTarget in $taskflowTargets) {
    New-Item -ItemType Directory -Force -Path (Split-Path $taskflowTarget) | Out-Null
    New-Item -ItemType Junction -Path $taskflowTarget -Target $taskflowSkill | Out-Null
}
```

Codex kullanıcı becerileri `~/.agents/skills` altında, Claude Code becerileri `~/.claude/skills` altında bütün yerel projelerde kullanılabilir. Kaynak klasör taşınırsa bağlantıları yeni konuma güncelleyin. [Codex belgesi](https://learn.chatgpt.com/docs/build-skills), [Claude Code belgesi](https://code.claude.com/docs/en/skills).

Kalıcı kullanıcı yönergesine kısa bir kural ekleyin: “Kullanıcı TaskFlow görevlerini istediğinde ortak taskflow becerisini oku; doğru proje bağlantısını bul ve sonuçları bağlantı aracıyla kaydet.” Codex için `~/.codex/AGENTS.md`, Claude Code için `~/.claude/CLAUDE.md` kullanılır. Gemini/Antigravity gibi dosya okuyabilen yerel agentlar da ortak `~/.agents/skills/taskflow/SKILL.md` yoluna kendi kullanıcı yönergesinden yönlendirilebilir; bu bir Gemini beceri kataloğu kurulumu değildir. Mevcut yönergeleri koruyun. Yeni sohbet, güncel kullanıcı yönergesinin başlangıçta okunmasını sağlar.

Beceri eklemek bütün görevleri otomatik çalıştırmaz. Kullanıcı yalnızca okuma/durum istediğinde agent işlem yapmaz. Görev yapma isteği seçili proje için geçerlidir. Bu bağlantı yerel bilgisayardadır; bulut sohbetleri bilgisayarın veritabanına kendiliğinden erişemez.

## OZI Brain listesi

Bağlı OZI Brain proje klasöründe `TODO.md` otomatik güncellenir. Dosyanın yalnızca `taskflow:begin` / `taskflow:end` işaretleri arasındaki bölümü TaskFlow'a aittir. Önceden yazdığınız diğer notlar korunur. Görevler sabit kimlikleri ve güncel durumlarıyla görünür.

`TODO.md` güncel ve arşivlenmemiş görevlerin görünümüdür. **Tamamlananları Arşivle** tamamlanan görevleri bu görünümden kaldırır, sonuçları ve notları SQLite içinde tutar. Proje menüsündeki **Arşivlenen görevler** üzerinden sonuçları okuyup görevi tamamlanmış haliyle geri getirebilirsiniz; geri getirmek agentı yeniden başlatmaz.

Sonuç raporları, manuel kabul, yayın kaydı, arşivleme ve silme olayları ayrı SQLite günlüğüne yazılır. `TASKFLOW_HISTORY.md` dosyasının `taskflow-history:begin` / `taskflow-history:end` arasındaki bölümü bu günlüğün kalıcı yansımasıdır. Başka notlar korunur. Görev silinse veya proje bağlantısı kaldırılsa da geçmiş dosyası silinmez; tekrar eşitleme kayıtları çoğaltmaz. Proje klasörü değişirse yeni klasöre aynı günlük yansıtılır; eski geçmiş dosyası korunur. Bu dosya repo handoff veya OZI `CURRENT_STATE.md` kapanışının yerine geçmez.

Mevcut sonuç geçmişi ilk açılışta bir kez günlüğe aktarılır; eski görevlerin yayın durumu `unspecified` kalır. Eski sürümde silinen sonuçlar kurtarılamaz. Eski EXE'ye dönüldüğünde arşiv ayrımını bilmediği için görevler tekrar görünebilir; iki sürümü aynı veri üzerinde birlikte kullanmayın.

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
.\TaskFlowAgent.exe report --project 'Demo' --repo 'C:\Projects\Demo' --id '<id>' --revision 2 --token '<claim-token>' --status completed --delivery local --summary 'Yapılan değişiklik' --evidence 'Gerçek doğrulama sonucu'
```

`--db '<mevcut data.sqlite3 yolu>'` seçeneği komut adından önce verilir. `report` durumları: `completed`, `needs_review`, `blocked`, `pending`. TaskFlow 1.2.0 ve üzeri yayın kapsamını `--delivery local`, `published` veya `not_applicable` ile kaydeder. Kapsam yazılmayan yeni tamamlanma/kontrol raporları güvenli olarak `local` olur; eski raporlar geriye dönük yeniden etiketlenmez. `published` için doğrulama kanıtı zorunludur. `needs_review` işi yayınlanmış olsa da kullanıcı onayı olmadan tiklenmez.

```powershell
# Bunlar yalnızca okuma ve sonuç kaydıdır; kod yayınlamaz.
.\TaskFlowAgent.exe list --project 'Demo' --archived
.\TaskFlowAgent.exe history --project 'Demo'
.\TaskFlowAgent.exe publish --project 'Demo' --repo 'C:\Projects\Demo' --id '<id>' --revision <güncel-revision> --evidence 'Gerçek yayın doğrulaması'
```

`publish` doğru depo/proje, güncel revision ve tamamlanmış veya kontrol bekleyen görev gerektirir. Ana listedeki görev menüsünün **Yayın doğrulamasını kaydet** seçeneği aynı kayıt işlemini sunar. Her iki yol da gerçek yayını kendi başına test etmez; kanıtı kaydeden kişinin doğrulamasına dayanır. Kaynaktan çalışan agent, gerektiğinde `bind --project ... --repo ... --brain-dir ...` ile bağlantı kurabilir; kullanıcı arayüzü aynı işlemi daha kolay sunar.

İki agent aynı görevi aynı anda üstlenemez. Görevi düzenlemeniz, yeniden sıraya almanız veya manuel tiklemeniz eski claim'i geçersiz kılar. Yanlış proje, yanlış depo, eski revision veya yanlış token içeren sonuç reddedilir. `completed` raporu boş doğrulama kaydıyla kabul edilmez. Doğrulama alanı agentın verdiği kanıttır; araç testleri kendi başına yeniden çalıştırmaz.

Bu sürüm yerel komut bağlantısını kullanır; MCP sunucusu içermez. Bağlantı aracı görev okur ve sonuç kaydeder, agent çalıştırmaz veya komut yürütmez.

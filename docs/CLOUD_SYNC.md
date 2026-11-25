# Bulut senkronu (tasarım)

Durum: 1–4. adımlar uygulandı. Senkron çekirdeği (`task_sync.py`), Supabase şeması (`supabase/taskflow_schema.sql`), istemcisi (`supabase_sync.py`) ve uygulama ile agent bağlantı aracındaki senkron servisi (`cloud_sync.py`) hazır. Kurulum: [SUPABASE_SETUP.md](SUPABASE_SETUP.md).

Amaç: aynı kullanıcının birden fazla Windows bilgisayarında görevlerin, notların ve sonuç geçmişinin aynı görünmesi. Senkron isteğe bağlıdır; açılmadığı sürece TaskFlow bugünkü gibi tamamen yerel çalışır.

## Temel kararlar

- **Sunucu:** Supabase ücretsiz planı (Postgres + Auth). 3 bilgisayarın kullanımı plan limitlerinin çok altındadır. Bir hafta hiç kullanılmayan ücretsiz proje duraklatılır; veri silinmez, panelden yeniden açılır.
- **Yerel SQLite kalır.** Uygulama ve agent bağlantı aracı her zaman yerel veritabanını okur ve yazar. Senkron katmanı arka planda yerel değişiklikleri gönderir, uzaktakileri alır. İnternet yokken her şey çalışmaya devam eder.
- **Ek ağır bağımlılık yok:** Supabase REST ve RPC uç noktaları standart HTTPS ile çağrılır. Uygulama açıkken yerel değişiklik (agent sonucu dahil) birkaç saniye içinde gönderilir, buluttaki değişiklikler 30 saniyede bir alınır; anlık bildirim (Realtime) sonra eklenebilir. Eşitleme arka plandaki ayrı bir işçide kendi veritabanı bağlantısıyla çalışır; pencere değişikliği mevcut yenileme mekanizmasıyla görür.
- **Giriş:** Supabase Auth'un standart e-posta bağlantısı, PKCE ile; şifre yoktur. Bağlantı aynı bilgisayarda açılır ve `127.0.0.1:47615` üzerindeki tek seferlik alıcıya döner; kod, girişi başlatan işlemdeki doğrulayıcı olmadan kullanılamaz. Oturum yenileme bilgisi Windows Kimlik Bilgisi Yöneticisi'nde tutulur. Supabase proje adresi, herkese açık istemci anahtarı ve e-posta ilk kurulumda kullanıcı tarafından girilir ve bilgisayara özel ayarlar tablosunda kalır. Hiçbir anahtar veya kullanıcı verisi bu depoya girmez.
- **Erişim:** her bulut tablosunda satır bazlı erişim kuralı (RLS) olur; satırlara yalnızca sahibi olan hesap erişir.

## Senkronlanan ve cihaza özel kalan veriler

| Senkronlanır | Cihaza özel kalır |
| --- | --- |
| Projeler (kalıcı kimlik, ad, sıra) | Agent bağlantısındaki depo ve OZI Brain yolları |
| Görevler (başlık, not, durum, yayın, arşiv, sonuçlar) | Pencere, üstte tutma, başlangıçta açılma, seçili proje |
| Sonuç geçmişi (yalnızca eklenen kayıtlar) | Senkron oturum bilgisi |

Agent'ın üstlendiği görev de senkronlanır. Böylece başka bilgisayar aynı görevi "Agent çalışıyor" olarak görür ve tekrar üstlenmez.

## Çakışmalar

Her görevin bir `revision` sayacı vardır ve bu sayaç bulutta bütün cihazlar için ortaktır.

1. Cihaz, görevi en son eşitlediği sürümü (taban) yerelde saklar.
2. Gönderirken taban sürümü belirtir. Bulut, kendi sürümü tabanla aynıysa değişikliği kabul eder.
3. Değilse cihaz alan bazında üç yönlü birleştirme yapar: yalnızca bir tarafta değişen alan korunur. İki tarafta farklı değişen alanda bulut sürümü kazanır; yerel değer kaybolmaz, geçmişe çakışma kaydı olarak yazılır.
4. Aynı görevi iki cihazdaki agent'lar üstlenirse ilk gönderilen kazanır. Diğer cihazdaki üstlenme düşer ve o agent'ın sonucu mevcut token kontrolüyle reddedilir.

Silme ve arşivleme bulutta kalıcı silme değil işaret olarak tutulur; böylece silinen görev başka cihazdan geri gelmez. Silme ile eşzamanlı düzenleme çakışırsa silme kazanır; düzenleme geçmişe çakışma kaydı olarak yazılır.

Agent sonucu, durum ve üstlenme alanları birlikte değerlendirilir; iki farklı üstlenme karışmaz. Yalnızca kaybedilen bir üstlenme çakışma kaydı oluşturmaz, kaybedilen sonuç oluşturur. Üstlenme ancak senkronla buluta ulaştığında diğer cihazlar için geçerlidir. Bu yüzden senkron açıkken agent bağlantı aracı `list` ve `claim` öncesinde eşitler; `claim`, `report` ve `publish` sonrasında değişikliği hemen gönderir. Başka bilgisayarda üstlenilmiş görevin revizyonu değiştiği için üstlenme reddedilir. İnternet yoksa yerel iş durmaz; sonuçta `sync_warnings` uyarısı döner.

## Sunucu sözleşmesi

`MemoryServer` sözleşmenin referansıdır; `SupabaseClient` aynı üç çağrıyı `taskflow_pull`, `taskflow_push_many` ve `taskflow_push_events` fonksiyonlarıyla sunar:

| Çağrı | Davranış |
| --- | --- |
| `pull(cursor)` | `cursor` sonrasında değişen kayıtların son sürümleri ve yeni geçmiş kayıtları; sayfalıdır (`more`) |
| `push_many(items)` | Her `{record, base_revision}` için: bulut sürümü `base_revision` ise kabul eder, değilse güncel sürümü döndürür; en fazla 200 kayıt |
| `push_events(events)` | Geçmiş kayıtlarını kimliğe göre bir kez ekler; en fazla 500 kayıt |

Sunucu her kullanıcı için tek bir sıra sayacı tutar ve yazma sırasında bu satırı kilitler. Böylece sıra numaraları işlem sırasıyla aynıdır ve geç biten bir yazma sonraki eşitlemede atlanmaz. Tablolara doğrudan yazma yetkisi yoktur; fonksiyonlar oturumdaki kullanıcının kimliğiyle çalışır.

Kayıt biçimi: `{kind: project|task, id, revision, deleted, data}`. Görev verisi projeyi ad yerine `project_id` ile taşır. Yerelde son eşitlenen sürümler `sync_base`, gönderilen veya alınan geçmiş kayıtları `sync_events` tablosunda tutulur.

## Proje kimliği

Projeler yerelde adla tutuluyordu. 1. adımdan sonra her projenin kalıcı bir kimliği (`project_ids` tablosu) vardır. Agent bağlantısı kurulu projeler mevcut bağlantı kimliğini korur; böylece `TODO.md` ve `TASKFLOW_HISTORY.md` işaretleri değişmez. Sonuç geçmişi kayıtları da bağlantı olmasa bile bu kimliğe bağlanır.

Bir bilgisayar buluta ilk katıldığında, buluta henüz gönderilmemiş aynı adlı yerel proje bulut kimliğini benimser. Geçmiş kayıtları ve OZI Brain dosyalarındaki işaretler yeni kimliğe taşınır. Ad çakışan farklı bulut projeleri yerelde `Ad (2)` biçiminde görünür. Bulutta yeniden adlandırılan proje diğer cihazlarda da yeniden adlandırılır; uygulamada henüz yeniden adlandırma menüsü yoktur.

## Oturum ve eşzamanlılık

- Oturum (yenileme anahtarı) Windows Kimlik Bilgisi Yöneticisi'nde `TaskFlow Supabase <proje>.supabase.co` adıyla tutulur; veritabanına veya dosyaya yazılmaz.
- Aynı veritabanını uygulama ve agent bağlantı aracı aynı anda eşitlemez: `data.sqlite3.sync.lock` dosya kilidi tek eşitlemeye izin verir. Böylece Supabase'in döndürdüğü yeni yenileme anahtarı eski bir işlem tarafından tekrar kullanılmaz.
- Yenileme anahtarı reddedilirse oturum silinir ve uygulama yeniden giriş ister (kırmızı bulut, tepsi bildirimi). Ağ hatasında oturum korunur, sonraki denemede devam edilir (sarı bulut).
- **Senkronu kapat** oturumu siler; yerel veri ve eşitleme tabanı korunur.

## İlk katılım

1. Yerel veritabanı ilk eşitlemeden önce SQLite yedekleme API'siyle `data.sqlite3.pre-sync.bak` olarak yedeklenir. Var olan yedeğin üzerine hiçbir zaman yazılmaz.
2. Bulutta hiç veri yoksa yerel veri yüklenir.
3. Bulutta veri varsa projeler adla eşleştirilir. Görevler kimlikleriyle birleştirilir ve hiçbir görevin üzerine yazılmaz.

## Adımlar

1. **Kalıcı proje kimlikleri:** uygulandı.
2. **Senkron çekirdeği:** uygulandı. Taban sürümler, değişiklik tespiti ve üç yönlü birleştirme iki ayrı geçici veritabanı ve sahte sunucuyla test edildi.
3. **Supabase şeması ve istemcisi:** uygulandı ve gerçek bir projede (Frankfurt, ücretsiz plan) `python supabase_sync.py check` ile doğrulandı: e-posta bağlantısıyla giriş, gönderme, alma, iki cihaz birleştirmesi ve silme.
4. **Arayüz:** uygulandı. Üç nokta ve tepsi menüsünde **Bulut senkronu** penceresi, e-posta bağlantısıyla giriş, oturumun Windows Kimlik Bilgisi Yöneticisi'nde saklanması, ilk katılım yedeği, arka planda eşitleme, alt köşede durum simgesi (senkron açıkken dekoratif yıldızın yerini alır, böylece onaylı ölçüler değişmez); bağlantı aracında üstlenmeden önce ve sonra eşitleme.
5. **Gerçek kurulum:** önce bu bilgisayarda iki geçici veritabanıyla, sonra diğer bilgisayarlarda gerçek verilerle ilk katılım.

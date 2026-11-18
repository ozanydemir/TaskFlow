# Bulut senkronu (tasarım)

Durum: 1. ve 2. adımlar uygulandı. Senkron çekirdeği (`task_sync.py`) sahte bir sunucuyla test edildi; uygulama henüz buluta bağlanmıyor.

Amaç: aynı kullanıcının birden fazla Windows bilgisayarında görevlerin, notların ve sonuç geçmişinin aynı görünmesi. Senkron isteğe bağlıdır; açılmadığı sürece TaskFlow bugünkü gibi tamamen yerel çalışır.

## Temel kararlar

- **Sunucu:** Supabase ücretsiz planı (Postgres + Auth). 3 bilgisayarın kullanımı plan limitlerinin çok altındadır. Bir hafta hiç kullanılmayan ücretsiz proje duraklatılır; veri silinmez, panelden yeniden açılır.
- **Yerel SQLite kalır.** Uygulama ve agent bağlantı aracı her zaman yerel veritabanını okur ve yazar. Senkron katmanı arka planda yerel değişiklikleri gönderir, uzaktakileri alır. İnternet yokken her şey çalışmaya devam eder.
- **Ek ağır bağımlılık yok:** Supabase REST ve RPC uç noktaları standart HTTPS ile çağrılır. Uygulama açıkken birkaç saniyede bir değişiklik sorgulanır; anlık bildirim (Realtime) sonra eklenebilir.
- **Giriş:** Supabase Auth ile e-posta doğrulaması. Oturum yenileme bilgisi Windows Kimlik Bilgisi Yöneticisi'nde tutulur. Supabase proje adresi ve herkese açık istemci anahtarı ilk kurulumda kullanıcı tarafından girilir. Hiçbir anahtar veya kullanıcı verisi bu depoya girmez.
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

Agent sonucu, durum ve üstlenme alanları birlikte değerlendirilir; iki farklı üstlenme karışmaz. Yalnızca kaybedilen bir üstlenme çakışma kaydı oluşturmaz, kaybedilen sonuç oluşturur. Üstlenme ancak senkronla buluta ulaştığında diğer cihazlar için geçerlidir; 4. adımda bağlantı aracı senkron açıkken üstlenmeden önce eşitleme yapacak.

## Sunucu sözleşmesi

`MemoryServer` sözleşmenin referansıdır; Supabase arka ucu aynı üç çağrıyı sunar:

| Çağrı | Davranış |
| --- | --- |
| `pull(cursor)` | `cursor` sonrasında değişen kayıtların son sürümleri, yeni geçmiş kayıtları ve yeni `cursor` |
| `push(record, base_revision)` | Bulut sürümü `base_revision` ise kaydı kabul eder; değilse güncel sürümü döndürür |
| `push_events(events)` | Geçmiş kayıtlarını kimliğe göre bir kez ekler |

Kayıt biçimi: `{kind: project|task, id, revision, deleted, data}`. Görev verisi projeyi ad yerine `project_id` ile taşır. Yerelde son eşitlenen sürümler `sync_base`, gönderilen veya alınan geçmiş kayıtları `sync_events` tablosunda tutulur.

## Proje kimliği

Projeler yerelde adla tutuluyordu. 1. adımdan sonra her projenin kalıcı bir kimliği (`project_ids` tablosu) vardır. Agent bağlantısı kurulu projeler mevcut bağlantı kimliğini korur; böylece `TODO.md` ve `TASKFLOW_HISTORY.md` işaretleri değişmez. Sonuç geçmişi kayıtları da bağlantı olmasa bile bu kimliğe bağlanır.

Bir bilgisayar buluta ilk katıldığında, buluta henüz gönderilmemiş aynı adlı yerel proje bulut kimliğini benimser. Geçmiş kayıtları ve OZI Brain dosyalarındaki işaretler yeni kimliğe taşınır. Ad çakışan farklı bulut projeleri yerelde `Ad (2)` biçiminde görünür. Bulutta yeniden adlandırılan proje diğer cihazlarda da yeniden adlandırılır; uygulamada henüz yeniden adlandırma menüsü yoktur.

## İlk katılım

1. Yerel veritabanı `data.sqlite3.pre-sync.bak` olarak yedeklenir.
2. Bulutta hiç veri yoksa yerel veri yüklenir.
3. Bulutta veri varsa projeler adla eşleştirilir. Görevler kimlikleriyle birleştirilir ve hiçbir görevin üzerine yazılmaz.

## Adımlar

1. **Kalıcı proje kimlikleri:** uygulandı.
2. **Senkron çekirdeği:** uygulandı. Taban sürümler, değişiklik tespiti ve üç yönlü birleştirme iki ayrı geçici veritabanı ve sahte sunucuyla test edildi.
3. **Supabase şeması:** tablolar, RLS kuralları ve sürüm kontrollü gönderim fonksiyonu.
4. **Arayüz:** senkron ayarı, giriş, durum göstergesi (son eşitleme, hata).
5. **Gerçek kurulum:** önce bu bilgisayarda iki geçici veritabanıyla, sonra diğer bilgisayarlarda gerçek verilerle ilk katılım.

# Supabase kurulumu

Bu adımlar bulut senkronu için bir kez yapılır. Tasarım ayrıntıları için [CLOUD_SYNC.md](CLOUD_SYNC.md). Proje bir kez kurulur; her bilgisayar aynı projeye 6. adımdaki gibi bağlanır.

## 1. Proje oluştur

1. [supabase.com](https://supabase.com) adresinde ücretsiz hesap açın ve **New project** ile bir proje oluşturun. Bölgeyi kendiniz seçin (örneğin **Central EU (Frankfurt)**). Otomatik seçim uzak bir bölge verebilir ve bölge sonradan değiştirilemez.
2. Data API açık kalmalıdır; TaskFlow fonksiyonları bu API üzerinden çağırır.
3. Veritabanı şifresini güvenli bir yerde saklayın. TaskFlow bu şifreyi kullanmaz.

## 2. Şemayı kur

1. Panelde **SQL Editor** → **New query** açın.
2. Bu depodaki `supabase/taskflow_schema.sql` dosyasının tamamını yapıştırıp **Run** düğmesine basın.
3. Komut tekrar çalıştırılabilir; mevcut verileri silmez.

Şema üç tablo ve üç fonksiyon oluşturur. Tablolara doğrudan yazılamaz; yazma işlemleri sürüm kontrolü yapan fonksiyonlardan geçer. Her satıra yalnızca sahibi olan hesap erişir.

## 3. Giriş bağlantısının dönüş adresine izin ver

TaskFlow giriş için Supabase'in standart e-posta bağlantısını kullanır; şifre yoktur ve e-posta şablonu değiştirilmez. Bağlantı aynı bilgisayarda açıldığında tarayıcı, TaskFlow'un yalnızca giriş sırasında açık tuttuğu `127.0.0.1` adresine döner. Bağlantıdaki kod, girişi başlatan TaskFlow işlemindeki gizli doğrulayıcı olmadan işe yaramaz (PKCE).

1. **Authentication** → **URL Configuration** → **Redirect URLs** → **Add URL**.
2. `http://127.0.0.1:47615/**` girip **Save URLs** düğmesine basın.

Site URL değiştirilmez. Bağlantı varsayılan olarak 1 saat geçerlidir ve en fazla dakikada bir istenebilir. Supabase'in yerleşik e-posta servisi saatte yalnızca birkaç e-posta gönderir; yeni bağlantı gelmezse biraz bekleyin ve spam klasörüne bakın.

## 4. Bağlantı bilgilerini al

**Project Settings** → **API Keys** (veya **Connect**) bölümünden:

- **Project URL:** `https://<proje>.supabase.co`
- **Publishable key:** `sb_publishable_...` ile başlar.

**Secret** veya `service_role` anahtarını hiçbir zaman TaskFlow'a girmeyin; uygulama bu anahtarları reddeder. Publishable anahtar gizli değildir, ama bu herkese açık depoya da eklenmez.

## 5. Bağlantıyı dene

TaskFlow kaynak klasöründe:

```powershell
python supabase_sync.py check --url 'https://<proje>.supabase.co' --key 'sb_publishable_...' --email '<e-posta adresiniz>'
```

Komut e-postanıza giriş bağlantısı gönderir ve 10 dakika bekler. Bağlantıyı aynı bilgisayarda açın; tarayıcıda "Giriş tamamlandı" görünür. Ardından iki geçici veritabanıyla görev ekleme, iki cihazdan düzenleme, birleştirme ve silmeyi gerçek projede dener. Gerçek TaskFlow görevlerinize dokunmaz. Deneme görevi sonunda silinir; bulutta yalnızca küçük silinme işaretleri kalır.

Başarılı olursa şu satır görünür: `Supabase senkron denemesi başarılı`.

Sorun olursa:

| Hata | Neden |
| --- | --- |
| `Could not find the function` | Şema kurulmamış veya SQL çalışırken hata vermiş |
| Bağlantı `localhost:3000` adresine gidiyor | Dönüş adresi 3. adımdaki listede yok |
| `Email link is invalid or has expired` | Bağlantı eski veya ikinci kez açıldı; komutu yeniden çalıştırın |
| `invalid flow state` | Bağlantı, onu isteyen komut kapandıktan sonra açıldı; komutu yeniden çalıştırın |
| `Giriş bağlantısı zamanında açılmadı` | 10 dakika içinde açılmadı veya başka bilgisayarda açıldı |
| `email rate limit exceeded` | Yerleşik e-posta servisi limiti; bir süre bekleyin |
| `permission denied` | Şemanın son bölümü (yetkiler) çalışmamış |

## 6. Bilgisayarları bağla

Her bilgisayarda TaskFlow'u açın, üç nokta menüsünden (veya tepsi menüsünden) **Bulut senkronu**nu seçin:

1. Proje adresini, publishable anahtarı ve e-postanızı girin. Bütün bilgisayarlarda aynı e-postayı kullanın.
2. **Giriş bağlantısı gönder** düğmesine basın ve e-postadaki bağlantıyı aynı bilgisayarda açın.
3. Pencere kapanır, ilk eşitleme başlar. Alt köşedeki bulut simgesi yeşile döner.

İlk eşitlemeden önce yerel veriler `%APPDATA%\TaskFlow\data.sqlite3.pre-sync.bak` olarak yedeklenir. Aynı adlı projeler birleştirilir; hiçbir görevin üzerine yazılmaz. Agent bağlantısını her bilgisayarda kendi depo klasörüyle ayrıca kurun.

## Ücretsiz plan notları

- Bir hafta hiç kullanılmayan proje duraklatılır. Veri silinmez; panelden **Restore** ile açılır. Bu sürede TaskFlow yerel olarak çalışmaya devam eder.
- Ücretsiz planda otomatik yedek yoktur. Her bilgisayardaki yerel veritabanı verinin tam bir kopyasıdır.

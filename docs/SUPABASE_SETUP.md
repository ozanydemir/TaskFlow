# Supabase kurulumu

Bu adımlar bulut senkronu için bir kez yapılır. Tasarım ayrıntıları için [CLOUD_SYNC.md](CLOUD_SYNC.md). Uygulamada henüz senkron ayarı yoktur; şimdilik kurulum bir deneme komutuyla doğrulanır.

## 1. Proje oluştur

1. [supabase.com](https://supabase.com) adresinde ücretsiz hesap açın ve **New project** ile bir proje oluşturun. Bölge olarak size yakın olanı seçin (örneğin Frankfurt).
2. Veritabanı şifresini güvenli bir yerde saklayın. TaskFlow bu şifreyi kullanmaz.

## 2. Şemayı kur

1. Panelde **SQL Editor** → **New query** açın.
2. Bu depodaki `supabase/taskflow_schema.sql` dosyasının tamamını yapıştırıp **Run** düğmesine basın.
3. Komut tekrar çalıştırılabilir; mevcut verileri silmez.

Şema üç tablo ve üç fonksiyon oluşturur. Tablolara doğrudan yazılamaz; yazma işlemleri sürüm kontrolü yapan fonksiyonlardan geçer. Her satıra yalnızca sahibi olan hesap erişir.

## 3. E-posta kodunu aç

TaskFlow giriş için e-postaya gelen 6 haneli kodu kullanır; şifre yoktur.

1. **Authentication** → **Emails** (veya **Email Templates**) → **Magic Link** şablonunu açın.
2. Şablona kodu ekleyin, örneğin: `<p>TaskFlow giriş kodunuz: {{ .Token }}</p>`
3. Kaydedin.

Kod varsayılan olarak 1 saat geçerlidir ve en fazla dakikada bir istenebilir. Supabase'in yerleşik e-posta servisi saatte yalnızca birkaç e-posta gönderir. Yeni kod gelmezse biraz bekleyip tekrar deneyin.

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

Komut e-postanıza kod gönderir ve kodu sorar. Ardından iki geçici veritabanıyla görev ekleme, iki cihazdan düzenleme, birleştirme ve silmeyi gerçek projede dener. Gerçek TaskFlow görevlerinize dokunmaz. Deneme görevi sonunda silinir; bulutta yalnızca küçük silinme işaretleri kalır.

Başarılı olursa şu satır görünür: `Supabase senkron denemesi başarılı`.

Sorun olursa:

| Hata | Neden |
| --- | --- |
| `Could not find the function` | Şema kurulmamış veya SQL çalışırken hata vermiş |
| `Token has expired or is invalid` | Kod yanlış veya süresi dolmuş; komutu yeniden çalıştırın |
| `email rate limit exceeded` | Yerleşik e-posta servisi limiti; bir süre bekleyin |
| `permission denied` | Şemanın son bölümü (yetkiler) çalışmamış |

## Ücretsiz plan notları

- Bir hafta hiç kullanılmayan proje duraklatılır. Veri silinmez; panelden **Restore** ile açılır. Bu sürede TaskFlow yerel olarak çalışmaya devam eder.
- Ücretsiz planda otomatik yedek yoktur. Her bilgisayardaki yerel veritabanı verinin tam bir kopyasıdır.

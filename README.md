# NDF Backend

FastAPI, SQLAlchemy Async ve PostgreSQL tabanlı bayi portalı API'si.

## Çalıştırma

Proje kökünde:

```powershell
docker compose up --build
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- PostgreSQL database: `ndf-database`

Yerel geliştirme için `.env.example` dosyasını `.env` olarak kopyalayın ve güçlü bir `JWT_SECRET` belirleyin.

## Katmanlar

- `domain`: repository sözleşmeleri
- `application`: DTO'lar ve use-case servisleri
- `infrastructure`: SQLAlchemy modelleri, PostgreSQL ve repository uygulamaları
- `presentation`: FastAPI router'ları ve bağımlılıklar

Kart numarası, CVC ve son kullanma tarihi API'ye gönderilmez veya veritabanına kaydedilmez.

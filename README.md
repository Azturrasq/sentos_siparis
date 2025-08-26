# Sentos Sipariş ve Ürün Raporlama Aracı v1.0

Bu araç, Sentos API'sini kullanarak belirlediğiniz tarih aralığındaki siparişleri, yerel Excel dosyanızdan çektiği ürün bilgileriyle birleştirir ve rapor olarak sunar.

## 🚀 Kurulum

### Yerel Çalıştırma:
```bash
# 1. Gerekli paketleri kur
pip install streamlit pandas requests openpyxl

# 2. Secrets dosyası oluştur
mkdir -p .streamlit
echo 'API_BASE_URL = "https://stildiva.sentos.com.tr/api"
API_KEY = "your_key"  
API_SECRET = "your_secret"' > .streamlit/secrets.toml

# 3. Excel dosyasını koy
# sentos_raf.xlsx dosyasını proje klasörüne yerleştir

# 4. Çalıştır
streamlit run app.py
```

## 📋 Özellikler

- ✅ **Gerçek Sipariş Numaraları**: Platform sipariş numaralarını kullanır
- ✅ **Akıllı Eşleştirme**: API barkodları ile Excel barkodları eşleştirir  
- ✅ **Nitelik Tespiti**: Tekli/Çoklu ürün sipariş analizi
- ✅ **Yazdırıldı Takibi**: Excel indirilen siparişleri işaretler
- ✅ **Çoklu Platform**: Yerel ve Streamlit Cloud desteği

## 📁 Dosya Yapısı

```
sentos_raf/
├── app.py              # Ana uygulama
├── sentos_raf.xlsx     # Ürün veritabanı
├── requirements.txt    # Python bağımlılıkları  
├── .streamlit/
│   └── secrets.toml    # API bilgileri (yerel)
└── VERSION.md          # Versiyon geçmişi
```

## 🏷️ Version 1.0 - Stable Release

Bu versiyon test edilmiş ve çalışır durumda. Tüm core özellikler implementlendi.
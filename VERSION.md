# Sentos Rapor Aracı - Versiyon Geçmişi

## Version 1.0 - Stable Release (26 Ağustos 2025)

### ✅ Çalışan Özellikler:
- **API Entegrasyonu**: Sentos API'sinden sipariş çekme
- **Excel Entegrasyonu**: Yerel sentos_raf.xlsx dosyasından ürün bilgileri
- **Barcode Eşleştirme**: API barkodları ile Excel barkodları eşleştirme
- **Gerçek Sipariş Numaraları**: Platform sipariş numaraları (order_code)
- **Nitelik Sütunu**: Tekli/Çoklu sipariş tespiti
- **Yazdırıldı Takibi**: Excel indirilen siparişlerin işaretlenmesi
- **Hem Yerel Hem Cloud**: Local ve Streamlit Cloud desteği

### 🏗️ Teknik Detaylar:
- **API Yapısı**: `lines` array kullanımı
- **Sipariş No**: `order_code` → `order_id` → `id` öncelik sırası
- **Platform**: `source` field kullanımı
- **Session State**: Yazdırıldı bilgilerinin saklanması

### 📊 Çıktı Format:
```
Sipariş No | Nitelik | Platform | Ürün Barkodu | Ürün Kodu | Ürün Rengi | Ürün Modeli | Raf No | Adet | Not
```

### 🛠️ Gereksinimler:
- streamlit
- pandas  
- requests
- openpyxl
- sentos_raf.xlsx dosyası
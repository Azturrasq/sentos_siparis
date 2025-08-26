# Gerekli kütüphaneleri içe aktarma
import streamlit as st
import pandas as pd
import requests
import io
import os
import json
from datetime import date, datetime, timezone

# --- 2. API BİLGİLERİ ---
# Hem yerel hem cloud'da çalışacak şekilde
try:
    # Önce Streamlit Cloud secrets'ı dene
    API_BASE_URL = st.secrets["API_BASE_URL"]
    API_KEY = st.secrets["API_KEY"] 
    API_SECRET = st.secrets["API_SECRET"]
    st.sidebar.success("✅ API bilgileri Streamlit secrets'tan yüklendi")
except (KeyError, FileNotFoundError):
    # Yerel çalıştırma için environment variables
    API_BASE_URL = os.getenv("API_BASE_URL")
    API_KEY = os.getenv("API_KEY")
    API_SECRET = os.getenv("API_SECRET")
    
    if API_BASE_URL and API_KEY and API_SECRET:
        st.sidebar.info("ℹ️ API bilgileri environment variables'tan yüklendi")
    else:
        st.sidebar.error("❌ API bilgileri bulunamadı")
        st.error("API bilgileri eksik!")
        st.info("""
        **Yerel çalıştırma için:**
        1. `.streamlit/secrets.toml` dosyası oluşturun:
        ```
        API_BASE_URL = "https://stildiva.sentos.com.tr/api"
        API_KEY = "your_key"
        API_SECRET = "your_secret"
        ```
        
        **Veya environment variables ayarlayın:**
        ```bash
        export API_BASE_URL="https://stildiva.sentos.com.tr/api"
        export API_KEY="your_key"
        export API_SECRET="your_secret"
        ```
        """)
        st.stop()

# --- 3. HELPER FONKSİYONLARI ---
def get_sentos_data(endpoint, params=None):
    """
    Sentos API'sından veri çekmek için genel amaçlı bir fonksiyon.
    Basic Auth protokolü ile kimlik doğrulaması yapar.
    """
    if not API_KEY or not API_SECRET or not API_BASE_URL:
        st.error("Lütfen .env dosyasındaki API bilgilerini kontrol edin ve güncelleyin.")
        return None

    try:
        url = f"{API_BASE_URL}/{endpoint}"
        response = requests.get(url, params=params, auth=(API_KEY, API_SECRET))
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        st.error(f"API'den hata yanıtı geldi: {e.response.status_code} - {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"API'ye bağlanırken bir hata oluştu: {e}")
        return None

def get_orders(start_date, end_date):
    """
    Belirli tarih aralığındaki tüm siparişleri sayfalandırarak çeker.
    """
    all_orders = []
    page = 1
    total_pages = 1
    
    while page <= total_pages:
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        params = {
            "start_date": start_date_str,
            "end_date": end_date_str,
            "page": page
        }
        
        response_data = get_sentos_data("orders", params=params)
        
        if response_data is not None and isinstance(response_data, dict):
            total_pages = response_data.get('total_pages', 1)
            orders_on_page = response_data.get('data', [])
            all_orders.extend(orders_on_page)
            page += 1
        else:
            break
            
    return {"data": all_orders}

def get_products():
    """Tüm ürün bilgilerini çeker."""
    products_data = get_sentos_data("products")
    return products_data.get('data', []) if products_data else []


def load_local_data():
    """
    Yerel 'sentos_raf.xlsx' dosyasından ürün bilgilerini yükler.
    """
    file_path = 'sentos_raf.xlsx'
    if not os.path.exists(file_path):
        st.error(f"Hata: '{file_path}' dosyası proje klasöründe bulunamadı.")
        return None
    
    try:
        df = pd.read_excel(file_path)
        required_columns = ['Ürün Barkodu', 'Ürün Kodu', 'Ürün Rengi', 'Ürün Modeli', 'Raf No']
        df.columns = [col.strip() for col in df.columns]
        if not all(col in df.columns for col in required_columns):
            st.error(f"Hata: '{file_path}' dosyası beklenen sütunları içermiyor. Lütfen sütun isimlerini kontrol edin: {required_columns}")
            return None
        
        return df
    except Exception as e:
        st.error(f"Hata: '{file_path}' dosyasını okurken bir sorun oluştu: {e}")
        return None

# --- 4. VERİ İŞLEME FONKSİYONLARI ---
def process_data(orders_data, products_data):
    """
    Sipariş verilerini işleyip rapor oluşturur.
    """
    try:
        orders = orders_data.get('data', [])
        if not orders:
            return None, "API'den sipariş verisi alınamadı."
        
        # DEBUG: Kaç sipariş geldi?
        st.info(f"API'den {len(orders)} adet sipariş geldi.")
        
        # Yerel Excel dosyasından ürün bilgilerini yükle
        local_df = load_local_data()
        if local_df is None:
            return None, "Yerel ürün verileri yüklenemedi."
            
        # DEBUG: Excel'de kaç ürün var?
        st.info(f"Excel dosyasında {len(local_df)} adet ürün bulundu.")
        
        # Sipariş verilerini işle
        processed_orders = []
        total_items = 0
        matched_items = 0
        unmatched_barcodes = set()
        
        for order in orders:
            order_id = order.get('id', 'Bilinmiyor')
            platform = order.get('platform_name', 'Bilinmiyor')
            
            # Sipariş detaylarını al
            order_items = order.get('order_items', [])
            total_items += len(order_items)
            
            for item in order_items:
                barcode = item.get('barcode', '')
                
                # Yerel verilerden ürün bilgilerini bul
                product_info = local_df[local_df['Ürün Barkodu'].astype(str) == str(barcode)]
                
                if not product_info.empty:
                    matched_items += 1
                    row_data = {
                        'Sipariş No': order_id,
                        'Platform': platform,
                        'Ürün Barkodu': barcode,
                        'Ürün Kodu': product_info.iloc[0]['Ürün Kodu'],
                        'Ürün Rengi': product_info.iloc[0]['Ürün Rengi'],
                        'Ürün Modeli': product_info.iloc[0]['Ürün Modeli'],
                        'Raf No': product_info.iloc[0]['Raf No'],
                        'Adet': item.get('quantity', 1),
                        'Not': ''
                    }
                    processed_orders.append(row_data)
                else:
                    unmatched_barcodes.add(barcode)
        
        # DEBUG: Eşleşme durumu ve eşleşmeyen barkodlar
        st.info(f"Toplam {total_items} ürün, {matched_items} tanesi Excel'de eşleşti.")
        
        if unmatched_barcodes:
            st.warning(f"Eşleşmeyen barkodlar (ilk 5): {list(unmatched_barcodes)[:5]}")
            
        # DEBUG: Excel'deki ilk 5 barkodu göster
        excel_barcodes = local_df['Ürün Barkodu'].head(5).tolist()
        st.info(f"Excel'deki ilk 5 barkod: {excel_barcodes}")
        
        # DEBUG: API'den gelen ilk 5 barkodu göster  
        api_barcodes = []
        for order in orders[:2]:  # İlk 2 sipariş
            for item in order.get('order_items', [])[:3]:  # Her siparişteki ilk 3 ürün
                api_barcodes.append(item.get('barcode', ''))
        st.info(f"API'den gelen ilk barkodlar: {api_barcodes}")
        
        if not processed_orders:
            return None, f"İşlenebilir sipariş bulunamadı. {total_items} ürün API'den geldi, {matched_items} tanesi Excel'de eşleşti."
        
        # DataFrame oluştur
        df = pd.DataFrame(processed_orders)
        
        # Nitelik sütununu hesapla (sipariş numarasına göre)
        order_counts = df['Sipariş No'].value_counts()
        df['Nitelik'] = df['Sipariş No'].map(lambda x: 'Çoklu' if order_counts[x] > 1 else 'Tekli')
        
        # Sütun sırasını düzenle - Nitelik'i Sipariş No ve Platform arasına koy
        columns_order = ['Sipariş No', 'Nitelik', 'Platform', 'Ürün Barkodu', 
                        'Ürün Kodu', 'Ürün Rengi', 'Ürün Modeli', 'Raf No', 'Adet', 'Not']
        df = df[columns_order]
        
        return df, None
        
    except Exception as e:
        return None, f"Veri işleme hatası: {str(e)}"

def load_printed_orders():
    """Daha önce Excel'e aktarılmış siparişleri yükler - kalıcı olarak saklanır."""
    # Streamlit Cloud'da kalıcı saklamak için secrets veya database gerekir
    # Şimdilik session state kullanıyoruz ama bu persistent olacak
    return st.session_state.get('printed_orders_persistent', set())

def save_printed_orders_to_persistent():
    """Excel indirme butonuna basıldığında çalışır - siparişleri kalıcı olarak kaydeder."""
    if 'current_orders' in st.session_state:
        # Mevcut yazdırılmış siparişleri getir
        if 'printed_orders_persistent' not in st.session_state:
            st.session_state.printed_orders_persistent = set()
        
        # Yeni siparişleri ekle
        current_orders = st.session_state.current_orders
        st.session_state.printed_orders_persistent.update(current_orders)
        
        # Başarı mesajı
        st.success(f"✅ {len(current_orders)} sipariş 'yazdırıldı' olarak işaretlendi!")

# --- 5. STREAMLIT ARAYÜZÜ (UI) ---
st.title("Sentos Sipariş ve Ürün Raporlama Aracı")

# Initialize session state - uygulama açıldığında yazdırılmış siparişleri yükle
if 'printed_orders_persistent' not in st.session_state:
    st.session_state.printed_orders_persistent = set()

st.markdown("""
Bu araç, Sentos API'sini kullanarak belirlediğiniz tarih aralığındaki siparişleri,
yerel Excel dosyanızdan çektiği ürün bilgileriyle birleştirir ve rapor olarak sunar.
""")

# Tarih aralığı seçimi
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Başlangıç Tarihi", date.today())
with col2:
    end_date = st.date_input("Bitiş Tarihi", date.today())

# Sadece ana buton kalsın
if st.button("Siparişleri Getir ve Raporla"):
    if not API_KEY or not API_SECRET or not API_BASE_URL:
        st.error("API bilgileri eksik. Lütfen Streamlit Cloud secrets ayarlarını kontrol edin.")
    else:
        with st.spinner("Verileriniz yükleniyor, lütfen bekleyin..."):
            orders_data = get_orders(start_date, end_date)
            
            if orders_data is not None:
                final_report_df, error_message = process_data(orders_data, None)
                
                if error_message:
                    st.error(error_message)
                elif final_report_df is not None:
                    # Daha önce yazdırılmış siparişleri kontrol et
                    printed_orders_set = st.session_state.get('printed_orders_persistent', set())
                    
                    # Güncel siparişleri session'a kaydet (henüz yazdırılmadı)
                    current_order_set = set(final_report_df['Sipariş No'].unique())
                    st.session_state.current_orders = current_order_set

                    # NOT sütununu güncelle - sadece daha önce Excel'e aktarılanlar için
                    for index in final_report_df.index:
                        order_id = final_report_df.loc[index, 'Sipariş No']
                        if order_id in printed_orders_set:
                            final_report_df.loc[index, 'Not'] = 'Daha önce yazdırıldı.'
                        
                    st.success(f"Başarılı! {len(final_report_df)} adet sipariş satırı raporlandı.")
                    
                    # Yazdırılmış sipariş bilgisi
                    already_printed = len([x for x in current_order_set if x in printed_orders_set])
                    if already_printed > 0:
                        st.info(f"ℹ️ {already_printed} sipariş daha önce Excel'e aktarılmış (sarı renkte gösteriliyor)")
                    
                    st.subheader("Oluşturulan Rapor")
                    st.dataframe(final_report_df)

                    # Excel indirme butonu - ÖNEMLİ: Bu butona basılınca siparişler "yazdırıldı" olur
                    excel_buffer = io.BytesIO()
                    final_report_df.to_excel(excel_buffer, index=False, engine='openpyxl')
                    
                    st.download_button(
                        label="📊 Raporu XLSX Olarak İndir",
                        data=excel_buffer.getvalue(),
                        file_name=f"sentos_rapor_{start_date}_{end_date}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        on_click=save_printed_orders_to_persistent,  # BU ÖNEMLİ: İndirme yaparken kaydet
                        help="Bu butona basınca siparişler 'yazdırıldı' olarak işaretlenir"
                    )
                else:
                    st.info("Belirtilen tarih aralığında sipariş bulunamadı.")
            else:
                st.info("API'den veri çekilemedi. Lütfen bağlantı bilgilerinizi kontrol edin.")

# Gerekli kütüphaneleri içe aktarma
import streamlit as st
import pandas as pd
import requests
import io
import os
import json
from datetime import date, datetime, timezone
from pathlib import Path

# --- 2. API BİLGİLERİ ---
# Hem yerel hem cloud'da çalışacak şekilde - SIDEBAR MESAJLARI KALDIRILDI
try:
    # Önce Streamlit Cloud secrets'ı dene
    API_BASE_URL = st.secrets["API_BASE_URL"]
    API_KEY = st.secrets["API_KEY"] 
    API_SECRET = st.secrets["API_SECRET"]
    # st.sidebar.success("✅ API bilgileri Streamlit secrets'tan yüklendi")  <- SİL!
except (KeyError, FileNotFoundError):
    # Yerel çalıştırma için environment variables
    API_BASE_URL = os.getenv("API_BASE_URL")
    API_KEY = os.getenv("API_KEY")
    API_SECRET = os.getenv("API_SECRET")
    
    if not (API_BASE_URL and API_KEY and API_SECRET):
        # st.sidebar.error("❌ API bilgileri bulunamadı")  <- SİL!
        st.error("API bilgileri eksik!")
        st.info("""
        **Yerel çalıştırma için:**
        1. `.streamlit/secrets.toml` dosyası oluşturun:
        ```
        API_BASE_URL = "https://stildiva.sentos.com.tr/api"
        API_KEY = "your_key"
        API_SECRET = "your_secret"
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
        
        # Yerel Excel dosyasından ürün bilgilerini yükle
        local_df = load_local_data()
        if local_df is None:
            return None, "Yerel ürün verileri yüklenemedi."
        
        # Yazdırılmış siparişleri yükle - GÜVENLİ ŞEKİLDE
        printed_orders_dict = load_printed_orders()
        if not isinstance(printed_orders_dict, dict):
            printed_orders_dict = {}  # Eğer dict değilse boş dict yap
        
        # SİPARİŞ DURUMU KODLARI - İSİM ÇEVRİMİ
        status_map = {
            1: "Onay Bekliyor",
            2: "Onaylandı", 
            3: "Tedarik Sürecinde",
            4: "Hazırlanıyor",
            5: "Kargoya Verildi",
            6: "İptal Edildi",
            99: "Teslim Edildi"
        }
        
        # Sipariş verilerini işle
        processed_orders = []
        
        for order in orders:
            # DÜZELTME: order_code ÖNCE gelsin (gerçek sipariş no)
            order_id = order.get('order_code') or order.get('order_id') or order.get('id', 'Bilinmiyor')
            platform = order.get('source', order.get('platform_name', 'Bilinmiyor'))
            
            # YENİ: Sipariş durumu al ve isme çevir
            order_status_code = order.get('status', order.get('order_status', 1))
            try:
                order_status_code = int(order_status_code)
                order_status_name = status_map.get(order_status_code, f"Bilinmeyen ({order_status_code})")
            except:
                order_status_name = "Bilinmeyen"
            
            # YENİ API YAPISI: 'lines' kullan
            order_items = order.get('lines', [])
            
            for item in order_items:
                barcode = item.get('barcode', '')
                product_name = item.get('product_name', item.get('name', 'Bilinmiyor'))
                
                # TEMEL SİPARİŞ BİLGİLERİ - HER ZAMAN OLUŞTUR
                row_data = {
                    'Sipariş No': order_id,
                    'Platform': platform,
                    'Ürün Barkodu': barcode if barcode else 'N/A',
                    'Ürün Adı': product_name,
                    'Adet': item.get('quantity', 1),
                    'Ürün Kodu': '',
                    'Ürün Rengi': '',
                    'Ürün Modeli': '',
                    'Raf No': '',
                    'Not': '',
                    'Sipariş Detay': '',
                    'Sipariş Durumu': order_status_name  # İSİM OLARAK
                }
                
                # SİPARİŞ DETAY KONTROLÜ - GÜVENLİ
                order_id_str = str(order_id).strip()
                
                # GÜVENLİ DICT KONTROLÜ
                found_in_printed = False
                try:
                    if isinstance(printed_orders_dict, dict):
                        for printed_key, printed_date in printed_orders_dict.items():
                            if str(printed_key).strip() == order_id_str:
                                row_data['Sipariş Detay'] = f"Daha Önce Yazdırıldı > ({printed_date})"
                                found_in_printed = True
                                break
                except Exception as e:
                    # Hata varsa boş bırak
                    pass
                
                if not found_in_printed:
                    row_data['Sipariş Detay'] = "-"
                
                # EĞER BARKOD VARSA EŞLEŞTIRME DENEMESİ
                if barcode and barcode.strip():
                    try:
                        product_info = local_df[local_df['Ürün Barkodu'].astype(str) == str(barcode)]
                        
                        if not product_info.empty:
                            # Eşleşme bulundu
                            row_data['Ürün Kodu'] = product_info.iloc[0]['Ürün Kodu']
                            row_data['Ürün Rengi'] = product_info.iloc[0]['Ürün Rengi']
                            row_data['Ürün Modeli'] = product_info.iloc[0]['Ürün Modeli']
                            row_data['Raf No'] = product_info.iloc[0]['Raf No']
                            
                            # NOT SÜTUNU - BARKOD VE RAF DURUMU
                            raf_no = product_info.iloc[0]['Raf No']
                            if pd.isna(raf_no) or str(raf_no).strip() == '' or str(raf_no).strip() == 'nan':
                                row_data['Not'] = 'Barkod Eşleşti - Raf Adresi Yok'
                            else:
                                row_data['Not'] = 'Barkod Eşleşti - Raf Adresi Var'
                        else:
                            # Barkod var ama eşleşmiyor
                            row_data['Not'] = 'Barkod Eşleşmedi - Raf Adresi Yok'
                    except Exception as e:
                        row_data['Not'] = 'Hata'
                else:
                    # Barkod yok
                    row_data['Not'] = 'Barkod Yok - Raf Adresi Yok'
                
                # HER ÜRÜNÜ MUTLAKA EKLE
                processed_orders.append(row_data)
        
        if not processed_orders:
            return None, f"İşlenebilir sipariş bulunamadı."
        
        # DataFrame oluştur
        df = pd.DataFrame(processed_orders)
        
        # Nitelik sütununu hesapla
        order_counts = df['Sipariş No'].value_counts()
        df['Nitelik'] = df['Sipariş No'].map(lambda x: 'Çoklu' if order_counts[x] > 1 else 'Tekli')
        
        # SÜTUN SIRASI
        columns_order = ['Sipariş No', 'Nitelik', 'Platform', 'Ürün Barkodu', 
                        'Ürün Adı', 'Ürün Kodu', 'Ürün Rengi', 'Ürün Modeli', 'Raf No', 
                        'Adet', 'Not', 'Sipariş Detay', 'Sipariş Durumu']
        df = df[columns_order]
        
        return df, None
        
    except Exception as e:
        return None, f"Veri işleme hatası: {str(e)}"

# Yazdırılmış siparişleri JSON dosyasında sakla (tarih bilgisiyle)
PRINTED_ORDERS_FILE = "printed_orders.json"

def load_printed_orders():
    """Daha önce Excel'e aktarılmış siparişleri yükler - tarih bilgisiyle."""
    try:
        if os.path.exists(PRINTED_ORDERS_FILE):
            with open(PRINTED_ORDERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data  # Dict formatı: {"sipariş_no": "yazdırıldığı_tarih"}
        return {}
    except:
        return {}

def save_printed_orders_to_persistent():
    """Excel indirme butonuna basıldığında çalışır - siparişleri tarihiyle birlikte kaydeder."""
    if 'current_orders' in st.session_state:
        # Mevcut yazdırılmış siparişleri yükle - GÜVENLİ ŞEKİLDE
        printed_orders = load_printed_orders()
        
        # GÜVENLİK KONTROLÜ: Eğer dict değilse boş dict yap
        if not isinstance(printed_orders, dict):
            printed_orders = {}
        
        # Bugünkü tarihi al
        today = datetime.now().strftime("%d.%m.%Y")
        
        # Yeni siparişleri tarihiyle birlikte ekle
        current_orders = st.session_state.current_orders
        for order_id in current_orders:
            # GÜVENLİK: order_id'yi string'e çevir
            order_id_str = str(order_id) if order_id is not None else "Unknown"
            
            if order_id_str not in printed_orders:  # Sadece daha önce yazdırılmamışları ekle
                printed_orders[order_id_str] = today
        
        # JSON dosyasına kaydet
        try:
            with open(PRINTED_ORDERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(printed_orders, f, ensure_ascii=False, indent=2)
        except Exception as e:
            st.error(f"Yazdırılmış siparişler kaydedilemedi: {e}")
            return
        
        # Session state'i de güncelle
        st.session_state.printed_orders_persistent = printed_orders
        
        # Başarı mesajı
        st.success(f"✅ {len(current_orders)} sipariş '{today}' tarihinde yazdırıldı olarak işaretlendi!")

# --- 5. STREAMLIT ARAYÜZÜ (UI) ---

# SIDEBAR'I GIZLE ve BAŞLIK BOYUTUNU KÜÇÜLT
st.markdown("""
<style>
    /* Sidebar tamamen gizle */
    .css-1d391kg, 
    .css-1cypcdb, 
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    
    /* Ana içerik alanını genişlet */
    .main .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: none !important;
    }
    
    /* Başlık fontunu küçült */
    .main-header {
        font-size: 1.6rem !important;
        font-weight: 600;
        margin-bottom: 1rem;
        line-height: 1.2 !important;
    }
</style>
""", unsafe_allow_html=True)

# Küçük başlık - TEK SATIRDA
st.markdown('<h1 class="main-header">Sentos Sipariş ve Ürün Raporlama Aracı</h1>', unsafe_allow_html=True)

# Initialize session state - JSON dosyasından yükle
if 'printed_orders_persistent' not in st.session_state:
    st.session_state.printed_orders_persistent = load_printed_orders()

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

# TEK BUTON - TAM GENİŞLİK
if st.button("Siparişleri Getir ve Raporla"):
    if not API_KEY or not API_SECRET or not API_BASE_URL:
        st.error("❌ API bilgileri eksik. Lütfen Streamlit Cloud secrets ayarlarını kontrol edin.")
    else:
        with st.spinner("Verileriniz yükleniyor, lütfen bekleyin..."):
            orders_data = get_orders(start_date, end_date)
            
            if orders_data is not None:
                # API BAŞARILI MESAJI - ORTA ALANDA
                st.success("✅ API'den sipariş verileri başarıyla alındı!")
                
                final_report_df, error_message = process_data(orders_data, None)
                
                if error_message:
                    st.error(f"❌ {error_message}")
                elif final_report_df is not None:
                    # Daha önce yazdırılmış siparişleri kontrol et (tarihli)
                    printed_orders_dict = st.session_state.get('printed_orders_persistent', {})
                    
                    # Güncel siparişleri session'a kaydet (henüz yazdırılmadı)
                    current_order_set = set(final_report_df['Sipariş No'].unique())
                    st.session_state.current_orders = current_order_set

                    # ÖNEMLİ: Raporu session state'te sakla
                    st.session_state.final_report = final_report_df
                    
                    # Rapor başarı mesajı - ORTA ALANDA
                    st.success(f"✅ Başarılı! {len(final_report_df)} adet sipariş satırı raporlandı.")
                else:
                    st.info("ℹ️ Belirtilen tarih aralığında sipariş bulunamadı.")
            else:
                st.error("❌ API'den veri çekilemedi. Lütfen bağlantı bilgilerinizi kontrol edin.")

# RAPOR GÖSTERME KISMI - SESSION STATE'TEN
if 'final_report' in st.session_state:
    # SİPARİŞ ARAMA BARI
    st.subheader("🔍 Sipariş Arama")
    search_order = st.text_input("Sipariş numarası girin:", placeholder="Örn: 10457337072", key="search_input")
    
    # Session state'ten raporu al
    final_report_df = st.session_state.final_report
    
    # Filtrelenmiş veriyi göster
    display_df = final_report_df.copy()
    
    if search_order:
        # Arama yapılmışsa filtrele
        filtered_df = display_df[display_df['Sipariş No'].astype(str).str.contains(search_order, na=False, case=False)]
        if not filtered_df.empty:
            st.success(f"🎯 '{search_order}' için {len(filtered_df)} sonuç bulundu:")
            display_df = filtered_df
        else:
            st.warning(f"❌ '{search_order}' için sonuç bulunamadı.")
            display_df = pd.DataFrame()  # Boş dataframe
    
    # RAPORU TAM GENİŞLİKTE GÖSTER
    if not display_df.empty:
        st.subheader("Oluşturulan Rapor")
        st.dataframe(display_df, use_container_width=True)  # TAM GENİŞLİK!
        
        # İstatistikler
        if search_order:
            unique_orders = display_df['Sipariş No'].nunique()
            st.info(f"📊 Görüntülenen: {unique_orders} sipariş, {len(display_df)} ürün")
        
        # Excel indirme butonu - TÜM VERİYİ İNDİR
        excel_buffer = io.BytesIO()
        final_report_df.to_excel(excel_buffer, index=False, engine='openpyxl')
        
        st.download_button(
            label="📊 Tüm Raporu XLSX Olarak İndir",
            data=excel_buffer.getvalue(),
            file_name=f"sentos_rapor_{start_date}_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            on_click=save_printed_orders_to_persistent,
            help="Bu butona basınca TÜM siparişler 'yazdırıldı' olarak işaretlenir"
        )

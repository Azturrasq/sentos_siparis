# Gerekli kütüphaneleri içe aktarma
import streamlit as st
import pandas as pd
import requests
import io
import os
import json
from datetime import date, datetime, timezone

# Excel dosyası oluşturmak için openpyxl kütüphanesi gereklidir.
# Bu kütüphaneyi sanal ortamınıza yüklediğinizden emin olun:
# pip install openpyxl
#
# Not: Eğer bu satır hata verirse, Streamlit kütüphaneyi otomatik olarak yüklemeyebilir.
# O zaman aşağıdaki komutu manuel olarak çalıştırmanız gerekir:
# pip install pandas openpyxl streamlit requests python-dotenv

# --- 1. GÜVENLİK: ORTAM DEĞİŞKENLERİNİ YÜKLEME ---
# Streamlit Cloud'da gizli anahtarlar kullanıldığı için dotenv'e gerek kalmayabilir.
# Bu nedenle, dotenv modülünün bulunamaması durumunda hata vermesini engelliyoruz.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- 2. API BİLGİLERİ ---
# API bilgilerini .env dosyasından veya Streamlit gizli anahtarlarından okur.
API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

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
    except requests.exceptions.RequestException as e:
        st.error(f"API'ye bağlanırken bir hata oluştu: {e}")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"API'den hata yanıtı geldi: {e.response.status_code} - {e.response.text}")
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
        
        local_data_dict = {}
        for index, row in df.iterrows():
            barcode = str(row['Ürün Barkodu']).strip()
            local_data_dict[barcode] = {
                'ürün_kodu': str(row['Ürün Kodu']).strip(),
                'renk': str(row['Ürün Rengi']).strip(),
                'beden': str(row['Ürün Modeli']).strip(),
                'raf_no': str(row['Raf No']).strip()
            }
        return local_data_dict
    except Exception as e:
        st.error(f"Hata: '{file_path}' dosyasını okurken bir sorun oluştu: {e}")
        return None

# --- 4. VERİ İŞLEME FONKSİYONLARI ---
def process_data(orders_data, products_data):
    """
    Sipariş verilerini yerel Excel dosyasından gelen ürün bilgileriyle birleştirir ve raporu oluşturur.
    """
    if not isinstance(orders_data, dict) or 'data' not in orders_data:
        return None, "API'den sipariş verisi beklenmedik bir formatta geldi."
    orders_list = orders_data.get('data', [])

    local_products_dict = load_local_data()
    if local_products_dict is None:
        return None, "Yerel ürün verileri yüklenemedi."

    all_order_lines = []
    for order in orders_list:
        for line in order.get('lines', []):
            order_line_data = {
                'siparis_no': order.get('order_code'),
                'platform': order.get('source'),
                'adet': line.get('quantity'),
                'barkod': line.get('barcode'),
                'siparis_tarihi': order.get('order_date')
            }
            
            barcode = str(order_line_data.get('barkod')).strip()
            local_info = local_products_dict.get(barcode, {})
            
            order_line_data['urun_kodu'] = local_info.get('ürün_kodu', '-')
            order_line_data['renk'] = local_info.get('renk', '-')
            order_line_data['beden'] = local_info.get('beden', '-')
            order_line_data['raf_adresi'] = local_info.get('raf_no', '-')
            
            all_order_lines.append(order_line_data)
    
    if not all_order_lines:
        return None, "Belirtilen tarih aralığında sipariş satırı bulunamadı."
        
    orders_df = pd.DataFrame(all_order_lines)

    final_df = orders_df[[
        'siparis_tarihi',
        'siparis_no', 
        'platform',
        'urun_kodu',
        'renk',
        'beden',
        'adet', 
        'barkod', 
        'raf_adresi'
    ]].copy()
    
    final_df = final_df.rename(columns={
        'siparis_tarihi': 'Sipariş Tarihi',
        'siparis_no': 'Sipariş No',
        'platform': 'Platform',
        'urun_kodu': 'Model Kodu',
        'renk': 'Renk',
        'beden': 'Beden',
        'adet': 'Adet',
        'barkod': 'Barkod',
        'raf_adresi': 'Raf Adresi',
    })
    
    final_df.fillna('-', inplace=True)
    final_df.replace('', '-', inplace=True)

    final_df['Not'] = ''
    
    return final_df, None

def load_printed_orders():
    """Daha önce yazdırılmış siparişleri JSON dosyasından yükler."""
    if os.path.exists('printed_orders.json'):
        with open('printed_orders.json', 'r') as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()

def save_printed_orders(orders):
    """Yazdırılan siparişleri JSON dosyasına kaydeder."""
    with open('printed_orders.json', 'w') as f:
        json.dump(list(orders), f)

def update_printed_orders_state():
    """Raporu indirdikten sonra, güncel siparişleri oturum durumuna ve dosyaya kaydeder."""
    if 'current_orders' in st.session_state:
        st.session_state.printed_orders.update(st.session_state.current_orders)
        save_printed_orders(st.session_state.printed_orders)

# --- 5. STREAMLIT ARAYÜZÜ (UI) ---
st.title("Sentos Sipariş ve Ürün Raporlama Aracı")

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

# Buton
if st.button("Siparişleri Getir ve Raporla"):
    if not API_KEY or not API_SECRET or not API_BASE_URL:
        st.error("API bilgileri eksik. Lütfen .env dosyasını kontrol edin.")
    else:
        with st.spinner("Verileriniz yükleniyor, lütfen bekleyin..."):
            orders_data = get_orders(start_date, end_date)
            
            if orders_data is not None:
                final_report_df, error_message = process_data(orders_data, None)
                
                if error_message:
                    st.error(error_message)
                elif final_report_df is not None:
                    printed_orders_set = load_printed_orders()
                    
                    st.session_state.current_orders = set(final_report_df['Sipariş No'].unique())

                    for index, row in final_report_df.iterrows():
                        order_id = row['Sipariş No']
                        if order_id in printed_orders_set:
                            final_report_df.loc[index, 'Not'] = 'Daha önce yazdırıldı.'
                        
                    st.success(f"Başarılı! {len(final_report_df)} adet sipariş satırı raporlandı.")
                    st.subheader("Oluşturulan Rapor")
                    st.dataframe(final_report_df)

                    excel_buffer = io.BytesIO()
                    final_report_df.to_excel(excel_buffer, index=False, engine='openpyxl')
                    st.download_button(
                        label="Raporu XLSX Olarak İndir",
                        data=excel_buffer.getvalue(),
                        file_name=f"sentos_rapor_{start_date}_{end_date}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        on_click=update_printed_orders_state
                    )
                else:
                    st.info("Belirtilen tarih aralığında sipariş bulunamadı.")
            else:
                st.info("API'den veri çekilemedi. Lütfen bağlantı bilgilerinizi kontrol edin.")
import pandas as pd
import numpy as np

# --- Adım 1: Veriyi Yükleme ve Temizleme ---
try:
    # Use semicolon as delimiter and specify decimal comma
    df = pd.read_csv('örnek.csv', delimiter=';', decimal=',', encoding='utf-8')
    print("Dosya başarıyla okundu.")
    print("Mevcut sütunlar:", df.columns.tolist())
except FileNotFoundError:
    print("Hata: 'örnek.csv' dosyası bulunamadı.")
    exit()

# Tarih sütununu doğru formatla datetime nesnesine çevirelim
df['TARİH'] = pd.to_datetime(df['TARİH'], format='%d.%m.%Y %H:%M:%S', errors='coerce')

# Sayısal olması gereken sütunları sayısal yapalım
numeric_cols = ['Akım L1', 'Akım L2', 'Akım L3', 'Gerilim L1', 'Gerilim L2', 'Gerilim L3']
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# Olası hatalı okumalardan kaynaklanan boş verileri 0 ile dolduralım
df.fillna(0, inplace=True)

# Analiz için veriyi abone ve tarih bazında sıralayalım
df.sort_values(by=['TESİSAT_NO', 'TARİH'], inplace=True)
print("Veri temizlendi ve sıralandı.")

# --- Adım 2: Gerçek Tüketimi (kWh) Hesaplama ---
cos_phi = 0.88  # Sulama motorları için ortalama güç faktörü

# Her bir zaman damgası için anlık gücü (kW) hesapla
df['Guc_kW'] = (df['Akım L1'] * df['Gerilim L1'] +
                df['Akım L2'] * df['Gerilim L2'] +
                df['Akım L3'] * df['Gerilim L3']) * cos_phi / 1000

# Okumalar arasındaki zaman farkını saat cinsinden hesapla
df['Zaman_Farki_saat'] = df.groupby('TESİSAT_NO')['TARİH'].diff().dt.total_seconds() / 3600
df.fillna({'Zaman_Farki_saat': 0}, inplace=True)  # İlk okumalar için zaman farkı 0 olacak

# Enerji tüketimini (kWh) hesapla ve her abonenin toplamını bul
df['Tuketim_kWh'] = df['Guc_kW'] * df['Zaman_Farki_saat']
gercek_tuketim_df = df.groupby('TESİSAT_NO')['Tuketim_kWh'].sum().reset_index()
gercek_tuketim_df.rename(columns={'Tuketim_kWh': 'Gercek_Tuketim_kWh'}, inplace=True)
print("Gerçek tüketimler (kWh) hesaplandı.")

# --- Adım 3: Varsayımsal Tarım Verisi Oluşturma ---
# Bu tabloları kendi gerçek verilerinizle kolayca değiştirebilirsiniz
urun_enerji_ihtiyaci = {
    'Urun_Adi': ['Mısır', 'Pamuk', 'Domates'],
    'Sulama_Yontemi': ['Yağmurlama', 'Yağmurlama', 'Damla Sulama'],
    'Enerji_ihtiyaci_kWh_dekar': [550, 620, 400]
}
urun_df = pd.DataFrame(urun_enerji_ihtiyaci)

abone_bilgileri = {
    'TESİSAT_NO': [4006513096, 4007399230, 4007611482],
    'Tarla_Alani_dekar': [70, 35, 120],
    'Ekilen_Urun': ['Mısır', 'Domates', 'Pamuk'],
    'Sulama_Yontemi': ['Yağmurlama', 'Damla Sulama', 'Yağmurlama']
}
abone_df = pd.DataFrame(abone_bilgileri)
print("Varsayımsal tarım veritabanı oluşturuldu.")

# --- Adım 4: Analiz, Karşılaştırma ve Raporlama ---
# Tüm verileri tek bir tabloda birleştirme
analiz_df = pd.merge(abone_df, urun_df, left_on=['Ekilen_Urun', 'Sulama_Yontemi'], right_on=['Urun_Adi', 'Sulama_Yontemi'])
analiz_df = pd.merge(analiz_df, gercek_tuketim_df, on='TESİSAT_NO')

# Beklenen tüketimi, sapmayı ve risk skorunu hesaplama
analiz_df['Beklenen_Tuketim_kWh'] = analiz_df['Tarla_Alani_dekar'] * analiz_df['Enerji_ihtiyaci_kWh_dekar']
analiz_df['Sapma_Yuzde'] = 100 * (analiz_df['Gercek_Tuketim_kWh'] - analiz_df['Beklenen_Tuketim_kWh']) / analiz_df['Beklenen_Tuketim_kWh'].replace(0, np.nan)
analiz_df['Risk_Skoru'] = abs(analiz_df['Sapma_Yuzde'] / 100) * analiz_df['Tarla_Alani_dekar']

# Durum tespiti yapma
sapma_esigi = 25  # %25'ten fazla sapma şüpheli kabul edilecek
def durum_tespiti(sapma):
    if pd.isna(sapma): return "Hesaplanamadı"
    if sapma > sapma_esigi: return "Kaçak Şüphesi (Yüksek Tüketim)"
    elif sapma < -sapma_esigi: return "Anomali (Düşük Tüketim)"
    else: return "Normal"
analiz_df['Durum'] = analiz_df['Sapma_Yuzde'].apply(durum_tespiti)

# Nihai rapor için sütunları düzenleme ve sıralama
sonuc_raporu = analiz_df[[
    'TESİSAT_NO', 'Ekilen_Urun', 'Tarla_Alani_dekar', 'Beklenen_Tuketim_kWh',
    'Gercek_Tuketim_kWh', 'Sapma_Yuzde', 'Risk_Skoru', 'Durum'
]].sort_values(by='Risk_Skoru', ascending=False).round(2)

print("\n" + "="*45)
print("     TOPRAK - Kaçak Elektrik Analiz Raporu")
print("="*45)
print(sonuc_raporu.to_string(index=False))

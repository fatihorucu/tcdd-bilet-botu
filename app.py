import requests
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os

# --- YAPILANDIRMA (E-POSTA) ---
SMTP_SERVER = "smtp.gmail.com" # Gmail kullanıyorsanız bu kalabilir
SMTP_PORT = 465                # SSL için standart port

GONDEREN_EMAIL = os.getenv("GONDEREN_EMAIL")
ALICI_EMAIL = os.getenv("ALICI_EMAIL")
EMAIL_SIFRESI = os.getenv("EMAIL_SIFRESI") # Google App Password
AUTH_TOKEN = os.getenv("AUTH_TOKEN")       # authorization (Bearer...)
USER_AUTH_TOKEN = os.getenv("USER_AUTH_TOKEN") # user-authorization



# --- YAPILANDIRMA (API & PAYLOAD) ---
API_URL = "https://web-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/train-availability?environment=dev&userId=1"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "authorization": AUTH_TOKEN, # Güncel token ekleyin
    "user-authorization": USER_AUTH_TOKEN, # Güncel token ekleyin
    "unit-id": "3895",
    "content-type": "application/json",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
}

PAYLOAD = {
    "blTrainTypes": ["TURISTIK_TREN"],
    "passengerTypeCounts": [{"id": 0, "count": 1}],
    "searchReservation": False,
    "searchRoutes": [
        {
            "departureStationId": 98,
            "departureStationName": "ANKARA GAR",
            "arrivalStationId": 532,
            "arrivalStationName": "KARS",
            "departureDate": "24-03-2026 21:00:00"
        }
    ]
}

def email_gonder(mesaj_metni):
    msg = MIMEMultipart()
    msg['From'] = GONDEREN_EMAIL
    msg['To'] = ALICI_EMAIL
    msg['Subject'] = "TCDD BİLET ALARMI: Yer Bulundu!"

    msg.attach(MIMEText(mesaj_metni, 'plain'))

    try:
        # SSL ile güvenli bağlantı kurup e-postayı gönderiyoruz
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(GONDEREN_EMAIL, EMAIL_SIFRESI)
            server.send_message(msg)
            print("E-posta başarıyla gönderildi.")
    except Exception as e:
        print(f"E-posta gönderim hatası: {e}")

def bilet_sorgula():
    zaman = datetime.now().strftime('%H:%M:%S')
    print(f"\n--- [{zaman}] Sorgu Başlatıldı ---")
    
    try:
        aranan_tarih = PAYLOAD['searchRoutes'][0]['departureDate']
        response = requests.post(API_URL, json=PAYLOAD, headers=HEADERS, timeout=30)
        
        # API yanıtını JSON olarak alıyoruz
        try:
            data = response.json()
        except:
            data = {}

        # 1. SENARYO: SEFER BULUNAMADI (Sessiz Kal)
        # TCDD 604 kodunu hem 200 hem de 400 HTTP koduyla gönderebilir.
        if data.get("code") == 604:
            print(f"DEBUG: Sefer henüz yok (604). Mail gönderilmedi.")
            return # Fonksiyonu burada bitir, mail atma.

        # 2. SENARYO: BAŞARILI SORGULAMA VE BİLET BULUNMASI (Mail At)
        if response.status_code == 200 and "trainLegs" in data:
            bulunan_seferler = []
            for leg in data["trainLegs"]:
                for avail in leg.get("trainAvailabilities", []):
                    for train in avail.get("trains", []):
                        tren_adi = train.get("name", "Bilinmeyen Tren")
                        bulunan_seferler.append(f"🚆 {tren_adi} | 📅 {aranan_tarih}")

            if bulunan_seferler:
                bildirim = "🚨 BİLET BULUNDU!\n\n" + "\n".join(bulunan_seferler)
                bildirim += f"\n\nSorgu Zamanı: {zaman}\n🔗 Al: https://ebilet.tcddtasimacilik.gov.tr/"
                email_gonder(bildirim)
                print("DEBUG: Bilet bulundu, mail gönderildi.")
                return

        # 3. SENARYO: TOKEN HATASI (401 veya 403) (Mail At)
        if response.status_code in [401, 403]:
            mesaj = f"⚠️ TCDD BOT: TOKEN DEĞİŞTİRMENİZ GEREKİYOR (Hata: {response.status_code})\nZaman: {zaman}"
            email_gonder(mesaj)
            print("DEBUG: Token hatası, uyarı maili gönderildi.")
            return

        # 4. SENARYO: DİĞER BEKLENMEDİK KRİTİK HATALAR (Opsiyonel Mail)
        # 604 ve 200 dışındaki hatalar sistemi durduracağı için bilgi veriyoruz.
        if response.status_code != 200:
            hata_notu = f"⚠️ TCDD BOT: Beklenmedik bir hata oluştu (HTTP {response.status_code})\nYanıt: {response.text[:100]}"
            email_gonder(hata_notu)
            print(f"DEBUG: Beklenmedik hata: {response.status_code}")

    except Exception as e:
        # İnternet kesilmesi veya zaman aşımı durumunda bilgilendirme
        mesaj = f"⚠️ TCDD BOT SİSTEM HATASI (Bağlantı/Timeout): {str(e)}"
        email_gonder(mesaj)
        print(f"DEBUG: Sistem hatası maili gönderildi: {e}")
        


if __name__ == "__main__":
    print("Email tabanlı TCDD alarmı aktif.")
    bilet_sorgula() # İlk kontrol

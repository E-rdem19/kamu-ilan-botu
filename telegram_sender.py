import os
import re
import requests

def temizle_dosya_adi(ad: str) -> str:
    """Türkçe ve geçersiz karakterleri temizler."""
    ad = re.sub(r'[\\/*?:"<>|]', "", ad)
    return ad.strip() or "ilan_eki.pdf"

class TelegramSender:
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

        if not self.token or not self.chat_id:
            raise ValueError("Telegram Bot Token veya Chat ID bulunamadı!")

    def mesaj_gonder(self, ilan: dict) -> int:
        """İlan mesajını Telegram kanalına gönderir ve mesaj ID'sini döner."""
        metin = (
            f"📢 <b>{ilan.get('baslik', 'Yeni İlan')}</b>\n\n"
            f"🏛 <b>Kurum:</b> {ilan.get('kurum', 'Belirtilmemiş')}\n"
            f"📍 <b>Şehir:</b> {ilan.get('il', 'Türkiye Geneli')}\n"
            f"📅 <b>Son Başvuru:</b> {ilan.get('son_basvuru_tarihi', 'Belirtilmemiş')}\n"
            f"🌐 <b>Kaynak:</b> #{ilan.get('kaynak_site', 'Kamu')}\n\n"
            f"🔗 <a href='{ilan.get('link')}'>İlan Detayına Git</a>"
        )

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": metin,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }

        cevap = requests.post(url, json=payload, timeout=20)
        cevap_json = cevap.json()
        if not cevap_json.get("ok"):
            raise RuntimeError(f"Mesaj gönderilemedi: {cevap_json.get('description')}")

        return cevap_json["result"]["message_id"]

    def pdf_gonder(self, dosya_url: str, dosya_adi: str, yanitlanacak_mesaj_id: int, max_boyut_mb: int = 50):
        """PDF dosyasını indirip ilgili mesaja yanıt olarak gönderir."""
        gecici_yol = f"/tmp/{temizle_dosya_adi(dosya_adi)}"
        
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            with requests.get(dosya_url, headers=headers, stream=True, timeout=30) as r:
                r.raise_for_status()
                boyut = 0
                with open(gecici_yol, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        boyut += len(chunk)
                        if boyut > max_boyut_mb * 1024 * 1024:
                            print(f"[UYARI] {dosya_adi} 50MB'tan büyük! İndirme durduruldu.")
                            return False
                        f.write(chunk)

            url = f"{self.base_url}/sendDocument"
            with open(gecici_yol, "rb") as f:
                dosyalar = {"document": (dosya_adi, f)}
                data = {
                    "chat_id": self.chat_id,
                    "reply_to_message_id": yanitlanacak_mesaj_id,
                    "caption": f"📎 {dosya_adi[:200]}"
                }
                cevap = requests.post(url, data=data, files=dosyalar, timeout=60)
                cevap_json = cevap.json()
                return cevap_json.get("ok", False)

        except Exception as e:
            print(f"[HATA] PDF gönderilemedi ({dosya_adi}): {e}")
            return False
        finally:
            if os.path.exists(gecici_yol):
                os.remove(gecici_yol)

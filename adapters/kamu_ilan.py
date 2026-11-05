import requests
import urllib3
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from models import Ilan

urllib3.disable_warnings()

class KamuIlanAdapter:
    def __init__(self, limit: int = 15):
        self.limit = limit
        self.kaynak_site = "kamuilan_sbb"
        self.base_url = "https://kamuilan.sbb.gov.tr"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9",
            "Referer": "https://kamuilan.sbb.gov.tr/"
        }

    def ilanlari_getir(self) -> list:
        toplanan_ilanlar = []
        print("[KamuilanSBB] İlanlar taranıyor...")

        try:
            session = requests.Session()
            session.headers.update(self.headers)

            r = session.get(self.base_url, timeout=15, verify=False)
            if r.status_code != 200:
                print(f"[KamuilanSBB] Siteye erişilemedi (Durum Kodu: {r.status_code}).")
                return []

            soup = BeautifulSoup(r.text, "html.parser")
            
            # Tablodaki veya listedeki ilan linklerini bul (ilanDetay.aspx?kod=...)
            ilan_linkleri = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "ilanDetay.aspx" in href or "kod=" in href:
                    tam_url = urljoin(self.base_url, href)
                    if tam_url not in ilan_linkleri:
                        ilan_linkleri.append(tam_url)

            print(f"[KamuilanSBB] Bulunan ilan linki sayısı: {len(ilan_linkleri)}")
            if self.limit:
                ilan_linkleri = ilan_linkleri[:self.limit]

            for i, link in enumerate(ilan_linkleri, 1):
                try:
                    kod_match = re.search(r"kod=([^&]+)", link)
                    ilan_id = kod_match.group(1) if kod_match else str(i)

                    detay_resp = session.get(link, timeout=12, verify=False)
                    if detay_resp.status_code != 200:
                        continue

                    detay_soup = BeautifulSoup(detay_resp.text, "html.parser")
                    
                    # Başlık ve Kurum bilgilerini yakala
                    baslik_etiketi = detay_soup.find(["h1", "h2", "h3", "span"], class_=lambda x: x and ("baslik" in x.lower() or "title" in x.lower()))
                    baslik = baslik_etiketi.get_text(strip=True) if baslik_etiketi else (detay_soup.title.string.strip() if detay_soup.title else "Kamu İlanı")

                    metin = detay_soup.get_text(separator="\n", strip=True)

                    # Tarihleri ayıkla
                    tarihler = re.findall(r"\d{2}[./]\d{2}[./]\d{4}", metin)
                    son_tarih = tarihler[-1] if tarihler else "Belirtilmemiş"
                    yayin_tarihi = tarihler[0] if tarihler else ""

                    # Kurum adını sayfadaki tablolardan veya başlıktan tahmin et
                    kurum = "Kamu Kurumu"
                    for row in detay_soup.find_all(["tr", "div"]):
                        row_text = row.get_text()
                        if "kurum" in row_text.lower():
                            parts = row_text.split(":")
                            if len(parts) > 1:
                                kurum = parts[1].strip()[:100]
                                break

                    # PDF / Ek dosyaları tespit et
                    ek_dosyalar = []
                    for a_tag in detay_soup.find_all("a", href=True):
                        h = a_tag["href"]
                        if ".pdf" in h.lower() or "indir" in h.lower() or "dosya" in h.lower():
                            pdf_url = urljoin(self.base_url, h)
                            dosya_adi = pdf_url.split("/")[-1].split("?")[0]
                            if not dosya_adi.endswith(".pdf"):
                                dosya_adi += ".pdf"
                            ek_dosyalar.append({"dosya_adi": dosya_adi, "url": pdf_url})

                    ilan_obj = Ilan(
                        kaynak_site=self.kaynak_site,
                        ilan_id=ilan_id,
                        baslik=baslik[:200],
                        kurum=kurum,
                        il="Belirtilmemiş",
                        ilan_tarihi=yayin_tarihi,
                        son_basvuru_tarihi=son_tarih,
                        link=link,
                        ek_dosyalar=ek_dosyalar,
                        detay_metni=metin[:5000]
                    )
                    toplanan_ilanlar.append(ilan_obj)
                    print(f"[{i}/{len(ilan_linkleri)}] Çekildi: {baslik[:40]}...")

                except Exception as inner_e:
                    print(f"[KamuilanSBB] İlan detayı ayrıştırılamadı: {inner_e}")
                    continue

        except Exception as e:
            print(f"[KamuilanSBB] Siteye bağlanılamadı (Muhtemelen Yurt Dışı Engeli): {e}")
            return []

        return toplanan_ilanlar

import requests
import urllib3
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from models import Ilan

urllib3.disable_warnings()

class YerelYonetimlerAdapter:
    def __init__(self, limit: int = 15):
        self.limit = limit
        self.kaynak_site = "yerel_yonetimler"
        self.base_url = "https://yerelyonetimler.csb.gov.tr"
        self.duyuru_url = "https://yerelyonetimler.csb.gov.tr/duyurular"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9",
            "Referer": "https://yerelyonetimler.csb.gov.tr/"
        }

    def ilanlari_getir(self) -> list:
        toplanan_ilanlar = []
        print("[YerelYonetimler] İlanlar ve duyurular taranıyor...")

        try:
            session = requests.Session()
            session.headers.update(self.headers)

            r = session.get(self.duyuru_url, timeout=15, verify=False)
            if r.status_code != 200:
                # Yedek olarak ana sayfayı dene
                r = session.get(self.base_url, timeout=15, verify=False)
                if r.status_code != 200:
                    print(f"[YerelYonetimler] Siteye erişilemedi (Durum Kodu: {r.status_code}).")
                    return []

            soup = BeautifulSoup(r.text, "html.parser")
            
            # Sayfadaki duyuru linklerini topla
            duyuru_linkleri = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                metin = a.get_text(strip=True)
                if any(k in href.lower() for k in ["duyuru", "haber", "ilan"]) and len(metin) > 10:
                    tam_url = urljoin(self.base_url, href)
                    if (tam_url, metin) not in duyuru_linkleri:
                        duyuru_linkleri.append((tam_url, metin))

            print(f"[YerelYonetimler] Bulunan duyuru/ilan sayısı: {len(duyuru_linkleri)}")
            if self.limit:
                duyuru_linkleri = duyuru_linkleri[:self.limit]

            for i, (link, baslik) in enumerate(duyuru_linkleri, 1):
                try:
                    ilan_id = link.rstrip("/").split("/")[-1].split("?")[0]
                    detay_resp = session.get(link, timeout=12, verify=False)
                    if detay_resp.status_code != 200:
                        continue

                    detay_soup = BeautifulSoup(detay_resp.text, "html.parser")
                    metin = detay_soup.get_text(separator="\n", strip=True)

                    # Tarihleri ayıkla
                    tarihler = re.findall(r"\d{2}[./]\d{2}[./]\d{4}", metin)
                    son_tarih = tarihler[-1] if tarihler else "Belirtilmemiş"
                    yayin_tarihi = tarihler[0] if tarihler else ""

                    # PDF / Ek dosyaları tespit et
                    ek_dosyalar = []
                    for a_tag in detay_soup.find_all("a", href=True):
                        h = a_tag["href"]
                        if ".pdf" in h.lower() or "indir" in h.lower() or "ek" in h.lower():
                            pdf_url = urljoin(self.base_url, h)
                            dosya_adi = pdf_url.split("/")[-1].split("?")[0]
                            if not dosya_adi.endswith(".pdf"):
                                dosya_adi += ".pdf"
                            ek_dosyalar.append({"dosya_adi": dosya_adi, "url": pdf_url})

                    ilan_obj = Ilan(
                        kaynak_site=self.kaynak_site,
                        ilan_id=ilan_id or str(i),
                        baslik=baslik[:200],
                        kurum="Belediye / Yerel Yönetim",
                        il="Belirtilmemiş",
                        ilan_tarihi=yayin_tarihi,
                        son_basvuru_tarihi=son_tarih,
                        link=link,
                        ek_dosyalar=ek_dosyalar,
                        detay_metni=metin[:5000]
                    )
                    toplanan_ilanlar.append(ilan_obj)
                    print(f"[{i}/{len(duyuru_linkleri)}] Çekildi: {baslik[:40]}...")

                except Exception as inner_e:
                    print(f"[YerelYonetimler] Duyuru detayı ayrıştırılamadı: {inner_e}")
                    continue

        except Exception as e:
            print(f"[YerelYonetimler] Siteye bağlanılamadı (Muhtemelen Yurt Dışı Engeli): {e}")
            return []

        return toplanan_ilanlar

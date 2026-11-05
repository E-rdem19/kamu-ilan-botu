import requests
import urllib3
import json
import time
from models import Ilan

urllib3.disable_warnings()

class KariyerKapisiAdapter:
    def __init__(self, limit: int = 20):
        self.limit = limit
        self.kaynak_site = "kariyer_kapisi"
        self.api_url = "https://api.kariyerkapisi.gov.tr/api/ilan/GetIseAlimPage"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://kariyerkapisi.gov.tr",
            "Referer": "https://kariyerkapisi.gov.tr/isealim"
        }

    def ilanlari_getir(self) -> list:
        toplanan_ilanlar = []
        print("[KariyerKapisi] İlanlar taranıyor...")

        try:
            r = requests.post(self.api_url, headers=self.headers, json={}, timeout=15, verify=False)
            if r.status_code != 200:
                print(f"[KariyerKapisi] Sunucu yanıt vermedi (Kod: {r.status_code}).")
                return []

            veri = r.json()
            ilan_listesi = []

            # Dönen JSON yapısından ilan listesini bul
            if isinstance(veri, list):
                ilan_listesi = veri
            elif isinstance(veri, dict):
                for k, v in veri.items():
                    if isinstance(v, list) and len(v) > 0:
                        ilan_listesi = v
                        break

            print(f"[KariyerKapisi] Toplam {len(ilan_listesi)} adet ham ilan bulundu.")
            if self.limit:
                ilan_listesi = ilan_listesi[:self.limit]

            for it in ilan_listesi:
                try:
                    ilan_id = str(it.get("id") or it.get("ilanId") or it.get("IlanId", ""))
                    baslik = it.get("baslik") or it.get("unvan") or it.get("IlanBaslik") or "Kariyer Kapısı İlanı"
                    kurum = it.get("kurumAdi") or it.get("kurum") or it.get("KurumAdi") or "Kamu Kurumu"
                    sehir = it.get("sehir") or it.get("il") or it.get("SehirAdi") or "Türkiye Geneli"
                    yayin = it.get("yayinTarihi") or it.get("baslangicTarihi") or ""
                    bitis = it.get("bitisTarihi") or it.get("sonBasvuruTarihi") or it.get("BitisTarihi") or "Belirtilmemiş"

                    link = f"https://kariyerkapisi.gov.tr/isealim/ilan/{ilan_id}" if ilan_id else "https://kariyerkapisi.gov.tr/isealim"

                    # PDF/Ek dosya kontrolü
                    ek_dosyalar = []
                    dosya_url = it.get("dosyaUrl") or it.get("dosyaYolu") or it.get("ekDosya")
                    if dosya_url:
                        if not dosya_url.startswith("http"):
                            dosya_url = f"https://kariyerkapisi.gov.tr{dosya_url}"
                        dosya_adi = dosya_url.split("/")[-1].split("?")[0]
                        ek_dosyalar.append({"dosya_adi": dosya_adi, "url": dosya_url})

                    detay_metni = f"{baslik} {kurum} {it.get('aciklama', '')} {it.get('sartlar', '')}"

                    ilan_obj = Ilan(
                        kaynak_site=self.kaynak_site,
                        ilan_id=ilan_id or str(hash(baslik + kurum)),
                        baslik=baslik,
                        kurum=kurum,
                        il=sehir,
                        ilan_tarihi=str(yayin)[:10],
                        son_basvuru_tarihi=str(bitis)[:10],
                        link=link,
                        ek_dosyalar=ek_dosyalar,
                        detay_metni=detay_metni
                    )
                    toplanan_ilanlar.append(ilan_obj)
                except Exception as inner_e:
                    print(f"[KariyerKapisi] İlan işlenirken hata: {inner_e}")
                    continue

        except Exception as e:
            print(f"[KariyerKapisi] Bağlantı kurulamadı (Muhtemelen Yurt Dışı Engeli): {e}")
            return []

        return toplanan_ilanlar

from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class EkDosya:
    dosya_adi: str
    url: str

@dataclass
class Ilan:
    kaynak_site: str        # 'ilan_gov_tr', 'kariyer_kapisi' vb.
    ilan_id: str            # Sitenin ilana verdiği benzersiz numara
    baslik: str
    kurum: str
    il: str
    ilan_tarihi: str
    son_basvuru_tarihi: str
    link: str
    ek_dosyalar: List[Dict[str, str]] = field(default_factory=list) # [{'dosya_adi': '...', 'url': '...'}]
    detay_metni: str = ""   # Filtreleme için detay sayfasındaki yazı

    @property
    def benzersiz_id(self) -> str:
        """Her ilan için benzersiz kimlik: site + id"""
        return f"{self.kaynak_site}_{self.ilan_id}"

    def to_dict(self) -> dict:
        return {
            "kaynak_site": self.kaynak_site,
            "ilan_id": self.ilan_id,
            "baslik": self.baslik,
            "kurum": self.kurum,
            "il": self.il,
            "ilan_tarihi": self.ilan_tarihi,
            "son_basvuru_tarihi": self.son_basvuru_tarihi,
            "link": self.link,
            "ek_dosyalar": self.ek_dosyalar
        }

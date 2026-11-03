import json
import os

class Database:
    def __init__(self, dosya_yolu: str = "gorulen_ilanlar.json"):
        self.dosya_yolu = dosya_yolu
        self.gorulen_idler = self._yukle()

    def _yukle(self) -> set:
        if os.path.exists(self.dosya_yolu):
            try:
                with open(self.dosya_yolu, "r", encoding="utf-8") as f:
                    veri = json.load(f)
                    return set(veri.get("gorulen_idler", []))
            except Exception as e:
                print(f"[UYARI] Veritabanı dosyası okunamadı, sıfırlanıyor: {e}")
                return set()
        return set()

    def ilan_goruldu_mu(self, benzersiz_id: str) -> bool:
        return benzersiz_id in self.gorulen_idler

    def ilani_kaydet(self, benzersiz_id: str):
        self.gorulen_idler.add(benzersiz_id)
        self._kaydet()

    def toplu_kaydet(self, id_listesi: list):
        for bid in id_listesi:
            self.gorulen_idler.add(bid)
        self._kaydet()

    def _kaydet(self):
        try:
            with open(self.dosya_yolu, "w", encoding="utf-8") as f:
                json.dump({"gorulen_idler": list(self.gorulen_idler)}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[HATA] Veritabanı kaydedilemedi: {e}")

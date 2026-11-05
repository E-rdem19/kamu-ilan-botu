import io
import requests
from pypdf import PdfReader
from models import Ilan

TR_MAP = str.maketrans({
    "İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c",
})

def fold_tr(s: str) -> str:
    """Türkçe karakterleri güvenli bir şekilde küçük harfe çevirir."""
    return (s or "").translate(TR_MAP).lower()

class FilterEngine:
    def __init__(self, config: dict):
        self.filtre_cfg = config.get("filtre", {})
        self.aktif = self.filtre_cfg.get("aktif", False)
        self.kelimeler = [fold_tr(k) for k in self.filtre_cfg.get("anahtar_kelimeler", ["önlisans", "ön lisans", "kpss"])]
        self.detayda_ara = self.filtre_cfg.get("detay_sayfasinda_ara", True)
        self.pdfte_ara = self.filtre_cfg.get("pdf_metninde_ara", False)
        self.okunamayan_pdf_kabul = self.filtre_cfg.get("okunamayan_pdf_kabul_et", True)

    def ilani_kontrol_et(self, ilan: Ilan) -> bool:
        """İlan filtreden geçiyor mu kontrol eder. Filtre kapalıysa her zaman True döner."""
        if not self.aktif:
            return True

        # 1. Başlıkta ara
        baslik_katla = fold_tr(ilan.baslik)
        if any(kelime in baslik_katla for kelime in self.kelimeler):
            print(f"[Filtre] Başlıkta bulundu: {ilan.baslik[:40]}")
            return True

        # 2. Detay metninde ara
        if self.detayda_ara and ilan.detay_metni:
            detay_katla = fold_tr(ilan.detay_metni)
            if any(kelime in detay_katla for kelime in self.kelimeler):
                print(f"[Filtre] Detay sayfasında bulundu: {ilan.baslik[:40]}")
                return True

        # 3. PDF metninde ara (Opsiyonel - Config'ten açılırsa)
        if self.pdfte_ara and ilan.ek_dosyalar:
            pdf_sonucu = self._pdf_metninde_ara(ilan)
            if pdf_sonucu:
                return True

        # Hiçbir yerde bulunamadı
        return False

    def _pdf_metninde_ara(self, ilan: Ilan) -> bool:
        for ek in ilan.ek_dosyalar:
            url = ek.get("url")
            if not url or not url.lower().endswith(".pdf"):
                continue

            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                r = requests.get(url, headers=headers, timeout=15)
                if r.status_code != 200:
                    continue

                reader = PdfReader(io.BytesIO(r.content))
                tam_metin = ""
                # İlk 5 sayfayı oku (performans için)
                for sayfa in reader.pages[:5]:
                    yazi = sayfa.extract_text() or ""
                    tam_metin += " " + yazi

                if not tam_metin.strip():
                    print(f"[Filtre/PDF] {ek['dosya_adi']}: Taranmış resim PDF, metin okunamadı.")
                    return self.okunamayan_pdf_kabul

                katlanmis = fold_tr(tam_metin)
                if any(kelime in katlanmis for kelime in self.kelimeler):
                    print(f"[Filtre/PDF] PDF içinde anahtar kelime bulundu: {ek['dosya_adi']}")
                    return True

            except Exception as e:
                print(f"[Filtre/PDF] Hata ({ek['dosya_adi']}): {e}")
                return self.okunamayan_pdf_kabul

        return False

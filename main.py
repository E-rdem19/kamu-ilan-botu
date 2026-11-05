import os
import sys
import time
import yaml
import traceback
from database import Database
from models import Ilan
from filter_engine import FilterEngine
from telegram_sender import TelegramSender

# Adaptörler
from adapters.ilan_gov_tr import IlanGovTrAdapter
from adapters.kariyer_kapisi import KariyerKapisiAdapter
from adapters.kamu_ilan import KamuIlanAdapter
from adapters.yerel_yonetimler import YerelYonetimlerAdapter

def config_yukle(dosya_yolu="config.yaml") -> dict:
    if os.path.exists(dosya_yolu):
        with open(dosya_yolu, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def main():
    print("=" * 60)
    print("📢 KAMU İLAN TAKİP VE TELEGRAM BİLDİRİM SİSTEMİ BAŞLATILIYOR")
    print("=" * 60)

    cfg = config_yukle()
    db = Database()
    filtre = FilterEngine(cfg)

    tg_cfg = cfg.get("telegram", {})
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or tg_cfg.get("bot_token")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or tg_cfg.get("chat_id")

    try:
        sender = TelegramSender(token=token, chat_id=chat_id)
    except Exception as e:
        print(f"[KRİTİK HATA] Telegram başlatılamadı: {e}")
        return

    sistem_cfg = cfg.get("sistem", {})
    pdf_cfg = cfg.get("pdf", {})
    bekleme_sn = sistem_cfg.get("istekler_arasi_bekleme_sn", 1.5)
    sessiz_mod = sistem_cfg.get("sessiz_kayit_modu", False)

    ilk_calistirma = len(db.gorulen_idler) == 0

    # Adaptör Listesi (Genişletilmiş Sayfa ve İlanlar)
    adaptorler = [
        ("İlan Gov Tr", IlanGovTrAdapter(max_pages=4, limit=0)),
        ("Kariyer Kapısı", KariyerKapisiAdapter(limit=30)),
        ("Kamuilan SBB", KamuIlanAdapter(limit=30)),
        ("Yerel Yönetimler", YerelYonetimlerAdapter(limit=30))
    ]

    toplam_yeni_ilan = 0
    hatali_siteler = []

    for ad, adaptor in adaptorler:
        print(f"\n--- [{ad}] Taranıyor ---")
        try:
            ilanlar = adaptor.ilanlari_getir()
            print(f"[{ad}] Çekilen ilan sayısı: {len(ilanlar)}")
        except Exception as e:
            print(f"[{ad}] HATA OLUŞTU: {e}")
            hatali_siteler.append(ad)
            continue

        for ilan in ilanlar:
            b_id = ilan.benzersiz_id

            if db.ilan_goruldu_mu(b_id):
                continue

            if not filtre.ilani_kontrol_et(ilan):
                db.ilani_kaydet(b_id)
                continue

            if sessiz_mod:
                print(f"[Sessiz Kayıt] Hafızaya alınıyor: {ilan.baslik[:40]}")
                db.ilani_kaydet(b_id)
                continue

            try:
                print(f"[Telegram] İlan gönderiliyor: {ilan.baslik[:45]}...")
                mesaj_id = sender.mesaj_gonder(ilan.to_dict())
                toplam_yeni_ilan += 1
                time.sleep(bekleme_sn)

                if pdf_cfg.get("gonder", True) and ilan.ek_dosyalar:
                    max_adet = pdf_cfg.get("maksimum_adet", 5)
                    max_boyut = pdf_cfg.get("maksimum_boyut_mb", 50)
                    
                    for ek in ilan.ek_dosyalar[:max_adet]:
                        print(f"   [PDF] Yükleniyor: {ek['dosya_adi']}")
                        sender.pdf_gonder(
                            dosya_url=ek["url"],
                            dosya_adi=ek["dosya_adi"],
                            yanitlanacak_mesaj_id=mesaj_id,
                            max_boyut_mb=max_boyut
                        )
                        time.sleep(bekleme_sn)

                db.ilani_kaydet(b_id)

            except Exception as tg_e:
                print(f"[Telegram Hata] İlan gönderilemedi ({b_id}): {tg_e}")
                time.sleep(bekleme_sn)

    print("\n" + "=" * 60)
    print(f"BİTTİ! Toplam {toplam_yeni_ilan} adet yeni ilan başarıyla kanala gönderildi.")
    if hatali_siteler:
        print(f"Ulaşılamayan Siteler: {', '.join(hatali_siteler)}")
    print("=" * 60)

if __name__ == "__main__":
    main()

import re
import json
import html
import time
import urllib3
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from playwright.sync_api import sync_playwright
from models import Ilan

urllib3.disable_warnings()

BASE = "https://www.ilan.gov.tr"
LIST_URL = BASE + "/ilan/tum-ilanlar/personel-alimi?ats=5"
DETAIL_API = BASE + "/api/api/services/app/AdDetail/GetAdDetail?id={id}"

API_HEADERS = {
    "accept": "text/plain",
    "accept-language": "tr-TR",
    "x-request-origin": "IGT-UI",
    "x-requested-with": "XMLHttpRequest",
    "referer": LIST_URL,
}

TR_MAP = str.maketrans({
    "İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c",
})

DATE_RE = r"\d{2}[./]\d{2}[./]\d{4}"

def fold(s):
    return (s or "").translate(TR_MAP).lower()

def html_to_text(s):
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>|</h\d>", "\n", s or "")
    s = re.sub(r"(?i)</t[dh]>", "\t", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ ]+", " ", s)
    s = re.sub(r"[ \t]*\n[ \t\n]*", "\n", s)
    return s.strip()

def find_item_list(obj):
    if isinstance(obj, dict):
        if "result" in obj and isinstance(obj["result"], dict):
            if "items" in obj["result"]:
                return obj["result"]["items"]
        for v in obj.values():
            res = find_item_list(v)
            if res:
                return res
    elif isinstance(obj, list):
        if obj and isinstance(obj[0], dict) and "id" in obj[0]:
            return obj
    return []

def extract_son_basvuru(text):
    for line in text.split("\n"):
        f = fold(line)
        if "son basvuru" in f or "basvuru bitis" in f or "duyuru bitis" in f:
            tarihler = re.findall(DATE_RE, line)
            if tarihler:
                return tarihler[0]
    # İkinci deneme
    tarihler = re.findall(DATE_RE, text)
    return tarihler[-1] if tarihler else "Belirtilmemiş"

class IlanGovTrAdapter:
    def __init__(self, limit: int = 5):
        self.limit = limit
        self.kaynak_site = "ilan_gov_tr"

    def ilanlari_getir(self) -> list:
        toplanan_ilanlar = []
        
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(locale="tr-TR", ignore_https_errors=True)
            page = ctx.new_page()

            captured = {}
            first_resp = {}

            def on_request(r):
                if "Ad/AdsByFilter" in r.url and "info" not in captured:
                    captured["info"] = (r.url, r.method, r.post_data, dict(r.headers))

            def on_response(r):
                if "Ad/AdsByFilter" in r.url and "data" not in first_resp:
                    try:
                        first_resp["data"] = r.json()
                    except Exception:
                        pass

            page.on("request", on_request)
            page.on("response", on_response)
            
            print("[İlanGovTr] Sayfa açılıyor...")
            page.goto(LIST_URL, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2000)

            items = find_item_list(first_resp.get("data", {}))
            print(f"[İlanGovTr] İlk sayfadan {len(items)} ilan yakalandı.")

            if self.limit:
                items = items[:self.limit]

            for i, it in enumerate(items, 1):
                ad_id = str(it.get("id"))
                try:
                    url = DETAIL_API.format(id=ad_id)
                    resp = ctx.request.get(url, headers=API_HEADERS)
                    
                    if not resp.ok:
                        # Tarayıcı içinden fetch yedeği
                        res = page.evaluate("""async (u) => {
                            const r = await fetch(u, {
                                credentials: 'include',
                                headers: {'accept': 'text/plain', 'x-request-origin': 'IGT-UI', 'x-requested-with': 'XMLHttpRequest'}
                            });
                            return {status: r.status, text: await r.text()};
                        }""", url)
                        j = json.loads(res["text"])
                    else:
                        j = resp.json()

                    result = j.get("result", j) if isinstance(j, dict) else j
                    
                    raw_html = result.get("content", "")
                    metin = html_to_text(raw_html)
                    baslik = result.get("title") or it.get("title") or "İlan"
                    kurum = result.get("advertiserName") or "Belirtilmemiş"
                    sehir = result.get("addressCityName") or "Türkiye"
                    yayin = result.get("publishDate") or ""
                    
                    son_basvuru = extract_son_basvuru(metin)
                    
                    u = result.get("url") or {}
                    link = f"{BASE}/ilan/{ad_id}" + (f"/{u['title']}" if isinstance(u, dict) and u.get("title") else "")

                    # PDF / Ek dosya linklerini metinden ve JSON'dan ara
                    ek_dosyalar = []
                    # HTML içindeki pdf linklerini bul
                    pdf_linkleri = re.findall(r'href=[\'"]([^\'"]+\.pdf)[\'"]', raw_html, re.I)
                    for pdf_url in set(pdf_linkleri):
                        if not pdf_url.startswith("http"):
                            pdf_url = BASE + pdf_url
                        dosya_adi = pdf_url.split("/")[-1].split("?")[0]
                        ek_dosyalar.append({"dosya_adi": dosya_adi, "url": pdf_url})

                    ilan_obj = Ilan(
                        kaynak_site=self.kaynak_site,
                        ilan_id=ad_id,
                        baslik=baslik,
                        kurum=kurum,
                        il=sehir,
                        ilan_tarihi=str(yayin)[:10],
                        son_basvuru_tarihi=son_basvuru,
                        link=link,
                        ek_dosyalar=ek_dosyalar,
                        detay_metni=metin
                    )
                    toplanan_ilanlar.append(ilan_obj)
                    print(f"[{i}/{len(items)}] Çekildi: {baslik[:50]}...")
                except Exception as e:
                    print(f"[HATA] İlan {ad_id} çekilemedi: {e}")
                
                time.sleep(1)

            browser.close()

        return toplanan_ilanlar

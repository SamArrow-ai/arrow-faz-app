"""
Scraper de prix composants PC — Arrow-Faz
Source : LDLC.com (données publiques, délai de 2.5s entre requêtes)
"""
import json
import re
import sys
import time
from pathlib import Path
import requests
from bs4 import BeautifulSoup

LDLC_SEARCH = "https://www.ldlc.com/recherche/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

COMPONENTS = {
    # CPUs
    "ryzen5-5600":   "AMD Ryzen 5 5600",
    "ryzen5-7600":   "AMD Ryzen 5 7600",
    "ryzen7-5800x":  "AMD Ryzen 7 5800X",
    "ryzen7-7700":   "AMD Ryzen 7 7700",
    "ryzen9-7900x":  "AMD Ryzen 9 7900X",
    "i5-12400f":     "Intel Core i5-12400F",
    "i5-13600k":     "Intel Core i5-13600K",
    "i7-13700k":     "Intel Core i7-13700K",
    "i9-13900k":     "Intel Core i9-13900K",
    "i5-14600k":     "Intel Core i5-14600K",
    # Cartes mères
    "b550-tomahawk": "MSI MAG B550 Tomahawk",
    "b650-tomahawk": "MSI MAG B650 Tomahawk WiFi",
    "x670e-strix":   "ASUS ROG Strix X670E-E Gaming",
    "b660m-mortar":  "MSI MAG B660M Mortar",
    "z790-tomahawk": "MSI MAG Z790 Tomahawk WiFi",
    "b760m-mortar":  "MSI MAG B760M Mortar WiFi",
    # RAM
    "corsair-vengeance-32-3200": "Corsair Vengeance LPX 32Go DDR4 3200MHz",
    "gskill-ripjaws-16-3600":    "G.Skill Ripjaws V 16Go DDR4 3600MHz",
    "corsair-vengeance-32-6000": "Corsair Vengeance 32Go DDR5 6000MHz",
    "gskill-trident-32-6400":    "G.Skill Trident Z5 32Go DDR5 6400MHz",
    "kingston-fury-16-5600":     "Kingston Fury Beast 16Go DDR5 5600MHz",
    # GPU
    "rtx3060":   "NVIDIA GeForce RTX 3060 12Go",
    "rtx4060":   "NVIDIA GeForce RTX 4060 8Go",
    "rtx4070":   "NVIDIA GeForce RTX 4070 12Go",
    "rtx4070ti": "NVIDIA GeForce RTX 4070 Ti Super 16Go",
    "rtx4080":   "NVIDIA GeForce RTX 4080 Super 16Go",
    "rtx4090":   "NVIDIA GeForce RTX 4090 24Go",
    "rtx5060ti": "NVIDIA GeForce RTX 5060 Ti",
    "rtx5070":   "NVIDIA GeForce RTX 5070",
    "rtx5080":   "NVIDIA GeForce RTX 5080",
    "rx7600":    "AMD Radeon RX 7600 8Go",
    "rx7800xt":  "AMD Radeon RX 7800 XT 16Go",
    "rx7900xt":  "AMD Radeon RX 7900 XT 20Go",
    # Alimentations
    "corsair-rm550x":      "Corsair RM550x",
    "corsair-rm650x":      "Corsair RM650x",
    "corsair-rm750x":      "Corsair RM750x",
    "corsair-rm850x":      "Corsair RM850x",
    "seasonic-focus-1000": "Seasonic Focus GX-1000",
    "beQuiet-pure11-600":  "be quiet Pure Power 11 FM 600W",
    # Stockage
    "wd-sn770-1tb":       "WD Black SN770 1To NVMe",
    "samsung-990pro-2tb": "Samsung 990 Pro 2To NVMe",
    "crucial-p3-500gb":   "Crucial P3 Plus 500Go NVMe",
    "seagate-barracuda-2tb": "Seagate BarraCuda 2To",
    "samsung-870evo-1tb": "Samsung 870 EVO 1To SSD",
    # Boîtiers
    "nzxt-h5-flow":    "NZXT H5 Flow",
    "lianli-o11-mini": "Lian Li O11 Dynamic Mini",
    "beQuiet-pure500": "be quiet Pure Base 500",
    "fractal-north":   "Fractal Design North",
}


def extract_price(text: str) -> float | None:
    text = text.replace("\xa0", " ").replace("\u202f", " ").strip()
    # Formats: "299,99" / "1 299,99" / "1299.99"
    m = re.search(r"(\d{1,4}(?:\s\d{3})?)[,.](\d{2})", text)
    if m:
        try:
            return float(m.group(0).replace(",", ".").replace(" ", ""))
        except ValueError:
            pass
    return None


def get_price(query: str, session: requests.Session) -> float | None:
    try:
        url = LDLC_SEARCH + requests.utils.quote(query) + "/"
        r = session.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}", file=sys.stderr)
            return None
        soup = BeautifulSoup(r.text, "lxml")

        # Essai 1 : microdata itemprop="price"
        el = soup.find(attrs={"itemprop": "price"})
        if el:
            content = el.get("content") or el.get_text()
            try:
                return float(content)
            except ValueError:
                p = extract_price(content)
                if p:
                    return p

        # Essai 2 : sélecteurs CSS connus de LDLC
        for selector in [
            "ul.listing-product .price .price",
            "ul.listing-product .price",
            ".listing-product .price",
            ".price .price",
            ".price",
        ]:
            els = soup.select(selector)
            for el in els:
                p = extract_price(el.get_text())
                if p and p > 5:
                    return p

    except Exception as e:
        print(f"  Exception: {e}", file=sys.stderr)
    return None


def main():
    prices_file = Path(__file__).parent.parent / "prix-live.json"

    with open(prices_file, "r", encoding="utf-8") as f:
        prices = json.load(f)

    session = requests.Session()
    updated, failed = 0, []

    for comp_id, query in COMPONENTS.items():
        print(f"→ {comp_id}...", end=" ", flush=True)
        price = get_price(query, session)
        if price and price > 5:
            old = prices.get(comp_id, "?")
            prices[comp_id] = round(price, 2)
            print(f"✓ {old}€ → {price}€")
            updated += 1
        else:
            print(f"✗ garde {prices.get(comp_id, '?')}€")
            failed.append(comp_id)
        time.sleep(2.5)

    with open(prices_file, "w", encoding="utf-8") as f:
        json.dump(prices, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*50}")
    print(f"✓ {updated}/{len(COMPONENTS)} prix mis à jour")
    if failed:
        print(f"✗ Non trouvés ({len(failed)}): {', '.join(failed)}")
    sys.exit(0)


if __name__ == "__main__":
    main()

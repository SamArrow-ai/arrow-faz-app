"""
Scraper de prix composants PC — Arrow-Faz
Source configurée via la variable d'environnement SCRAPER_BASE_URL
(stockée en secret GitHub pour ne pas exposer le revendeur)
"""
import json
import os
import re
import sys
import time
from pathlib import Path
import requests
from bs4 import BeautifulSoup

BASE_URL = os.environ.get("SCRAPER_BASE_URL", "").rstrip("/")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
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
    "wd-sn770-1tb":          "WD Black SN770 1To NVMe",
    "samsung-990pro-2tb":    "Samsung 990 Pro 2To NVMe",
    "crucial-p3-500gb":      "Crucial P3 Plus 500Go NVMe",
    "seagate-barracuda-2tb": "Seagate BarraCuda 2To",
    "samsung-870evo-1tb":    "Samsung 870 EVO 1To SSD",
    # Boîtiers
    "nzxt-h5-flow":    "NZXT H5 Flow",
    "lianli-o11-mini": "Lian Li O11 Dynamic Mini",
    "beQuiet-pure500": "be quiet Pure Base 500",
    "fractal-north":   "Fractal Design North",
}


def extract_price(text: str) -> float | None:
    text = text.replace("\xa0", " ").replace(" ", " ").strip()
    m = re.search(r"(\d{1,4}(?:[\s]\d{3})?)[,.](\d{2})", text)
    if m:
        try:
            return float(m.group(0).replace(",", ".").replace(" ", ""))
        except ValueError:
            pass
    return None


def get_price(query: str, session: requests.Session) -> float | None:
    if not BASE_URL:
        return None
    try:
        url = BASE_URL + "/" + requests.utils.quote(query) + "/"
        r = session.get(url, headers=HEADERS, timeout=20)
        print(f"  [HTTP {r.status_code}]", end=" ", flush=True)
        if r.status_code != 200:
            print(f"  erreur HTTP {r.status_code}")
            return None

        soup = BeautifulSoup(r.text, "lxml")

        # 1. JSON-LD schema.org (le plus fiable)
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if not isinstance(data, dict):
                    continue
                offers = data.get("offers", {})
                if isinstance(offers, dict):
                    p = offers.get("price") or offers.get("lowPrice")
                    if p:
                        return float(str(p).replace(",", "."))
                elif isinstance(offers, list) and offers:
                    p = offers[0].get("price")
                    if p:
                        return float(str(p).replace(",", "."))
            except Exception:
                pass

        # 2. itemprop="price" (microdata)
        el = soup.find(attrs={"itemprop": "price"})
        if el:
            content = el.get("content") or el.get_text()
            try:
                return float(str(content).replace(",", "."))
            except ValueError:
                p = extract_price(str(content))
                if p:
                    return p

        # 3. data-price attribute
        for el in soup.find_all(attrs={"data-price": True}):
            try:
                val = float(str(el["data-price"]).replace(",", "."))
                if val > 5:
                    return val
            except (ValueError, TypeError):
                pass

        # 4. Sélecteurs CSS (du plus précis au plus large)
        for selector in [
            ".price-ht",
            ".product-price",
            "ul.listing-product .price .price",
            "ul.listing-product .price",
            ".listing-product .price",
            ".price .price",
            ".priceFinal",
            ".price",
            "[class*='price']",
        ]:
            els = soup.select(selector)
            for el in els:
                p = extract_price(el.get_text())
                if p and p > 5:
                    return p

        # 5. Regex brute sur le texte visible (dernier recours)
        visible = soup.get_text(" ", strip=True)
        matches = re.findall(r"(\d{2,4}[,.]?\d{0,2})\s*€", visible)
        for m in matches:
            try:
                val = float(m.replace(",", "."))
                if 10 < val < 5000:
                    return val
            except ValueError:
                pass

        # Debug : montre un extrait HTML brut si rien trouvé
        print(f"\n  DEBUG HTML brut: {r.text[:500]}")

    except Exception as e:
        print(f"  Exception: {e}")
    return None


def main():
    if not BASE_URL:
        print("✗ SCRAPER_BASE_URL non défini, abandon")
        sys.exit(1)

    prices_file = Path(__file__).parent.parent / "prix-live.json"

    with open(prices_file, "r", encoding="utf-8") as f:
        prices = json.load(f)

    session = requests.Session()
    # Chargement de la page d'accueil pour initialiser les cookies
    try:
        home = BASE_URL.split("/recherche")[0]
        session.get(home, headers=HEADERS, timeout=10)
        time.sleep(2)
    except Exception:
        pass

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
        time.sleep(3)

    with open(prices_file, "w", encoding="utf-8") as f:
        json.dump(prices, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*50}")
    print(f"✓ {updated}/{len(COMPONENTS)} prix mis à jour")
    if failed:
        print(f"✗ Non trouvés ({len(failed)}): {', '.join(failed)}")
    sys.exit(0)


if __name__ == "__main__":
    main()

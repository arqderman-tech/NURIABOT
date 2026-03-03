import requests, re, os, time, random
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

MASTER_CSV = "nuria_precios.csv"
API_DOLAR_URL = "https://api.comparadolar.ar/usd"

CATEGORIAS_A_RASTREAR = [
    {"nombre": "Tortas y Postres",       "url": "https://www.nuria.com.ar/categoria-producto/tortas-y-postres/"},
    {"nombre": "Pasteleria y Panaderia", "url": "https://www.nuria.com.ar/categoria-producto/pasteleria-y-panaderia/"},
    {"nombre": "Salados",                "url": "https://www.nuria.com.ar/categoria-producto/salados/"}
]

PRODUCTOS_A_EXCLUIR = ["PANES", "SANDWICHES DE MIGA"]

PRODUCTOS_A_RECLASIFICAR = {
    "GANACHE DE CHOCOLATE": "Tortas Individuales",
    "LEMON PIE":            "Tortas Individuales",
    "MIL HOJAS":            "Tortas Individuales",
    "POSTRE NURIA":         "Tortas Individuales",
    "TARTA DE FRUTAS DE ESTACION": "Tortas Individuales",
    "TARTA TOFFI":          "Tortas Individuales"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9",
}

def obtener_dolar():
    try:
        r = requests.get(API_DOLAR_URL, headers=HEADERS, timeout=10)
        bn = next((x for x in r.json() if x.get("slug") == "banco-nacion"), None)
        return float(bn["ask"]) if bn else 1.0
    except Exception:
        return 1.0

def scrape_pagina(url):
    """Extrae productos de una URL (una página)."""
    time.sleep(random.uniform(1, 2))
    r = requests.get(url, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(r.content, "html.parser")
    items = soup.find_all("li", class_="product")
    # Detectar si hay pagina siguiente
    next_page = None
    nav = soup.select_one("a.next.page-numbers")
    if nav:
        next_page = nav["href"]
    return items, next_page

def obtener_precios(url_base, categoria_default):
    productos = []
    url_actual = url_base
    pagina = 1
    while url_actual:
        try:
            print("    Pagina " + str(pagina) + ": " + url_actual)
            items, next_page = scrape_pagina(url_actual)
            print("    Items encontrados: " + str(len(items)))
            for item in items:
                titulo_tag = item.find("h4", class_="card-title")
                if not titulo_tag or not titulo_tag.a:
                    continue
                nombre = titulo_tag.a.get_text(strip=True)
                if nombre.upper() in [p.upper() for p in PRODUCTOS_A_EXCLUIR]:
                    continue
                cat = PRODUCTOS_A_RECLASIFICAR.get(nombre.upper(), categoria_default)
                precio_tag = item.find("span", class_="woocommerce-Price-amount")
                if not precio_tag:
                    continue
                txt = re.sub(r"[^\d,\.]", "", precio_tag.get_text(strip=True))
                try:
                    precio = float(txt.replace(".", "").replace(",", ".")) if "," in txt else float(txt.replace(",", ""))
                except Exception:
                    continue
                if precio > 0:
                    productos.append({"nombre": nombre, "categoria": cat, "precio_ars": precio})
            url_actual = next_page
            pagina += 1
        except Exception as e:
            print("    Error pagina " + str(pagina) + ": " + str(e))
            break
    return productos

def main():
    print("NURIABOT iniciando...")
    dolar = obtener_dolar()
    print("Dolar BN: " + str(dolar))
    hoy = datetime.now().strftime("%Y-%m-%d")
    nuevos = []
    for cat in CATEGORIAS_A_RASTREAR:
        prods = obtener_precios(cat["url"], cat["nombre"])
        print("  " + cat["nombre"] + ": " + str(len(prods)) + " productos")
        for p in prods:
            nuevos.append({
                "Fecha": hoy,
                "Categoria": p["categoria"],
                "Producto": p["nombre"],
                "Precio_ARS": p["precio_ars"],
                "Precio_USD": round(p["precio_ars"] / dolar, 2),
                "Dolar_ARS": dolar
            })
    if not nuevos:
        print("Sin productos.")
        return
    df = pd.DataFrame(nuevos)
    if os.path.exists(MASTER_CSV):
        dh = pd.read_csv(MASTER_CSV)
        dh["Fecha"] = pd.to_datetime(dh["Fecha"]).dt.strftime("%Y-%m-%d")
        dh = dh[dh["Fecha"] != hoy]
        df = pd.concat([dh, df], ignore_index=True)
    df.to_csv(MASTER_CSV, index=False)
    print("OK: " + str(len(nuevos)) + " productos guardados para " + hoy)

if __name__ == "__main__":
    main()

"""
nuria.py - NURIABOT
Scraper para Nuria pasteleria (Rosario).
Extrae precios de 3 categorias y guarda en CSV.
"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import os

CATEGORIAS_A_RASTREAR = [
    {'nombre': 'Tortas y Postres', 'url': 'https://www.nuria.com.ar/categoria-producto/tortas-y-postres/'},
    {'nombre': 'Pasteleria y Panaderia', 'url': 'https://www.nuria.com.ar/categoria-producto/pasteleria-y-panaderia/'},
    {'nombre': 'Salados', 'url': 'https://www.nuria.com.ar/categoria-producto/salados/'}
]

PRODUCTOS_A_EXCLUIR = ["PANES", "SANDWICHES DE MIGA", "SÁNDWICHES DE MIGA"]

PRODUCTOS_A_RECLASIFICAR = {
    "GANACHE DE CHOCOLATE": "Tortas Individuales",
    "LEMON PIE": "Tortas Individuales",
    "MIL HOJAS": "Tortas Individuales",
    "POSTRE NURIA": "Tortas Individuales",
    "TARTA DE FRUTAS DE ESTACION": "Tortas Individuales",
    "TARTA TOFFI": "Tortas Individuales"
}

API_DOLAR_URL = "https://api.comparadolar.ar/usd"
MASTER_CSV = "nuria_precios.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def obtener_dolar():
    try:
        r = requests.get(API_DOLAR_URL, headers=HEADERS, timeout=10)
        data = r.json()
        bn = next((x for x in data if x.get('slug') == 'banco-nacion'), None)
        return float(bn['ask']) if bn else 1.0
    except:
        return 1.0

def es_excluido(nombre):
    nombre_limpio = re.sub(r'\[.*?\]\s*', '', nombre).strip().upper()
    return nombre_limpio in [p.upper() for p in PRODUCTOS_A_EXCLUIR]

def extraer_categoria(nombre):
    m = re.match(r'\[(.*?)\]', nombre)
    return m.group(1).strip() if m else ""

def limpiar_nombre(nombre):
    return re.sub(r'\[.*?\]\s*', '', nombre).strip()

def obtener_precios(url, categoria_default):
    productos = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        items = soup.select('li.product')
        for item in items:
            nombre_tag = item.select_one('.woocommerce-loop-product__title')
            precio_tag = item.select_one('.price .woocommerce-Price-amount bdi')
            if not nombre_tag or not precio_tag:
                continue
            nombre_raw = nombre_tag.get_text(strip=True)
            if es_excluido(nombre_raw):
                continue
            cat = extraer_categoria(nombre_raw) or categoria_default
            nombre = limpiar_nombre(nombre_raw)
            # Reclasificar si aplica
            cat = PRODUCTOS_A_RECLASIFICAR.get(nombre.upper(), cat)
            precio_str = precio_tag.get_text(strip=True).replace('$','').replace('.','').replace(',','.').strip()
            try:
                precio = float(precio_str)
            except:
                continue
            if precio > 0:
                productos.append({'nombre': nombre, 'categoria': cat, 'precio_ars': precio})
    except Exception as e:
        print(f"Error {url}: {e}")
    return productos

def main():
    print("NURIABOT iniciando...")
    dolar = obtener_dolar()
    print(f"Dolar BN: ${dolar:,.2f}")
    hoy = datetime.now().strftime("%Y-%m-%d")
    nuevos = []
    for cat in CATEGORIAS_A_RASTREAR:
        prods = obtener_precios(cat['url'], cat['nombre'])
        print(f"  {cat['nombre']}: {len(prods)} productos")
        for p in prods:
            nuevos.append({
                'Fecha': hoy,
                'Categoria': p['categoria'],
                'Producto': p['nombre'],
                'Precio_ARS': p['precio_ars'],
                'Precio_USD': round(p['precio_ars'] / dolar, 2),
                'Dolar_ARS': dolar
            })
    if not nuevos:
        print("Sin datos.")
        return
    df_nuevo = pd.DataFrame(nuevos)
    if os.path.exists(MASTER_CSV):
        df_hist = pd.read_csv(MASTER_CSV)
        df_hist['Fecha'] = pd.to_datetime(df_hist['Fecha']).dt.strftime('%Y-%m-%d')
        df_hist = df_hist[df_hist['Fecha'] != hoy]
        df_final = pd.concat([df_hist, df_nuevo], ignore_index=True)
    else:
        df_final = df_nuevo
    df_final.to_csv(MASTER_CSV, index=False)
    print(f"OK: {len(df_nuevo)} registros guardados para {hoy}")

if __name__ == "__main__":
    main()

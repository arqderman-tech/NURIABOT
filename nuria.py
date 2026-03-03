import requests
from bs4 import BeautifulSoup
import os
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
import json
import re 
import sys

# ==============================================================================
# ----------------------------
# CONFIGURACIÓN (editar si hace falta)
# ----------------------------
# Credenciales y destino del email
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_USER = 'wifienrosario@gmail.com' 
# IMPORTANTE: DEBE ser una Contraseña de Aplicación (App Password) de Google
EMAIL_PASSWORD = 'zrmr mgws hjtz brsk' 
EMAIL_RECIPIENT = 'arqderman@gmail.com'

# Configuración de archivos
MASTER_CSV = "nuria_precios.csv"
REPORT_XLSX = "nuria_reporte.xlsx"
CHART_DIR = "charts_nuria"

# URLs de las categorías a rastrear
CATEGORIAS_A_RASTREAR = [
    {'nombre': 'Tortas y Postres', 'url': 'https://www.nuria.com.ar/categoria-producto/tortas-y-postres/'},
    {'nombre': 'Pastelería y Panadería', 'url': 'https://www.nuria.com.ar/categoria-producto/pasteleria-y-panaderia/'},
    {'nombre': 'Salados', 'url': 'https://www.nuria.com.ar/categoria-producto/salados/'}
]

# PRODUCTOS A EXCLUIR (se excluyen del rastreo y del reporte/historial)
PRODUCTOS_A_EXCLUIR = [
    "PANES", 
    "SÁNDWICHES DE MIGA" 
] 

# PRODUCTOS QUE DEBEN SER RECLASIFICADOS COMO "Tortas Individuales"
# Clave: Nombre exacto del producto (MAYÚSCULAS) / Valor: Nombre de la nueva categoría
PRODUCTOS_A_RECLASIFICAR = {
    "GANACHE DE CHOCOLATE": "Tortas Individuales",
    "LEMON PIE": "Tortas Individuales",
    "MIL HOJAS": "Tortas Individuales",
    "POSTRE NURIA": "Tortas Individuales",
    "TARTA DE FRUTAS DE ESTACION": "Tortas Individuales",
    "TARTA TOFFI": "Tortas Individuales"
}

# API del Dólar
API_DOLAR_URL = "https://api.comparadolar.ar/usd"

# Crear directorio para gráficos
os.makedirs(CHART_DIR, exist_ok=True)
# ==============================================================================

# --- Función Auxiliar ---
def es_producto_excluido(nombre_completo):
    """Verifica si el nombre de un producto está en la lista de exclusión, ignorando categorías."""
    # Extrae solo el nombre del producto (sin la categoría entre corchetes)
    nombre_limpio = re.sub(r'\[.*?\]\s*', '', nombre_completo).strip()
    return nombre_limpio.upper() in [p.upper() for p in PRODUCTOS_A_EXCLUIR]

# --- Funciones de Lógica de Extracción de Precios (Nuria y Dólar) ---

def obtener_precio_dolar_api(url_api):
    """
    Obtiene la cotización del dólar de la API.
    """
    print("🔎 Intentando obtener cotización del dólar de la API...")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url_api, headers=headers, timeout=10)
        response.raise_for_status() 
        data = response.json() 
        cotizacion_nacion = next((item for item in data if item.get('slug') == 'banco-nacion'), None)
        
        if cotizacion_nacion and 'ask' in cotizacion_nacion:
            precio_dolar = float(cotizacion_nacion['ask'])
            print(f"✅ Precio del Dólar Oficial (Banco Nación, Venta - ask) extraído: ${precio_dolar:,.2f} ARS")
            return precio_dolar
        else:
            print("❌ No se pudo encontrar la cotización 'banco-nacion' o el campo 'ask'. Usando 1.0.")
            return 1.0

    except Exception as e:
        print(f"❌ Error al obtener el precio del dólar: {e}. Usando 1.0.")
        return 1.0

def obtener_precios_nuria(url_categoria, nombre_categoria):
    """
    Realiza scraping de una URL de categoría de Nuria para extraer nombres y precios. 
    SE ELIMINÓ LA EXTRACCIÓN DE PRESENTACIÓN/DESCRIPCIÓN.
    """
    print(f"\n🔎 Buscando productos en la categoría: {nombre_categoria} ({url_categoria})...")
    productos_encontrados = []
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url_categoria, headers=headers, timeout=15)
        response.raise_for_status() 
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        productos = soup.find_all('li', class_='product') 
        
        if not productos:
             productos = soup.select('.products .product')
             
        if not productos:
             print(f"⚠️ No se encontraron contenedores de productos con clase 'product' en {nombre_categoria}.")
             return []

        for producto in productos:
            try:
                # 1. Extraer Nombre
                titulo_tag = producto.find('h4', class_='card-title') 
                nombre_producto = 'Nombre Desconocido'
                if titulo_tag and titulo_tag.a:
                    nombre_producto = titulo_tag.a.text.strip()
                
                # --- LÓGICA DE FILTRADO (Exclusión del Rastreo) ---
                if es_producto_excluido(nombre_producto):
                    continue
                # -----------------------------------
                
                # 2. DETERMINAR CATEGORÍA FINAL (Sobreescribir si es Torta Individual)
                categoria_final = nombre_categoria
                if nombre_producto.upper() in PRODUCTOS_A_RECLASIFICAR:
                    categoria_final = PRODUCTOS_A_RECLASIFICAR[nombre_producto.upper()]
                
                # 3. Extraer Precio
                precio_tag = producto.find('span', class_='woocommerce-Price-amount amount')
                precio_ars = None
                
                if precio_tag:
                    price_text_full = precio_tag.get_text(strip=True) 
                    price_str = re.sub(r'[^\d\.,]', '', price_text_full) 
                    
                    final_price_str = price_str.replace(',', '') 
                    
                    try:
                        precio_ars = float(final_price_str)
                    except ValueError:
                         final_price_str_european = price_str.replace('.', '').replace(',', '.') 
                         try:
                             precio_ars = float(final_price_str_european)
                         except ValueError:
                             precio_ars = None

                
                if precio_ars is not None and precio_ars > 0:
                    productos_encontrados.append({
                        # Se registra el nombre con la categoría en el corchete
                        'nombre': f"[{categoria_final}] {nombre_producto}", 
                        'precio_ars': precio_ars,
                    })

            except Exception as product_e:
                print(f"   ❌ Error al procesar un producto en {nombre_categoria}: {product_e}. Continuando con el siguiente.")
                continue


        print(f"   ✅ Extracción completa: {len(productos_encontrados)} productos con precio válido encontrados en {nombre_categoria}.")
        return productos_encontrados

    except requests.exceptions.RequestException as e:
        print(f"❌ Error de conexión al obtener la categoría {nombre_categoria}: {e}")
        return []
    except Exception as e:
        print(f"❌ Error inesperado en el scraping de {nombre_categoria}: {e}")
        return []


# --- Funciones de Data Management (CSV Maestro) ---

def cargar_o_crear_maestro():
    """Carga el DataFrame maestro desde CSV o crea uno nuevo. SE ELIMINA LA COLUMNA 'Presentacion'."""
    columnas = ['Fecha', 'Producto', 'Precio_ARS', 'Precio_USD', 'Dolar_ARS'] 
    if os.path.exists(MASTER_CSV):
        try:
            df = pd.read_csv(MASTER_CSV)
            df['Fecha'] = pd.to_datetime(df['Fecha']).dt.normalize()
            
            # Limpiar columnas viejas que puedan tener 'Presentacion'
            if 'Presentacion' in df.columns:
                df = df.drop(columns=['Presentacion'])
            
            return df[columnas] if all(col in df.columns for col in columnas) else pd.DataFrame(columns=columnas)

        except Exception as e:
            print(f"⚠️ Error al leer el CSV: {e}. Creando un DataFrame vacío.")
            return pd.DataFrame(columns=columnas)
    else:
        print("📁 Archivo maestro no encontrado. Creando uno nuevo.")
        return pd.DataFrame(columns=columnas)


def guardar_datos(df, nombre, precio_ars, dolar_ars):
    """Añade los datos de hoy al maestro si no existe una entrada para la fecha y el producto. SE ELIMINÓ 'presentacion'."""
    now = datetime.now() 
    hoy = now.date()
    
    df_temp = df.copy()
    if not df_temp.empty:
        df_temp['Fecha_Dia'] = df_temp['Fecha'].dt.date
    else:
        df_temp['Fecha_Dia'] = pd.Series([], dtype='object')
        
    ya_existe = ((df_temp['Fecha_Dia'] == hoy) & (df_temp['Producto'] == nombre)).any()

    if not ya_existe:
        precio_usd = precio_ars / dolar_ars
        
        fecha_almacenamiento = now.replace(hour=0, minute=0, second=0, microsecond=0) 
        
        nueva_fila = pd.DataFrame([{
            'Fecha': fecha_almacenamiento,
            'Producto': nombre,
            # 'Presentacion' ELIMINADO
            'Precio_ARS': precio_ars,
            'Precio_USD': precio_usd,
            'Dolar_ARS': dolar_ars
        }])
        
        df_final = pd.concat([df, nueva_fila], ignore_index=True)
        
        df_final = df_final.sort_values(by=['Fecha', 'Producto']).reset_index(drop=True)
        
        df_final.to_csv(MASTER_CSV, index=False)
        return df_final
    else:
        return df

# --- Funciones de Reporte y Análisis (Excel y Gráficos) ---

def calcular_variacion_historica(df):
    """Calcula la variación porcentual de cada producto respecto a: Ayer, 30 días atrás, 1 año atrás."""
    
    now = datetime.now().date()
    df_historico = df.copy()
    df_historico['Fecha'] = df_historico['Fecha'].dt.date
    
    productos = df_historico['Producto'].unique()
    
    resultados_lista = []
    
    for producto in productos:
        df_prod = df_historico[df_historico['Producto'] == producto].sort_values(by='Fecha')
        
        # Último precio disponible
        if df_prod.empty:
            continue
            
        precio_actual = df_prod.iloc[-1]['Precio_ARS']
        nombre_limpio = re.sub(r'\[.*?\]\s*', '', producto).strip()
        
        # Buscar precios de referencia
        
        # 1. Precio de Ayer (o el día hábil anterior si no hay dato)
        yesterday = now - pd.Timedelta(days=1)
        precio_ayer = df_prod[df_prod['Fecha'] < now].tail(1)['Precio_ARS'].iloc[0] if not df_prod[df_prod['Fecha'] < now].empty else None
        
        # 2. Precio de Hace 30 días (aproximado)
        hace_30_dias = now - pd.Timedelta(days=30)
        # Buscar la fecha más cercana anterior o igual a 30 días atrás
        precio_mes = df_prod[df_prod['Fecha'] <= hace_30_dias].tail(1)['Precio_ARS'].iloc[0] if not df_prod[df_prod['Fecha'] <= hace_30_dias].empty else None
        
        # 3. Precio de Hace 1 año (aproximado)
        hace_1_año = now - pd.Timedelta(days=365)
        precio_año = df_prod[df_prod['Fecha'] <= hace_1_año].tail(1)['Precio_ARS'].iloc[0] if not df_prod[df_prod['Fecha'] <= hace_1_año].empty else None

        
        # Calcular variaciones y formatear
        def calcular_pct_change(precio_actual, precio_ref):
            if precio_ref is not None and precio_ref > 0:
                return ((precio_actual - precio_ref) / precio_ref) * 100
            return None

        var_dia = calcular_pct_change(precio_actual, precio_ayer)
        var_mes = calcular_pct_change(precio_actual, precio_mes)
        var_año = calcular_pct_change(precio_actual, precio_año)

        # Formateo (Se mantiene en %)
        var_dia_str = f"{var_dia:.2f}%" if var_dia is not None else "-"
        var_mes_str = f"{var_mes:.2f}%" if var_mes is not None else "-"
        var_año_str = f"{var_año:.2f}%" if var_año is not None else "-"
        
        # Obtener la categoría para el reporte final (esencial para la sub-división)
        categoria_producto = re.search(r'\[(.*?)\]', producto).group(1) if re.search(r'\[(.*?)\]', producto) else 'Otros'

        resultados_lista.append({
            'Producto': nombre_limpio,
            'Categoria': categoria_producto,
            'Precio Actual (ARS)': f"${precio_actual:,.2f}",
            'Variacion vs Ayer': var_dia_str,
            'Variacion vs 30 Días': var_mes_str,
            'Variacion vs 1 Año': var_año_str,
            'Variacion_Dia_Val': var_dia # Para el Top 3 (valor numérico)
        })
        
    df_final = pd.DataFrame(resultados_lista)
    return df_final


def generar_reporte_y_graficos(df):
    """Genera el archivo Excel y los gráficos agrupados por categoría. Aplica filtro de exclusión. SE ELIMINÓ 'Presentacion'."""
    
    if df.shape[0] < 1:
        print("⚠️ No hay suficientes datos para generar el reporte.")
        return None, "No hay datos."
    
    # --- FILTRADO ADICIONAL PARA REPORTES Y GRÁFICOS (Excluye historial de productos NO deseados) ---
    df_filtrado = df[~df['Producto'].apply(es_producto_excluido)].copy()
    
    if df_filtrado.empty:
        print("⚠️ Después de filtrar, el DataFrame está vacío. No se puede generar el reporte.")
        return None, "No hay datos después del filtrado."

    print(f"🧹 Reporte generado para {df_filtrado.shape[0]} filas (productos excluidos filtrados).")
    df = df_filtrado
    # ------------------------------------------------------------------------

    df = df.sort_values(by=['Fecha', 'Producto']).reset_index(drop=True)
    
    # 1. Preparación del DataFrame (Cálculo de variación y Extracción de Categoría)
    
    df['Categoria'] = df['Producto'].apply(lambda x: re.search(r'\[(.*?)\]', x).group(1) if re.search(r'\[(.*?)\]', x) else 'Otros')
    
    productos = df['Producto'].unique()
    categorias = df['Categoria'].unique()
    
    df_list = []
    tiene_variacion = False
    
    for producto in productos:
        df_prod = df[df['Producto'] == producto].copy()
        
        if df_prod.shape[0] >= 2:
            df_prod['Variacion_ARS'] = df_prod['Precio_ARS'].pct_change() * 100
            df_prod['Variacion_USD'] = df_prod['Precio_USD'].pct_change() * 100
            tiene_variacion = True
        else:
            df_prod['Variacion_ARS'] = None
            df_prod['Variacion_USD'] = None
            
        df_list.append(df_prod)
        
    df_con_variacion = pd.concat(df_list, ignore_index=True)
    df_con_variacion = df_con_variacion.sort_values(by=['Fecha', 'Producto']).reset_index(drop=True)
    
    if 'Categoria' not in df_con_variacion.columns:
         df_con_variacion['Categoria'] = df_con_variacion['Producto'].apply(lambda x: re.search(r'\[(.*?)\]', x).group(1) if re.search(r'\[(.*?)\]', x) else 'Otros')
    
    # 2. Generación del Archivo Excel 
    writer = pd.ExcelWriter(REPORT_XLSX, engine='xlsxwriter')
    
    # Pestaña 1: Maestro (Sin Presentacion)
    df_maestro = df_con_variacion[['Fecha', 'Producto', 'Precio_ARS', 'Precio_USD', 'Dolar_ARS']].copy()
    df_maestro['Fecha'] = df_maestro['Fecha'].dt.strftime('%Y-%m-%d')
    df_maestro.to_excel(writer, sheet_name='1. Maestro ARS USD', index=False)
    
    # Pestañas de Precios Pivotados
    df_pivot_ars = df_con_variacion.pivot_table(index='Producto', columns='Fecha', values='Precio_ARS')
    df_pivot_usd = df_con_variacion.pivot_table(index='Producto', columns='Fecha', values='Precio_USD')
    
    df_ars = df_pivot_ars.copy()
    df_ars.columns = df_ars.columns.strftime('%Y-%m-%d')
    df_ars.reset_index(inplace=True)
    df_ars.insert(1, 'Moneda', 'ARS')
    df_ars.to_excel(writer, sheet_name='2. Precios ARS', index=False)
    
    df_usd = df_pivot_usd.copy()
    df_usd.columns = df_usd.columns.strftime('%Y-%m-%d')
    df_usd.reset_index(inplace=True)
    df_usd.insert(1, 'Moneda', 'USD')
    df_usd.to_excel(writer, sheet_name='3. Precios USD', index=False)

    # Pestañas de Variación (Si hay suficiente historial)
    if tiene_variacion:
        df_variacion_diaria = df_con_variacion[['Fecha', 'Producto', 'Variacion_ARS', 'Variacion_USD']].dropna(subset=['Variacion_ARS', 'Variacion_USD']).copy()
        df_variacion_diaria['Fecha'] = df_variacion_diaria['Fecha'].dt.strftime('%Y-%m-%d')
        df_variacion_diaria['Variacion_ARS'] = df_variacion_diaria['Variacion_ARS'].map('{:.2f}%'.format)
        df_variacion_diaria['Variacion_USD'] = df_variacion_diaria['Variacion_USD'].map('{:.2f}%'.format)
        df_variacion_diaria.to_excel(writer, sheet_name='4. Variacion Diaria', index=False)

        # Variación Mensual y Anual
        df_variaciones = pd.DataFrame(columns=['Periodo', 'Moneda', 'Producto', 'Variacion (%)'])

        for producto in productos:
            df_prod = df_con_variacion[df_con_variacion['Producto'] == producto]
            
            df_mensual_ars = df_prod.groupby(df_prod['Fecha'].dt.to_period('M'))['Precio_ARS'].last().pct_change().dropna() * 100
            df_mensual_usd = df_prod.groupby(df_prod['Fecha'].dt.to_period('M'))['Precio_USD'].last().pct_change().dropna() * 100
            
            if not df_mensual_ars.empty and df_mensual_ars.shape[0] > 0:
                df_variaciones.loc[len(df_variaciones)] = ['Mensual', 'ARS', producto, f"{df_mensual_ars.iloc[-1]:.2f}%"]
            if not df_mensual_usd.empty and df_mensual_usd.shape[0] > 0:
                df_variaciones.loc[len(df_variaciones)] = ['Mensual', 'USD', producto, f"{df_mensual_usd.iloc[-1]:.2f}%"]

            df_anual_ars = df_prod.groupby(df_prod['Fecha'].dt.to_period('Y'))['Precio_ARS'].last().pct_change().dropna() * 100
            df_anual_usd = df_prod.groupby(df_prod['Fecha'].dt.to_period('Y'))['Precio_USD'].last().pct_change().dropna() * 100

            if not df_anual_ars.empty and df_anual_ars.shape[0] > 0:
                df_variaciones.loc[len(df_variaciones)] = ['Anual', 'ARS', producto, f"{df_anual_ars.iloc[-1]:.2f}%"]
            if not df_anual_usd.empty and df_anual_usd.shape[0] > 0:
                df_variaciones.loc[len(df_variaciones)] = ['Anual', 'USD', producto, f"{df_anual_usd.iloc[-1]:.2f}%"]

        df_variaciones.to_excel(writer, sheet_name='5. Variacion Mensual Anual', index=False)
    else:
        pd.DataFrame().to_excel(writer, sheet_name='4. Variacion Diaria', index=False)
        pd.DataFrame().to_excel(writer, sheet_name='5. Variacion Mensual Anual', index=False)
        
    # Pestaña 6: Variación vs Histórico (Valores en %)
    df_variacion_historica = calcular_variacion_historica(df)
    
    # Filtramos la columna temporal 'Variacion_Dia_Val' y ordenamos para el Excel
    df_excel_variacion = df_variacion_historica.drop(columns=['Variacion_Dia_Val']).sort_values(by='Categoria').reset_index(drop=True)
    df_excel_variacion.to_excel(writer, sheet_name='6. Variacion vs Histórico', index=False)

    writer.close()
    print(f"📄 Archivo Excel de reporte guardado en {REPORT_XLSX}.")
    
    # 3. Generación de Gráficos AGRUPADOS POR CATEGORÍA (Sin cambios necesarios)
    
    sns.set_theme(style="whitegrid")
    imagenes_generadas = []
    
    print("📊 Generando gráficos agrupados por categoría...")

    for i, categoria in enumerate(categorias):
        df_cat = df_con_variacion[df_con_variacion['Categoria'] == categoria].copy()
        nombre_limpio_cat = categoria.replace(' ', '_').replace('/', '_').replace('-', '_').replace('[', '').replace(']', '').lower()
        
        productos_con_historia_cat = df_cat.groupby('Producto').filter(lambda x: len(x) >= 2)['Producto'].unique()
        df_cat_historia = df_cat[df_cat['Producto'].isin(productos_con_historia_cat)].copy()

        # A. Gráficos de Precios Históricos (Línea) - Usamos todos los datos (df_cat)
        if df_cat.shape[0] > 0:
            # Gráfico ARS
            plt.figure(figsize=(12, 7))
            sns.lineplot(x='Fecha', y='Precio_ARS', data=df_cat, hue='Producto', marker='o') 
            plt.title(f'Precios Históricos: {categoria} (ARS)')
            plt.xlabel('Fecha')
            plt.ylabel('Precio ARS')
            plt.xticks(rotation=45)
            plt.legend(title='Producto', bbox_to_anchor=(1.05, 1), loc='upper left') 
            plt.tight_layout()
            chart_file_ars = os.path.join(CHART_DIR, f"{i+1}_{nombre_limpio_cat}_precios_ars.png") 
            plt.savefig(chart_file_ars)
            plt.close()
            imagenes_generadas.append({'file': chart_file_ars, 'name': f"Precios Históricos: {categoria} (ARS)"})

            # Gráfico USD
            plt.figure(figsize=(12, 7))
            sns.lineplot(x='Fecha', y='Precio_USD', data=df_cat, hue='Producto', marker='o') 
            plt.title(f'Precios Históricos: {categoria} (USD)')
            plt.xlabel('Fecha')
            plt.ylabel('Precio USD')
            plt.xticks(rotation=45)
            plt.legend(title='Producto', bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.tight_layout()
            chart_file_usd = os.path.join(CHART_DIR, f"{i+1}_{nombre_limpio_cat}_precios_usd.png")
            plt.savefig(chart_file_usd)
            plt.close()
            imagenes_generadas.append({'file': chart_file_usd, 'name': f"Precios Históricos: {categoria} (USD)"})

        # B. Gráficos de Variación Diaria (Barras) - Solo si hay historial
        if not df_cat_historia.empty:
            # Gráfico Variación ARS
            df_variacion_ars = df_cat_historia[['Fecha', 'Producto', 'Variacion_ARS']].dropna()
            if not df_variacion_ars.empty:
                plt.figure(figsize=(12, 7))
                sns.barplot(x='Fecha', y='Variacion_ARS', hue='Producto', data=df_variacion_ars) 
                plt.title(f'Variación Diaria: {categoria} (ARS %)')
                plt.xlabel('Fecha')
                plt.ylabel('Variación (%)')
                plt.xticks(rotation=45)
                plt.legend(title='Producto', bbox_to_anchor=(1.05, 1), loc='upper left')
                plt.tight_layout()
                chart_file_var_ars = os.path.join(CHART_DIR, f"{i+1}_{nombre_limpio_cat}_variacion_ars.png") 
                plt.savefig(chart_file_var_ars)
                plt.close()
                imagenes_generadas.append({'file': chart_file_var_ars, 'name': f"Variación Diaria: {categoria} (ARS)"})

            # Gráfico Variación USD
            df_variacion_usd = df_cat_historia[['Fecha', 'Producto', 'Variacion_USD']].dropna()
            if not df_variacion_usd.empty:
                plt.figure(figsize=(12, 7))
                sns.barplot(x='Fecha', y='Variacion_USD', hue='Producto', data=df_variacion_usd)
                plt.title(f'Variación Diaria: {categoria} (USD %)')
                plt.xlabel('Fecha')
                plt.ylabel('Variación (%)')
                plt.xticks(rotation=45)
                plt.legend(title='Producto', bbox_to_anchor=(1.05, 1), loc='upper left')
                plt.tight_layout()
                chart_file_var_usd = os.path.join(CHART_DIR, f"{i+1}_{nombre_limpio_cat}_variacion_usd.png")
                plt.savefig(chart_file_var_usd)
                plt.close()
                imagenes_generadas.append({'file': chart_file_var_usd, 'name': f"Variación Diaria: {categoria} (USD)"})

    print(f"📊 Gráficos guardados en {CHART_DIR}.")
    
    # 4. Generar Tablas de Variación (Top 3 y Histórico)
    df_top_variacion = None
    if 'Variacion_Dia_Val' in df_variacion_historica.columns:
        df_top_variacion = df_variacion_historica.dropna(subset=['Variacion_Dia_Val'])
    
    return imagenes_generadas, df_variacion_historica, df_top_variacion

# --- Función de Email ---

def df_to_html_table(df, title="Tabla"):
    """Convierte un DataFrame a una tabla HTML estilizada. SE ASEGURA FORMATO %."""
    if df is None or df.empty:
        return f"<p><em>No hay datos disponibles para {title}.</em></p>"
    
    # Estilos básicos
    html_string = df.to_html(index=False, classes='table table-striped', escape=False)
    
    # Añadir estilos para mejor visualización en el email
    styles = """
    <style>
        .dataframe {
            width: 90%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 14px;
            font-family: Arial, sans-serif;
            text-align: left;
        }
        .dataframe th, .dataframe td {
            border: 1px solid #dddddd;
            padding: 8px;
        }
        .dataframe th {
            background-color: #f2f2f2;
            color: #333;
            font-weight: bold;
        }
        /* Colores para la variación */
        .positive { color: green; font-weight: bold; }
        .negative { color: red; font-weight: bold; }
    </style>
    """
    
    # Aplicar colores a las celdas de variación
    def color_variacion(val):
        # La función calcula y aplica color a las celdas que contienen el signo %
        if isinstance(val, str) and '%' in val and val != '-':
            try:
                # Quitamos el '%' y reemplazamos la coma por punto para el float si fuera necesario
                val_num = float(val.replace('%', '').replace(',', ''))
                if val_num > 0:
                    return f'<span class="positive">{val}</span>'
                elif val_num < 0:
                    return f'<span class="negative">{val}</span>'
            except ValueError:
                pass 
        return val

    df_styled = df.copy()
    
    # Se aplica el estilo de color a las columnas que contienen porcentajes
    for col in ['Variacion vs Ayer', 'Variacion vs 30 Días', 'Variacion vs 1 Año']:
        if col in df_styled.columns:
            df_styled[col] = df_styled[col].apply(color_variacion)
        
    # Se dropea la columna temporal 'Categoria' si existe en la tabla a mostrar
    if 'Categoria' in df_styled.columns:
        df_styled = df_styled.drop(columns=['Categoria'])
        
    html_string = df_styled.to_html(index=False, classes='dataframe', escape=False)
    
    return styles + html_string

def enviar_email(df, imagenes_generadas, df_variacion_historica, df_top_variacion):
    """Envía el email con el reporte adjunto, gráficos incrustados y tablas de variación. Se añade deduplicación."""
    
    msg = MIMEMultipart('related')
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_RECIPIENT
    msg['Subject'] = f"Reporte Automatizado: Precios Nuria ({datetime.now().strftime('%Y-%m-%d')})"

    # --- 1. Resumen Diario (Cuerpo del Email) ---
    if not df.empty:
        hoy = datetime.now().date()
        df_hoy_sin_filtrar = df[df['Fecha'].dt.date == hoy].copy()
        
        # FILTRADO DE EXCLUSIÓN
        df_hoy = df_hoy_sin_filtrar[~df_hoy_sin_filtrar['Producto'].apply(es_producto_excluido)].sort_values(by='Producto').copy()
        
        if not df_hoy.empty:
            
            # --- LÓGICA DE DEDUPLICACIÓN PARA EL RESUMEN DEL EMAIL ---
            
            # 1. Extraer el nombre limpio del producto (sin etiqueta de categoría)
            df_hoy['Nombre_Limpio'] = df_hoy['Producto'].apply(lambda x: re.sub(r'\[.*?\]\s*', '', x).strip())
            
            # 2. Identificar productos que tienen más de una entrada para hoy (duplicados por nombre limpio)
            productos_a_filtrar = df_hoy[df_hoy.duplicated(subset=['Nombre_Limpio'], keep=False)]['Nombre_Limpio'].unique()
            
            # Separar el DataFrame: productos limpios y productos duplicados
            df_filtrado_final = df_hoy[~df_hoy['Nombre_Limpio'].isin(productos_a_filtrar)].copy()
            df_duplicados = df_hoy[df_hoy['Nombre_Limpio'].isin(productos_a_filtrar)].copy()

            # 3. Aplicar regla de desduplicación a los duplicados: priorizar la categoría reclasificada.
            categorias_especiales = list(PRODUCTOS_A_RECLASIFICAR.values())
            
            # Extraer la categoría actual de la etiqueta para poder priorizarla
            df_duplicados['Categoria_Actual'] = df_duplicados['Producto'].apply(lambda x: re.search(r'\[(.*?)\]', x).group(1) if re.search(r'\[(.*?)\]', x) else 'Otros')

            # Para cada nombre duplicado, tomar solo la fila cuya categoría esté en la lista de categorías especiales.
            df_duplicados_limpios = df_duplicados.groupby('Nombre_Limpio').filter(
                lambda x: x['Categoria_Actual'].isin(categorias_especiales).any() and x['Categoria_Actual'].isin(categorias_especiales).any()
            )
            # Y si hay más de una, tomar solo las que están en las categorías especiales
            df_duplicados_limpios = df_duplicados_limpios[df_duplicados_limpios['Categoria_Actual'].isin(categorias_especiales)].copy()


            # 4. Reunir el DataFrame limpio para el resumen del email
            df_hoy = pd.concat([df_filtrado_final, df_duplicados_limpios], ignore_index=True)
            df_hoy = df_hoy.drop(columns=['Nombre_Limpio'])
            
            # --- FIN DE LA LÓGICA DE DEDUPLICACIÓN ---
            
            resumen_productos = ""
            # Extracción de la categoría (para la sub-división)
            df_hoy['Categoria'] = df_hoy['Producto'].apply(lambda x: re.search(r'\[(.*?)\]', x).group(1) if re.search(r'\[(.*?)\]', x) else 'Otros')
            
            # AGRUPACIÓN POR CATEGORÍA FINAL (incluye la subdivisión como Tortas Individuales)
            for categoria, group in df_hoy.groupby('Categoria'):
                # Asegurarse de que el conteo de productos sea correcto después de la deduplicación
                resumen_productos += f"""<p><strong>--- {categoria} ({group.shape[0]} productos) ---</strong></p><ul>"""
                
                for index, row in group.iterrows():
                    nombre_limpio = re.sub(r'\[.*?\]\s*', '', row['Producto']) 
                    
                    # Se elimina la presentación
                    resumen_productos += f"""
                        <li>{nombre_limpio} (ARS: ${row['Precio_ARS']:,.2f} / USD: ${row['Precio_USD']:,.2f})</li>
                    """
                
                resumen_productos += "</ul>"
            
            ultima_data = df_hoy.iloc[-1]
            resumen_html = f"""
                <h3>Resumen de Datos de Hoy ({ultima_data['Fecha'].strftime('%d/%m/%Y')})</h3>
                <p><strong>Dólar Oficial (BN):</strong> ${ultima_data['Dolar_ARS']:,.2f} ARS</p>
                {resumen_productos}
            """
        else:
            resumen_html = "<p>No hay datos nuevos para hoy (después de aplicar los filtros de exclusión).</p>"
    else:
        resumen_html = "<p>No hay suficientes datos históricos para mostrar un resumen.</p>"

    # --- 2. Tablas de Variación (Top 3 y Histórico) ---
    
    # a. Top 3
    top_3_subieron = None
    top_3_bajaron = None
    if df_top_variacion is not None and not df_top_variacion.empty:
        # Se asegura que la columna 'Categoria' no se muestre
        df_sorted = df_top_variacion.sort_values(by='Variacion_Dia_Val', ascending=False).head(3).copy()
        top_3_subieron = df_sorted.drop(columns=['Categoria', 'Variacion_Dia_Val'])
        
        df_sorted_neg = df_top_variacion.sort_values(by='Variacion_Dia_Val', ascending=True).head(3).copy()
        top_3_bajaron = df_sorted_neg.drop(columns=['Categoria', 'Variacion_Dia_Val'])

    html_top_3 = f"""
        <h3>📈 Top 3 Productos que Más Subieron (vs. Ayer)</h3>
        {df_to_html_table(top_3_subieron, title="Top 3 que subieron")}
        <h3>📉 Top 3 Productos que Más Bajaron (vs. Ayer)</h3>
        {df_to_html_table(top_3_bajaron, title="Top 3 que bajaron")}
    """
    
    # b. Variación Histórica (Se asegura que la columna 'Categoria' no se muestre)
    df_var_html = df_variacion_historica.drop(columns=['Variacion_Dia_Val']) if df_variacion_historica is not None else None
    
    html_historico = f"""
        <h3>📊 Variación de Precios vs Histórico (ARS)</h3>
        {df_to_html_table(df_var_html, title="Variación Histórica")}
    """

    # --- 3. Contenido HTML Completo ---
    html_charts = ""
    for idx, item in enumerate(imagenes_generadas):
        cid_name = f"chart_{idx+1}" 
        html_charts += f'''
            <p><strong>{item['name']}</strong></p>
            <img src="cid:{cid_name}" width="700" height="400">
        '''
    
    # Mensaje introductorio simple (sin mencionar exclusiones)
    mensaje_introductorio = """
        <p>Este informe automatizado rastrea el precio de productos de las categorías principales de Nuria.</p>
    """

    html_body = f"""
    <html>
        <body>
            <h2>Reporte Diario de Precios Nuria</h2>
            <p><strong>Fecha del Reporte:</strong> {datetime.now().strftime('%d/%m/%Y')}</p>
            
            {mensaje_introductorio} 
            
            {resumen_html}
            
            {html_top_3}
            
            {html_historico}
            
            <p>El archivo adjunto <strong>{REPORT_XLSX}</strong> contiene las pestañas detalladas.</p>
            
            <h3>Gráficos de Análisis de Historial Agrupado por Categoría</h3>
            {html_charts}
            
            <br>
            <p><i>Este correo fue generado automáticamente.</i></p>
        </body>
    </html>
    """
    msg.attach(MIMEText(html_body, 'html'))
    
    # 4. Adjuntar el archivo Excel
    try:
        with open(REPORT_XLSX, "rb") as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(REPORT_XLSX))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(REPORT_XLSX)}"'
            msg.attach(part)
    except FileNotFoundError:
        print(f"❌ No se pudo adjuntar el archivo {REPORT_XLSX}. Revisar generación.")
        
    # 5. Incrustar los gráficos
    for idx, item in enumerate(imagenes_generadas):
        file_path = item['file']
        cid_name = f"chart_{idx+1}"
        try:
            with open(file_path, 'rb') as fp:
                img = MIMEImage(fp.read())
                img.add_header('Content-ID', f'<{cid_name}>')
                msg.attach(img)
        except FileNotFoundError:
             print(f"❌ No se pudo incrustar el gráfico {file_path}. Revisar generación.")

    # 6. Enviar el email
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, EMAIL_RECIPIENT, msg.as_string())
        server.quit()
        print(f"\n📧 Reporte enviado exitosamente a {EMAIL_RECIPIENT}.")
    except Exception as e:
        print(f"\n❌ Error al enviar el email. Verifique la contraseña de aplicación (App Password): {e}")


# ==============================================================================
# --- Flujo Principal de Ejecución ---
# ==============================================================================

def main():
    print("=========================================================")
    print("      INICIO DEL RASTREO Y REPORTE AUTOMATIZADO NURIA")
    print("=========================================================")

    # 1. Obtener cotización del dólar (solo una vez)
    dolar_ars = obtener_precio_dolar_api(API_DOLAR_URL)
    
    if dolar_ars == 1.0:
        print("\n❌ Falla crítica: No se pudo obtener la cotización del dólar. Deteniendo ejecución.")
        return

    # 2. Cargar el maestro CSV
    df_maestro = cargar_o_crear_maestro()
    df_actualizado = df_maestro.copy()
    
    # 3. Iterar sobre las categorías para obtener los precios y guardar
    total_productos_nuevos = 0
    for categoria in CATEGORIAS_A_RASTREAR:
        productos_categoria = obtener_precios_nuria(categoria['url'], categoria['nombre'])
        
        for producto in productos_categoria:
            try:
                nombre_producto = producto['nombre']
                precio_ars = producto['precio_ars']
                
                if precio_ars is not None:
                    filas_antes = df_actualizado.shape[0]
                    # Se actualiza la llamada a guardar_datos
                    df_actualizado = guardar_datos(df_actualizado, nombre_producto, precio_ars, dolar_ars) 
                    if df_actualizado.shape[0] > filas_antes:
                        total_productos_nuevos += 1
            except Exception as e:
                print(f"⚠️ Error al procesar y guardar un producto: {e}. Continuando...")


    print(f"\n✅ Proceso de recolección finalizado. Nuevos precios guardados: {total_productos_nuevos}")

    if df_actualizado.shape[0] > 0: 
        # 4. Generar Reporte, Análisis y Gráficos (Devuelve DF de variación histórica y el Top 3)
        imagenes, df_var_historica, df_top_variacion = generar_reporte_y_graficos(df_actualizado)
        
        # 5. Enviar Reporte por Email (Se le pasa el nuevo DF de variación)
        enviar_email(df_actualizado, imagenes, df_var_historica, df_top_variacion)
    else:
        print("\nℹ️ No se pudo recopilar ningún dato para procesar. No se genera reporte ni email.")

    print("\n=========================================================")
    print("                   EJECUCIÓN FINALIZADA")

if __name__ == "__main__":
    main()
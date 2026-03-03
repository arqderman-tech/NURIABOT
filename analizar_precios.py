import pandas as pd, json
from pathlib import Path
from datetime import timedelta

DIR_DATA = Path("data")
DIR_DATA.mkdir(exist_ok=True)

def load():
    try:
        df = pd.read_csv("nuria_precios.csv")
        df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.normalize()
        return df.dropna(subset=["Precio_ARS","Fecha"])
    except Exception as e:
        print(f"Error: {e}"); return pd.DataFrame()

def var_pct(df, dias, cat=None):
    d = df[df["Categoria"]==cat].copy() if cat else df.copy()
    if d.empty: return None
    hoy = d["Fecha"].max()
    ref = hoy - timedelta(days=dias)
    h = d[d["Fecha"]==hoy]
    r = d[d["Fecha"]<=ref].sort_values("Fecha").groupby("Producto").last().reset_index()
    m = h.merge(r[["Producto","Precio_ARS"]], on="Producto", suffixes=("_h","_r"))
    if m.empty: return None
    return round(((m["Precio_ARS_h"]-m["Precio_ARS_r"])/m["Precio_ARS_r"]*100).mean(), 2)

def serie_pct(df, dias, cat=None):
    d = df[df["Categoria"]==cat].copy() if cat else df.copy()
    if d.empty: return []
    hoy = d["Fecha"].max()
    dp = d[d["Fecha"]>=hoy-timedelta(days=dias)]
    st = dp.groupby("Fecha")["Precio_ARS"].mean().reset_index()
    if len(st)<2: return []
    b = st["Precio_ARS"].iloc[0]
    return [{"fecha":r["Fecha"].strftime("%Y-%m-%d"),"pct":round((r["Precio_ARS"]/b-1)*100,2)} for _,r in st.iterrows()]

def ranking(df, dias):
    if df.empty: return []
    hoy = df["Fecha"].max()
    h = df[df["Fecha"]==hoy]
    r = df[df["Fecha"]<=hoy-timedelta(days=dias)].sort_values("Fecha").groupby("Producto").last().reset_index()
    m = h.merge(r[["Producto","Precio_ARS"]], on="Producto", suffixes=("_h","_r"))
    if m.empty: return []
    m["d"] = (m["Precio_ARS_h"]-m["Precio_ARS_r"])/m["Precio_ARS_r"]*100
    m = m[m["d"].abs()>0]
    cat_map = h.set_index("Producto")["Categoria"].to_dict()
    return m.sort_values("d",ascending=False).apply(lambda row:{
        "nombre":row["Producto"],"categoria":cat_map.get(row["Producto"],""),
        "diff_pct":round(row["d"],2),"precio_hoy":round(row["Precio_ARS_h"],2)
    },axis=1).tolist()

def main():
    df = load()
    if df.empty: print("Sin datos"); return
    hoy = df["Fecha"].max()
    df_hoy = df[df["Fecha"]==hoy]
    cats_stats = {cat: {"total":len(df_hoy[df_hoy["Categoria"]==cat]),"variacion_dia":var_pct(df,1,cat)} for cat in df_hoy["Categoria"].unique()}
    graficos = {k: {"total":serie_pct(df,d),"por_categoria":{cat:serie_pct(df,d,cat) for cat in df["Categoria"].unique()}} for k,d in {"7d":7,"30d":30,"6m":180}.items()}
    resumen = {"variacion_dia":var_pct(df,1),"variacion_mes":var_pct(df,30),"total_productos":len(df_hoy),"categorias":cats_stats,"fecha_actualizacion":hoy.strftime("%Y-%m-%d")}
    (DIR_DATA/"resumen.json").write_text(json.dumps(resumen,ensure_ascii=False,indent=2),encoding="utf-8")
    (DIR_DATA/"graficos.json").write_text(json.dumps(graficos,ensure_ascii=False,indent=2),encoding="utf-8")
    (DIR_DATA/"ranking_dia.json").write_text(json.dumps(ranking(df,1)[:30],ensure_ascii=False,indent=2),encoding="utf-8")
    (DIR_DATA/"ranking_7d.json").write_text(json.dumps(ranking(df,7)[:30],ensure_ascii=False,indent=2),encoding="utf-8")
    (DIR_DATA/"ranking_mes.json").write_text(json.dumps(ranking(df,30)[:30],ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"JSONs NURIABOT ok. Hoy: {len(df_hoy)} productos")

if __name__=="__main__": main()

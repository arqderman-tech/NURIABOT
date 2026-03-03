"""analizar_precios.py - NURIABOT"""
import pandas as pd, json, re
from pathlib import Path
from datetime import timedelta

DIR_DATA = Path("data")
DIR_DATA.mkdir(exist_ok=True)
ORDEN_CATS = ["Tortas Individuales", "Tortas y Postres", "Pasteleria y Panaderia", "Salados", "Otros"]

def cat(nombre):
    m = re.search(r'\[(.*?)\]', str(nombre))
    return m.group(1) if m else "Otros"

def clean(nombre):
    return re.sub(r'\[.*?\]\s*', '', str(nombre)).strip()

def load():
    try:
        df = pd.read_csv("nuria_precios.csv")
        df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.normalize()
        df["Categoria"] = df["Producto"].apply(cat)
        return df.dropna(subset=["Precio_ARS","Fecha"])
    except: return pd.DataFrame()

def var(df, dias):
    hoy = df["Fecha"].max()
    h = df[df["Fecha"]==hoy]
    r = df[df["Fecha"]<=hoy-timedelta(days=dias)].sort_values("Fecha").groupby("Producto").last().reset_index()
    m = h.merge(r[["Producto","Precio_ARS"]], on="Producto", suffixes=("_h","_r"))
    if m.empty: return None
    return ((m["Precio_ARS_h"]-m["Precio_ARS_r"])/m["Precio_ARS_r"]*100).mean()

def graficos(df):
    hoy = df["Fecha"].max()
    res = {}
    for key,dias in {"7d":7,"30d":30,"6m":180,"1y":365}.items():
        dp = df[df["Fecha"]>=hoy-timedelta(days=dias)]
        st = dp.groupby("Fecha")["Precio_ARS"].mean().reset_index()
        if st.empty: res[key]={"total":[],"categorias":{}}; continue
        b = st["Precio_ARS"].iloc[0]
        total=[{"fecha":r["Fecha"].strftime("%Y-%m-%d"),"pct":round((r["Precio_ARS"]/b-1)*100,2)} for _,r in st.iterrows()]
        cats={}
        for c in ORDEN_CATS:
            s = dp[dp["Categoria"]==c].groupby("Fecha")["Precio_ARS"].mean().reset_index()
            if len(s)<2: continue
            b2=s["Precio_ARS"].iloc[0]
            cats[c]=[{"fecha":r["Fecha"].strftime("%Y-%m-%d"),"pct":round((r["Precio_ARS"]/b2-1)*100,2)} for _,r in s.iterrows()]
        res[key]={"total":total,"categorias":cats}
    return res

def ranking(df, dias):
    hoy = df["Fecha"].max()
    h = df[df["Fecha"]==hoy]
    r = df[df["Fecha"]<=hoy-timedelta(days=dias)].sort_values("Fecha").groupby("Producto").last().reset_index()
    m = h.merge(r[["Producto","Precio_ARS"]], on="Producto", suffixes=("_h","_r"))
    if m.empty: return []
    m["d"] = (m["Precio_ARS_h"]-m["Precio_ARS_r"])/m["Precio_ARS_r"]*100
    m = m[m["d"].abs()>0]
    return m.sort_values("d",ascending=False).apply(lambda r:{"nombre":clean(r["Producto"]),"categoria":cat(r["Producto"]),"diff_pct":round(r["d"],2),"precio_hoy":round(r["Precio_ARS_h"],2)},axis=1).tolist()

def main():
    df = load()
    if df.empty: print("Sin datos"); return
    hoy = df["Fecha"].max()
    dh = df[df["Fecha"]==hoy]
    v1 = var(df,1); v30 = var(df,30)
    dr = df[df["Fecha"]==hoy-timedelta(days=1)]
    sube=baja=igual=0; cats=[]
    if not dr.empty:
        m = dh.merge(dr[["Producto","Precio_ARS"]], on="Producto", suffixes=("_h","_r"))
        m["d"]=(m["Precio_ARS_h"]-m["Precio_ARS_r"])/m["Precio_ARS_r"]*100
        sube=int((m["d"]>0.01).sum()); baja=int((m["d"]<-0.01).sum()); igual=int((m["d"].abs()<=0.01).sum())
        m["Cat"]=m["Producto"].apply(cat)
        for c in ORDEN_CATS:
            g=m[m["Cat"]==c]
            if g.empty: continue
            cats.append({"categoria":c,"variacion_pct_promedio":round(g["d"].mean(),2),"productos_subieron":int((g["d"]>0.01).sum()),"productos_bajaron":int((g["d"]<-0.01).sum()),"total_productos":len(g)})
    res={"variacion_dia":round(v1,2) if v1 is not None else None,"variacion_mes":round(v30,2) if v30 is not None else None,"total_productos":len(dh),"productos_subieron_dia":sube,"productos_bajaron_dia":baja,"productos_sin_cambio_dia":igual,"categorias_dia":cats}
    (DIR_DATA/"resumen.json").write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding="utf-8")
    (DIR_DATA/"graficos.json").write_text(json.dumps(graficos(df),ensure_ascii=False,indent=2),encoding="utf-8")
    (DIR_DATA/"ranking_dia.json").write_text(json.dumps(ranking(df,1),ensure_ascii=False,indent=2),encoding="utf-8")
    (DIR_DATA/"ranking_7d.json").write_text(json.dumps(ranking(df,7),ensure_ascii=False,indent=2),encoding="utf-8")
    (DIR_DATA/"ranking_mes.json").write_text(json.dumps(ranking(df,30),ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"JSONs NURIABOT ok. Hoy: {len(dh)} productos")

if __name__=="__main__": main()

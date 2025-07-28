from __future__ import annotations
import io, math
from itertools import cycle
from typing import Dict, List, Tuple

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ────────────── lógica (embutida) ──────────────
class Box:
    def __init__(self, sku: str, c: float, l: float, a: float):
        self.id = sku; self.c, self.l, self.a = c, l, a
        self.pos: Tuple[float, float, float] | None = None
    def orientations(self): return [(self.c, self.l), (self.l, self.c)]
    @property
    def volume(self): return self.c * self.l * self.a

class Trailer:
    def __init__(self, c: float, l: float, a: float): self.c, self.l, self.a = c, l, a
    @property
    def volume(self): return self.c * self.l * self.a

class SkylineLayer:
    def __init__(self, C: float, L: float): self.C, self.L, self.sky = C, L, [(0.0,0.0,C)]
    def place(self, b: Box):
        for w,d in b.orientations():
            for i,(x,y,fx) in enumerate(self.sky):
                if w<=fx and y+d<=self.L:
                    self.sky[i]=(x+w,y,fx-w); self.sky.append((x,y+d,w))
                    return True,(x,y)
        return False,None

def pack_grouped(trailer: Trailer, groups: List[List[Box]]):
    placed, unplaced, z, layer, lh = [],[],0.0,SkylineLayer(trailer.c,trailer.l),0.0
    for g_idx,grp in enumerate(groups):
        grp.sort(key=lambda b:b.c*b.l,reverse=True); i=0
        while i<len(grp):
            b=grp[i]; ok,pos=layer.place(b)
            if ok: b.pos=(*pos,z); placed.append(b); lh=max(lh,b.a); i+=1
            else:
                if lh==0: unplaced.extend(grp[i:]); break
                z+=lh
                if z>trailer.a+1e-6:
                    unplaced.extend(grp[i:]); [unplaced.extend(g) for g in groups[g_idx+1:]]
                    return placed,unplaced
                layer,SkylineLayer(trailer.c,trailer.l); lh=0.0
    return placed,unplaced

# ────────────── util planilhas ──────────────
def _key(fam,tam,qmm): return f"{fam}-{tam}-{int(qmm)}"
def load_files(car_bytes,med_bytes):
    car=pd.read_excel(io.BytesIO(car_bytes),engine="openpyxl")
    med=pd.read_excel(io.BytesIO(med_bytes),engine="openpyxl")
    med["KEY"]=med.apply(lambda r:_key(r["COD FAMILIA"],r["COD TAMANHO"],r["QMM"]),axis=1)
    car["KEY"]=car.apply(lambda r:_key(r["COD SKU"].split("-")[0],r["COD SKU"].split("-")[2],r["QMM"]),axis=1)
    merged=car.merge(med[["KEY","ALTURA","LARGURA","COMPRIMENTO"]],on="KEY",how="left")
    missing=merged[merged["ALTURA"].isna()]; merged=merged.dropna(subset=["ALTURA"])
    return merged,missing

def expand_grouped(df: pd.DataFrame):
    groups,order={},[]
    for _,r in df.iterrows():
        sku=r["COD SKU"]; groups.setdefault(sku,[]); order.append(sku) if sku not in order else None
        if r["QMM"]==0 or math.isnan(r["QMM"]): continue
        n=math.ceil(r["QTDE"]/r["QMM"])
        for i in range(1,n+1):
            groups[sku].append(Box(f"{sku}-{i}",r["COMPRIMENTO"],r["LARGURA"],r["ALTURA"]))
    return [groups[k] for k in order]

# ────────────── Streamlit UI ──────────────
st.set_page_config("Simulador de Cubagem",layout="wide")
st.title("📦 Simulador de Cubagem — algoritmo Skyline")

C=st.sidebar.number_input("Comprimento (m)",0.1,50.0,13.6,0.1)
L=st.sidebar.number_input("Largura (m)",0.1,5.0,2.45,0.05)
A=st.sidebar.number_input("Altura (m)",0.1,5.0,2.70,0.05)
st.sidebar.markdown("---")
car=st.sidebar.file_uploader("Carregamento.xlsx",type="xlsx")
med=st.sidebar.file_uploader("Medidas.xlsx",type="xlsx")

if st.sidebar.button("Simular") and car and med:
    merged,missing=load_files(car.read(),med.read())
    if merged.empty: st.error("Nenhum SKU com medida."); st.stop()
    groups=expand_grouped(merged); trailer=Trailer(C,L,A)
    placed,left=pack_grouped(trailer,groups)

    col1,col2,col3=st.columns(3)
    col1.metric("Caixas alocadas",len(placed))
    col2.metric("Não alocadas",len(left))
    col3.metric("Ocupação de volume",f"{sum(b.volume for b in placed)/trailer.volume*100:.1f}%")

    with st.expander("SKUs sem medida"): st.write(missing["COD SKU"].unique().tolist() or "Nenhum.")
    with st.expander("SKUs não alocados"):
        if not left: st.write("Todos alocados")
        else:
            cnt:Dict[str,int]={}
            for b in left: base="-".join(b.id.split("-")[:-1]); cnt[base]=cnt.get(base,0)+1
            st.write([f"{k} — {v}" for k,v in sorted(cnt.items())])

    # ───────── plot 3-D ─────────
    fig=go.Figure()
    fig.add_trace(go.Mesh3d(
        x=[0,C,C,0,0,C,C,0],y=[0,0,L,L,0,0,L,L],z=[0,0,0,0,A,A,A,A],
        i=[0,0,0,4,4,1,2,5,6,3,7,7],
        j=[1,2,3,5,6,5,6,4,7,7,4,5],
        k=[2,3,0,6,7,2,3,0,4,4,5,6],
        opacity=0.05,color="gray",showscale=False))
    palette=cycle(["#4e79a7","#f28e2b","#e15759","#76b7b2","#59a14f",
                   "#edc948","#b07aa1","#ff9da7","#9c755f","#bab0ab"])
    colors={sku:next(palette) for sku in
            sorted({ "-".join(b.id.split("-")[:-1]) for b in placed })}
    for b in placed:
        x,y,z=b.pos
        xs=[x,x+b.c,x+b.c,x,x,x+b.c,x+b.c,x]
        ys=[y,y,y+b.l,y+b.l,y,y,y+b.l,y+b.l]
        zs=[z,z,z,z,z+b.a,z+b.a,z+b.a,z+b.a]
        fig.add_trace(go.Mesh3d(x=xs,y=ys,z=zs,
                                color=colors["-".join(b.id.split("-")[:-1])],
                                opacity=0.85,showscale=False))
    fig.update_layout(scene=dict(aspectmode="data",
                                 xaxis_title="C (m)",yaxis_title="L (m)",zaxis_title="A (m)"),
                      margin=dict(l=0,r=0,t=30,b=0),height=650)
    st.plotly_chart(fig,use_container_width=True)

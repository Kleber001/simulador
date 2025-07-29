import math
import streamlit as st
from typing import Dict, List, Tuple
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

# ────────────────────────── Modelos e Algoritmos ──────────────────────────
class Box:
    def __init__(self, sku: str, c: float, l: float, a: float):
        self.id = sku
        self.c, self.l, self.a = c, l, a
        self.pos: Tuple[float, float, float] | None = None

    def orientations(self):
        return [(self.c, self.l), (self.l, self.c)]

    @property
    def volume(self):
        return self.c * self.l * self.a

class Trailer:
    def __init__(self, c: float, l: float, a: float):
        self.c, self.l, self.a = c, l, a

    @property
    def volume(self):
        return self.c * self.l * self.a

class SkylineLayer:
    def __init__(self, C: float, L: float):
        self.C, self.L = C, L
        self.sky = [(0.0, 0.0, C)]

    def place(self, b: Box):
        for w, d in b.orientations():
            for i, (x, y, fx) in enumerate(self.sky):
                if w <= fx and y + d <= self.L:
                    self.sky[i] = (x + w, y, fx - w)
                    self.sky.append((x, y + d, w))
                    return True, (x, y)
        return False, None

def pack_grouped(trailer: Trailer, sku_groups: List[List[Box]]):
    placed: List[Box] = []
    unplaced: List[Box] = []
    z = 0.0
    layer = SkylineLayer(trailer.c, trailer.l)
    layer_h = 0.0

    for g_idx, group in enumerate(sku_groups):
        group.sort(key=lambda b: b.c * b.l, reverse=True)
        idx = 0
        while idx < len(group):
            b = group[idx]
            ok, pos = layer.place(b)
            if ok:
                b.pos = (*pos, z)
                placed.append(b)
                layer_h = max(layer_h, b.a)
                idx += 1
            else:
                if layer_h == 0.0:
                    unplaced.extend(group[idx:])
                    idx = len(group)
                else:
                    z += layer_h
                    if z + 1e-6 > trailer.a:
                        unplaced.extend(group[idx:])
                        for rest in sku_groups[g_idx + 1:]:
                            unplaced.extend(rest)
                        return placed, unplaced
                    layer = SkylineLayer(trailer.c, trailer.l)
                    layer_h = 0.0
    return placed, unplaced

# ────────────────────────── Processamento de Dados ──────────────────────────
def key(fam: str, tam: str, qmm):
    return f"{fam}-{tam}-{int(qmm)}"

def load_files(car_file, med_file):
    car = pd.read_excel(car_file, engine="openpyxl")
    med = pd.read_excel(med_file, engine="openpyxl")

    med["KEY"] = med.apply(
        lambda r: key(str(r["COD FAMILIA"]), str(r["COD TAMANHO"]), r["QMM"]), axis=1
    )
    car["KEY"] = car.apply(
        lambda r: key(r["COD SKU"].split("-")[0], r["COD SKU"].split("-")[2], r["QMM"]), axis=1
    )

    merged = car.merge(
        med[["KEY", "ALTURA", "LARGURA", "COMPRIMENTO"]],
        on="KEY",
        how="left",
    )
    missing = merged[merged["ALTURA"].isna()]
    merged = merged.dropna(subset=["ALTURA"])
    return merged, missing

def expand_grouped(df: pd.DataFrame) -> List[List[Box]]:
    groups: Dict[str, List[Box]] = {}
    order: List[str] = []
    for _, r in df.iterrows():
        sku = r["COD SKU"]
        if sku not in groups:
            groups[sku] = []
            order.append(sku)
        qmm = r["QMM"]
        if qmm == 0 or math.isnan(qmm):
            continue
        n = math.ceil(r["QTDE"] / qmm)
        for i in range(1, n + 1):
            groups[sku].append(
                Box(f"{sku}-{i}", r["COMPRIMENTO"], r["LARGURA"], r["ALTURA"])
            )
    return [groups[k] for k in order]

# ────────────────────────── Visualização 3D ──────────────────────────
def cube_edges(x, y, z, dx, dy, dz):
    p = [
        (x, y, z), (x + dx, y, z), (x + dx, y + dy, z), (x, y + dy, z),
        (x, y, z + dz), (x + dx, y, z + dz), (x + dx, y + dy, z + dz), (x, y + dy, z + dz)
    ]
    idx = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7)
    ]
    return [(p[i], p[j]) for i, j in idx]

def add_box(ax, x, y, z, dx, dy, dz, color):
    faces = [
        [(x, y, z), (x + dx, y, z), (x + dx, y + dy, z), (x, y + dy, z)],
        [(x, y, z + dz), (x + dx, y, z + dz), (x + dx, y + dy, z + dz), (x, y + dy, z + dz)],
        [(x, y, z), (x + dx, y, z), (x + dx, y, z + dz), (x, y, z + dz)],
        [(x, y + dy, z), (x + dx, y + dy, z), (x + dx, y + dy, z + dz), (x, y + dy, z + dz)],
        [(x, y, z), (x, y + dy, z), (x, y + dy, z + dz), (x, y, z + dz)],
        [(x + dx, y, z), (x + dx, y + dy, z), (x + dx, y + dy, z + dz), (x + dx, y, z + dz)],
    ]
    ax.add_collection3d(
        Poly3DCollection(faces, facecolors=color, edgecolors="k", linewidths=0.3, alpha=0.85)
    )

# ────────────────────────── Interface Streamlit ──────────────────────────
st.set_page_config(page_title="Simulador de Cubagem", layout="wide")
st.title("Simulador de Cubagem — Skyline + SKUs agrupados")

# Sidebar de configurações
with st.sidebar:
    st.header("Configurações do Trailer")
    c = st.number_input("Comprimento (m)", min_value=0.1, value=13.6)
    l = st.number_input("Largura (m)", min_value=0.1, value=2.45)
    a = st.number_input("Altura (m)", min_value=0.1, value=2.9)
    
    st.header("Arquivos de Entrada")
    car_file = st.file_uploader("Carregamento.xlsx", type="xlsx")
    med_file = st.file_uploader("Medidas.xlsx", type="xlsx")

# Área principal
if car_file and med_file:
    try:
        merged, missing = load_files(car_file, med_file)
        
        if not merged.empty:
            sku_groups = expand_grouped(merged)
            trailer = Trailer(c, l, a)
            placed, left = pack_grouped(trailer, sku_groups)
            
            # Cálculo de métricas
            vol_used = sum(b.volume for b in placed)
            utilization = vol_used / trailer.volume * 100
            
            # Layout de colunas
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # Plotagem 3D
                fig = plt.figure(figsize=(10, 6))
                ax = fig.add_subplot(111, projection='3d')
                
                ax.set_xlim(0, trailer.c)
                ax.set_ylim(0, trailer.l)
                ax.set_zlim(0, trailer.a)
                ax.set_xlabel("Comprimento (m)")
                ax.set_ylabel("Largura (m)")
                ax.set_zlabel("Altura (m)")
                ax.view_init(elev=18, azim=-60)
                ax.set_box_aspect((trailer.c, trailer.l, trailer.a))
                
                # Contorno do trailer
                ax.add_collection3d(
                    Line3DCollection(cube_edges(0, 0, 0, trailer.c, trailer.l, trailer.a),
                                    colors="black", linewidths=0.5)
                )
                
                # Caixas colocadas
                if placed:
                    bases = list(set("-".join(b.id.split("-")[:-1]) for b in placed))
                    cmap = plt.cm.get_cmap("tab20", len(bases))
                    colors = {sku: cmap(i) for i, sku in enumerate(bases)}
                    for b in placed:
                        add_box(ax, *b.pos, b.c, b.l, b.a, colors["-".join(b.id.split("-")[:-1])])
                
                st.pyplot(fig)
            
            with col2:
                st.metric("Utilização de Volume", f"{utilization:.1f}%")
                st.metric("Caixas Alocadas", f"{len(placed)}")
                st.metric("Caixas Não Alocadas", f"{len(left)}")
                
                with st.expander("SKUs sem Medidas", expanded=False):
                    if not missing.empty:
                        st.dataframe(missing[["COD SKU", "QTDE", "QMM"]])
                    else:
                        st.success("Todos os SKUs foram encontrados")
                
                with st.expander("Caixas Não Alocadas", expanded=False):
                    if left:
                        counts = {}
                        for b in left:
                            base = "-".join(b.id.split("-")[:-1])
                            counts[base] = counts.get(base, 0) + 1
                        df_left = pd.DataFrame({
                            "SKU": counts.keys(),
                            "Não Alocados": counts.values()
                        })
                        st.dataframe(df_left)
                    else:
                        st.success("Todas as caixas foram alocadas")
        else:
            st.error("Nenhum SKU válido encontrado nos arquivos carregados")
            
    except Exception as e:
        st.error(f"Erro no processamento: {str(e)}")
else:
    st.info("Faça upload de ambos os arquivos para iniciar a simulação")

st.markdown("---")
st.caption("Simulador desenvolvido para otimização de cargas utilizando algoritmo Skyline")

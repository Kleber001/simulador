import math
import streamlit as st
from typing import Dict, List, Tuple
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

# ────────────────────────── CLASSES E ALGORITMO ──────────────────────────
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

# ────────────────────────── PROCESSAMENTO DE DADOS ──────────────────────────
def load_files(car_file, med_file):
    car = pd.read_excel(car_file, engine="openpyxl")
    med = pd.read_excel(med_file, engine="openpyxl")

    med["KEY"] = med.apply(
        lambda r: f"{str(r['COD FAMILIA'])}-{str(r['COD TAMANHO'])}-{int(r['QMM'])}", axis=1
    )
    car["KEY"] = car.apply(
        lambda r: f"{r['COD SKU'].split('-')[0]}-{r['COD SKU'].split('-')[2]}-{int(r['QMM'])}", axis=1
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
        groups[sku].extend(
            Box(f"{sku}-{i}", r["COMPRIMENTO"], r["LARGURA"], r["ALTURA"])
            for i in range(1, n + 1)
        )
    return [groups[k] for k in order]

# ────────────────────────── VISUALIZAÇÃO 3D ──────────────────────────
def cube_edges(x, y, z, dx, dy, dz):
    return [
        ((x, y, z), (x+dx, y, z)), ((x+dx, y, z), (x+dx, y+dy, z)),
        ((x+dx, y+dy, z), (x, y+dy, z)), ((x, y+dy, z), (x, y, z)),
        ((x, y, z+dz), (x+dx, y, z+dz)), ((x+dx, y, z+dz), (x+dx, y+dy, z+dz)),
        ((x+dx, y+dy, z+dz), (x, y+dy, z+dz)), ((x, y+dy, z+dz), (x, y, z+dz)),
        ((x, y, z), (x, y, z+dz)), ((x+dx, y, z), (x+dx, y, z+dz)),
        ((x+dx, y+dy, z), (x+dx, y+dy, z+dz)), ((x, y+dy, z), (x, y+dy, z+dz)),
    ]

def add_box(ax, x, y, z, dx, dy, dz, color):
    faces = [
        [(x, y, z), (x+dx, y, z), (x+dx, y+dy, z), (x, y+dy, z)],
        [(x, y, z+dz), (x+dx, y, z+dz), (x+dx, y+dy, z+dz), (x, y+dy, z+dz)],
        [(x, y, z), (x+dx, y, z), (x+dx, y, z+dz), (x, y, z+dz)],
        [(x+dx, y, z), (x+dx, y+dy, z), (x+dx, y+dy, z+dz), (x+dx, y, z+dz)],
        [(x, y+dy, z), (x, y+dy, z+dz), (x+dx, y+dy, z+dz), (x+dx, y+dy, z)],
        [(x, y, z), (x, y, z+dz), (x, y+dy, z+dz), (x, y+dy, z)],
    ]
    ax.add_collection3d(
        Poly3DCollection(faces, facecolors=color, edgecolors="k", linewidths=0.3, alpha=0.85)
    )

# ────────────────────────── INTERFACE STREAMLIT ──────────────────────────
st.set_page_config(page_title="Simulador 3D de Cubagem", layout="wide")
st.title("🚚 Simulador Inteligente de Cubagem em 3D")

with st.sidebar:
    st.header("Configurações do Veículo")
    c = st.number_input("Comprimento Interno (m)", min_value=1.0, value=13.6)
    l = st.number_input("Largura Interna (m)", min_value=1.0, value=2.45)
    a = st.number_input("Altura Máxima (m)", min_value=1.0, value=2.9)
    
    st.header("Dados de Entrada")
    car_file = st.file_uploader("Planilha de Carregamento (.xlsx)", type="xlsx")
    med_file = st.file_uploader("Tabela de Medidas (.xlsx)", type="xlsx")

if car_file and med_file:
    try:
        merged, missing = load_files(car_file, med_file)
        
        if not merged.empty:
            sku_groups = expand_grouped(merged)
            trailer = Trailer(c, l, a)
            placed, left = pack_grouped(trailer, sku_groups)
            
            # Cálculos principais
            vol_used = sum(b.volume for b in placed)
            utilization = vol_used / trailer.volume * 100
            remaining_vol = trailer.volume - vol_used
            
            # Cálculo de capacidade residual
            last_product_info = None
            if sku_groups and remaining_vol > 0:
                last_group = sku_groups[-1]
                if last_group:
                    sample_box = last_group[0]
                    box_volume = sample_box.volume
                    additional_count = int(remaining_vol // box_volume)
                    if additional_count > 0:
                        last_product_info = {
                            'count': additional_count,
                            'sku': "-".join(sample_box.id.split("-")[:-2]),
                            'dims': f"{sample_box.c}m x {sample_box.l}m x {sample_box.a}m"
                        }
            
            # Layout principal
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.subheader("Visualização Tridimensional")
                fig = plt.figure(figsize=(10, 6))
                ax = fig.add_subplot(111, projection='3d')
                
                ax.set_xlim(0, trailer.c)
                ax.set_ylim(0, trailer.l)
                ax.set_zlim(0, trailer.a)
                ax.set_xlabel("Comprimento")
                ax.set_ylabel("Largura")
                ax.set_zlabel("Altura")
                ax.view_init(elev=20, azim=-60)
                ax.set_box_aspect((trailer.c, trailer.l, trailer.a))
                
                # Container
                ax.add_collection3d(
                    Line3DCollection(cube_edges(0, 0, 0, c, l, a), colors="gray", linewidths=1)
                )
                
                # Caixas alocadas
                if placed:
                    unique_skus = list(set("-".join(b.id.split("-")[:-1]) for b in placed))
                    colors = plt.cm.tab20.colors[:len(unique_skus)]
                    color_map = {sku: colors[i] for i, sku in enumerate(unique_skus)}
                    
                    for b in placed:
                        sku_base = "-".join(b.id.split("-")[:-1])
                        add_box(ax, *b.pos, b.c, b.l, b.a, color_map[sku_base])
                
                plt.tight_layout()
                st.pyplot(fig)
            
            with col2:
                st.subheader("Métricas de Carga")
                st.metric("**Ocupação Total**", f"{utilization:.1f}%")
                st.metric("Caixas Posicionadas", len(placed))
                st.metric("Caixas Remanescentes", len(left))
                
                if last_product_info:
                    st.divider()
                    st.subheader("📦 Capacidade Residual")
                    st.markdown(f"""
                    **{last_product_info['count']} unidades** adicionais do último produto:
                    - **SKU:** {last_product_info['sku']}
                    - **Dimensões:** {last_product_info['dims']}
                    - **Volume Unitário:** {sample_box.volume:.2f}m³
                    - **Volume Total Disponível:** {remaining_vol:.2f}m³
                    """)
                
                with st.expander("▶ Detalhes dos SKUs Não Mapeados", expanded=False):
                    if not missing.empty:
                        st.dataframe(
                            missing[['COD SKU', 'QTDE', 'QMM']],
                            column_config={
                                'COD SKU': 'SKU',
                                'QTDE': 'Quantidade',
                                'QMM': 'Qtd. por Medida'
                            }
                        )
                    else:
                        st.success("Todas as medições foram encontradas")
                
                with st.expander("▶ Relatório de Não Posicionados", expanded=False):
                    if left:
                        non_placed = {}
                        for b in left:
                            sku_base = "-".join(b.id.split("-")[:-2])
                            non_placed[sku_base] = non_placed.get(sku_base, 0) + 1
                        st.dataframe(
                            pd.DataFrame({
                                'SKU': non_placed.keys(),
                                'Caixas Não Posicionadas': non_placed.values()
                            }),
                            hide_index=True
                        )
                    else:
                        st.success("Toda a carga foi posicionada com sucesso!")

        else:
            st.error("Nenhum SKU válido encontrado nos arquivos carregados")
    
    except Exception as e:
        st.error(f"Erro no processamento: {str(e)}")
        st.stop()

else:
    st.info("⭐ Faça upload dos arquivos necessários para iniciar a simulação")
    st.image("https://images.unsplash.com/photo-1602016652320-227de97c5e4c?auto=format&fit=crop&w=600", 
             caption="Otimização logística inteligente")

st.markdown("---")
st.caption("Sistema desenvolvido para planejamento logístico avançado | Versão 2.1")


import math
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from typing import List, Tuple, Dict
from matplotlib.colors import ListedColormap
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# =================== CLASSES ORIGINAIS ===================
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

# =================== FUNÇÕES DE CÁLCULO ===================
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

def load_files(car_path, med_path):
    car = pd.read_excel(car_path, engine="openpyxl")
    med = pd.read_excel(med_path, engine="openpyxl")

    med["KEY"] = med.apply(
        lambda r: f"{str(r['COD FAMILIA'])}-{str(r['COD TAMANHO'])}-{int(r['QMM'])}", axis=1)
    
    car["KEY"] = car.apply(
        lambda r: f"{r['COD SKU'].split('-')[0]}-{r['COD SKU'].split('-')[2]}-{r['QMM']}", axis=1)

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

# =================== FUNÇÕES DE VISUALIZAÇÃO ===================
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

# =================== INTERFACE STREAMLIT ===================
def main():
    st.set_page_config(
        page_title="Cubagem Inteligente 4.0",
        page_icon="🚛",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Estilos CSS customizados
    st.markdown("""
    <style>
    .metric-card {
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        background: #ffffff;
        margin-bottom: 25px;
        transition: transform 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-3px);
    }
    .header-section {
        background: linear-gradient(15deg, #2c3e50, #3498db);
        padding: 25px;
        border-radius: 10px;
        color: white;
        margin-bottom: 30px;
    }
    .stButton>button {
        width: 100%;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        transform: scale(1.05);
    }
    </style>
    """, unsafe_allow_html=True)

    # Header
    st.markdown("""
    <div class="header-section">
        <h1 style="margin:0;">📦 CUBAGEM INTELIGENTE - LOGPROD</h1>
        <p style="margin:0; opacity:0.9;">Sistema de otimização de carregamento 3D em tempo real</p>
    </div>
    """, unsafe_allow_html=True)

    # Controles principais
    with st.expander("⚙️ CONFIGURAÇÕES DO CARREGAMENTO", expanded=True):
        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("📏 Dimensões da Carreta")
            c = st.number_input("Comprimento (metros)", min_value=1.0, value=13.6, step=0.1)
            l = st.number_input("Largura (metros)", min_value=1.0, value=2.45, step=0.1)
            a = st.number_input("Altura (metros)", min_value=1.0, value=2.5, step=0.1)
            trailer = Trailer(c, l, a)

        with col2:
            st.subheader("📂 Entrada de Dados")
            col21, col22 = st.columns(2)
            with col21:
                car_file = st.file_uploader("Arquivo de Carregamento (XLSX)", type="xlsx")
            with col22:
                med_file = st.file_uploader("Arquivo de Medidas (XLSX)", type="xlsx")

    # Processamento
    if st.button("🚀 EXECUTAR SIMULAÇÃO", type="primary", use_container_width=True):
        if not car_file or not med_file:
            st.error("⚠️ Precisa selecionar ambos arquivos para prosseguir")
            return

        try:
            with st.spinner("Processando dados e calculando cubagem..."):
                merged, missing = load_files(car_file, med_file)
                sku_groups = expand_grouped(merged)
                placed, left = pack_grouped(trailer, sku_groups)

                # Cálculo das métricas
                vol_total = trailer.volume
                vol_usado = sum(b.volume for b in placed)
                percent_ocupacao = (vol_usado / vol_total) * 100
                eficiencia = f"{percent_ocupacao:.1f}%"
                status = ("✅ Carregamento Completo" if len(left) == 0 
                        else f"⚠️ Parcial - {len(left)} volumes não alocados")

                # Exibição das métricas
                cols = st.columns(4)
                metrics = [
                    ("📦 Volumes Alocados", f"{len(placed)}", "#4CAF50"),
                    ("📭 Volumes Restantes", f"{len(left)}", "#FF5722"),
                    ("📊 Cubagem Utilizada", f"{vol_usado:.1f}m³/{vol_total:.1f}m³", "#2196F3"),
                    ("🎯 Eficiência", eficiencia, "#9C27B0"),
                ]

                for col, (title, value, color) in zip(cols, metrics):
                    with col:
                        st.markdown(f"""
                        <div class="metric-card" style="border-left: 5px solid {color};">
                            <div style="color: {color}; font-size: 24px; margin-bottom: 10px;">{value}</div>
                            <div style="color: #666; font-size: 14px;">{title}</div>
                        </div>
                        """, unsafe_allow_html=True)

                # Visualização 3D
                st.subheader("🗺️ Visualização Tridimensional do Carregamento")
                plt.style.use('seaborn')
                fig = plt.figure(figsize=(12, 7))
                ax = fig.add_subplot(111, projection='3d')
                
                # Configurações do gráfico
                ax.set_xlim(0, trailer.c)
                ax.set_ylim(0, trailer.l)
                ax.set_zlim(0, trailer.a)
                ax.set_xlabel("Comprimento (m)", fontsize=10)
                ax.set_ylabel("Largura (m)", fontsize=10)
                ax.set_zlabel("Altura (m)", fontsize=10)
                ax.view_init(elev=22, azim=-60)
                ax.set_title("Distribuição das Cargas na Carreta", pad=20)

                # Cores únicas para cada SKU
                skus = list(set(["-".join(b.id.split("-")[:-1]) for b in placed]))
                cores = cm.tab20.colors[:len(skus)]
                
                # Desenhar caixas
                for b in placed:
                    sku_idx = skus.index("-".join(b.id.split("-")[:-1]))
                    add_box(ax, *b.pos, b.c, b.l, b.a, cores[sku_idx])

                # Legenda
                from matplotlib.patches import Rectangle
                legend_elements = [Rectangle((0,0),1,1, color=cores[i], alpha=0.8, 
                                   label=skus[i]) for i in range(len(skus))]
                ax.legend(handles=legend_elements, bbox_to_anchor=(0.9, 0.9), 
                        title="SKUs", fontsize=8)

                st.pyplot(fig)

                # Relatório de problemas
                if len(left) > 0 or not missing.empty:
                    st.subheader("🚨 Relatório de Inconsistências")
                    tab1, tab2 = st.tabs(["Volumes Não Alocados", "SKUs sem Medidas"])

                    with tab1:
                        nao_alocados = pd.DataFrame({
                            "SKU": [b.id.split("-")[0] for b in left],
                            "Quantidade": [1]*len(left)
                        }).groupby("SKU").count().reset_index()
                        st.dataframe(nao_alocados, use_container_width=True, hide_index=True)

                    with tab2:
                        st.dataframe(missing[["COD SKU"]].drop_duplicates(), 
                                   use_container_width=True, hide_index=True)

                st.success(f"Simulação concluída: {status}")

        except Exception as e:
            st.error(f"Erro crítico durante o processamento: {str(e)}")
            st.error("Verifique os formatos dos arquivos e os dados de entrada")

if __name__ == "__main__":
    main()

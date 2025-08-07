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

# =================== INTERFACE STREAMLIT CORRIGIDA ===================
def main():
    st.set_page_config(
        page_title="Cubagem Inteligente 4.0",
        page_icon="🚛",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Configuração visual customizada
    st.markdown("""
    <style>
    .metric-card {
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        background: #ffffff;
        margin-bottom: 25px;
        transition: all 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
    .header-section {
        background: linear-gradient(145deg, #2c3e50, #2980b9);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2.5rem;
        text-align: center;
    }
    .stButton>button {
        width: 100%;
        padding: 12px !important;
        border-radius: 8px !important;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: scale(1.02);
    }
    </style>
    """, unsafe_allow_html=True)

    # Interface principal
    st.markdown("""
    <div class="header-section">
        <h1 style="margin:0; font-size:2.5rem;">🚚 CUBAGEM INTELIGENTE</h1>
        <p style="margin:0; font-size:1.1rem; opacity:0.95;">Otimização de cargas em tempo real com visualização 3D</p>
    </div>
    """, unsafe_allow_html=True)

    # Configurações do carregamento
    with st.expander("⚙️ CONFIGURAÇÕES DA CARGA", expanded=True):
        col_dim, col_files = st.columns([1, 2])
        
        with col_dim:
            st.subheader("📐 Dimensões do Veículo")
            c = st.number_input("Comprimento Total (m)", 5.0, 30.0, 13.6, 0.1)
            l = st.number_input("Largura Interna (m)", 1.5, 3.0, 2.45, 0.01)
            a = st.number_input("Altura Máxima (m)", 1.5, 4.0, 2.5, 0.1)
            trailer = Trailer(c, l, a)
        
        with col_files:
            st.subheader("📂 Arquivos de Entrada")
            col_car, col_med = st.columns(2)
            with col_car:
                car_file = st.file_uploader("Planilha de Carregamento", type="xlsx")
            with col_med:
                med_file = st.file_uploader("Planilha de Medidas", type="xlsx")

    # Processamento principal
    if st.button("🚀 INICIAR SIMULAÇÃO", type="primary", use_container_width=True):
        if not (car_file and med_file):
            st.error("⚠️ Selecione ambos os arquivos para continuar")
            return

        try:
            with st.spinner("Analisando dados e calculando disposição 3D..."):
                merged, missing = load_files(car_file, med_file)
                sku_groups = expand_grouped(merged)
                placed, left = pack_grouped(trailer, sku_groups)
                
                vol_total = trailer.volume
                vol_usado = sum(b.volume for b in placed)
                perc_ocup = (vol_usado / vol_total) * 100 if vol_total > 0 else 0

                # Painel de métricas
                st.subheader("📊 RESULTADOS DA SIMULAÇÃO")
                cols = st.columns(4)
                with cols[0]:
                    st.markdown(f"""
                    <div class="metric-card" style="border-left: 4px solid #27ae60;">
                        <div style="font-size: 24px; color: #27ae60;">{len(placed)}</div>
                        <div style="color: #666;">Volumes Carregados</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with cols[1]:
                    st.markdown(f"""
                    <div class="metric-card" style="border-left: 4px solid #e67e22;">
                        <div style="font-size: 24px; color: #e67e22;">{len(left)}</div>
                        <div style="color: #666;">Volumes não Alocados</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with cols[2]:
                    st.markdown(f"""
                    <div class="metric-card" style="border-left: 4px solid #2980b9;">
                        <div style="font-size: 24px; color: #2980b9;">{perc_ocup:.1f}%</div>
                        <div style="color: #666;">Taxa de Ocupação</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with cols[3]:
                    st.markdown(f"""
                    <div class="metric-card" style="border-left: 4px solid #9b59b6;">
                        <div style="font-size: 24px; color: #9b59b6;">{vol_total:.1f}m³</div>
                        <div style="color: #666;">Capacidade Total</div>
                    </div>
                    """, unsafe_allow_html=True)

                # Visualização 3D
                st.subheader("📦 DISPOSIÇÃO TRIDIMENSIONAL")
                plt.rcParams.update({
                    'figure.facecolor': 'white',
                    'axes.grid': True,
                    'grid.color': '#f0f0f0',
                    'axes.edgecolor': '#333333',
                    'axes.labelcolor': '#333333',
                    'xtick.color': '#333333',
                    'ytick.color': '#333333',
                    'font.family': 'DejaVu Sans'
                })
                
                fig = plt.figure(figsize=(12, 7))
                ax = fig.add_subplot(111, projection='3d')
                
                ax.set_xlim(0, trailer.c)
                ax.set_ylim(0, trailer.l)
                ax.set_zlim(0, trailer.a)
                ax.set_xlabel("Comprimento (m)", fontsize=9, labelpad=10)
                ax.set_ylabel("Largura (m)", fontsize=9, labelpad=10)
                ax.set_zlabel("Altura (m)", fontsize=9, labelpad=10)
                ax.view_init(elev=24, azim=-58)
                
                skus = list(set([b.id.split('-')[0] for b in placed]))
                cores = cm.get_cmap('tab20', len(skus))(range(len(skus)))
                
                for b in placed:
                    sku_id = b.id.split('-')[0]
                    add_box(ax, *b.pos, b.c, b.l, b.a, cores[skus.index(sku_id)])

                st.pyplot(fig)

                # Seção de alertas
                if len(left) > 0 or not missing.empty:
                    st.subheader("⚠️ ITENS COM PROBLEMAS")
                    tab1, tab2 = st.tabs(["Volumes Não Alocados", "SKUs Sem Medidas"])
                    
                    with tab1:
                        df = pd.DataFrame({
                            "SKU": [b.id.split('-')[0] for b in left],
                            "Quantidade": len(left) * [1]
                        }).groupby("SKU").sum().reset_index()
                        st.dataframe(df, hide_index=True, use_container_width=True)
                    
                    with tab2:
                        st.dataframe(missing[["COD SKU"]].drop_duplicates(), 
                                   hide_index=True, use_container_width=True)

                st.success(f"Simulação concluída com sucesso! Ocupação: {perc_ocup:.1f}%")

        except Exception as e:
            st.error(f"ERRO: {str(e)}")
            st.info("Verifique se os arquivos estão corretos e no formato adequado")

if __name__ == "__main__":
    main()

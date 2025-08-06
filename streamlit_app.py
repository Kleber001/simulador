import math
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.backends.backend_agg import RendererAgg
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from typing import List, Tuple, Dict

# Configurações iniciais
plt.rcParams.update({'figure.max_open_warning': 0})
_lock = RendererAgg.lock

# Classes principais mantidas do código original
class Box:
    def __init__(self, sku: str, c: float, l: float, a: float):
        self.id = sku
        self.c, self.l, self.a = c, l, a
        self.pos: Tuple[float, float, float] | None = None

    def orientations(self):
        return [(self.c, self.l, self.a), 
                (self.l, self.c, self.a),
                (self.c, self.a, self.l),
                (self.a, self.c, self.l),
                (self.l, self.a, self.c),
                (self.a, self.l, self.c)]

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

    def place(self, w: float, d: float):
        for i, (x, y, fx) in enumerate(self.sky):
            if w <= fx and y + d <= self.L:
                self.sky[i] = (x + w, y, fx - w)
                self.sky.append((x, y + d, w))
                return True, (x, y)
        return False, None

# Algoritmo de empacotamento otimizado
def pack_grouped(trailer: Trailer, sku_groups: List[List[Box]]):
    placed: List[Box] = []
    unplaced: List[Box] = []
    
    layer = SkylineLayer(trailer.c, trailer.l)
    current_z = 0.0
    current_layer_height = 0.0

    for group_idx, group in enumerate(sku_groups):
        group.sort(key=lambda b: math.prod(b.dimensoes()[:2]), reverse=True)
        
        idx = 0
        while idx < len(group):
            box = group[idx]
            
            best_fit = None
            best_orientation = None
            min_height = float('inf')
            
            for orientation in box.orientations():
                w, d, h = orientation
                success, (x, y) = layer.place(w, d)
                if success:
                    total_height = current_z + max(current_layer_height, h)
                    if total_height < min_height:
                        best_fit = (x, y, current_z)
                        best_orientation = orientation
                        min_height = total_height
            
            if best_fit:
                box.pos = best_fit
                box.dimensoes = best_orientation
                placed.append(box)
                current_layer_height = max(current_layer_height, best_orientation[2])
                idx += 1
            else:
                if current_layer_height == 0:
                    unplaced.extend(group[idx:])
                    break
                    
                current_z += current_layer_height
                if current_z > trailer.a:
                    unplaced.extend(group[idx:])
                    return placed, unplaced
                    
                layer = SkylineLayer(trailer.c, trailer.l)
                current_layer_height = 0.0

    return placed, unplaced

# Função para carregar dados
def load_files(car_file, med_file):
    car = pd.read_excel(car_file, engine='openpyxl')
    med = pd.read_excel(med_file, engine='openpyxl')

    med['KEY'] = med.apply(
        lambda r: f"{r['COD FAMILIA']}-{r['COD TAMANHO']}-{int(r['QMM'])}", axis=1)
    
    car['KEY'] = car.apply(
        lambda r: f"{r['COD SKU'].split('-')[0]}-{r['COD SKU'].split('-')[2]}-{r['QMM']}", axis=1)

    merged = car.merge(
        med[['KEY', 'ALTURA', 'LARGURA', 'COMPRIMENTO']],
        on='KEY',
        how='left'
    )
    missing = merged[merged['ALTURA'].isna()]
    merged = merged.dropna(subset=['ALTURA'])
    
    return merged, missing

# Função para expandir grupos de SKUs
def expand_grouped(df: pd.DataFrame) -> List[List[Box]]:
    groups = {}
    order = []
    for _, row in df.iterrows():
        sku = row['COD SKU']
        if sku not in groups:
            groups[sku] = []
            order.append(sku)
        qmm = row['QMM']
        if pd.notnull(qmm) and qmm > 0:
            qtd = math.ceil(row['QTDE'] / qmm)
            for i in range(qtd):
                groups[sku].append(Box(
                    f"{sku}-{i+1}",
                    row['COMPRIMENTO'],
                    row['LARGURA'],
                    row['ALTURA']
                ))
    return [groups[sku] for sku in order]

# Função de visualização 3D profissional
def plot_3d(trailer, boxes, elev=25, azim=-60):
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection='3d', proj_type='ortho')
    
    ax.set_box_aspect((trailer.c, trailer.l, trailer.a))
    ax.set_xlim(0, trailer.c)
    ax.set_ylim(0, trailer.l)
    ax.set_zlim(0, trailer.a)
    
    ax.view_init(elev=elev, azim=azim)
    ax.grid(True, alpha=0.3)
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    
    cmap = cm.get_cmap('tab20')
    colors = {}
    for box in boxes:
        sku = '-'.join(box.id.split('-')[:-1])
        if sku not in colors:
            colors[sku] = cmap(len(colors) % 20)
        
        x, y, z = box.pos
        dx, dy, dz = box.dimensoes()
        
        faces = [
            [(x, y, z), (x+dx, y, z), (x+dx, y+dy, z), (x, y+dy, z)],
            [(x, y, z+dz), (x+dx, y, z+dz), (x+dx, y+dy, z+dz), (x, y+dy, z+dz)],
            [(x, y, z), (x+dx, y, z), (x+dx, y, z+dz), (x, y, z+dz)],
            [(x, y+dy, z), (x+dx, y+dy, z), (x+dx, y+dy, z+dz), (x, y+dy, z+dz)],
            [(x, y, z), (x, y+dy, z), (x, y+dy, z+dz), (x, y, z+dz)],
            [(x+dx, y, z), (x+dx, y+dy, z), (x+dx, y+dy, z+dz), (x+dx, y, z+dz)]
        ]
        
        ax.add_collection3d(Poly3DCollection(
            faces,
            facecolors=colors[sku],
            edgecolors='k',
            linewidths=0.3,
            alpha=0.85
        ))
    
    return fig

# Interface Streamlit profissional
def main():
    st.set_page_config(
        page_title="Cubagem 4.0 - Logística Inteligente",
        page_icon="🚚",
        layout="wide"
    )
    
    st.markdown("""
    <style>
    .metric-card {
        padding: 20px;
        border-radius: 10px;
        background: #f8f9fa;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: transform 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-3px);
    }
    .header {
        background: linear-gradient(15deg, #2c3e50, #3498db);
        padding: 2rem;
        color: white;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="header"><h1>📦 Sistema Inteligente de Cubagem 4.0</h1></div>', unsafe_allow_html=True)
    
    with st.expander("⚙️ Configurações da Carreta", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            c = st.number_input("Comprimento (m)", 1.0, 30.0, 13.6)
            l = st.number_input("Largura (m)", 1.0, 3.0, 2.45)
        with col2:
            a = st.number_input("Altura (m)", 1.0, 4.0, 2.5)
            trailer = Trailer(c, l, a)
    
    with st.expander("📤 Upload de Arquivos", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            car_file = st.file_uploader("Carregamento (.xlsx)", type="xlsx")
        with col2:
            med_file = st.file_uploader("Medidas (.xlsx)", type="xlsx")
    
    if st.button("▶️ Executar Simulação", use_container_width=True):
        if not (car_file and med_file):
            st.error("Selecione ambos os arquivos para continuar")
            return
            
        with st.spinner("Processando dados..."):
            try:
                merged, missing = load_files(car_file, med_file)
                groups = expand_grouped(merged)
                
                placed, unplaced = pack_grouped(trailer, groups)
                
                vol_total = trailer.volume
                vol_usado = sum(b.volume for b in placed)
                perc_ocup = (vol_usado / vol_total) * 100
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(f"""
                    <div class="metric-card">
                        <h3>💼 Cubagem</h3>
                        <p style="font-size: 24px">{vol_usado:.1f}m³ / {vol_total:.1f}m³</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"""
                    <div class="metric-card">
                        <h3>📊 Ocupação</h3>
                        <p style="font-size: 24px; color: {"#2ecc71" if perc_ocup > 85 else "#e74c3c"}">{perc_ocup:.1f}%</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col3:
                    status_text = "💯 Carregamento Completo" if not unplaced else f"⚠️ {len(unplaced)} volumes não alocados"
                    st.markdown(f"""
                    <div class="metric-card">
                        <h3>🔄 Status</h3>
                        <p style="font-size: 24px">{status_text}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with st.expander("🎯 Visualização 3D Interativa", expanded=True):
                    col_v1, col_v2 = st.columns([3, 1])
                    with col_v1:
                        with _lock:
                            elev = st.slider("Ângulo Vertical", 0, 90, 25, key='elev')
                            azim = st.slider("Ângulo Horizontal", -180, 180, -60, key='azim')
                            fig = plot_3d(trailer, placed, elev, azim)
                            st.pyplot(fig)
                    
                    with col_v2:
                        st.markdown("**Legenda de Cores**")
                        skus = list(set(["-".join(b.id.split('-')[:-1]) for b in placed]))
                        cmap = cm.get_cmap('tab20')
                        for i, sku in enumerate(skus):
                            st.color_picker(sku, value=cmap(i % 20), disabled=True)
                
                if missing.shape[0] > 0:
                    with st.expander("⚠️ SKUs com Dados Incompletos"):
                        st.dataframe(missing[['COD SKU']].drop_duplicates())
                    
            except Exception as e:
                st.error(f"Erro durante o processamento: {str(e)}")

if __name__ == "__main__":
    main()




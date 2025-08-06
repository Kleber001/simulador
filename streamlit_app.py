import math
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from typing import List, Tuple, Dict

class Box:
    def __init__(self, sku: str, c: float, l: float, a: float):
        self.id = sku
        self.c = c  # comprimento
        self.l = l  # largura
        self.a = a  # altura
        self.pos: Tuple[float, float, float] | None = None

    def orientations(self):
        """Retorna todas as rotações possíveis na base"""
        return [(self.c, self.l), (self.l, self.c)]

    @property
    def volume(self):
        return self.c * self.l * self.a

class Trailer:
    def __init__(self, c: float, l: float, a: float):
        self.c = c  # comprimento total
        self.l = l  # largura interna
        self.a = a  # altura máxima

    @property
    def volume(self):
        return self.c * self.l * self.a

class SkylineLayer:
    def __init__(self, C: float, L: float):
        self.C = C  # comprimento do trailer
        self.L = L  # largura do trailer
        self.sky = [(0.0, 0.0, C)]  # lista de espaços disponíveis

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

def load_files(car_file, med_file):
    car = pd.read_excel(car_file, engine='openpyxl')
    med = pd.read_excel(med_file, engine='openpyxl')

    med['KEY'] = med.apply(
        lambda r: f"{r['COD FAMILIA']}-{r['COD TAMANHO']}-{int(r['QMM'])}", 
        axis=1
    )
    
    car['KEY'] = car.apply(
        lambda r: f"{r['COD SKU'].split('-')[0]}-{r['COD SKU'].split('-')[2]}-{r['QMM']}", 
        axis=1
    )

    merged = car.merge(
        med[['KEY', 'ALTURA', 'LARGURA', 'COMPRIMENTO']],
        on='KEY',
        how='left'
    )
    missing = merged[merged['ALTURA'].isna()]
    merged = merged.dropna(subset=['ALTURA'])
    
    return merged, missing

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

def plot_3d(trailer, boxes, elev=25, azim=-60):
    fig = plt.figure(figsize=(12, 7))
    ax = fig.add_subplot(111, projection='3d')
    
    ax.set_box_aspect((trailer.c, trailer.l, trailer.a))
    ax.set_xlim(0, trailer.c)
    ax.set_ylim(0, trailer.l)
    ax.set_zlim(0, trailer.a)
    
    ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel('Comprimento (m)')
    ax.set_ylabel('Largura (m)')
    ax.set_zlabel('Altura (m)')
    
    cmap = plt.cm.get_cmap('tab20')
    sku_colors = {}
    skus = list(set([b.id.split('-')[0] for b in boxes]))
    
    for i, sku in enumerate(skus):
        sku_colors[sku] = cmap(i % 20)
    
    for box in boxes:
        sku = box.id.split('-')[0]
        color = sku_colors[sku]
        x, y, z = box.pos
        dx, dy = box.c, box.l
        dz = box.a
        
        faces = [
            [(x, y, z), (x+dx, y, z), (x+dx, y+dy, z), (x, y+dy, z)],
            [(x, y, z+dz), (x+dx, y, z+dz), (x+dx, y+dy, z+dz), (x, y+dy, z+dz)],
            [(x, y, z), (x+dx, y, z), (x+dx, y, z+dz), (x, y, z+dz)],
            [(x, y+dy, z), (x+dx, y+dy, z), (x+dx, y+dy, z+dz), (x, y+dy, z+dz)],
            [(x, y, z), (x, y+dy, z), (x, y+dy, z+dz), (x, y, z+dz)],
            [(x+dx, y, z), (x+dx, y+dy, z), (x+dx, y+dy, z+dz), (x+dx, y, z+dz)]
        ]
        
        poly = Poly3DCollection(
            faces,
            facecolors=color,
            edgecolors='k',
            linewidths=0.3,
            alpha=0.85
        )
        ax.add_collection3d(poly)
    
    return fig

def main():
    st.set_page_config(
        page_title="Simulador de Cubagem 3D",
        layout="wide",
        page_icon="🚚"
    )
    
    st.markdown("""
    <style>
    .header {
        background: #2c3e50;
        padding: 2rem;
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .metric-card {
        padding: 1.5rem;
        border-radius: 10px;
        background: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="header"><h1>📦 Simulador de Cubagem 3D Inteligente</h1></div>', unsafe_allow_html=True)
    
    # Entrada de dados
    with st.expander("⚙️ Configurações do Veículo", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            c = st.number_input("Comprimento (m)", 5.0, 30.0, 13.6)
            l = st.number_input("Largura (m)", 1.5, 3.0, 2.45)
        with col2:
            a = st.number_input("Altura (m)", 1.5, 4.0, 2.5)
            trailer = Trailer(c, l, a)
    
    # Upload de arquivos
    with st.expander("📁 Upload de Arquivos", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            car_file = st.file_uploader("Arquivo de Carregamento (.xlsx)", type="xlsx")
        with col2:
            med_file = st.file_uploader("Arquivo de Medidas (.xlsx)", type="xlsx")
    
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
                perc_ocup = round((vol_usado / vol_total) * 100, 1) if vol_total > 0 else 0
                
                # Métricas
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(f"""
                    <div class="metric-card">
                        <h3>📦 Volume Utilizado</h3>
                        <p>{vol_usado:,.1f}m³ / {vol_total:,.1f}m³</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"""
                    <div class="metric-card">
                        <h3>📈 Taxa de Ocupação</h3>
                        <p style="color: {"#27ae60" if perc_ocup > 85 else "#e74c3c"}">{perc_ocup}%</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col3:
                    status = "✅ Completo" if not unplaced else f"⚠️ {len(unplaced)} não alocados"
                    st.markdown(f"""
                    <div class="metric-card">
                        <h3>🔄 Status</h3>
                        <p>{status}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Visualização 3D
                with st.expander("🎯 Visualização 3D", expanded=True):
                    col_viz, col_cont = st.columns([3, 1])
                    with col_viz:
                        elev = st.slider("Ângulo Vertical", 0, 90, 25, key='elev')
                        azim = st.slider("Ângulo Horizontal", -180, 180, -60, key='azim')
                        fig = plot_3d(trailer, placed, elev, azim)
                        st.pyplot(fig)
            
            except Exception as e:
                st.error(f"Erro durante o processamento: {str(e)}")

if __name__ == "__main__":
    main()





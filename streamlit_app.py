import math
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from typing import List, Tuple, Dict
from itertools import permutations
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

class Box:
    def __init__(self, sku: str, c: float, l: float, a: float):
        self.id = sku
        self.original_dim = (c, l, a)
        self.pos: Tuple[float, float, float] = None
        self.current_orientation = (c, l, a)
        
    def get_orientations(self, allowed_rotations: List[str]):
        orientations = []
        if 'height' in allowed_rotations:
            orientations += list(permutations([self.original_dim[0], self.original_dim[1], self.original_dim[2]]))
        if 'width' in allowed_rotations:
            orientations += list(permutations([self.original_dim[1], self.original_dim[0], self.original_dim[2]]))
        if 'length' in allowed_rotations:
            orientations += list(permutations([self.original_dim[2], self.original_dim[1], self.original_dim[0]]))
        return list(set(orientations))

    @property
    def dimensions(self):
        return self.current_orientation
    
    @property
    def volume(self):
        return math.prod(self.original_dim)

class Trailer:
    def __init__(self, c: float, l: float, a: float):
        self.c = c
        self.l = l
        self.a = a
        
    @property
    def volume(self):
        return self.c * self.l * self.a

class SkylineLayer:
    def __init__(self, width: float, depth: float):
        self.width = width
        self.depth = depth
        self.skyline = [(0.0, 0.0, width)]
        
    def place_box(self, box_width: float, box_depth: float):
        for i, (x, y, avail_width) in enumerate(self.skyline):
            if box_width <= avail_width and (y + box_depth) <= self.depth:
                self.skyline[i] = (x + box_width, y, avail_width - box_width)
                self.skyline.append((x, y + box_depth, box_width))
                return True, (x, y)
        return False, None

def pack_boxes(trailer: Trailer, sku_groups: List[List[Box]], allowed_rotations: List[str]):
    placed = []
    unplaced = []
    z_level = 0.0
    current_layer_height = 0.0
    
    layer = SkylineLayer(trailer.c, trailer.l)
    
    for group_idx, group in enumerate(sku_groups):
        group = sorted(group, key=lambda x: math.prod(x.original_dim), reverse=True)
        
        idx = 0
        while idx < len(group):
            box = group[idx]
            best_fit = None
            best_orientation = None
            
            for orientation in box.get_orientations(allowed_rotations):
                w, d, h = orientation
                success, pos = layer.place_box(w, d)
                
                if success:
                    total_height = z_level + max(current_layer_height, h)
                    if total_height <= trailer.a:
                        if best_fit is None or total_height < best_fit[2]:
                            best_fit = (*pos, z_level)
                            best_orientation = orientation
            
            if best_fit:
                box.current_orientation = best_orientation
                box.pos = best_fit
                placed.append(box)
                current_layer_height = max(current_layer_height, best_orientation[2])
                idx += 1
            else:
                if current_layer_height == 0:
                    unplaced.extend(group[idx:])
                    break
                
                z_level += current_layer_height
                if z_level > trailer.a:
                    unplaced.extend(group[idx:])
                    for remaining in sku_groups[group_idx + 1:]:
                        unplaced.extend(remaining)
                    return placed, unplaced
                
                layer = SkylineLayer(trailer.c, trailer.l)
                current_layer_height = 0.0
                
    return placed, unplaced

def create_visualizations(trailer, boxes):
    fig = plt.figure(figsize=(20, 15))
    
    # 3D Perspective
    ax1 = fig.add_subplot(221, projection='3d')
    ax1.set_title('Perspectiva 3D')
    ax1.view_init(elev=25, azim=-60)
    
    # Top View
    ax2 = fig.add_subplot(222, projection='3d')
    ax2.set_title('Vista Superior')
    ax2.view_init(elev=90, azim=-90)
    
    # Side View
    ax3 = fig.add_subplot(223, projection='3d')
    ax3.set_title('Vista Lateral')
    ax3.view_init(elev=0, azim=-90)
    
    # Front View
    ax4 = fig.add_subplot(224, projection='3d')
    ax4.set_title('Vista Frontal')
    ax4.view_init(elev=0, azim=0)
    
    axes = [ax1, ax2, ax3, ax4]
    colors = cm.get_cmap('tab20', len(boxes))
    
    for ax in axes:
        ax.set_box_aspect([trailer.c, trailer.l, trailer.a])
        ax.set_xlim(0, trailer.c)
        ax.set_ylim(0, trailer.l)
        ax.set_zlim(0, trailer.a)
        ax.set_xlabel('Comprimento (m)')
        ax.set_ylabel('Largura (m)')
        ax.set_zlabel('Altura (m)')
        
        for i, box in enumerate(boxes):
            x, y, z = box.pos
            w, d, h = box.dimensions
            
            faces = [
                [[x, y, z], [x+w, y, z], [x+w, y+d, z], [x, y+d, z]],
                [[x, y, z+h], [x+w, y, z+h], [x+w, y+d, z+h], [x, y+d, z+h]],
                [[x, y, z], [x+w, y, z], [x+w, y, z+h], [x, y, z+h]],
                [[x, y+d, z], [x+w, y+d, z], [x+w, y+d, z+h], [x, y+d, z+h]],
                [[x, y, z], [x, y+d, z], [x, y+d, z+h], [x, y, z+h]],
                [[x+w, y, z], [x+w, y+d, z], [x+w, y+d, z+h], [x+w, y, z+h]],
            ]
            
            ax.add_collection3d(Poly3DCollection(faces, 
                facecolors=colors(i % 20), 
                edgecolors='k', 
                linewidths=0.3,
                alpha=0.8))

    plt.tight_layout()
    return fig

def main():
    st.set_page_config(
        page_title="Sistema de Cubagem 4.0",
        layout="wide",
        page_icon="📦"
    )
    
    st.title("📦 Sistema Avançado de Cubagem 3D")
    
    with st.sidebar:
        st.header("Configurações de Rotação")
        rotations = st.multiselect(
            'Eixos de Rotação Permitidos:',
            ['Comprimento', 'Largura', 'Altura'],
            ['Comprimento', 'Largura']
        )
        
        st.header("Dimensões da Carreta")
        length = st.number_input("Comprimento (m)", 5.0, 30.0, 13.6)
        width = st.number_input("Largura (m)", 1.5, 3.0, 2.45)
        height = st.number_input("Altura (m)", 1.5, 4.0, 2.5)
        
        st.header("Upload de Arquivos")
        car_file = st.file_uploader("Arquivo de Carregamento", type="xlsx")
        med_file = st.file_uploader("Arquivo de Medidas", type="xlsx")
    
    if st.button("Executar Simulação", type="primary"):
        if not (car_file and med_file):
            st.error("Selecione ambos os arquivos!")
            return
            
        with st.spinner("Processando..."):
            try:
                # Carregar e processar dados
                trailer = Trailer(length, width, height)
                merged, missing = load_files(car_file, med_file)
                sku_groups = expand_grouped(merged)
                
                # Empacotamento com rotações selecionadas
                allowed_rot = [r.lower()[:3] for r in rotations]
                placed, unplaced = pack_boxes(trailer, sku_groups, allowed_rot)
                
                # Métricas
                used_vol = sum(b.volume for b in placed)
                total_vol = trailer.volume
                efficiency = (used_vol / total_vol) * 100 if total_vol > 0 else 0
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Volume Utilizado", f"{used_vol:.1f}m³")
                col2.metric("Eficiência", f"{efficiency:.1f}%")
                col3.metric("Volumes Não Alocados", len(unplaced))
                
                # Visualizações
                st.subheader("Visualizações Multidimensionais")
                fig = create_visualizations(trailer, placed)
                st.pyplot(fig)
                
                # Dados problemáticos
                if len(unplaced) > 0 or not missing.empty:
                    with st.expander("Detalhes de Problemas", expanded=True):
                        tab1, tab2 = st.tabs(["Não Alocados", "Sem Medidas"])
                        with tab1:
                            st.write(pd.DataFrame({
                                "SKU": [b.id.split('-')[0] for b in unplaced],
                                "Quantidade": len(unplaced) * [1]
                            }).groupby("SKU").count())
                        with tab2:
                            st.write(missing[['COD SKU']].drop_duplicates())
                
            except Exception as e:
                st.error(f"Erro: {str(e)}")

def load_files(car_file, med_file):
    car = pd.read_excel(car_file)
    med = pd.read_excel(med_file)
    
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
    return merged.dropna(), missing

def expand_grouped(df):
    groups = {}
    for _, row in df.iterrows():
        sku = row['COD SKU']
        if sku not in groups:
            groups[sku] = []
        qmm = row['QMM']
        if pd.notna(qmm) and qmm > 0:
            qtd = math.ceil(row['QTDE'] / qmm)
            for i in range(qtd):
                groups[sku].append(Box(
                    f"{sku}-{i+1}",
                    row['COMPRIMENTO'],
                    row['LARGURA'],
                    row['ALTURA']
                ))
    return [v for v in groups.values()]

if __name__ == "__main__":
    main()


import math
import streamlit as st
from typing import Dict, List, Tuple, Optional
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

# ========================== CLASSES PRINCIPAIS ==========================
class Box:
    def __init__(self, sku: str, c: float, l: float, a: float):
        self.id = sku
        self.c = c  # Comprimento
        self.l = l  # Largura
        self.a = a  # Altura
        self.pos: Optional[Tuple[float, float, float]] = None

    @property
    def volume(self):
        return self.c * self.l * self.a

class Trailer:
    def __init__(self, c: float, l: float, a: float):
        self.c = c  # Comprimento
        self.l = l  # Largura
        self.a = a  # Altura
    
    @property
    def volume(self):
        return self.c * self.l * self.a

class SkylineLayer:
    def __init__(self, C: float, L: float):
        self.C = C  # Comprimento máximo
        self.L = L  # Largura máxima
        self.sky = [(0.0, 0.0, C)]  # (x_initial, y_initial, available_length)

# ========================== PROCESSAMENTO DE DADOS ==========================
def safe_sku_split(sku: str) -> List[str]:
    return sku.split('-') if isinstance(sku, str) else []

def validate_columns(df: pd.DataFrame, required: List[str]) -> bool:
    missing = [col for col in required if col not in df.columns]
    if missing:
        st.error(f"Colunas obrigatórias ausentes: {', '.join(missing)}")
        return False
    return True

def create_key(row, is_med: bool = False) -> Optional[str]:
    try:
        if is_med:
            components = [
                str(row["COD FAMILIA"]) if pd.notna(row["COD FAMILIA"]) else "ND",
                str(row["COD TAMANHO"]) if pd.notna(row["COD TAMANHO"]) else "ND",
                str(int(row["QMM"]))
            ]
        else:
            sku = str(row["COD SKU"]) if pd.notna(row["COD SKU"]) else "ND-ND-ND"
            parts = safe_sku_split(sku)
            components = [
                parts[0] if len(parts) > 0 else "ND",
                parts[2] if len(parts) >= 3 else "ND",
                str(int(row["QMM"]))
            ]
        return "-".join(components)
    except Exception as e:
        st.error(f"Erro ao criar chave: {str(e)}")
        return None

def load_files(car_file, med_file):
    try:
        car = pd.read_excel(car_file, engine='openpyxl')
        med = pd.read_excel(med_file, engine='openpyxl')

        if not validate_columns(car, ["COD SKU", "QMM", "QTDE"]):
            return pd.DataFrame(), pd.DataFrame()
        if not validate_columns(med, ["COD FAMILIA", "COD TAMANHO", "ALTURA", "LARGURA", "COMPRIMENTO"]):
            return pd.DataFrame(), pd.DataFrame()

        med["KEY"] = med.apply(lambda r: create_key(r, True), axis=1)
        car["KEY"] = car.apply(create_key, axis=1)

        merged = car.merge(
            med[["KEY", "ALTURA", "LARGURA", "COMPRIMENTO"]],
            on="KEY",
            how="left"
        )
        missing = merged[merged["ALTURA"].isna()]
        valid = merged.dropna(subset=["ALTURA"])
        
        return valid, missing
    except Exception as e:
        st.error(f"Erro crítico na carga de dados: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

def expand_grouped(df: pd.DataFrame) -> List[List[Box]]:
    groups = {}
    for _, row in df.iterrows():
        try:
            sku = row["COD SKU"] or "DESCONHECIDO"
            qmm = int(row["QMM"])
            qtde = int(row["QTDE"])
            num_boxes = math.ceil(qtde / qmm)
            
            if sku not in groups:
                groups[sku] = []
            
            groups[sku].extend([
                Box(f"{sku}-{i}", 
                    row["COMPRIMENTO"], 
                    row["LARGURA"], 
                    row["ALTURA"])
                for i in range(1, num_boxes + 1)
            ])
        except:
            continue
    return list(groups.values())

# ========================== ALGORITMO DE EMPACOTAMENTO ==========================
def pack_grouped(trailer: Trailer, groups: List[List[Box]]):
    placed = []
    unplaced = []
    z = 0.0
    current_layer = SkylineLayer(trailer.c, trailer.l)
    current_height = 0.0

    for group in groups:
        for box in group:
            placed_flag = False
            for orientation in [(box.c, box.l), (box.l, box.c)]:
                for idx, (x, y, available) in enumerate(current_layer.sky):
                    w, d = orientation
                    if w <= available and y + d <= current_layer.L:
                        # Atualiza skyline
                        current_layer.sky[idx] = (x + w, y, available - w)
                        current_layer.sky.append((x, y + d, w))
                        # Define posição da caixa
                        box.pos = (x, y, z)
                        placed.append(box)
                        current_height = max(current_height, box.a)
                        placed_flag = True
                        break
                if placed_flag:
                    break
            if not placed_flag:
                if current_height == 0:
                    unplaced.append(box)
                else:
                    z += current_height
                    if z > trailer.a:
                        unplaced.append(box)
                        unplaced.extend([b for g in groups[groups.index(group)+1:] for b in g])
                        return placed, unplaced
                    current_layer = SkylineLayer(trailer.c, trailer.l)
                    current_height = 0.0
    return placed, unplaced

# ========================== VISUALIZAÇÃO 3D ==========================
def create_cube_edges(x, y, z, dx, dy, dz):
    return [
        ((x, y, z), (x+dx, y, z)),
        ((x+dx, y, z), (x+dx, y+dy, z)),
        ((x+dx, y+dy, z), (x, y+dy, z)),
        ((x, y+dy, z), (x, y, z)),
        ((x, y, z+dz), (x+dx, y, z+dz)),
        ((x+dx, y, z+dz), (x+dx, y+dy, z+dz)),
        ((x+dx, y+dy, z+dz), (x, y+dy, z+dz)),
        ((x, y+dy, z+dz), (x, y, z+dz)),
        ((x, y, z), (x, y, z+dz)),
        ((x+dx, y, z), (x+dx, y, z+dz)),
        ((x+dx, y+dy, z), (x+dx, y+dy, z+dz)),
        ((x, y+dy, z), (x, y+dy, z+dz)),
    ]

def create_3d_view(trailer: Trailer, boxes: List[Box], elev: float, azim: float):
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    # Configurar proporção real
    ax.set_box_aspect([trailer.c, trailer.l, trailer.a])
    ax.set_xlim(0, trailer.c)
    ax.set_ylim(0, trailer.l)
    ax.set_zlim(0, trailer.a)
    
    # Adicionar trailer
    ax.add_collection3d(Line3DCollection(
        create_cube_edges(0, 0, 0, trailer.c, trailer.l, trailer.a),
        colors='#404040',
        linewidths=1.5
    ))
    
    # Adicionar caixas
    cmap = plt.get_cmap('tab20')
    colors = {}
    for box in boxes:
        sku_base = box.id.split('-')[0]
        if sku_base not in colors:
            colors[sku_base] = cmap(len(colors) % 20)
        
        x, y, z = box.pos
        verts = [
            [(x, y, z), (x+box.c, y, z), (x+box.c, y+box.l, z), (x, y+box.l, z)],
            [(x, y, z+box.a), (x+box.c, y, z+box.a), (x+box.c, y+box.l, z+box.a), (x, y+box.l, z+box.a)],
            [(x, y, z), (x+box.c, y, z), (x+box.c, y, z+box.a), (x, y, z+box.a)],
            [(x+box.c, y, z), (x+box.c, y+box.l, z), (x+box.c, y+box.l, z+box.a), (x+box.c, y, z+box.a)],
            [(x, y+box.l, z), (x, y+box.l, z+box.a), (x+box.c, y+box.l, z+box.a), (x+box.c, y+box.l, z)],
            [(x, y, z), (x, y, z+box.a), (x, y+box.l, z+box.a), (x, y+box.l, z)]
        ]
        ax.add_collection3d(Poly3DCollection(
            verts,
            facecolors=colors[sku_base],
            edgecolors='k',
            alpha=0.9,
            linewidths=0.5
        ))
    
    ax.view_init(elev=elev, azim=azim)
    ax.set_title(f"Visualização 3D Proporcional\nCubagem Total: {trailer.volume:.2f}m³", pad=20)
    ax.set_xlabel('Comprimento (m)')
    ax.set_ylabel('Largura (m)')
    ax.set_zlabel('Altura (m)')
    return fig

# ========================== INTERFACE STREAMLIT ==========================
def main():
    st.set_page_config(
        page_title="Otimizador de Carga 3D Pro",
        layout="wide",
        page_icon="🚚"
    )
    
    st.title("Sistema Inteligente de Otimização de Carga")
    
    with st.sidebar:
        st.header("Configurações do Veículo")
        c = st.number_input("Comprimento (m)", 1.0, 20.0, 13.6)
        l = st.number_input("Largura (m)", 1.0, 3.0, 2.45)
        a = st.number_input("Altura (m)", 1.0, 3.0, 2.9)
        st.markdown(f"**Cubagem Total:** {c*l*a:.2f}m³")
        
        st.header("Upload de Arquivos")
        car_file = st.file_uploader("Planejamento de Carga", type="xlsx")
        med_file = st.file_uploader("Tabela de Medidas", type="xlsx")
    
    if car_file and med_file:
        with st.spinner("Processando dados..."):
            try:
                merged, missing = load_files(car_file, med_file)
                if merged.empty:
                    st.warning("Não há dados válidos para processar")
                    return
                
                trailer = Trailer(c, l, a)
                groups = expand_grouped(merged)
                placed, unplaced = pack_grouped(trailer, groups)
                
                st.header("Resultados da Simulação")
                
                # Métricas
                cols = st.columns(5)
                cols[0].metric("Cubagem Total", f"{trailer.volume:.2f}m³")
                cols[1].metric("Ocupação", f"{(sum(b.volume for b in placed)/trailer.volume*100):.1f}%")
                cols[2].metric("Caixas Posicionadas", len(placed))
                cols[3].metric("Espaço Residual", f"{trailer.volume - sum(b.volume for b in placed):.2f}m³")
                cols[4].metric("Não Alocados", len(unplaced), delta_color="inverse" if unplaced else "off")
                
                # Visualização 3D
                tab1, tab2, tab3 = st.tabs(["Visão 3D", "Visão Superior", "Visão Lateral"])
                with tab1:
                    fig = create_3d_view(trailer, placed, 25, -45)
                    st.pyplot(fig)
                with tab2:
                    fig = create_3d_view(trailer, placed, 90, -90)
                    st.pyplot(fig)
                with tab3:
                    fig = create_3d_view(trailer, placed, 0, 0)
                    st.pyplot(fig)
                
                # Detalhes não alocados
                if unplaced:
                    with st.expander("Detalhes dos Itens Não Alocados"):
                        st.error(f"{len(unplaced)} volumes não puderam ser posicionados!")
                        unplaced_stats = pd.DataFrame({
                            "SKU": [b.id.split('-')[0] for b in unplaced],
                            "Comprimento": [b.c for b in unplaced],
                            "Largura": [b.l for b in unplaced],
                            "Altura": [b.a for b in unplaced]
                        })
                        st.dataframe(unplaced_stats.groupby("SKU").agg({
                            "Comprimento": "mean",
                            "Largura": "mean",
                            "Altura": "mean"
                        }).style.format("{:.2f}"))
                
            except Exception as e:
                st.error(f"Erro na simulação: {str(e)}")
    else:
        st.info("Faça upload dos arquivos na barra lateral para iniciar")

if __name__ == "__main__":
    main()

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

# ========================== FUNÇÕES DE PROCESSAMENTO ==========================
def load_files(car_file, med_file):
    try:
        car = pd.read_excel(car_file, engine='openpyxl')
        med = pd.read_excel(med_file, engine='openpyxl')

        required_car = ["COD SKU", "QMM", "QTDE"]
        required_med = ["COD FAMILIA", "COD TAMANHO", "ALTURA", "LARGURA", "COMPRIMENTO"]
        
        for col in required_car:
            if col not in car.columns:
                st.error(f"Coluna obrigatória ausente no arquivo de carga: {col}")
                return pd.DataFrame(), pd.DataFrame()
                
        for col in required_med:
            if col not in med.columns:
                st.error(f"Coluna obrigatória ausente no arquivo de medidas: {col}")
                return pd.DataFrame(), pd.DataFrame()

        med["KEY"] = med.apply(lambda r: f"{r['COD FAMILIA']}-{r['COD TAMANHO']}-{int(r['QMM'])}", axis=1)
        car["KEY"] = car.apply(lambda r: f"{r['COD SKU'].split('-')[0]}-{r['COD SKU'].split('-')[2]}-{int(r['QMM'])}", axis=1)

        merged = car.merge(
            med[["KEY", "ALTURA", "LARGURA", "COMPRIMENTO"]],
            on="KEY",
            how="left"
        )
        missing = merged[merged["ALTURA"].isna()]
        valid = merged.dropna(subset=["ALTURA"])
        
        return valid, missing
    except Exception as e:
        st.error(f"Erro na carga de dados: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

def expand_grouped(df: pd.DataFrame) -> List[List[Box]]:
    groups = {}
    for _, row in df.iterrows():
        try:
            sku = row["COD SKU"]
            qmm = int(row["QMM"])
            qtde = int(row["QTDE"])
            num_boxes = math.ceil(qtde / qmm)
            
            if sku not in groups:
                groups[sku] = []
            
            groups[sku].extend([
                Box(f"{sku}-{i+1}", 
                    row["COMPRIMENTO"], 
                    row["LARGURA"], 
                    row["ALTURA"])
                for i in range(num_boxes)
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
                        current_layer.sky[idx] = (x + w, y, available - w)
                        current_layer.sky.append((x, y + d, w))
                        box.pos = (x, y, z)
                        placed.append(box)
                        current_height = max(current_height, box.a)
                        placed_flag = True
                        break
                if placed_flag:
                    break
            if not placed_flag:
                if z + current_height + box.a > trailer.a:
                    unplaced.append(box)
                    unplaced.extend([b for g in groups[groups.index(group)+1:] for b in g])
                    return placed, unplaced
                else:
                    z += current_height
                    current_layer = SkylineLayer(trailer.c, trailer.l)
                    current_height = box.a
                    current_layer.sky = [(0.0, 0.0, trailer.c)]
                    box.pos = (0, 0, z)
                    placed.append(box)
    return placed, unplaced

# ========================== VISUALIZAÇÃO 3D ==========================
def create_cube_edges(x, y, z, dx, dy, dz):
    return [
        [(x, y, z), (x+dx, y, z)],
        [(x+dx, y, z), (x+dx, y+dy, z)],
        [(x+dx, y+dy, z), (x, y+dy, z)],
        [(x, y+dy, z), (x, y, z)],
        [(x, y, z), (x, y, z+dz)],
        [(x+dx, y, z), (x+dx, y, z+dz)],
        [(x+dx, y+dy, z), (x+dx, y+dy, z+dz)],
        [(x, y+dy, z), (x, y+dy, z+dz)],
        [(x, y, z+dz), (x+dx, y, z+dz)],
        [(x+dx, y, z+dz), (x+dx, y+dy, z+dz)],
        [(x+dx, y+dy, z+dz), (x, y+dy, z+dz)],
        [(x, y+dy, z+dz), (x, y, z+dz)],
    ]

def create_3d_view(trailer: Trailer, boxes: List[Box], elev: float, azim: float):
    fig = plt.figure(figsize=(12, 7))
    ax = fig.add_subplot(111, projection='3d')
    
    # Configurar proporções reais
    ax.set_box_aspect([trailer.c, trailer.l, trailer.a])
    ax.set_xlim(0, trailer.c)
    ax.set_ylim(0, trailer.l)
    ax.set_zlim(0, trailer.a)
    
    # Adicionar contorno do trailer
    ax.add_collection3d(Line3DCollection(
        create_cube_edges(0, 0, 0, trailer.c, trailer.l, trailer.a),
        colors='#404040',
        linewidths=1.2
    ))
    
    # Adicionar caixas com cores por SKU
    color_map = {}
    for box in boxes:
        if box.pos:
            sku_base = box.id.split('-')[0]
            if sku_base not in color_map:
                color_map[sku_base] = plt.cm.tab20(len(color_map) % 20)
            
            x, y, z = box.pos
            verts = [
                [(x, y, z), (x+box.c, y, z), (x+box.c, y+box.l, z), (x, y+box.l, z)],
                [(x, y, z), (x, y, z+box.a), (x+box.c, y, z+box.a), (x+box.c, y, z)],
                [(x+box.c, y, z), (x+box.c, y, z+box.a), (x+box.c, y+box.l, z+box.a), (x+box.c, y+box.l, z)],
                [(x+box.c, y+box.l, z), (x, y+box.l, z), (x, y+box.l, z+box.a), (x+box.c, y+box.l, z+box.a)],
                [(x, y, z+box.a), (x+box.c, y, z+box.a), (x+box.c, y+box.l, z+box.a), (x, y+box.l, z+box.a)],
                [(x, y+box.l, z), (x, y+box.l, z+box.a), (x, y, z+box.a), (x, y, z)]
            ]
            ax.add_collection3d(Poly3DCollection(
                verts,
                facecolors=color_map[sku_base],
                edgecolors='k',
                alpha=0.9,
                linewidths=0.5
            ))
    
    ax.view_init(elev=elev, azim=azim)
    ax.set_title(f"Visualização 3D - Cubagem Total: {trailer.volume:.2f}m³", pad=20)
    ax.set_xlabel('Comprimento (m)')
    ax.set_ylabel('Largura (m)')
    ax.set_zlabel('Altura (m)')
    return fig

# ========================== INTERFACE PRINCIPAL ==========================
def main():
    st.set_page_config(
        page_title="Otimizador de Carga 3D Pro",
        layout="wide",
        page_icon="🚚"
    )
    
    st.title("Sistema Inteligente de Otimização de Carga")
    
    with st.sidebar:
        st.header("Configurações do Veículo")
        cols = st.columns(3)
        with cols[0]: c = st.number_input("Comprimento (m)", 1.0, 20.0, 13.6)
        with cols[1]: l = st.number_input("Largura (m)", 1.0, 3.0, 2.45)
        with cols[2]: a = st.number_input("Altura (m)", 1.0, 3.0, 2.9)
        st.markdown(f"**Cubagem Total:** {c*l*a:.2f}m³")
        
        st.header("Upload de Arquivos")
        car_file = st.file_uploader("Planejamento de Carga (.xlsx)", type="xlsx")
        med_file = st.file_uploader("Tabela de Medidas (.xlsx)", type="xlsx")
    
    if car_file and med_file:
        with st.spinner("Analisando dados e calculando melhor disposição..."):
            try:
                merged, missing = load_files(car_file, med_file)
                if merged.empty:
                    st.warning("Nenhum dado válido encontrado para processamento")
                    return
                
                trailer = Trailer(c, l, a)
                groups = expand_grouped(merged)
                placed, unplaced = pack_grouped(trailer, groups)
                
                # Seção de Métricas
                st.header("Resultados da Simulação")
                cols = st.columns(5)
                cols[0].metric("Capacidade Total", f"{trailer.volume:.2f}m³")
                cols[1].metric("Taxa de Ocupação", f"{sum(b.volume for b in placed)/trailer.volume*100:.1f}%")
                cols[2].metric("Caixas Alocadas", len(placed), "volumes")
                cols[3].metric("Espaço Livre", f"{trailer.volume - sum(b.volume for b in placed):.2f}m³")
                cols[4].metric("Não Alocados", len(unplaced), "volumes", delta_color="inverse")
                
                # Detalhes dos Não Alocados
                st.subheader("🔍 Análise Detalhada dos Não Alocados")
                if unplaced:
                    unplaced_stats = pd.DataFrame({
                        "Produto": [b.id.split('-')[0] for b in unplaced],
                        "Quantidade": [1]*len(unplaced),
                        "Comprimento (m)": [b.c for b in unplaced],
                        "Largura (m)": [b.l for b in unplaced],
                        "Altura (m)": [b.a for b in unplaced]
                    })
                    
                    grouped = unplaced_stats.groupby("Produto").agg({
                        "Quantidade": "sum",
                        "Comprimento (m)": "mean",
                        "Largura (m)": "mean",
                        "Altura (m)": "mean"
                    }).reset_index()
                    
                    st.error(f"**Atenção:** {len(unplaced)} volumes não puderam ser alocados!")
                    st.dataframe(
                        grouped.style
                        .format({
                            "Comprimento (m)": "{:.2f}",
                            "Largura (m)": "{:.2f}",
                            "Altura (m)": "{:.2f}"
                        })
                        .set_properties(**{'background-color': '#fff0f0'}),
                        column_config={
                            "Produto": st.column_config.TextColumn(width="medium"),
                            "Quantidade": st.column_config.NumberColumn(
                                "Qtd Não Alocada",
                                help="Quantidade total deste produto não alocada"
                            )
                        },
                        hide_index=True,
                        height=300
                    )
                else:
                    st.success("**Sucesso:** Todos os volumes foram alocados adequadamente!")
                
                # Visualizações 3D
                st.subheader("📐 Visualização Tridimensional")
                tab1, tab2, tab3 = st.tabs(["Perspectiva 3D", "Visão Superior", "Visão Frontal"])
                
                with tab1:
                    fig = create_3d_view(trailer, placed, 25, -45)
                    st.pyplot(fig)
                
                with tab2:
                    fig = create_3d_view(trailer, placed, 90, -90)
                    st.pyplot(fig)
                
                with tab3:
                    fig = create_3d_view(trailer, placed, 0, 0)
                    st.pyplot(fig)
                
                # Dados Faltantes
                if not missing.empty:
                    with st.expander("⚠️ Itens com Dados Incompletos"):
                        st.warning("Os seguintes itens possuem dados incompletos ou inconsistentes:")
                        st.dataframe(
                            missing[["COD SKU", "QTDE", "QMM"]],
                            column_config={
                                "COD SKU": "SKU",
                                "QTDE": "Quantidade Total",
                                "QMM": "Quantidade por Pallet"
                            }
                        )
                
            except Exception as e:
                st.error(f"Erro durante a simulação: {str(e)}")
    else:
        st.info("⤵️ Faça upload dos arquivos na barra lateral para iniciar a simulação")

if __name__ == "__main__":
    main()

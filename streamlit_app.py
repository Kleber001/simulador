import math
import streamlit as st
from typing import Dict, List, Tuple, Optional
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

# ================================= CLASSES PRINCIPAIS =================================
class Box:
    def __init__(self, sku: str, c: float, l: float, a: float):
        self.id = sku
        self.c, self.l, self.a = c, l, a
        self.pos: Optional[Tuple[float, float, float]] = None

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

# ================================= PROCESSAMENTO DE DADOS =================================
def safe_sku_split(sku: str) -> List[str]:
    return sku.split('-') if isinstance(sku, str) else []

def create_key(row, is_med: bool = False) -> Optional[str]:
    try:
        if is_med:
            familia = str(row["COD FAMILIA"]) if pd.notna(row["COD FAMILIA"]) else "ND"
            tamanho = str(row["COD TAMANHO"]) if pd.notna(row["COD TAMANHO"]) else "ND"
            qmm = int(row["QMM"])
            return f"{familia}-{tamanho}-{qmm}"
        else:
            sku = str(row["COD SKU"]) if pd.notna(row["COD SKU"]) else "ND-ND-ND"
            sku_parts = safe_sku_split(sku)
            parts = [
                sku_parts[0] if len(sku_parts) > 0 else "ND",
                sku_parts[2] if len(sku_parts) >= 3 else "ND"
            ]
            qmm = int(row["QMM"]) if pd.notna(row["QMM"]) else 0
            return f"{parts[0]}-{parts[1]}-{qmm}"
    except KeyError as e:
        st.error(f"Coluna faltante: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Erro ao criar chave: {str(e)}")
        return None

def validate_columns(df: pd.DataFrame, required: List[str]) -> bool:
    missing = [col for col in required if col not in df.columns]
    if missing:
        st.error(f"Colunas obrigatórias faltantes: {', '.join(missing)}")
        return False
    return True

def load_files(car_file, med_file):
    try:
        car = pd.read_excel(car_file, engine="openpyxl")
        med = pd.read_excel(med_file, engine="openpyxl")

        if not validate_columns(car, ["COD SKU", "QMM", "QTDE"]):
            return pd.DataFrame(), pd.DataFrame()
        if not validate_columns(med, ["COD FAMILIA", "COD TAMANHO", "ALTURA", "LARGURA", "COMPRIMENTO"]):
            return pd.DataFrame(), pd.DataFrame()

        med["KEY"] = med.apply(lambda r: create_key(r, is_med=True), axis=1)
        car["KEY"] = car.apply(create_key, axis=1)

        valid_car = car.dropna(subset=["KEY"])
        valid_med = med.dropna(subset=["KEY"])

        merged = valid_car.merge(
            valid_med[["KEY", "ALTURA", "LARGURA", "COMPRIMENTO"]],
            on="KEY",
            how="left",
        )
        
        missing = merged[merged["ALTURA"].isna()]
        merged = merged.dropna(subset=["ALTURA"])
        return merged, missing
    
    except Exception as e:
        st.error(f"Erro crítico ao carregar arquivos: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

def expand_grouped(df: pd.DataFrame) -> List[List[Box]]:
    groups: Dict[str, List[Box]] = {}
    order: List[str] = []
    
    for _, r in df.iterrows():
        try:
            sku = r["COD SKU"] if pd.notna(r["COD SKU"]) else "DESCONHECIDO"
            sku_parts = safe_sku_split(sku)
            base_sku = "-".join(sku_parts[:3]) if sku_parts else sku
            
            qmm = r["QMM"]
            if pd.isna(qmm) or qmm <= 0:
                continue
                
            qtde = r["QTDE"]
            if qtde <= 0:
                continue
                
            n = math.ceil(qtde / qmm)
            
            if sku not in groups:
                groups[sku] = []
                order.append(sku)
                
            groups[sku].extend(
                Box(f"{base_sku}-{i}", r["COMPRIMENTO"], r["LARGURA"], r["ALTURA"])
                for i in range(1, n + 1)
            )
            
        except Exception as e:
            st.error(f"Erro ao processar linha: {str(e)}")
            
    return [groups[k] for k in order if k in groups]

# ================================= ALGORITMO DE EMPACOTAMENTO =================================
def pack_grouped(trailer: Trailer, sku_groups: List[List[Box]]):
    placed: List[Box] = []
    unplaced: List[Box] = []
    
    try:
        z = 0.0
        layer = SkylineLayer(trailer.c, trailer.l)
        layer_h = 0.0

        for g_idx, group in enumerate(sku_groups):
            if not group:
                continue
                
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
                        break
                    else:
                        z += layer_h
                        if z > trailer.a:
                            unplaced.extend(group[idx:])
                            for rest in sku_groups[g_idx + 1:]:
                                unplaced.extend(rest)
                            return placed, unplaced
                        layer = SkylineLayer(trailer.c, trailer.l)
                        layer_h = 0.0
    except Exception as e:
        st.error(f"Erro durante empacotamento: {str(e)}")
    
    return placed, unplaced

# ================================= VISUALIZAÇÃO 3D =================================
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

def add_box_to_plot(ax, box, color):
    try:
        x, y, z = box.pos
        faces = [
            [(x, y, z), (x+box.c, y, z), (x+box.c, y+box.l, z), (x, y+box.l, z)],
            [(x, y, z+box.a), (x+box.c, y, z+box.a), (x+box.c, y+box.l, z+box.a), (x, y+box.l, z+box.a)],
            [(x, y, z), (x+box.c, y, z), (x+box.c, y, z+box.a), (x, y, z+box.a)],
            [(x+box.c, y, z), (x+box.c, y+box.l, z), (x+box.c, y+box.l, z+box.a), (x+box.c, y, z+box.a)],
            [(x, y+box.l, z), (x, y+box.l, z+box.a), (x+box.c, y+box.l, z+box.a), (x+box.c, y+box.l, z)],
            [(x, y, z), (x, y, z+box.a), (x, y+box.l, z+box.a), (x, y+box.l, z)],
        ]
        ax.add_collection3d(
            Poly3DCollection(faces, facecolors=color, edgecolors="k", linewidths=0.3, alpha=0.85)
        )
    except Exception as e:
        st.error(f"Erro ao renderizar caixa: {str(e)}")

# ================================= INTERFACE STREAMLIT =================================
def setup_interface():
    st.set_page_config(
        page_title="Otimizador de Carga 3D Pro",
        layout="wide",
        page_icon="🚛"
    )
    st.title("Sistema Inteligente de Otimização Logística")
    
    with st.sidebar:
        st.header("Configuração do Veículo")
        cols = st.columns(3)
        with cols[0]: c = st.number_input("Comprimento (m)", 1.0, 20.0, 13.6)
        with cols[1]: l = st.number_input("Largura (m)", 1.0, 5.0, 2.45)
        with cols[2]: a = st.number_input("Altura (m)", 1.0, 5.0, 2.9)
        
        st.divider()
        st.header("Upload de Arquivos")
        car_file = st.file_uploader("Planilha de Carregamento (.xlsx)", type="xlsx")
        med_file = st.file_uploader("Tabela de Medidas (.xlsx)", type="xlsx")
        
    return c, l, a, car_file, med_file

def create_3d_view(trailer, boxes, ax, elev, azim, title):
    """Cria uma visualização 3D com configurações específicas"""
    ax.clear()
    ax.set_xlim(0, trailer.c)
    ax.set_ylim(0, trailer.l)
    ax.set_zlim(0, trailer.a)
    ax.set_title(title, pad=15)
    ax.view_init(elev=elev, azim=azim)
    
    # Grade de referência
    ax.grid(True, alpha=0.3)
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    
    # Contorno do trailer
    ax.add_collection3d(Line3DCollection(
        create_cube_edges(0, 0, 0, trailer.c, trailer.l, trailer.a),
        colors="#404040", 
        linewidths=1.2
    ))
    
    # Plotagem das caixas
    if boxes:
        unique_skus = {b.id.split('-')[0] for b in boxes}
        cmap = plt.get_cmap("gist_ncar")
        colors = {sku: cmap(i/len(unique_skus)) for i, sku in enumerate(unique_skus)}
        
        for b in boxes:
            sku_base = b.id.split('-')[0]
            add_box_to_plot(ax, b, colors[sku_base])

def display_results(trailer: Trailer, placed: List[Box], left: List[Box], missing: pd.DataFrame):
    st.header("📊 Resultados da Otimização")
    
    # Métricas Principais
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        vol_used = sum(b.volume for b in placed)
        st.metric("Ocupação do Veículo", 
                f"{vol_used/trailer.volume*100:.1f}%", 
                help="Percentual do espaço total utilizado")
    
    with col2:
        st.metric("Caixas Posicionadas", 
                f"{len(placed)} ✅", 
                delta=f"{vol_used:.2f}m³" if placed else None)
    
    with col3:
        residual = trailer.volume - vol_used
        st.metric("Espaço Residual", 
                f"{residual:.2f}m³", 
                "Espaço não utilizado" if residual > 0 else "")
    
    with col4:
        status_color = "red" if left else "green"
        st.metric("Caixas Não Alocadas", 
                f"{len(left)} ❗" if left else "0 ✅", 
                help="Volumes que não couberam no espaço disponível",
                delta_color="off")

    # Seção de Não Alocados
    if left:
        with st.expander("🚨 Análise Detalhada de Não Alocados", expanded=True):
            st.error(f"**ATENÇÃO:** {len(left)} volumes não puderam ser posicionados!")
            
            # Calcula estatísticas
            total_vol_nao_alocado = sum(b.volume for b in left)
            tipos_nao_alocados = {}
            
            for b in left:
                sku_base = b.id.split('-')[0]
                tipos_nao_alocados[sku_base] = tipos_nao_alocados.get(sku_base, 0) + 1
            
            # Layout em Colunas
            cols = st.columns([2, 1])
            with cols[0]:
                st.write("**Distribuição por Tipo:**")
                for sku, qtd in tipos_nao_alocados.items():
                    st.write(f"- {sku}: {qtd} unidades")
                
                st.write(f"\n**Volume Total Não Alocado:** {total_vol_nao_alocado:.2f}m³")
            
            with cols[1]:
                st.write("**Dimensões Médias:**")
                avg_c = sum(b.c for b in left)/len(left)
                avg_l = sum(b.l for b in left)/len(left)
                avg_a = sum(b.a for b in left)/len(left)
                st.write(f"""
                - Largura: {avg_c:.2f}m  
                - Profundidade: {avg_l:.2f}m  
                - Altura: {avg_a:.2f}m
                """)

    # Visualização 3D
    st.header("🎮 Visualização Interativa")
    tabs = st.tabs(["Vista 3D", "Vista Superior", "Vista Lateral"])
    
    with tabs[0]:
        fig = plt.figure(figsize=(10, 6))
        ax = fig.add_subplot(111, projection='3d')
        create_3d_view(trailer, placed, ax, 25, -60, "Visão Tridimensional")
        st.pyplot(fig)
    
    with tabs[1]:
        fig = plt.figure(figsize=(10, 5))
        ax = fig.add_subplot(111, projection='3d')
        create_3d_view(trailer, placed, ax, 90, -90, "Visão Aérea")
        st.pyplot(fig)
    
    with tabs[2]:
        fig = plt.figure(figsize=(10, 5))
        ax = fig.add_subplot(111, projection='3d')
        create_3d_view(trailer, placed, ax, 0, 0, "Visão Lateral")
        st.pyplot(fig)

    # Dados Faltantes
    if not missing.empty:
        with st.expander("⚠️ Itens com Dados Incompletos"):
            st.dataframe(
                missing[["COD SKU", "QTDE", "QMM"]],
                column_config={
                    "COD SKU": "SKU",
                    "QTDE": "Quantidade Total",
                    "QMM": "Qtd. por Pallet"
                },
                height=200
            )

def main():
    c, l, a, car_file, med_file = setup_interface()
    
    if car_file and med_file:
        try:
            with st.spinner("⌛ Processando dados..."):
                merged, missing = load_files(car_file, med_file)
                
                if not merged.empty:
                    sku_groups = expand_grouped(merged)
                    trailer = Trailer(c, l, a)
                    placed, left = pack_grouped(trailer, sku_groups)
                    display_results(trailer, placed, left, missing)
                else:
                    st.warning("⚠️ Nenhum dado válido encontrado nos arquivos!")
        except Exception as e:
            st.error(f"❌ Erro crítico: {str(e)}")
    else:
        st.info("📤 Faça upload dos arquivos na barra lateral para iniciar")

if __name__ == "__main__":
    main()

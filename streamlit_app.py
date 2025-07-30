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
            # Acesso direto às colunas com verificação
            familia = str(row["COD FAMILIA"]) if pd.notna(row["COD FAMILIA"]) else "ND"
            tamanho = str(row["COD TAMANHO"]) if pd.notna(row["COD TAMANHO"]) else "ND"
            qmm = int(row["QMM"])
            return f"{familia}-{tamanho}-{qmm}"
        else:
            # Tratamento robusto para SKUs
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

        # Validação das colunas
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
        page_title="Otimizador de Cargas 3D v2",
        layout="wide",
        page_icon="📦"
    )
    st.title("Sistema Inteligente de Otimização de Carga")
    
    with st.sidebar:
        st.header("Parâmetros do Veículo")
        cols = st.columns(3)
        with cols[0]: c = st.number_input("Comprimento (m)", 1.0, 20.0, 13.6)
        with cols[1]: l = st.number_input("Largura (m)", 1.0, 5.0, 2.45)
        with cols[2]: a = st.number_input("Altura (m)", 1.0, 5.0, 2.9)
        
        st.divider()
        st.header("Upload de Dados")
        with st.form(key="upload_form"):
            car_file = st.file_uploader("Dados de Carregamento", type="xlsx")
            med_file = st.file_uploader("Tabela de Medidas", type="xlsx")
            submitted = st.form_submit_button("Processar Dados")
    
    return c, l, a, car_file, med_file, submitted

def create_3d_view(trailer, boxes, ax, elev, azim, title):
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
    st.header("Resultados da Simulação")
    
    # Painel de métricas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Taxa de Ocupação", 
                f"{(sum(b.volume for b in placed)/trailer.volume*100):.1f}%")
    with col2:
        st.metric("Caixas Posicionadas", f"{len(placed)} 📦")
    with col3:
        st.metric("Espaço Residual", 
                f"{(trailer.volume - sum(b.volume for b in placed)):.2f} m³")

    # Abas de visualização
    tab1, tab2, tab3 = st.tabs(["Perspectiva 3D", "Vista Superior", "Análise Técnica"])
    
    with tab1:
        fig = plt.figure(figsize=(10, 6))
        ax = fig.add_subplot(111, projection='3d')
        create_3d_view(trailer, placed, ax, 25, -60, "Visão 3D da Carga")
        st.pyplot(fig)
    
    with tab2:
        fig = plt.figure(figsize=(10, 5))
        ax = fig.add_subplot(111, projection='3d')
        create_3d_view(trailer, placed, ax, 90, -90, "Visão Aérea")
        st.pyplot(fig)
        st.info("Áreas em branco representam espaços não utilizados")

    with tab3:
        st.subheader("Otimização por Camadas")
        if placed:
            layers = {}
            for b in placed:
                layer = int(b.pos[2]//1)
                layers[layer] = layers.get(layer, 0) + 1
            
            cols = st.columns(2)
            with cols[0]:
                st.bar_chart(layers, use_container_width=True)
            with cols[1]:
                st.write("**Distribuição Vertical:**")
                for layer in sorted(layers.keys()):
                    st.write(f"- Camada {layer}m: {layers[layer]} caixas")

def main():
    c, l, a, car_file, med_file, submitted = setup_interface()
    
    if submitted and car_file and med_file:
        with st.spinner("Processando dados..."):
            try:
                merged, missing = load_files(car_file, med_file)
                
                if not merged.empty:
                    sku_groups = expand_grouped(merged)
                    trailer = Trailer(c, l, a)
                    placed, left = pack_grouped(trailer, sku_groups)
                    display_results(trailer, placed, left, missing)
                else:
                    st.warning("Nenhum dado válido para processar")

            except Exception as e:
                st.error(f"Erro no processamento: {type(e).__name__} - {str(e)}")

if __name__ == "__main__":
    main()

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
            parts = [
                str(row.get("COD FAMILIA", "")),
                str(row.get("COD TAMANHO", ""))
            ]
        else:
            sku_parts = safe_sku_split(row.get("COD SKU", ""))
            parts = [
                sku_parts[0] if len(sku_parts) > 0 else "ND",
                sku_parts[2] if len(sku_parts) >= 3 else "ND"
            ]
            
        qmm = int(row.get("QMM", 0))
        return f"{parts[0]}-{parts[1]}-{qmm}"
    except Exception:
        return None

def load_files(car_file, med_file):
    try:
        car = pd.read_excel(car_file, engine="openpyxl")
        med = pd.read_excel(med_file, engine="openpyxl")

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
            sku = r.get("COD SKU", "DESCONHECIDO")
            sku_parts = safe_sku_split(sku)
            base_sku = "-".join(sku_parts[:3]) if sku_parts else sku
            
            qmm = r.get("QMM", 0)
            if pd.isna(qmm) or qmm <= 0:
                continue
                
            qtde = r.get("QTDE", 0)
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
        page_title="Otimizador de Cargas 3D",
        layout="wide",
        page_icon="🚚"
    )
    st.title("Otimização Inteligente de Carga Veicular")
    
    with st.sidebar:
        st.header("Configuração do Veículo")
        col1, col2, col3 = st.columns(3)
        with col1: 
            c = st.number_input("Comprimento (m)", 1.0, 20.0, 13.6, step=0.1)
        with col2: 
            l = st.number_input("Largura (m)", 1.0, 5.0, 2.45, step=0.1)
        with col3: 
            a = st.number_input("Altura (m)", 1.0, 5.0, 2.9, step=0.1)
        
        st.header("Upload de Arquivos")
        car_file = st.file_uploader("Arquivo de Carregamento (.xlsx)", type="xlsx")
        med_file = st.file_uploader("Arquivo de Medidas (.xlsx)", type="xlsx")
        
    return c, l, a, car_file, med_file

def create_3d_view(trailer, boxes, ax, elev, azim, title):
    """Cria uma visualização 3D com configurações específicas"""
    ax.clear()
    ax.set_xlim(0, trailer.c)
    ax.set_ylim(0, trailer.l)
    ax.set_zlim(0, trailer.a)
    ax.set_title(title, pad=15)
    ax.view_init(elev=elev, azim=azim)
    
    # Contorno do trailer
    ax.add_collection3d(Line3DCollection(
        create_cube_edges(0, 0, 0, trailer.c, trailer.l, trailer.a),
        colors="#404040", 
        linewidths=0.8
    ))
    
    # Plotar caixas
    if boxes:
        unique_skus = {b.id.rsplit("-", 1)[0] for b in boxes}
        cmap = plt.get_cmap("tab20")
        colors = {sku: cmap(i % 20) for i, sku in enumerate(unique_skus)}
        
        for b in boxes:
            sku_base = b.id.rsplit("-", 1)[0]
            add_box_to_plot(ax, b, colors[sku_base])

def display_results(trailer: Trailer, placed: List[Box], left: List[Box], sku_groups: List[List[Box]], missing: pd.DataFrame):
    # Seção de Métricas
    st.subheader("📊 Análise de Eficiência")
    cols = st.columns(4)
    with cols[0]:
        vol_used = sum(b.volume for b in placed)
        utilizacao = vol_used / trailer.volume * 100
        st.metric("Ocupação Total", f"{utilizacao:.1f}%")

    with cols[1]:
        st.metric("Unidades Alocadas", len(placed), "caixas")

    with cols[2]:
        st.metric("Resíduo Espacial", f"{trailer.volume - vol_used:.1f} m³")

    with cols[3]:
        st.metric("Não Alocados", len(left), "unidades" if len(left) > 0 else "-")

    # Visualizações Multiplos Ângulos
    st.subheader("🔍 Inspeção Tridimensional")
    
    fig = plt.figure(figsize=(16, 12))
    views = [
        (211, (25, -60), "Vista 3D Padrão"), 
        (212, (90, -90), "Vista Superior")
    ]
    
    for i, (subplot, (elev, azim), title) in enumerate(views, 1):
        ax = fig.add_subplot(subplot, projection='3d')
        create_3d_view(trailer, placed, ax, elev, azim, title)
    
    st.pyplot(fig)

    st.subheader("🔄 Análise por Perspectivas")
    tabs = st.tabs(["Frontal", "Lateral", "Isométrica", "Detalhe"])
    
    angles = [
        (10, -90),  # Frontal
        (10, 0),    # Lateral
        (25, -45),  # Isométrica
        (25, -30)   # Detalhe
    ]
    
    for tab, (elev, azim) in zip(tabs, angles):
        with tab:
            fig = plt.figure(figsize=(8, 5))
            ax = fig.add_subplot(111, projection='3d')
            create_3d_view(trailer, placed, ax, elev, azim, f"Vista {tab.get('label')}")
            st.pyplot(fig)

    # Análise de Densidade
    with st.expander("📈 Análise de Camadas"):
        if placed:
            layers = {}
            for box in placed:
                layer = int(box.pos[2])
                layers[layer] = layers.get(layer, 0) + 1
            
            st.write("**Distribuição por Altura:**")
            st.bar_chart(layers)
            
            st.write("**Eficiência por Camada:**")
            for layer in sorted(layers.keys()):
                layer_vol = sum(b.volume for b in placed if int(b.pos[2]) == layer)
                st.write(f"- Camada {layer}m: {layer_vol/trailer.volume*100:.1f}%")
    
    # Dados Não Processados
    with st.expander("📦 Itens Não Mapeados"):
        if not missing.empty:
            st.dataframe(
                missing[["COD SKU", "QTDE", "QMM"]],
                column_config={
                    "COD SKU": "SKU",
                    "QTDE": "Quantidade Total",
                    "QMM": "Qtd. por Pallet"
                },
                height=250
            )
        else:
            st.success("✅ Todos os itens foram devidamente mapeados")

def main():
    c, l, a, car_file, med_file = setup_interface()
    
    if car_file and med_file:
        try:
            merged, missing = load_files(car_file, med_file)
            
            if not merged.empty:
                sku_groups = expand_grouped(merged)
                trailer = Trailer(c, l, a)
                placed, left = pack_grouped(trailer, sku_groups)
                display_results(trailer, placed, left, sku_groups, missing)
            else:
                st.warning("🔍 Nenhum dado válido encontrado nos arquivos!")
                
        except Exception as e:
            st.error(f"❌ Erro no processamento: {str(e)}")
    else:
        st.info("📤 Faça upload dos arquivos na barra lateral para iniciar a simulação")

if __name__ == "__main__":
    main()

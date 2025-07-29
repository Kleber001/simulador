import math
import streamlit as st
from typing import Dict, List, Tuple, Optional
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

# ────────────────────────── CLASSES PRINCIPAIS ──────────────────────────
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

# ────────────────────────── FUNÇÕES DE PROCESSAMENTO ──────────────────────────
def safe_sku_split(sku: str) -> List[str]:
    """Divide o SKU de forma segura com tratamento de erros"""
    try:
        return sku.split('-')
    except:
        return []

def create_key(row, is_med: bool = False) -> Optional[str]:
    """Cria chave de lookup com tratamento de erros"""
    try:
        if is_med:
            parts = [
                str(row.get("COD FAMILIA", "")),
                str(row.get("COD TAMANHO", ""))
            ]
        else:
            sku_parts = safe_sku_split(row.get("COD SKU", ""))
            p1 = sku_parts[0] if len(sku_parts) > 0 else "ND"
            p3 = sku_parts[2] if len(sku_parts) >= 3 else "ND"
            parts = [p1, p3]
            
        qmm = int(row.get("QMM", 0))
        return f"{parts[0]}-{parts[1]}-{qmm}"
    except Exception as e:
        st.error(f"Erro ao criar chave: {str(e)}")
        return None

def load_files(car_file, med_file):
    """Carrega e processa os arquivos com tratamento de erros"""
    try:
        car = pd.read_excel(car_file, engine="openpyxl")
        med = pd.read_excel(med_file, engine="openpyxl")

        # Criar chaves com validação
        med["KEY"] = med.apply(lambda r: create_key(r, is_med=True), axis=1)
        car["KEY"] = car.apply(create_key, axis=1)

        # Filtrar dados válidos
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
    """Expande os grupos de SKUs com tratamento robusto"""
    groups: Dict[str, List[Box]] = {}
    order: List[str] = []
    
    for _, r in df.iterrows():
        try:
            sku = r.get("COD SKU", "DESCONHECIDO")
            sku_parts = safe_sku_split(sku)
            base_sku = "-".join(sku_parts[:3]) if len(sku_parts) >=3 else sku
            
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
                Box(
                    f"{base_sku}-{i}",
                    r["COMPRIMENTO"],
                    r["LARGURA"],
                    r["ALTURA"]
                ) for i in range(1, n + 1)
            )
            
        except Exception as e:
            st.error(f"Erro ao processar linha {_}: {str(e)}")
            continue
            
    return [groups[k] for k in order if k in groups and groups[k]]

# ────────────────────────── ALGORITMO DE EMPACOTAMENTO ──────────────────────────
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
        st.error(f"Erro durante o empacotamento: {str(e)}")
    
    return placed, unplaced

# ────────────────────────── VISUALIZAÇÃO 3D ──────────────────────────
def create_cube_edges(x, y, z, dx, dy, dz):
    """Gera os vertices para visualização 3D"""
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
    """Adiciona uma caixa ao plot 3D"""
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

# ────────────────────────── INTERFACE STREAMLIT ──────────────────────────
def setup_interface():
    st.set_page_config(
        page_title="Otimização de Cargas 3D",
        layout="wide",
        page_icon="🚚"
    )
    st.title("Otimizador Inteligente de Carga de Veículos")

    with st.sidebar:
        st.header("Configurações do Veículo")
        col1, col2, col3 = st.columns(3)
        with col1:
            c = st.number_input("Comprimento (m)", min_value=1.0, value=13.6)
        with col2:
            l = st.number_input("Largura (m)", min_value=1.0, value=2.45)
        with col3:
            a = st.number_input("Altura (m)", min_value=1.0, value=2.9)

        st.header("Upload de Arquivos")
        car_file = st.file_uploader("Carregamento (.xlsx)", type="xlsx")
        med_file = st.file_uploader("Medidas (.xlsx)", type="xlsx")
        return c, l, a, car_file, med_file

def display_results(trailer, placed, left, sku_groups):
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("Visualização 3D da Carga")
        fig = plt.figure(figsize=(10, 6))
        ax = fig.add_subplot(111, projection='3d')
        
        ax.set_xlim(0, trailer.c)
        ax.set_ylim(0, trailer.l)
        ax.set_zlim(0, trailer.a)
        ax.set_xlabel("Comprimento (m)")
        ax.set_ylabel("Largura (m)")
        ax.set_zlabel("Altura (m)")
        ax.view_init(elev=25, azim=-60)
        ax.grid(False)
        
        # Contorno do trailer
        ax.add_collection3d(
            Line3DCollection(
                create_cube_edges(0, 0, 0, trailer.c, trailer.l, trailer.a),
                colors="gray",
                linewidths=0.8
            )
        )
        
        # Cores para os SKUs
        if placed:
            unique_skus = list({"-".join(b.id.split("-")[:-1]) for b in placed})
            cmap = plt.get_cmap("tab20")
            colors = {sku: cmap(i % 20) for i, sku in enumerate(unique_skus)}
            
            for b in placed:
                sku = "-".join(b.id.split("-")[:-1])
                add_box_to_plot(ax, b, colors[sku])
        
        st.pyplot(fig)

    with col2:
        st.subheader("Indicadores de Performance")
        vol_used = sum(b.volume for b in placed)
        utilization = (vol_used / trailer.volume * 100) if trailer.volume > 0 else 0
        
        st.metric("🌐 Taxa de Ocupação", f"{utilization:.1f}%")
        st.metric("✅ Caixas Posicionadas", len(placed))
        st.metric("❌ Caixas Não Alocadas", len(left))
        
        # Capacidade residual
        if sku_groups and (trailer.volume - vol_used) > 0:
            last_group = [g for g in sku_groups if g][-1]
            if last_group:
                sample = last_group[0]
                box_vol = sample.volume
                remaining = trailer.volume - vol_used
                additional = int(remaining // box_vol) if box_vol > 0 else 0
                
                if additional > 0:
                    st.divider()
                    st.markdown(f"""
                    **📦 Capacidade Residual**
                    - {additional} unid. do último SKU
                    - Dimensões: {sample.c}m × {sample.l}m × {sample.a}m
                    - Volume resto: {remaining:.2f}m³
                    """)

        with st.expander("⚠ SKUs Não Mapeados", expanded=False):
            if not missing.empty:
                st.dataframe(
                    missing[['COD SKU', 'QMM']],
                    use_container_width=True,
                    column_config={
                        "COD SKU": "SKU",
                        "QMM": "Qtd. por Medida"
                    }
                )
            else:
                st.success("Todos os SKUs foram mapeados")

def main():
    c, l, a, car_file, med_file = setup_interface()

    if car_file and med_file:
        try:
            merged, missing = load_files(car_file, med_file)
            
            if not merged.empty:
                sku_groups = expand_grouped(merged)
                trailer = Trailer(c, l, a)
                placed, left = pack_grouped(trailer, sku_groups)
                display_results(trailer, placed, left, sku_groups)
            else:
                st.warning("Nenhum dado válido encontrado para processamento")
                
        except Exception as e:
            st.error(f"Falha crítica no processamento: {str(e)}")
            st.stop()

    else:
        st.info("📤 Faça upload dos arquivos para iniciar a otimização")

if __name__ == "__main__":
    main()



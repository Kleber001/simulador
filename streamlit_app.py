import math
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from typing import List, Tuple, Dict
from matplotlib.colors import ListedColormap
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# =================== CLASSES MELHORADAS ===================
class Box:
    def __init__(self, sku: str, c: float, l: float, a: float, rotation_axes: List[str] = None):
        self.id = sku
        self.c, self.l, self.a = c, l, a
        self.pos: Tuple[float, float, float] | None = None
        self.rotation_axes = rotation_axes or ['XY']  # Default apenas rotação XY
        
    def orientations(self):
        """Gera todas as orientações possíveis baseadas nos eixos de rotação selecionados"""
        orientations = set()
        
        # Orientação original
        orientations.add((self.c, self.l, self.a))
        
        # Rotação XY (no plano horizontal)
        if 'XY' in self.rotation_axes:
            orientations.add((self.l, self.c, self.a))
            
        # Rotação XZ (no plano vertical comprimento-altura)
        if 'XZ' in self.rotation_axes:
            orientations.add((self.a, self.l, self.c))
            orientations.add((self.c, self.a, self.l))
            
        # Rotação YZ (no plano vertical largura-altura)
        if 'YZ' in self.rotation_axes:
            orientations.add((self.c, self.a, self.l))
            orientations.add((self.a, self.c, self.l))
            
        # Todas as rotações (combinações)
        if 'XY' in self.rotation_axes and 'XZ' in self.rotation_axes:
            orientations.add((self.l, self.a, self.c))
            orientations.add((self.a, self.l, self.c))
            
        if 'XY' in self.rotation_axes and 'YZ' in self.rotation_axes:
            orientations.add((self.l, self.a, self.c))
            orientations.add((self.a, self.c, self.l))
            
        # Converte para lista de tuplas (largura, profundidade, altura)
        return [(o[0], o[1], o[2]) for o in orientations]

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
    def __init__(self, C: float, L: float, A: float):
        self.C, self.L, self.A = C, L, A
        self.sky = [(0.0, 0.0, C, 0.0)]  # (x, y, width_available, current_height)

    def place(self, b: Box):
        """Tenta posicionar uma caixa considerando todas as orientações possíveis"""
        best_fit = None
        best_orientation = None
        best_position = None
        best_skyline_idx = -1
        
        for orientation in b.orientations():
            w, d, h = orientation
            
            for i, (x, y, fw, current_h) in enumerate(self.sky):
                # Verifica se cabe horizontalmente
                if w <= fw and y + d <= self.L and current_h + h <= self.A:
                    # Calcula o "desperdício" de espaço (para otimização)
                    waste = (fw - w) * d
                    
                    if best_fit is None or waste < best_fit:
                        best_fit = waste
                        best_orientation = orientation
                        best_position = (x, y, current_h)
                        best_skyline_idx = i
        
        if best_fit is not None:
            x, y, z = best_position
            w, d, h = best_orientation
            
            # Atualiza a skyline
            old_x, old_y, old_fw, old_h = self.sky[best_skyline_idx]
            self.sky[best_skyline_idx] = (old_x + w, old_y, old_fw - w, old_h)
            
            # Adiciona nova área ocupada
            if old_fw - w > 0:  # Se ainda há espaço restante
                self.sky.append((x, y + d, w, max(old_h, z + h)))
            
            return True, (x, y, z), best_orientation
        
        return False, None, None

# =================== FUNÇÕES DE CÁLCULO MELHORADAS ===================
def pack_grouped_advanced(trailer: Trailer, sku_groups: List[List[Box]]):
    """Algoritmo de empacotamento 3D melhorado"""
    placed: List[Box] = []
    unplaced: List[Box] = []
    
    # Ordena grupos por volume decrescente
    sku_groups.sort(key=lambda group: sum(b.volume for b in group), reverse=True)
    
    # Usa camadas 3D
    layers = []
    current_layer = SkylineLayer(trailer.c, trailer.l, trailer.a)
    layers.append(current_layer)
    
    for group in sku_groups:
        # Ordena caixas do grupo por volume decrescente
        group.sort(key=lambda b: b.volume, reverse=True)
        
        for box in group:
            placed_in_layer = False
            
            # Tenta colocar em alguma camada existente
            for layer in layers:
                success, pos, orientation = layer.place(box)
                if success:
                    box.pos = pos
                    # Atualiza dimensões da caixa com a orientação usada
                    box.c, box.l, box.a = orientation
                    placed.append(box)
                    placed_in_layer = True
                    break
            
            if not placed_in_layer:
                # Tenta criar nova camada se necessário
                unplaced.append(box)
    
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

def expand_grouped_with_rotation(df: pd.DataFrame, rotation_axes: List[str]) -> List[List[Box]]:
    """Expande os grupos considerando os eixos de rotação selecionados"""
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
                Box(f"{sku}-{i}", r["COMPRIMENTO"], r["LARGURA"], r["ALTURA"], rotation_axes)
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

def add_box(ax, x, y, z, dx, dy, dz, color, alpha=0.85):
    faces = [
        [(x, y, z), (x + dx, y, z), (x + dx, y + dy, z), (x, y + dy, z)],
        [(x, y, z + dz), (x + dx, y, z + dz), (x + dx, y + dy, z + dz), (x, y + dy, z + dz)],
        [(x, y, z), (x + dx, y, z), (x + dx, y, z + dz), (x, y, z + dz)],
        [(x, y + dy, z), (x + dx, y + dy, z), (x + dx, y + dy, z + dz), (x, y + dy, z + dz)],
        [(x, y, z), (x, y + dy, z), (x, y + dy, z + dz), (x, y, z + dz)],
        [(x + dx, y, z), (x + dx, y + dy, z), (x + dx, y + dy, z + dz), (x + dx, y, z + dz)],
    ]
    ax.add_collection3d(
        Poly3DCollection(faces, facecolors=color, edgecolors="k", linewidths=0.5, alpha=alpha)
    )

def add_trailer_wireframe(ax, trailer):
    """Adiciona a estrutura do trailer como wireframe"""
    # Desenha as arestas do trailer
    edges = cube_edges(0, 0, 0, trailer.c, trailer.l, trailer.a)
    for edge in edges:
        ax.plot3D(*zip(*edge), color='red', linewidth=2, alpha=0.6)

# =================== INTERFACE STREAMLIT MELHORADA ===================
def main():
    st.set_page_config(
        page_title="Cubagem Inteligente 5.0",
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
    .rotation-section {
        background: linear-gradient(145deg, #27ae60, #2ecc71);
        padding: 1.5rem;
        border-radius: 8px;
        color: white;
        margin-bottom: 1.5rem;
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
        <h1 style="margin:0; font-size:2.5rem;">🚛 CUBAGEM INTELIGENTE 5.0</h1>
        <p style="margin:0; font-size:1.1rem; opacity:0.95;">Otimização avançada de cargas com rotação 3D</p>
    </div>
    """, unsafe_allow_html=True)

    # Configurações do carregamento
    with st.expander("⚙️ CONFIGURAÇÕES DA CARGA", expanded=True):
        col_dim, col_files = st.columns([1, 2])
        
        with col_dim:
            st.subheader("📦 Dimensões do Veículo")
            c = st.number_input("Comprimento Total (m)", 5.0, 30.0, 13.6, 0.1)
            l = st.number_input("Largura Interna (m)", 1.5, 3.0, 2.45, 0.01)
            a = st.number_input("Altura Máxima (m)", 1.5, 4.0, 2.5, 0.1)
            trailer = Trailer(c, l, a)
        
        with col_files:
            st.subheader("📋 Arquivos de Entrada")
            col_car, col_med = st.columns(2)
            with col_car:
                car_file = st.file_uploader("Planilha de Carregamento", type="xlsx")
            with col_med:
                med_file = st.file_uploader("Planilha de Medidas", type="xlsx")

    # NOVA SEÇÃO: Seleção de Eixos de Rotação
    with st.expander("🔄 CONFIGURAÇÕES DE ROTAÇÃO", expanded=True):
        st.markdown("""
        <div class="rotation-section">
            <h4 style="margin:0; color:white;">🎯 Selecione os eixos de rotação permitidos</h4>
            <p style="margin:5px 0 0 0; opacity:0.9;">Mais opções de rotação = melhor aproveitamento do espaço</p>
        </div>
        """, unsafe_allow_html=True)
        
        col_rot1, col_rot2, col_rot3 = st.columns(3)
        
        with col_rot1:
            xy_rotation = st.checkbox(
                "🔄 Rotação XY (Horizontal)", 
                value=True, 
                help="Permite rotacionar as caixas no plano horizontal (trocar comprimento por largura)"
            )
        
        with col_rot2:
            xz_rotation = st.checkbox(
                "🔃 Rotação XZ (Vertical C-A)", 
                value=False,
                help="Permite rotacionar no plano vertical comprimento-altura"
            )
        
        with col_rot3:
            yz_rotation = st.checkbox(
                "🔀 Rotação YZ (Vertical L-A)", 
                value=False,
                help="Permite rotacionar no plano vertical largura-altura"
            )
        
        # Monta lista de eixos selecionados
        rotation_axes = []
        if xy_rotation:
            rotation_axes.append('XY')
        if xz_rotation:
            rotation_axes.append('XZ')
        if yz_rotation:
            rotation_axes.append('YZ')
        
        if not rotation_axes:
            st.warning("⚠️ Selecione pelo menos um eixo de rotação!")
            rotation_axes = ['XY']  # Default
        
        # Mostra resumo das rotações
        st.info(f"✅ Eixos selecionados: {', '.join(rotation_axes)} | "
               f"Total de orientações possíveis por caixa: {2 if len(rotation_axes) == 1 and 'XY' in rotation_axes else len(rotation_axes) * 2}")

    # Processamento principal
    if st.button("🚀 INICIAR SIMULAÇÃO AVANÇADA", type="primary", use_container_width=True):
        if not (car_file and med_file):
            st.error("⚠️ Selecione ambos os arquivos para continuar")
            return

        try:
            with st.spinner("🔄 Analisando dados e calculando disposição 3D com rotações..."):
                merged, missing = load_files(car_file, med_file)
                sku_groups = expand_grouped_with_rotation(merged, rotation_axes)
                placed, left = pack_grouped_advanced(trailer, sku_groups)
                
                vol_total = trailer.volume
                vol_usado = sum(b.volume for b in placed)
                perc_ocup = (vol_usado / vol_total) * 100 if vol_total > 0 else 0

                # Painel de métricas
                st.subheader("📊 RESULTADOS DA SIMULAÇÃO")
                cols = st.columns(5)
                
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
                        <div style="color: #666;">Não Alocados</div>
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
                
                with cols[4]:
                    st.markdown(f"""
                    <div class="metric-card" style="border-left: 4px solid #34495e;">
                        <div style="font-size: 24px; color: #34495e;">{vol_usado:.1f}m³</div>
                        <div style="color: #666;">Volume Ocupado</div>
                    </div>
                    """, unsafe_allow_html=True)

                # Visualização 3D melhorada
                st.subheader("🎯 DISPOSIÇÃO TRIDIMENSIONAL OTIMIZADA")
                
                col_3d, col_controls = st.columns([3, 1])
                
                with col_controls:
                    st.subheader("🎮 Controles da Visualização")
                    show_wireframe = st.checkbox("Mostrar estrutura do trailer", value=True)
                    alpha_value = st.slider("Transparência das caixas", 0.3, 1.0, 0.85, 0.05)
                    view_angle = st.selectbox("Ângulo de visualização", 
                                            ["Isométrico", "Frontal", "Lateral", "Superior"])
                
                with col_3d:
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
                    
                    fig = plt.figure(figsize=(14, 8))
                    ax = fig.add_subplot(111, projection='3d')
                    
                    ax.set_xlim(0, trailer.c)
                    ax.set_ylim(0, trailer.l)
                    ax.set_zlim(0, trailer.a)
                    ax.set_xlabel("Comprimento (m)", fontsize=10, labelpad=10)
                    ax.set_ylabel("Largura (m)", fontsize=10, labelpad=10)
                    ax.set_zlabel("Altura (m)", fontsize=10, labelpad=10)
                    
                    # Define o ângulo de visualização
                    angles = {
                        "Isométrico": (24, -58),
                        "Frontal": (0, 0),
                        "Lateral": (0, 90),
                        "Superior": (90, 0)
                    }
                    elev, azim = angles[view_angle]
                    ax.view_init(elev=elev, azim=azim)
                    
                    # Mostra wireframe do trailer se selecionado
                    if show_wireframe:
                        add_trailer_wireframe(ax, trailer)
                    
                    # Desenha as caixas
                    skus = list(set([b.id.split('-')[0] for b in placed]))
                    cores = cm.get_cmap('tab20', len(skus))(range(len(skus)))
                    
                    for b in placed:
                        sku_id = b.id.split('-')[0]
                        add_box(ax, *b.pos, b.c, b.l, b.a, cores[skus.index(sku_id)], alpha_value)

                    # Adiciona título com informações
                    ax.set_title(f"Simulação com {len(rotation_axes)} eixo(s) de rotação | "
                               f"Ocupação: {perc_ocup:.1f}% | "
                               f"Rotações: {', '.join(rotation_axes)}", 
                               fontsize=12, pad=20)

                st.pyplot(fig)

                # Análise de eficiência por rotação
                if len(rotation_axes) > 1:
                    st.subheader("📈 ANÁLISE DE EFICIÊNCIA POR ROTAÇÃO")
                    rotation_info = pd.DataFrame({
                        'Eixo de Rotação': rotation_axes,
                        'Descrição': [
                            'Rotação horizontal (C ↔ L)' if axis == 'XY' else
                            'Rotação vertical C-A (C ↔ A)' if axis == 'XZ' else
                            'Rotação vertical L-A (L ↔ A)' for axis in rotation_axes
                        ],
                        'Impacto': [
                            'Melhora distribuição horizontal' if axis == 'XY' else
                            'Otimiza altura do carregamento' if axis == 'XZ' else
                            'Balanceia largura e altura' for axis in rotation_axes
                        ]
                    })
                    st.dataframe(rotation_info, hide_index=True, use_container_width=True)

                # Seção de alertas
                if len(left) > 0 or not missing.empty:
                    st.subheader("⚠️ ITENS COM PROBLEMAS")
                    tab1, tab2 = st.tabs(["Volumes Não Alocados", "SKUs Sem Medidas"])
                    
                    with tab1:
                        if len(left) > 0:
                            df_left = pd.DataFrame({
                                "SKU": [b.id.split('-')[0] for b in left],
                                "Dimensões (C×L×A)": [f"{b.c:.2f}×{b.l:.2f}×{b.a:.2f}" for b in left],
                                "Volume (m³)": [b.volume for b in left]
                            })
                            df_left = df_left.groupby(["SKU", "Dimensões (C×L×A)", "Volume (m³)"]).size().reset_index(name="Quantidade")
                            st.dataframe(df_left, hide_index=True, use_container_width=True)
                        else:
                            st.success("✅ Todos os volumes foram alocados com sucesso!")
                    
                    with tab2:
                        if not missing.empty:
                            st.dataframe(missing[["COD SKU"]].drop_duplicates(), 
                                       hide_index=True, use_container_width=True)
                        else:
                            st.success("✅ Todas as medidas foram encontradas!")

                # Resumo final
                improvement = ""
                if len(rotation_axes) > 1:
                    improvement = f" com {len(rotation_axes)} eixos de rotação"
                
                st.success(f"🎉 Simulação concluída{improvement}! "
                         f"Taxa de ocupação: {perc_ocup:.1f}% | "
                         f"Volumes carregados: {len(placed)}/{len(placed) + len(left)}")

        except Exception as e:
            st.error(f"❌ ERRO: {str(e)}")
            st.info("Verifique se os arquivos estão corretos e no formato adequado")
            st.exception(e)  # Mostra detalhes do erro para debug

if __name__ == "__main__":
    main()


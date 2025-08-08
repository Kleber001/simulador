import math
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from typing import List, Tuple, Dict
from matplotlib.colors import ListedColormap
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# =================== CLASSES CORRIGIDAS ===================
class Box:
    def __init__(self, sku: str, c: float, l: float, a: float, rotation_axes: List[str] = None):
        self.id = sku
        self.original_c, self.original_l, self.original_a = c, l, a
        self.c, self.l, self.a = c, l, a
        self.pos: Tuple[float, float, float] | None = None
        self.rotation_axes = rotation_axes or ['XY']
        self.used_orientation = None

    def orientations(self):
        """Retorna orientações possíveis como (largura_base, profundidade_base) mantendo altura fixa"""
        orientations = []
        
        # Orientação original (comprimento x largura)
        orientations.append((self.original_c, self.original_l))
        
        # Rotação XY (largura x comprimento) - apenas troca no plano horizontal
        if 'XY' in self.rotation_axes:
            orientations.append((self.original_l, self.original_c))
            
        # Para rotações verticais, precisamos considerar altura também
        if 'XZ' in self.rotation_axes:
            # Comprimento vira altura, altura vira comprimento
            orientations.append((self.original_a, self.original_l))
            orientations.append((self.original_l, self.original_a))
            
        if 'YZ' in self.rotation_axes:
            # Largura vira altura, altura vira largura  
            orientations.append((self.original_c, self.original_a))
            orientations.append((self.original_a, self.original_c))
        
        # Remove duplicatas
        unique_orientations = list(set(orientations))
        return unique_orientations

    @property
    def volume(self):
        return self.original_c * self.original_l * self.original_a

class Trailer:
    def __init__(self, c: float, l: float, a: float):
        self.c, self.l, self.a = c, l, a

    @property
    def volume(self):
        return self.c * self.l * self.a

class SkylineLayer:
    """Algoritmo Skyline original - corrigido e funcional"""
    def __init__(self, C: float, L: float):
        self.C, self.L = C, L
        self.sky = [(0.0, 0.0, C)]

    def place(self, b: Box):
        """Tenta todas as orientações da caixa e escolhe a melhor posição"""
        best_position = None
        best_orientation = None
        best_waste = float('inf')
        
        for w, d in b.orientations():
            # Verifica todas as posições possíveis na skyline
            for i, (x, y, fx) in enumerate(self.sky):
                if w <= fx and y + d <= self.L:
                    # Calcula desperdício de espaço
                    waste = fx - w
                    if waste < best_waste:
                        best_waste = waste
                        best_position = i
                        best_orientation = (w, d)
        
        if best_position is not None:
            i = best_position
            w, d = best_orientation
            x, y, fx = self.sky[i]
            
            # Atualiza dimensões da caixa para a orientação escolhida
            altura_atual = b.original_a
            if 'XZ' in b.rotation_axes and (w == b.original_a or d == b.original_a):
                if w == b.original_a and d == b.original_l:
                    altura_atual = b.original_c
                elif w == b.original_l and d == b.original_a:
                    altura_atual = b.original_c
            elif 'YZ' in b.rotation_axes and (w == b.original_a or d == b.original_a):
                if w == b.original_c and d == b.original_a:
                    altura_atual = b.original_l
                elif w == b.original_a and d == b.original_c:
                    altura_atual = b.original_l
            
            # Atualiza a skyline
            self.sky[i] = (x + w, y, fx - w)
            self.sky.append((x, y + d, w))
            
            # Limpa entradas inválidas da skyline
            self.sky = [(sx, sy, sfw) for sx, sy, sfw in self.sky if sfw > 0]
            
            # Atualiza dimensões da caixa
            b.c, b.l, b.a = w, d, altura_atual
            b.used_orientation = f"{w:.2f}x{d:.2f}x{altura_atual:.2f}"
            
            return True, (x, y)
        
        return False, None

# =================== FUNÇÕES DE CÁLCULO CORRIGIDAS ===================
def pack_grouped_corrected(trailer: Trailer, sku_groups: List[List[Box]]):
    """Algoritmo de empacotamento original corrigido com rotações"""
    placed: List[Box] = []
    unplaced: List[Box] = []
    z = 0.0
    layer = SkylineLayer(trailer.c, trailer.l)
    layer_h = 0.0

    for g_idx, group in enumerate(sku_groups):
        # Ordena por área da base (maior primeiro)
        group.sort(key=lambda b: max([w*d for w, d in b.orientations()]), reverse=True)
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
                # Se não coube, tenta próxima camada
                if layer_h == 0.0:
                    # Se nem o primeiro item coube, marca como não colocado
                    unplaced.extend(group[idx:])
                    idx = len(group)
                else:
                    # Nova camada
                    z += layer_h
                    if z + max([b.a for b in group[idx:] if hasattr(b, 'a')], default=[0])[0] > trailer.a:
                        # Não cabe mais em altura
                        unplaced.extend(group[idx:])
                        # Adiciona todos os grupos restantes
                        for rest_group in sku_groups[g_idx + 1:]:
                            unplaced.extend(rest_group)
                        return placed, unplaced
                    
                    layer = SkylineLayer(trailer.c, trailer.l)
                    layer_h = 0.0
    
    return placed, unplaced

def load_files(car_path, med_path):
    """Função de carregamento de arquivos - mantida original"""
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
    """Expande grupos com configuração de rotação"""
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
def add_box(ax, x, y, z, dx, dy, dz, color, alpha=0.85):
    """Adiciona uma caixa 3D ao gráfico"""
    faces = [
        [(x, y, z), (x + dx, y, z), (x + dx, y + dy, z), (x, y + dy, z)],
        [(x, y, z + dz), (x + dx, y, z + dz), (x + dx, y + dy, z + dz), (x, y + dy, z + dz)],
        [(x, y, z), (x + dx, y, z), (x + dx, y, z + dz), (x, y, z + dz)],
        [(x, y + dy, z), (x + dx, y + dy, z), (x + dx, y + dy, z + dz), (x, y + dy, z + dz)],
        [(x, y, z), (x, y + dy, z), (x, y + dy, z + dz), (x, y, z + dz)],
        [(x + dx, y, z), (x + dx, y + dy, z), (x + dx, y + dy, z + dz), (x + dx, y, z + dz)],
    ]
    ax.add_collection3d(
        Poly3DCollection(faces, facecolors=color, edgecolors="black", linewidths=0.5, alpha=alpha)
    )

def add_trailer_wireframe(ax, trailer):
    """Adiciona wireframe do trailer"""
    # Contorno do trailer
    corners = [
        [0, 0, 0], [trailer.c, 0, 0], [trailer.c, trailer.l, 0], [0, trailer.l, 0],
        [0, 0, trailer.a], [trailer.c, 0, trailer.a], [trailer.c, trailer.l, trailer.a], [0, trailer.l, trailer.a]
    ]
    
    # Arestas do trailer
    edges = [
        [0, 1], [1, 2], [2, 3], [3, 0],  # base
        [4, 5], [5, 6], [6, 7], [7, 4],  # topo
        [0, 4], [1, 5], [2, 6], [3, 7]   # verticais
    ]
    
    for edge in edges:
        points = [corners[edge[0]], corners[edge[1]]]
        ax.plot3D(*zip(*points), color='red', linewidth=2, alpha=0.8)

# =================== FUNÇÕES DE ANÁLISE ===================
def analyze_packing_efficiency(placed: List[Box], trailer: Trailer):
    """Analisa a eficiência do empacotamento"""
    if not placed:
        return {}
    
    # Estatísticas básicas
    total_boxes = len(placed)
    total_volume_used = sum(b.volume for b in placed)
    trailer_volume = trailer.volume
    efficiency = (total_volume_used / trailer_volume) * 100
    
    # Análise por altura
    max_height = max(b.pos[2] + b.a for b in placed) if placed else 0
    height_usage = (max_height / trailer.a) * 100
    
    # Análise de orientações usadas
    orientations_used = {}
    for box in placed:
        if hasattr(box, 'used_orientation') and box.used_orientation:
            ori = box.used_orientation
            orientations_used[ori] = orientations_used.get(ori, 0) + 1
    
    return {
        'total_boxes': total_boxes,
        'volume_efficiency': efficiency,
        'height_usage': height_usage,
        'max_height_used': max_height,
        'orientations_used': orientations_used
    }

# =================== INTERFACE STREAMLIT ===================
def main():
    st.set_page_config(
        page_title="Cubagem Inteligente - Corrigido",
        page_icon="🚛",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # CSS customizado
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
    </style>
    """, unsafe_allow_html=True)

    # Header
    st.markdown("""
    <div class="header-section">
        <h1 style="margin:0; font-size:2.5rem;">🚛 CUBAGEM INTELIGENTE - CORRIGIDO</h1>
        <p style="margin:0; font-size:1.1rem; opacity:0.95;">Algoritmo de empacotamento otimizado e funcional</p>
    </div>
    """, unsafe_allow_html=True)

    # Configurações
    with st.expander("⚙️ CONFIGURAÇÕES", expanded=True):
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("📦 Dimensões do Veículo")
            c = st.number_input("Comprimento (m)", 5.0, 30.0, 13.6, 0.1)
            l = st.number_input("Largura (m)", 1.5, 3.0, 2.45, 0.01)
            a = st.number_input("Altura (m)", 1.5, 4.0, 2.5, 0.1)
            trailer = Trailer(c, l, a)
            
            # Mostra volume do trailer
            st.info(f"Volume total: {trailer.volume:.2f} m³")
        
        with col2:
            st.subheader("📋 Arquivos")
            col_car, col_med = st.columns(2)
            with col_car:
                car_file = st.file_uploader("Planilha de Carregamento", type="xlsx")
            with col_med:
                med_file = st.file_uploader("Planilha de Medidas", type="xlsx")

    # Configurações de Rotação
    with st.expander("🔄 OPÇÕES DE ROTAÇÃO", expanded=True):
        st.markdown("""
        <div class="rotation-section">
            <h4 style="margin:0;">🎯 Configurar rotações permitidas</h4>
        </div>
        """, unsafe_allow_html=True)
        
        col_rot1, col_rot2, col_rot3 = st.columns(3)
        
        with col_rot1:
            xy_rotation = st.checkbox("🔄 Rotação XY (Horizontal)", value=True, 
                                    help="Permite trocar comprimento por largura")
        
        with col_rot2:
            xz_rotation = st.checkbox("🔃 Rotação XZ (Vertical C-A)", value=False,
                                    help="Altura pode virar comprimento")
        
        with col_rot3:
            yz_rotation = st.checkbox("🔀 Rotação YZ (Vertical L-A)", value=False,
                                    help="Altura pode virar largura")
        
        # Lista de rotações
        rotation_axes = []
        if xy_rotation: rotation_axes.append('XY')
        if xz_rotation: rotation_axes.append('XZ')
        if yz_rotation: rotation_axes.append('YZ')
        
        if not rotation_axes:
            rotation_axes = ['XY']
            
        st.info(f"✅ Rotações ativas: {', '.join(rotation_axes)}")

    # Botão principal
    if st.button("🚀 EXECUTAR SIMULAÇÃO", type="primary", use_container_width=True):
        if not (car_file and med_file):
            st.error("⚠️ Selecione ambos os arquivos!")
            return

        try:
            with st.spinner("🔄 Processando empacotamento..."):
                # Carrega dados
                merged, missing = load_files(car_file, med_file)
                st.success(f"✅ Dados carregados: {len(merged)} itens válidos")
                
                # Cria grupos com rotação
                sku_groups = expand_grouped_with_rotation(merged, rotation_axes)
                total_boxes = sum(len(group) for group in sku_groups)
                st.info(f"📦 Total de caixas a serem empacotadas: {total_boxes}")
                
                # Executa empacotamento
                placed, unplaced = pack_grouped_corrected(trailer, sku_groups)
                
                # Calcula estatísticas
                vol_total = trailer.volume
                vol_usado = sum(b.volume for b in placed)
                eficiencia = (vol_usado / vol_total) * 100 if vol_total > 0 else 0
                
                # Análise detalhada
                analysis = analyze_packing_efficiency(placed, trailer)

            # Resultados
            st.subheader("📊 RESULTADOS")
            
            # Métricas principais
            cols = st.columns(5)
            with cols[0]:
                st.metric("📦 Caixas Empacotadas", len(placed))
            with cols[1]:
                st.metric("❌ Não Empacotadas", len(unplaced))
            with cols[2]:
                st.metric("📈 Taxa de Ocupação", f"{eficiencia:.1f}%")
            with cols[3]:
                st.metric("📏 Altura Utilizada", f"{analysis.get('height_usage', 0):.1f}%")
            with cols[4]:
                st.metric("🎯 Volume Ocupado", f"{vol_usado:.2f} m³")

            # Visualização 3D
            st.subheader("🎯 VISUALIZAÇÃO 3D")
            
            # Controles de visualização
            col_vis1, col_vis2 = st.columns([3, 1])
            
            with col_vis2:
                show_wireframe = st.checkbox("Mostrar estrutura", value=True)
                alpha_val = st.slider("Transparência", 0.3, 1.0, 0.85)
                view_preset = st.selectbox("Ângulo", ["Isométrico", "Frontal", "Lateral", "Superior"])
            
            with col_vis1:
                # Configura o plot
                fig = plt.figure(figsize=(14, 10))
                ax = fig.add_subplot(111, projection='3d')
                
                ax.set_xlim(0, trailer.c)
                ax.set_ylim(0, trailer.l) 
                ax.set_zlim(0, trailer.a)
                ax.set_xlabel("Comprimento (m)")
                ax.set_ylabel("Largura (m)")
                ax.set_zlabel("Altura (m)")
                
                # Ângulos de visualização
                view_angles = {
                    "Isométrico": (25, -60),
                    "Frontal": (0, 0),
                    "Lateral": (0, 90),
                    "Superior": (90, 0)
                }
                elev, azim = view_angles[view_preset]
                ax.view_init(elev=elev, azim=azim)
                
                # Wireframe do trailer
                if show_wireframe:
                    add_trailer_wireframe(ax, trailer)
                
                # Desenha as caixas
                if placed:
                    skus_unicos = list(set([b.id.split('-')[0] for b in placed]))
                    cores = cm.get_cmap('tab20', len(skus_unicos))(range(len(skus_unicos)))
                    
                    for box in placed:
                        sku_id = box.id.split('-')[0]
                        cor = cores[skus_unicos.index(sku_id)]
                        add_box(ax, *box.pos, box.c, box.l, box.a, cor, alpha_val)
                
                ax.set_title(f"Empacotamento - {len(placed)} caixas - {eficiencia:.1f}% ocupação", 
                           fontsize=14)
                
                st.pyplot(fig)

            # Análises complementares
            if analysis['orientations_used']:
                st.subheader("📐 ORIENTAÇÕES UTILIZADAS")
                ori_df = pd.DataFrame([
                    {"Orientação (CxLxA)": k, "Quantidade": v} 
                    for k, v in analysis['orientations_used'].items()
                ])
                st.dataframe(ori_df, hide_index=True, use_container_width=True)

            # Problemas encontrados
            if unplaced or not missing.empty:
                st.subheader("⚠️ ITENS NÃO PROCESSADOS")
                
                tab1, tab2 = st.tabs(["Não Empacotados", "Sem Medidas"])
                
                with tab1:
                    if unplaced:
                        unplaced_df = pd.DataFrame([
                            {
                                "SKU": b.id.split('-')[0],
                                "Dimensões Originais": f"{b.original_c:.2f}x{b.original_l:.2f}x{b.original_a:.2f}",
                                "Volume": f"{b.volume:.3f} m³"
                            } for b in unplaced
                        ])
                        unplaced_summary = unplaced_df.groupby(['SKU', 'Dimensões Originais', 'Volume']).size().reset_index(name='Quantidade')
                        st.dataframe(unplaced_summary, hide_index=True, use_container_width=True)
                        
                        st.error(f"❌ {len(unplaced)} caixas não couberam no trailer")
                    else:
                        st.success("✅ Todas as caixas foram empacotadas!")
                
                with tab2:
                    if not missing.empty:
                        st.dataframe(missing[['COD SKU']].drop_duplicates(), hide_index=True)
                    else:
                        st.success("✅ Todas as medidas foram encontradas!")

            # Resumo final
            if eficiencia > 80:
                st.success(f"🎉 Excelente! Ocupação de {eficiencia:.1f}% com {len(placed)} caixas empacotadas")
            elif eficiencia > 60:
                st.warning(f"⚠️ Razoável. Ocupação de {eficiencia:.1f}% - considere ajustar rotações")
            else:
                st.error(f"❌ Baixa eficiência: {eficiencia:.1f}% - verifique dimensões e rotações")

        except Exception as e:
            st.error(f"❌ ERRO: {str(e)}")
            st.exception(e)

if __name__ == "__main__":
    main()



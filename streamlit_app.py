import math
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import List, Tuple, Optional
from itertools import cycle

# ========================== CLASSE OTIMIZADA ==========================
class Box:
    __slots__ = ['id', 'dims', 'pos', 'color']
    def __init__(self, sku: str, dims: tuple):
        self.id = sku
        self.dims = sorted(dims, reverse=True)  # Sempre orienta maior lado primeiro
        self.pos: Optional[Tuple[float, float, float]] = None
        self.color: Optional[str] = None
        
    @property
    def volume(self):
        return self.dims[0] * self.dims[1] * self.dims[2]

    def rotate(self, axis: int):
        """Permite rotação em 3 eixos diferentes"""
        axes = [(0,1,2), (0,2,1), (1,2,0)]
        new_dims = [self.dims[axes[axis][0]], 
                   self.dims[axes[axis][1]], 
                   self.dims[axes[axis][2]]]
        return new_dims

class Truck:
    def __init__(self, length: float, width: float, height: float):
        self.dims = (length, width, height)
        self.volume = length * width * height
        self.layers = []
        
    def add_layer(self, height: float):
        self.layers.append({
            'height': height,
            'skyline': [(0, 0, self.dims[0])],  # (x, y, available_length)
            'boxes': []
        })

# ========================== ALGORITMO FORTEMENTE TIPADO ==========================
def optimized_packer(truck: Truck, boxes: List[Box], palette_colors: list):
    current_z = 0.0
    color_cycle = cycle(palette_colors)
    remaining_boxes = boxes.copy()
    
    while remaining_boxes and current_z < truck.dims[2]:
        best_fit = None
        best_orientation = 0
        best_position = (0, 0, current_z)
        
        # Tenta encontrar o melhor encaixe para cada caixa restante
        for idx, box in enumerate(remaining_boxes):
            for orientation in range(3):
                dims = box.rotate(orientation)
                if dims[2] > (truck.dims[2] - current_z):
                    continue  # Não cabe na altura restante
                
                # Procura no último layer primeiro
                if truck.layers:
                    layer = truck.layers[-1]
                    for seg in layer['skyline']:
                        x, y, avail = seg
                        if dims[0] <= avail and dims[1] <= (truck.dims[1] - y):
                            # Calcula eficiência do posicionamento
                            space_usage = (dims[0] * dims[1]) / (avail * truck.dims[1])
                            if not best_fit or space_usage > best_fit[2]:
                                best_fit = (idx, orientation, (x, y, current_z), space_usage)
                            break
                
                # Se não encontrou, tenta novo layer
                if not best_fit and dims[2] <= (truck.dims[2] - current_z):
                    layer_height = dims[2]
                    best_fit = (idx, orientation, (0, 0, current_z + layer_height), 1.0)
        
        if best_fit:
            idx, orient, pos, _ = best_fit
            selected = remaining_boxes.pop(idx)
            selected.dims = selected.rotate(orient)
            selected.pos = pos
            selected.color = next(color_cycle)
            
            if not truck.layers or pos[2] > current_z:
                truck.add_layer(selected.dims[2])
                current_z += selected.dims[2]
            
            # Atualiza skyline
            layer = truck.layers[-1]
            new_segments = []
            for seg in layer['skyline']:
                x, y, avail = seg
                if x == pos[0] and y <= pos[1] < (y + avail):
                    # Divide o segmento
                    new_segments.append((x, pos[1] + selected.dims[1], avail - (pos[1] - y)))
                else:
                    new_segments.append(seg)
            layer['skyline'] = new_segments
            layer['boxes'].append(selected)
        else:
            break  # Não cabe mais nada
    
    return remaining_boxes

# ========================== VISUALIZAÇÃO INTERATIVA ==========================
def create_interactive_3d(truck: Truck):
    fig = go.Figure()
    
    # Adiciona o contorno do caminhão
    fig.add_trace(go.Scatter3d(
        x=[0, truck.dims[0], truck.dims[0], 0, 0],
        y=[0, 0, truck.dims[1], truck.dims[1], 0],
        z=[0, 0, 0, 0, 0],
        mode='lines',
        line=dict(color='gray', width=2),
        name='Base'
    ))
    
    # Adiciona as caixas
    for layer in truck.layers:
        for box in layer['boxes']:
            x, y, z = box.pos
            fig.add_trace(go.Mesh3d(
                x=[x, x+box.dims[0], x+box.dims[0], x, x, x+box.dims[0], x+box.dims[0], x],
                y=[y, y, y+box.dims[1], y+box.dims[1], y, y, y+box.dims[1], y+box.dims[1]],
                z=[z, z, z, z, z+box.dims[2], z+box.dims[2], z+box.dims[2], z+box.dims[2]],
                i=[7, 0, 0, 0, 4, 4, 6, 6],
                j=[3, 4, 1, 2, 5, 6, 5, 2],
                k=[0, 7, 2, 3, 6, 7, 1, 1],
                color=box.color,
                opacity=0.8,
                text=f"SKU: {box.id}<br>Dimensões: {box.dims[0]}x{box.dims[1]}x{box.dims[2]}",
                hoverinfo='text'
            ))
    
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Comprimento (m)', range=[0, truck.dims[0]]),
            yaxis=dict(title='Largura (m)', range=[0, truck.dims[1]]),
            zaxis=dict(title='Altura (m)', range=[0, truck.dims[2]]),
            aspectratio=dict(x=truck.dims[0], y=truck.dims[1], z=truck.dims[2])
        ),
        margin=dict(r=20, l=20, b=20, t=40),
        hovermode='closest'
    )
    return fig

# ========================== INTERFACE STREAMLIT ==========================
def main():
    st.set_page_config(page_title="Otimizador 3D Avançado", layout="wide")
    
    st.title("🚛 Sistema Inteligente de Gestão de Carga")
    
    with st.sidebar:
        st.header("Configurações do Veículo")
        col1, col2, col3 = st.columns(3)
        length = col1.number_input("Comprimento (m)", 1.0, 20.0, 13.6)
        width = col2.number_input("Largura (m)", 1.0, 3.0, 2.45)
        height = col3.number_input("Altura (m)", 1.0, 4.0, 2.9)
        
        st.header("Cores da Paleta")
        colors = st.multiselect(
            "Selecione cores para os produtos",
            options=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEEAD', '#FF9999'],
            default=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
        )
        
        st.header("Upload de Dados")
        cargo_file = st.file_uploader("Dados de Carga (Excel)", type="xlsx")
        measures_file = st.file_uploader("Tabela de Medidas (Excel)", type="xlsx")
    
    if cargo_file and measures_file:
        try:
            with st.spinner("Processando dados e otimizando layout..."):
                # Carregar e validar dados
                cargo_df = pd.read_excel(cargo_file)
                measures_df = pd.read_excel(measures_file)
                
                required_cols = ['SKU', 'QMM', 'QTDE', 'ALTURA', 'LARGURA', 'COMPRIMENTO']
                if not all(col in cargo_df.columns for col in required_cols):
                    st.error("Colunas obrigatórias ausentes nos arquivos!")
                    return
                
                # Processar caixas
                boxes = []
                for _, row in cargo_df.iterrows():
                    num_boxes = math.ceil(row['QTDE'] / row['QMM'])
                    for i in range(num_boxes):
                        boxes.append(Box(
                            sku=row['SKU'],
                            dims=(row['COMPRIMENTO'], row['LARGURA'], row['ALTURA'])
                        ))
                
                if not boxes:
                    st.warning("Nenhuma caixa para carregar!")
                    return
                
                # Otimizar layout
                truck = Truck(length, width, height)
                unloaded = optimized_packer(truck, boxes, colors)
                
                # Resultados
                st.header(f"Resultados: {len(boxes)-len(unloaded)}/{len(boxes)} Caixas Carregadas")
                
                cols = st.columns(4)
                cols[0].metric("Cubagem Utilizada", f"{sum(b.volume for b in truck.layers[-1]['boxes'])/truck.volume:.1%}")
                cols[1].metric("Espaço Residual", f"{truck.volume - sum(b.volume for b in boxes):.2f}m³")
                cols[2].metric("Camadas Utilizadas", len(truck.layers))
                cols[3].metric("Não Carregados", len(unloaded), delta_color="inverse")
                
                # Visualização 3D Interativa
                st.subheader("Visualização Tridimensional")
                fig = create_interactive_3d(truck)
                st.plotly_chart(fig, use_container_width=True)
                
                # Análise Detalhada
                with st.expander("📊 Detalhamento da Carga"):
                    loaded_df = pd.DataFrame([{
                        'SKU': box.id,
                        'Posição': f"{box.pos[0]:.2f}x{box.pos[1]:.2f}x{box.pos[2]:.2f}",
                        'Dimensões': f"{box.dims[0]}x{box.dims[1]}x{box.dims[2]}",
                        'Volume': box.volume,
                        'Camada': idx+1
                    } for idx, layer in enumerate(truck.layers) for box in layer['boxes']])
                    
                    st.dataframe(
                        loaded_df,
                        column_config={
                            'SKU': 'Produto',
                            'Posição': st.column_config.TextColumn(width='medium'),
                            'Dimensões': st.column_config.TextColumn('Medidas (m)'),
                            'Volume': st.column_config.NumberColumn(format="%.2f m³")
                        },
                        hide_index=True
                    )
                
                # Verificação de Integridade
                with st.expander("🔍 Validação de Cálculos"):
                    st.subheader("Verificação de Consistência")
                    
                    total_loaded = sum(b.volume for layer in truck.layers for b in layer['boxes'])
                    overlaps = 0
                    for i, box1 in enumerate(boxes):
                        if not box1.pos:
                            continue
                        for box2 in boxes[i+1:]:
                            if box2.pos and (
                                box1.pos[0] < box2.pos[0]+box2.dims[0] and
                                box1.pos[0]+box1.dims[0] > box2.pos[0] and
                                box1.pos[1] < box2.pos[1]+box2.dims[1] and
                                box1.pos[1]+box1.dims[1] > box2.pos[1] and
                                box1.pos[2] < box2.pos[2]+box2.dims[2] and
                                box1.pos[2]+box1.dims[2] > box2.pos[2]
                            ):
                                overlaps += 1
                    
                    check_cols = st.columns(3)
                    check_cols[0].metric("Sobreposições Detectadas", overlaps, help="Número de caixas sobrepostas")
                    check_cols[1].metric("Volume Total x Capacidade", 
                                       f"{total_loaded:.2f}/{truck.volume:.2f}m³",
                                       f"{(total_loaded/truck.volume)*100:.1f}%")
                    check_cols[2].metric("Integridade Espacial", 
                                       "✅ Válido" if overlaps == 0 else "❌ Inválido")
                
                # Não Carregados
                if unloaded:
                    st.error(f"⚠️ {len(unloaded)} volumes não puderam ser carregados!")
                    unloaded_summary = pd.DataFrame({
                        'SKU': [b.id for b in unloaded],
                        'Quantidade': [1]*len(unloaded),
                        'Motivo': ['Altura insuficiente' if b.dims[2] > (height - 0.1) 
                                  else 'Espaço inadequado' for b in unloaded]
                    }).groupby(['SKU', 'Motivo']).count().reset_index()
                    
                    st.dataframe(
                        unloaded_summary,
                        column_config={
                            'SKU': 'Produto',
                            'Motivo': 'Causa',
                            'Quantidade': 'Qtd'
                        },
                        hide_index=True
                    )
                
        except Exception as e:
            st.error(f"Erro crítico: {str(e)}")
    else:
        st.info("⤵️ Carregue os arquivos necessários na barra lateral para iniciar")

if __name__ == "__main__":
    main()

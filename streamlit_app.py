import math
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# ... (mantenha as mesmas classes Box, Trailer, SkylineLayer e funções pack_grouped, load_files, expand_grouped, cube_edges e add_box)

def main():
    # Configuração inicial da página
    st.set_page_config(
        page_title="Cubagem Inteligente - Logística 4.0",
        page_icon="🚚",
        layout="wide"
    )
    
    # CSS customizado para melhorar a aparência
    st.markdown("""
    <style>
    .metric-card {
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        background: #f8f9fa;
        margin-bottom: 20px;
    }
    .header {
        color: #2c3e50;
        border-bottom: 3px solid #3498db;
        margin-bottom: 30px;
    }
    </style>
    """, unsafe_allow_html=True)

    # Header profissional
    st.markdown('<div class="header"><h1>📦 Sistema Inteligente de Cubagem - LogProd</h1></div>', unsafe_allow_html=True)
    
    # Divisão em colunas para entrada de dados
    col1, col2, col3 = st.columns([1,2,3])
    
    with col1:
        st.subheader("📐 Dimensões da Carreta")
        c = st.number_input("Comprimento (m)", min_value=1.0, value=13.6, step=0.1)
        l = st.number_input("Largura (m)", min_value=1.0, value=2.4, step=0.1)
        a = st.number_input("Altura (m)", min_value=1.0, value=2.5, step=0.1)
        trailer = Trailer(c, l, a)
        
        st.subheader("📁 Arquivos de Entrada")
        car_file = st.file_uploader("Carregamento (.xlsx)", type="xlsx")
        med_file = st.file_uploader("Medidas (.xlsx)", type="xlsx")
        
        btn_processar = st.button("🚀 Processar Cubagem", type="primary")

    if btn_processar and car_file and med_file:
        try:
            merged, missing = load_files(car_file, med_file)
            sku_groups = expand_grouped(merged)
            placed, left = pack_grouped(trailer, sku_groups)
            
            # Métricas principais
            vol_total = trailer.volume
            vol_usado = sum(b.volume for b in placed)
            percentual = (vol_usado / vol_total) * 100 if vol_total > 0 else 0
            
            metric_cols = st.columns(4)
            with metric_cols[0]:
                st.markdown(f'<div class="metric-card">'
                            f'<h3>📦 Volumes</h3>'
                            f'<p style="font-size:24px; margin:0;">{len(placed)}/{len(placed)+len(left)}</p>'
                            f'</div>', unsafe_allow_html=True)
                
            with metric_cols[1]:
                st.markdown(f'<div class="metric-card">'
                            f'<h3>📏 Cubagem</h3>'
                            f'<p style="font-size:24px; margin:0;">{vol_usado:.1f}m³/{vol_total:.1f}m³</p>'
                            f'</div>', unsafe_allow_html=True)
                
            with metric_cols[2]:
                st.markdown(f'<div class="metric-card">'
                            f'<h3>📈 Ocupação</h3>'
                            f'<p style="font-size:24px; margin:0;">{percentual:.1f}%</p>'
                            f'</div>', unsafe_allow_html=True)
                
            with metric_cols[3]:
                status = "💚 Espaço Suficiente" if len(left) == 0 else "🔴 Espaço Insuficiente"
                st.markdown(f'<div class="metric-card">'
                            f'<h3>🔄 Status</h3>'
                            f'<p style="font-size:24px; margin:0;">{status}</p>'
                            f'</div>', unsafe_allow_html=True)
            
            # Visualização 3D
            st.subheader("🖼️ Visualização Tridimensional")
            fig = plt.figure(figsize=(12, 6))
            ax = fig.add_subplot(111, projection='3d')
            
            ax.set_xlim(0, trailer.c)
            ax.set_ylim(0, trailer.l)
            ax.set_zlim(0, trailer.a)
            ax.set_xlabel("Comprimento")
            ax.set_ylabel("Largura")
            ax.set_zlabel("Altura")
            ax.view_init(elev=18, azim=-60)
            
            # Gerar cores
            bases = list(set(["-".join(b.id.split("-")[:-1]) for b in placed]))
            cores = ListedColormap(plt.cm.tab20.colors[:len(bases)])(range(len(bases)))
            color_map = {base: cor for base, cor in zip(bases, cores)}
            
            for b in placed:
                sku_base = "-".join(b.id.split("-")[:-1])
                add_box(ax, *b.pos, b.c, b.l, b.a, color_map[sku_base])
            
            st.pyplot(fig)
            
            # Dados das exceções
            if len(left) > 0 or not missing.empty:
                st.subheader("⚠️ Itens com Problemas")
                tabs = st.tabs(["Volumes Não Alocados", "SKUs sem Medidas"])
                
                with tabs[0]:
                    nao_alocados = pd.DataFrame({
                        "SKU": [b.id.split("-")[0] for b in left],
                        "Quantidade": [1]*len(left)
                    }).groupby("SKU").count().reset_index()
                    st.dataframe(nao_alocados, hide_index=True)
                
                with tabs[1]:
                    st.dataframe(missing[["COD SKU"]].drop_duplicates(), hide_index=True)
            
        except Exception as e:
            st.error(f"Erro no processamento: {str(e)}")

if __name__ == "__main__":
    main()

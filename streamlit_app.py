import math
import streamlit as st
from typing import Dict, List, Tuple
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

# ... (mantidas as classes Box, Trailer, SkylineLayer e funções auxiliares, exceto a GUI)

# Configurações iniciais do Streamlit
st.set_page_config(page_title="Simulador de Cubagem", layout="wide")
st.title("Simulador de Cubagem — Skyline + SKUs agrupados")

# Sidebar para inputs
with st.sidebar:
    st.header("Configurações do Trailer")
    c = st.number_input("Comprimento (m)", min_value=0.1, value=13.6)
    l = st.number_input("Largura (m)", min_value=0.1, value=2.45)
    a = st.number_input("Altura (m)", min_value=0.1, value=2.9)
    
    st.header("Arquivos de Entrada")
    car_file = st.file_uploader("Carregamento.xlsx", type="xlsx")
    med_file = st.file_uploader("Medidas.xlsx", type="xlsx")

# Seção principal
if car_file and med_file:
    # Processamento dos dados
    merged, missing = load_files(car_file, med_file)
    
    if not merged.empty:
        sku_groups = expand_grouped(merged)
        trailer = Trailer(c, l, a)
        placed, left = pack_grouped(trailer, sku_groups)
        
        # Cálculo de métricas
        vol_used = sum(b.volume for b in placed)
        utilization = vol_used / trailer.volume * 100
        
        # Exibição dos resultados
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Plotagem 3D
            fig = plt.figure(figsize=(10, 6))
            ax = fig.add_subplot(111, projection='3d')
            
            ax.set_xlim(0, trailer.c)
            ax.set_ylim(0, trailer.l)
            ax.set_zlim(0, trailer.a)
            ax.set_xlabel("Comprimento (m)")
            ax.set_ylabel("Largura (m)")
            ax.set_zlabel("Altura (m)")
            ax.view_init(elev=18, azim=-60)
            ax.set_box_aspect((trailer.c, trailer.l, trailer.a))
            
            # Contorno do trailer
            ax.add_collection3d(
                Line3DCollection(cube_edges(0, 0, 0, trailer.c, trailer.l, trailer.a),
                                colors="black", linewidths=0.5)
            )
            
            # Caixas colocadas
            bases = list(set("-".join(b.id.split("-")[:-1]) for b in placed))
            cmap = plt.cm.get_cmap("tab20", len(bases))
            colors = {sku: cmap(i) for i, sku in enumerate(bases)}
            
            for b in placed:
                add_box(ax, *b.pos, b.c, b.l, b.a, colors["-".join(b.id.split("-")[:-1])])
            
            st.pyplot(fig)
        
        with col2:
            st.metric("Utilização de Volume", f"{utilization:.1f}%")
            st.metric("Caixas Alocadas/Total", f"{len(placed)}/{len(placed)+len(left)}")
            
            with st.expander("SKUs Não Encontrados", expanded=False):
                if not missing.empty:
                    st.write(missing[["COD SKU", "QTDE", "QMM"]])
                else:
                    st.write("Todos os SKUs foram encontrados")
            
            with st.expander("Não Alocados", expanded=False):
                if left:
                    counts = {}
                    for b in left:
                        base = "-".join(b.id.split("-")[:-1])
                        counts[base] = counts.get(base, 0) + 1
                    st.write(pd.DataFrame({"SKU": counts.keys(), "Não Alocados": counts.values()}))
                else:
                    st.write("Todas as caixas foram alocadas")
    else:
        st.error("Nenhum SKU válido encontrado nos arquivos carregados")
else:
    st.info("Faça upload dos dois arquivos Excel para iniciar a simulação")

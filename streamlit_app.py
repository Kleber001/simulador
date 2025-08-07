import math
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from itertools import permutations

class Box3D:
    def __init__(self, sku: str, comprimento: float, largura: float, altura: float):
        self.id = sku
        self.dimensoes = (comprimento, largura, altura)
        self.posicao = (0.0, 0.0, 0.0)
        self.orientacao = self.dimensoes

    def gerar_rotacoes(self, eixos_ativos: list):
        rotacoes = list(permutations(self.dimensoes))
        return [r for r in rotacoes 
                if (r[0] == self.dimensoes[0] and 'comprimento' in eixos_ativos) or
                   (r[1] == self.dimensoes[1] and 'largura' in eixos_ativos) or
                   (r[2] == self.dimensoes[2] and 'altura' in eixos_ativos)]

class Trailer3D:
    def __init__(self, comprimento: float, largura: float, altura: float):
        self.dimensoes = (comprimento, largura, altura)
        self.volume_total = comprimento * largura * altura

class Cubagem3D:
    def __init__(self, trailer: Trailer3D):
        self.trailer = trailer
        self.camadas = []
        self.caixas_colocadas = []
        self.nao_colocados = []

    def empacotar(self, lista_caixas: list, eixos_rotacao: list):
        c, l, a = self.trailer.dimensoes
        z_atual = 0.0
        altura_camada = 0.0
        
        for caixa in sorted(lista_caixas, key=lambda x: max(x.dimensoes), reverse=True):
            melhor_pos = None
            melhor_orient = None
            
            for rot in caixa.gerar_rotacoes(eixos_rotacao):
                cx, cy, cz = rot
                if self._verificar_colocacao(cx, cy, z_atual, cz):
                    melhor_orient = rot
                    altura_camada = max(altura_camada, cz)
                    break
                    
            if melhor_orient:
                caixa.orientacao = melhor_orient
                caixa.posicao = (0.0, 0.0, z_atual)
                self.caixas_colocadas.append(caixa)
                z_atual += altura_camada
                
                if z_atual > a:
                    self.nao_colocados.extend(lista_caixas[lista_caixas.index(caixa):])
                    break
            else:
                self.nao_colocados.append(caixa)
                
        return self.caixas_colocadas, self.nao_colocados

    def _verificar_colocacao(self, cx: float, cy: float, z_base: float, cz: float):
        c_t, l_t, a_t = self.trailer.dimensoes
        return (cx <= c_t and cy <= l_t and (z_base + cz) <= a_t)

class Visualizacao3D:
    def __init__(self, trailer: Trailer3D):
        self.trailer = trailer
        self.figuras = []
        
    def gerar_vistas(self, caixas: list):
        self.figuras = [
            self._criar_figura(caixas, elev=25, azim=-45, titulo='Perspectiva 3D'),
            self._criar_figura(caixas, elev=90, azim=-90, titulo='Vista Superior'),
            self._criar_figura(caixas, elev=0, azim=-90, titulo='Vista Lateral'),
            self._criar_figura(caixas, elev=0, azim=0, titulo='Vista Frontal')
        ]
        return self.figuras

    def _criar_figura(self, caixas: list, elev: float, azim: float, titulo: str):
        c_t, l_t, a_t = self.trailer.dimensoes
        fig = plt.figure(figsize=(8, 6))
        ax = fig.add_subplot(111, projection='3d')
        
        ax.set(
            xlim=(0, c_t),
            ylim=(0, l_t),
            zlim=(0, a_t),
            xlabel='Comprimento (m)',
            ylabel='Largura (m)',
            zlabel='Altura (m)',
            box_aspect=(c_t, l_t, a_t)
        )
        ax.view_init(elev=elev, azim=azim)
        ax.set_title(titulo, pad=12)
        
        cmap = cm.get_cmap('tab20')
        skus = list({c.id.split('-')[0] for c in caixas})
        cores = {sku: cmap(i/len(skus)) for i, sku in enumerate(skus)}
        
        for caixa in caixas:
            x, y, z = caixa.posicao
            cx, cy, cz = caixa.orientacao
            
            faces = [
                [[x, y, z], [x+cx, y, z], [x+cx, y+cy, z], [x, y+cy, z]],
                [[x, y, z+cz], [x+cx, y, z+cz], [x+cx, y+cy, z+cz], [x, y+cy, z+cz]],
                [[x, y, z], [x+cx, y, z], [x+cx, y, z+cz], [x, y, z+cz]],
                [[x, y+cy, z], [x+cx, y+cy, z], [x+cx, y+cy, z+cz], [x, y+cy, z+cz]],
                [[x, y, z], [x, y+cy, z], [x, y+cy, z+cz], [x, y, z+cz]],
                [[x+cx, y, z], [x+cx, y+cy, z], [x+cx, y+cy, z+cz], [x+cx, y, z+cz]],
            ]
            
            ax.add_collection3d(Poly3DCollection(
                faces, facecolors=cores[caixa.id.split('-')[0]], edgecolors='#333', linewidths=0.3, alpha=0.9
            ))
            
        return fig

def processar_arquivos(car_file, med_file):
    df_car = pd.read_excel(car_file)
    df_med = pd.read_excel(med_file)
    
    df_med['CHAVE'] = df_med.apply(
        lambda r: f"{r['COD_FAMILIA']}-{r['COD_TAMANHO']}-{int(r['QMM'])}", axis=1)
    
    df_merged = df_car.merge(
        df_med[['CHAVE', 'COMPRIMENTO', 'LARGURA', 'ALTURA']],
        on='CHAVE',
        how='left'
    )
    
    df_merged['QTD_CAIXAS'] = df_med.apply(
        lambda r: math.ceil(r['QUANTIDADE'] / r['QMM']) if r['QMM'] > 0 else 0, axis=1)
    
    caixas = []
    for _, row in df_merged.iterrows():
        for i in range(row['QTD_CAIXAS']):
            caixas.append(Box3D(
                f"{row['COD_SKU']}-{i+1}",
                row['COMPRIMENTO'],
                row['LARGURA'],
                row['ALTURA']
            ))
            
    return caixas, df_merged[df_merged['COMPRIMENTO'].isna()]

def main():
    st.set_page_config(
        page_title="Sistema de Cubagem 3D Profissional",
        layout="wide",
        page_icon="📦"
    )
    
    st.title("📦 Sistema Inteligente de Cubagem 3D")
    
    with st.sidebar:
        st.header("⚙️ Configurações")
        rotacoes = st.multiselect(
            'Eixos Permitidos para Rotação:',
            ['Comprimento', 'Largura', 'Altura'],
            ['Comprimento', 'Largura']
        )
        
        st.header("📐 Dimensões da Carreta")
        comprimento = st.number_input("Comprimento (m)", 5.0, 20.0, 13.6)
        largura = st.number_input("Largura (m)", 2.0, 3.0, 2.45)
        altura = st.number_input("Altura (m)", 2.0, 4.0, 2.5)
        
        st.header("📂 Upload de Arquivos")
        car_file = st.file_uploader("Carregamento.xlsx", type="xlsx")
        med_file = st.file_uploader("Medidas.xlsx", type="xlsx")
    
    if st.button("▶️ Executar Simulação", type="primary"):
        if not (car_file and med_file):
            st.error("Por favor, carregue ambos os arquivos!")
            return
            
        with st.spinner("Processando arquivos..."):
            try:
                caixas, erros = processar_arquivos(car_file, med_file)
                trailer = Trailer3D(comprimento, largura, altura)
                
                cubagem = Cubagem3D(trailer)
                colocadas, nao_colocadas = cubagem.empacotar(caixas, [r[0].lower() for r in rotacoes])
                
                st.subheader("📊 Resultados da Simulação")
                col1, col2, col3 = st.columns(3)
                col1.metric("Caixas Alocadas", len(colocadas))
                col2.metric("Taxa de Ocupação", 
                           f"{(sum(c.volume for c in colocadas)/trailer.volume_total)*100:.1f}%")
                col3.metric("Caixas Não Alocadas", len(nao_colocadas))
                
                vis = Visualizacao3D(trailer)
                figs = vis.gerar_vistas(colocadas)
                
                st.subheader("📐 Visualizações Técnicas")
                cols = st.columns(2)
                for idx, fig in enumerate(figs):
                    with cols[idx % 2]:
                        st.pyplot(fig)
                        st.caption(f"Visualização: {['Perspectiva 3D', 'Superior', 'Lateral', 'Frontal'][idx]}")
                        
                if not erros.empty:
                    st.subheader("⚠️ Dados com Problemas")
                    st.dataframe(erros[['COD_SKU', 'CHAVE']].drop_duplicates())
                    
            except Exception as e:
                st.error(f"Erro no processamento: {str(e)}")

if __name__ == "__main__":
    main()

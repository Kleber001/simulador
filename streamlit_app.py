import math
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from typing import List, Tuple

class Box:
    def __init__(self, sku: str, comprimento: float, largura: float, altura: float):
        self.id = sku
        self.dimensoes_originais = (comprimento, largura, altura)
        self.posicao = (0.0, 0.0, 0.0)
        self.orientacao = self.dimensoes_originais

    def gerar_rotacoes(self, eixos_ativos: list):
        """Gera combinações válidas baseadas nos eixos selecionados"""
        rotacoes = []
        c, l, a = self.dimensoes_originais
        
        if 'Comprimento' in eixos_ativos:
            rotacoes += [(c, l, a), (a, l, c), (c, a, l), (l, c, a)]
        if 'Largura' in eixos_ativos:
            rotacoes += [(l, c, a), (a, c, l), (l, a, c), (c, l, a)]
        if 'Altura' in eixos_ativos:
            rotacoes += [(a, c, l), (l, c, a), (a, l, c), (c, a, l)]
            
        return list(set(rotacoes))

    @property
    def volume(self):
        return math.prod(self.dimensoes_originais)

class Carreta:
    def __init__(self, comprimento: float, largura: float, altura: float):
        self.comprimento = comprimento
        self.largura = largura
        self.altura = altura
        
    @property
    def volume_total(self):
        return self.comprimento * self.largura * self.altura

class AlgoritmoCubagem:
    def __init__(self, carreta: Carreta):
        self.carreta = carreta
    
    def empacotar(self, caixas: list, eixos_rotacao: list):
        colocadas = []
        nao_colocadas = []
        z_atual = 0.0
        altura_camada = 0.0
        
        for caixa in sorted(caixas, key=lambda x: max(x.dimensoes_originais), reverse=True):
            melhor_orientacao = None
            melhor_posicao = None
            
            for rotacao in caixa.gerar_rotacoes(eixos_rotacao):
                c, l, a = rotacao
                if self._verificar_colocacao(c, l, z_atual + altura_camada + a):
                    if not melhor_orientacao or a < melhor_orientacao[2]:
                        melhor_orientacao = rotacao
                        pos_x = 0.0  # Simulação simplificada
                        pos_y = 0.0
                        melhor_posicao = (pos_x, pos_y, z_atual)
            
            if melhor_orientacao:
                caixa.orientacao = melhor_orientacao
                caixa.posicao = melhor_posicao
                colocadas.append(caixa)
                altura_camada = max(altura_camada, melhor_orientacao[2])
            else:
                nao_colocadas.append(caixa)
                z_atual += altura_camada
                altura_camada = 0.0
                
        return colocadas, nao_colocadas
    
    def _verificar_colocacao(self, comprimento: float, largura: float, altura_total: float):
        return (comprimento <= self.carreta.comprimento and
                largura <= self.carreta.largura and
                altura_total <= self.carreta.altura)

class Visualizador3D:
    def __init__(self, carreta: Carreta):
        self.carreta = carreta
    
    def gerar_vistas(self, caixas: list):
        figuras = []
        visoes = [
            {'elev': 35, 'azim': -60, 'titulo': 'Perspectiva 3D'},
            {'elev': 90, 'azim': -90, 'titulo': 'Vista Superior'},
            {'elev': 0, 'azim': -90, 'titulo': 'Vista Lateral'},
            {'elev': 0, 'azim': 0, 'titulo': 'Vista Frontal'}
        ]
        
        for visao in visoes:
            fig = plt.figure(figsize=(8, 6))
            ax = fig.add_subplot(111, projection='3d')
            self._configurar_vista(ax, visao)
            self._plotar_caixas(ax, caixas)
            figuras.append(fig)
            
        return figuras
    
    def _configurar_vista(self, ax, visao):
        ax.set_xlim3d(0, self.carreta.comprimento)
        ax.set_ylim3d(0, self.carreta.largura)
        ax.set_zlim3d(0, self.carreta.altura)
        ax.set_box_aspect((self.carreta.comprimento, 
                         self.carreta.largura, 
                         self.carreta.altura))
        ax.view_init(elev=visao['elev'], azim=visao['azim'])
        ax.set_title(visao['titulo'], pad=15)
        ax.grid(True, alpha=0.3)
        
    def _plotar_caixas(self, ax, caixas):
        cores = cm.get_cmap('tab20', len(caixas))
        for idx, caixa in enumerate(caixas):
            x, y, z = caixa.posicao
            dx, dy, dz = caixa.orientacao
            
            faces = [
                [(x, y, z), (x+dx, y, z), (x+dx, y+dy, z), (x, y+dy, z)],
                [(x, y, z+dz), (x+dx, y, z+dz), (x+dx, y+dy, z+dz), (x, y+dy, z+dz)],
                [(x, y, z), (x+dx, y, z), (x+dx, y, z+dz), (x, y, z+dz)],
                [(x, y+dy, z), (x+dx, y+dy, z), (x+dx, y+dy, z+dz), (x, y+dy, z+dz)],
                [(x, y, z), (x, y+dy, z), (x, y+dy, z+dz), (x, y, z+dz)],
                [(x+dx, y, z), (x+dx, y+dy, z), (x+dx, y+dy, z+dz), (x+dx, y, z+dz)],
            ]
            
            ax.add_collection3d(Poly3DCollection(
                faces, 
                facecolors=cores(idx),
                edgecolors='#333',
                linewidths=0.3,
                alpha=0.9
            ))

def processar_arquivos(car_file, med_file):
    try:
        df_car = pd.read_excel(car_file, engine='openpyxl')
        df_med = pd.read_excel(med_file, engine='openpyxl')
        
        # Validação de colunas
        colunas_necessarias = {
            'car': ['COD SKU', 'QTDE', 'QMM'],
            'med': ['COD FAMILIA', 'COD TAMANHO', 'QMM', 'COMPRIMENTO', 'LARGURA', 'ALTURA']
        }
        
        for col in colunas_necessarias['car']:
            if col not in df_car.columns:
                raise ValueError(f"Coluna '{col}' ausente no arquivo de carregamento")
                
        for col in colunas_necessarias['med']:
            if col not in df_med.columns:
                raise ValueError(f"Coluna '{col}' ausente no arquivo de medidas")
        
        # Processamento dos dados
        df_med['CHAVE'] = df_med['COD FAMILIA'] + '-' + df_med['COD TAMANHO'].astype(str) + '-' + df_med['QMM'].astype(str)
        df_car['CHAVE'] = df_car['COD SKU'].str.split('-').str[0] + '-' + df_car['COD SKU'].str.split('-').str[2] + '-' + df_car['QMM'].astype(str)
        
        df_merged = df_car.merge(df_med, on='CHAVE', how='left')
        df_merged['QTD_CAIXAS'] = df_merged.apply(lambda x: math.ceil(x['QTDE'] / x['QMM']) if x['QMM'] > 0 else 0, axis=1)
        
        missing = df_merged[df_merged['COMPRIMENTO'].isna()]
        df_valid = df_merged.dropna(subset=['COMPRIMENTO'])
        
        # Gerar caixas
        caixas = []
        for _, row in df_valid.iterrows():
            for i in range(row['QTD_CAIXAS']):
                caixas.append(Box(
                    f"{row['COD SKU']}-{i+1}",
                    row['COMPRIMENTO'],
                    row['LARGURA'],
                    row['ALTURA']
                ))
                
        return caixas, missing
    
    except Exception as e:
        st.error(f"Erro no processamento: {str(e)}")
        return [], pd.DataFrame()

def main():
    st.set_page_config(
        page_title="Sistema de Cubagem 3D Pro",
        layout="wide",
        page_icon="📦"
    )
    
    st.title("📦 Sistema Avançado de Cubagem 3D")
    
    with st.sidebar:
        st.header("⚙ Configurações")
        eixos_rotacao = st.multiselect(
            "Eixos de Rotação Permitidos:",
            options=['Comprimento', 'Largura', 'Altura'],
            default=['Comprimento', 'Largura']
        )
        
        st.header("📐 Dimensões da Carreta")
        comprimento = st.number_input("Comprimento (m)", 5.0, 30.0, 13.6)
        largura = st.number_input("Largura (m)", 1.5, 3.0, 2.45)
        altura = st.number_input("Altura (m)", 2.0, 4.0, 2.5)
        
        st.header("📂 Upload de Arquivos")
        car_file = st.file_uploader("Arquivo de Carregamento (.xlsx)", type="xlsx")
        med_file = st.file_uploader("Arquivo de Medidas (.xlsx)", type="xlsx")
    
    if st.button("▶ Iniciar Simulação", type="primary"):
        if not (car_file and med_file):
            st.error("Por favor, carregue ambos os arquivos!")
            return
            
        with st.spinner("Processando dados e calculando a melhor disposição..."):
            caixas, missing = processar_arquivos(car_file, med_file)
            
            if not caixas:
                st.error("Nenhum dado válido encontrado para simulação!")
                return
                
            carreta = Carreta(comprimento, largura, altura)
            algoritmo = AlgoritmoCubagem(carreta)
            colocadas, nao_colocadas = algoritmo.empacotar(caixas, eixos_rotacao)
            
            # Cálculo de métricas
            volume_ocupado = sum(c.volume for c in colocadas)
            eficiencia = (volume_ocupado / carreta.volume_total) * 100 if carreta.volume_total > 0 else 0
            
            # Exibição dos resultados
            col1, col2, col3 = st.columns(3)
            col1.metric("Caixas Alocadas", len(colocadas))
            col2.metric("Eficiência de Carga", f"{eficiencia:.1f}%")
            col3.metric("Volume Ocupado", f"{volume_ocupado:.2f}m³ / {carreta.volume_total:.2f}m³")
            
            # Visualizações
            st.subheader("🎯 Visualizações Técnicas")
            visualizador = Visualizador3D(carreta)
            figuras = visualizador.gerar_vistas(colocadas)
            
            cols = st.columns(2)
            for idx, figura in enumerate(figuras):
                with cols[idx % 2]:
                    st.pyplot(figura)
            
            # Seção de alertas
            if not nao_colocadas or not missing.empty:
                st.subheader("⚠ Itens Problemáticos")
                tab1, tab2 = st.tabs(["Caixas Não Alocadas", "SKUs Sem Medidas"])
                
                with tab1:
                    st.dataframe(pd.DataFrame(
                        {"SKU": [c.id.split('-')[0] for c in nao_colocadas]}
                    ).value_counts().reset_index(name='Quantidade'))
                    
                with tab2:
                    st.dataframe(missing[['COD SKU', 'CHAVE']].drop_duplicates())

if __name__ == "__main__":
    main()

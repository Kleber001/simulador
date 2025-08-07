import math
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

class Caixa3D:
    def __init__(self, sku: str, comprimento: float, largura: float, altura: float):
        self.id = sku
        self.dimensoes = (comprimento, largura, altura)
        self.posicao = (0.0, 0.0, 0.0)
        self.orientacao = self.dimensoes

    def gerar_rotacoes(self, eixos_ativos: list):
        rotacoes = []
        c, l, a = self.dimensoes
        if 'comprimento' in eixos_ativos:
            rotacoes += [(c, l, a), (a, l, c)]
        if 'largura' in eixos_ativos:
            rotacoes += [(l, c, a), (a, c, l)]
        if 'altura' in eixos_ativos:
            rotacoes += [(c, a, l), (l, a, c)]
        return list(set(rotacoes))

    @property
    def volume(self):
        return math.prod(self.dimensoes)

class Carreta3D:
    def __init__(self, comprimento: float, largura: float, altura: float):
        self.comprimento = comprimento
        self.largura = largura
        self.altura = altura
    
    @property
    def volume(self):
        return self.comprimento * self.largura * self.altura

class AlgoritmoEmpacotamento:
    def __init__(self, carreta: Carreta3D):
        self.carreta = carreta
        self.z_atual = 0.0
        self.camada_atual = []
    
    def empacotar(self, caixas: list, eixos_rotacao: list):
        colocadas = []
        nao_colocadas = []
        
        for caixa in sorted(caixas, key=lambda x: max(x.dimensoes), reverse=True):
            colocada = False
            
            for orientacao in caixa.gerar_rotacoes(eixos_rotacao):
                c, l, a = orientacao
                if self._verificar_colocacao(c, l, a):
                    caixa.orientacao = orientacao
                    caixa.posicao = (0, 0, self.z_atual)
                    colocadas.append(caixa)
                    self._atualizar_camada(a)
                    colocada = True
                    break
                    
            if not colocada:
                nao_colocadas.append(caixa)
                
        return colocadas, nao_colocadas
    
    def _verificar_colocacao(self, c: float, l: float, a: float):
        return (c <= self.carreta.comprimento and 
                l <= self.carreta.largura and 
                (self.z_atual + a) <= self.carreta.altura)
    
    def _atualizar_camada(self, altura_caixa: float):
        self.z_atual += altura_caixa

class Visualizador3D:
    def __init__(self, carreta: Carreta3D):
        self.carreta = carreta
        
    def gerar_vistas(self, caixas: list):
        figuras = []
        visoes = [
            {'elev': 25, 'azim': -60, 'titulo': 'Perspectiva 3D'},
            {'elev': 90, 'azim': -90, 'titulo': 'Vista Superior'},
            {'elev': 0, 'azim': -90, 'titulo': 'Vista Lateral'},
            {'elev': 0, 'azim': 0, 'titulo': 'Vista Frontal'}
        ]
        
        for visao in visoes:
            fig = plt.figure(figsize=(8, 6))
            ax = fig.add_subplot(111, projection='3d')
            self._configurar_vista(ax, visao)
            self._desenhar_caixas(ax, caixas)
            figuras.append(fig)
        
        return figuras
    
    def _configurar_vista(self, ax, visao):
        ax.set_xlim(0, self.carreta.comprimento)
        ax.set_ylim(0, self.carreta.largura)
        ax.set_zlim(0, self.carreta.altura)
        ax.set_box_aspect((self.carreta.comprimento, 
                         self.carreta.largura, 
                         self.carreta.altura))
        ax.view_init(elev=visao['elev'], azim=visao['azim'])
        ax.set_title(visao['titulo'], pad=12)
        ax.grid(True, alpha=0.4)
    
    def _desenhar_caixas(self, ax, caixas):
        cmap = cm.get_cmap('tab20')
        skus = {caixa.id.split('-')[0] for caixa in caixas}
        
        for i, sku in enumerate(skus):
            cor = cmap(i / len(skus))
            for caixa in filter(lambda x: x.id.startswith(sku), caixas):
                x, y, z = caixa.posicao
                dx, dy, dz = caixa.orientacao
                
                faces = [
                    [[x, y, z], [x+dx, y, z], [x+dx, y+dy, z], [x, y+dy, z]],
                    [[x, y, z+dz], [x+dx, y, z+dz], [x+dx, y+dy, z+dz], [x, y+dy, z+dz]],
                    [[x, y, z], [x+dx, y, z], [x+dx, y, z+dz], [x, y, z+dz]],
                    [[x, y+dy, z], [x+dx, y+dy, z], [x+dx, y+dy, z+dz], [x, y+dy, z+dz]],
                    [[x, y, z], [x, y+dy, z], [x, y+dy, z+dz], [x, y, z+dz]],
                    [[x+dx, y, z], [x+dx, y+dy, z], [x+dx, y+dy, z+dz], [x+dx, y, z+dz]],
                ]
                
                ax.add_collection3d(Poly3DCollection(faces, 
                    facecolors=cor, edgecolors='#333', linewidths=0.3, alpha=0.9))

def processar_dados(car_file, med_file):
    # Validar arquivos
    colunas_necessarias = {
        'car': ['COD SKU', 'QTDE', 'QMM'],
        'med': ['COD FAMILIA', 'COD TAMANHO', 'QMM', 'COMPRIMENTO', 'LARGURA', 'ALTURA']
    }
    
    try:
        df_car = pd.read_excel(car_file, engine='openpyxl')
        df_med = pd.read_excel(med_file, engine='openpyxl')
        
        # Verificar colunas
        for col in colunas_necessarias['car']:
            if col not in df_car.columns:
                raise ValueError(f"Coluna '{col}' não encontrada no arquivo de carregamento")
                
        for col in colunas_necessarias['med']:
            if col not in df_med.columns:
                raise ValueError(f"Coluna '{col}' não encontrada no arquivo de medidas")
        
        # Processamento
        df_med['CHAVE'] = df_med.apply(
            lambda r: f"{r['COD FAMILIA']}-{r['COD TAMANHO']}-{r['QMM']}", axis=1)
            
        df_car['CHAVE'] = df_car.apply(
            lambda r: f"{r['COD SKU'].split('-')[0]}-{r['COD SKU'].split('-')[2]}-{r['QMM']}", axis=1)
        
        df_merge = df_car.merge(df_med, on='CHAVE', how='left')
        df_merge['QTD_CAIXAS'] = df_merge.apply(
            lambda r: math.ceil(r['QTDE'] / r['QMM']) if r['QMM'] > 0 else 0, axis=1)
        
        missing = df_merge[df_merge['COMPRIMENTO'].isna()]
        df_valid = df_merge.dropna(subset=['COMPRIMENTO'])
        
        # Gerar caixas
        caixas = []
        for _, row in df_valid.iterrows():
            for i in range(row['QTD_CAIXAS']):
                caixas.append(Caixa3D(
                    f"{row['COD SKU']}-{i+1}",
                    row['COMPRIMENTO'],
                    row['LARGURA'],
                    row['ALTURA']
                ))
                
        return caixas, missing
    
    except Exception as e:
        st.error(f"Erro no processamento de arquivos: {str(e)}")
        return [], pd.DataFrame()

def main():
    st.set_page_config(
        page_title="Simulador de Cubagem 3D",
        layout="wide",
        page_icon="📦"
    )
    
    st.title("📦 Simulador Profissional de Cubagem 3D")
    
    with st.sidebar:
        st.header("⚙️ Configurações")
        rotacoes = st.multiselect(
            'Eixos de Rotação Habilitados:',
            ['comprimento', 'largura', 'altura'],
            ['comprimento', 'largura']
        )
        
        st.header("📐 Dimensões da Carreta")
        comprimento = st.number_input("Comprimento (m)", 1.0, 20.0, 13.6)
        largura = st.number_input("Largura (m)", 1.0, 3.0, 2.45)
        altura = st.number_input("Altura (m)", 1.0, 4.0, 2.5)
        
        st.header("📂 Upload de Arquivos")
        car_file = st.file_uploader("Arquivo de Carregamento", type="xlsx")
        med_file = st.file_uploader("Arquivo de Medidas", type="xlsx")
    
    if st.button("▶️ Executar Simulação", type="primary"):
        if not (car_file and med_file):
            st.error("Por favor, carregue ambos os arquivos!")
            return
            
        with st.spinner("Processando dados..."):
            caixas, missing = processar_dados(car_file, med_file)
            
            if not caixas:
                st.error("Nenhum dado válido encontrado para processamento!")
                return
                
            carreta = Carreta3D(comprimento, largura, altura)
            algoritmo = AlgoritmoEmpacotamento(carreta)
            colocadas, nao_colocadas = algoritmo.empacotar(caixas, rotacoes)
            
            total_volume = sum(c.volume for c in colocadas)
            eficiencia = (total_volume / carreta.volume) * 100 if carreta.volume > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Caixas Alocadas", len(colocadas))
            col2.metric("Eficiência de Carga", f"{eficiencia:.1f}%")
            col3.metric("Caixas não Alocadas", len(nao_colocadas))
            
            st.subheader("📊 Visualização Tridimensional")
            visualizador = Visualizador3D(carreta)
            figuras = visualizador.gerar_vistas(colocadas)
            
            cols = st.columns(2)
            for idx, fig in enumerate(figuras):
                with cols[idx % 2]:
                    st.pyplot(fig)
                    st.caption(f"Visualização {idx+1}: {['Perspectiva 3D', 'Superior', 'Lateral', 'Frontal'][idx]}")
            
            if not missing.empty:
                st.subheader("⚠️ Dados com Problemas")
                st.dataframe(missing[['COD SKU', 'CHAVE']].drop_duplicates())

if __name__ == "__main__":
    main()


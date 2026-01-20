import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import base64
from io import BytesIO
from datetime import datetime, timedelta
import unicodedata
from weasyprint import HTML
import warnings
import os
import time
import shutil

# Configurações iniciais
st.set_page_config(page_title="Gerador de Relatórios", page_icon="📊", layout="wide")
warnings.filterwarnings('ignore')

# Tenta importar Selenium (Necessário para o Robô)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False

# --- CSS PARA ESTILO ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; height: 50px; font-weight: bold; }
    .main-header { font-size: 24px; font-weight: bold; color: #333; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Gerador de Relatório de Eventos")

# ==============================================================================
# 1. CONFIGURAÇÃO DO EVENTO (INPUTS GERAIS)
# ==============================================================================
st.sidebar.header("Dados do Relatório")
con_event = st.sidebar.text_input("Nome do Evento (para o PDF)", value="SOBED DAYS")
con_year = st.sidebar.text_input("Ano do Evento", value="2026")

modo_entrada = st.sidebar.radio("Fonte dos Dados:", ("Fazer Upload Manual", "Baixar Automaticamente (Robô)"))

df_final = None

# ==============================================================================
# 2. MODO ROBÔ (DOWNLOAD AUTOMÁTICO)
# ==============================================================================
if modo_entrada == "Baixar Automaticamente (Robô)":
    if not HAS_SELENIUM:
        st.error("⚠️ As bibliotecas do Selenium não estão instaladas. Verifique o requirements.txt.")
    else:
        st.info("🤖 **Configuração do Robô de Acesso**")
        
        c1, c2 = st.columns(2)
        with c1:
            subdominio = st.text_input("Subdomínio (ex: ccm, funfarme)", value="ccm")
            usuario = st.text_input("Usuário do Sistema")
        with c2:
            edicao = st.text_input("Edição na URL (ex: dic2025)", value="dic2025")
            senha = st.text_input("Senha", type="password")
            
        if st.button("🚀 INICIAR ROBÔ DE DOWNLOAD"):
            if not usuario or not senha:
                st.warning("Preencha usuário e senha!")
            else:
                status = st.empty()
                status.info("⏳ Iniciando navegador no servidor...")
                
                try:
                    # CONFIGURAÇÃO ESPECÍFICA PARA STREAMLIT CLOUD/LINUX
                    chrome_options = Options()
                    chrome_options.add_argument("--headless")
                    chrome_options.add_argument("--no-sandbox")
                    chrome_options.add_argument("--disable-dev-shm-usage")
                    chrome_options.add_argument("--disable-gpu")
                    chrome_options.add_argument("--window-size=1920,1080")
                    
                    # Caminhos padrão do Linux (Debian/Ubuntu)
                    chrome_options.binary_location = "/usr/bin/chromium"
                    
                    # Define pasta de download
                    download_dir = os.getcwd()
                    prefs = {"download.default_directory": download_dir}
                    chrome_options.add_experimental_option("prefs", prefs)
                    
                    # Usa o Driver do Sistema
                    service = Service("/usr/bin/chromedriver")
                    
                    driver = webdriver.Chrome(service=service, options=chrome_options)
                    wait = WebDriverWait(driver, 15)

                    # 1. Login
                    status.info("🔑 Acessando login...")
                    url_login = f"https://{subdominio}.iweventos.com.br/sistema/not/acesso/login"
                    driver.get(url_login)
                    
                    # Busca inteligente do campo de usuário
                    campo_user = None
                    seletores = [(By.NAME, "login"), (By.ID, "usuario"), (By.CSS_SELECTOR, "input[type='text']")]
                    for met, sel in seletores:
                        try:
                            campo_user = wait.until(EC.presence_of_element_located((met, sel)))
                            break
                        except: continue
                        
                    if campo_user:
                        campo_user.send_keys(usuario)
                        # Senha
                        try:
                            driver.find_element(By.NAME, "senha").send_keys(senha)
                            driver.find_element(By.NAME, "senha").submit()
                        except:
                            driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(senha)
                            driver.find_element(By.CSS_SELECTOR, "input[type='password']").submit()
                    else:
                        raise Exception("Campo de usuário não encontrado na página de login.")

                    time.sleep(3)
                    
                    # 2. Página do Relatório
                    status.info(f"📍 Acessando edição {edicao}...")
                    url_rel = f"https://{subdominio}.iweventos.com.br/sistema/{edicao}/relinscricoesexcel/inscricoes"
                    driver.get(url_rel)
                    
                    if "login" in driver.current_url:
                        raise Exception("Login falhou. Verifique usuário e senha.")

                    # 3. Marcar Checkboxes (JS para garantir)
                    status.info("☑️ Selecionando opções...")
                    js_click = """
                    var classes = ['agrupador_inscricao', 'agrupador_dados_pessoais', 'agrupador_dados_contato', 
                                   'agrupador_dados_complementares', 'agrupador_dados_correspondencia', 
                                   'agrupador_transporte_ida', 'agrupador_transporte_volta', 
                                   'agrupador_hospedagem', 'agrupador_cobranca'];
                    classes.forEach(function(cls) {
                        var el = document.getElementsByClassName(cls)[0];
                        if(el) el.click();
                    });
                    """
                    driver.execute_script(js_click)
                    
                    # 4. Download
                    status.info("⬇️ Baixando arquivo Excel...")
                    driver.execute_script("document.getElementById('btGerar').click();")
                    
                    # Loop de espera
                    arquivo_baixado = None
                    for i in range(60):
                        time.sleep(1)
                        files = [f for f in os.listdir(download_dir) if f.endswith(('.xlsx', '.xls', '.csv'))]
                        if files:
                            # Pega o mais recente
                            files.sort(key=lambda x: os.path.getmtime(os.path.join(download_dir, x)), reverse=True)
                            cand = os.path.join(download_dir, files[0])
                            if not cand.endswith('.crdownload'):
                                arquivo_baixado = cand
                                break
                    
                    driver.quit()
                    
                    if arquivo_baixado:
                        status.success("✅ Download concluído!")
                        # Carrega para o Pandas
                        if arquivo_baixado.endswith('.csv'):
                            try:
                                df_final = pd.read_csv(arquivo_baixado, sep=',')
                                if len(df_final.columns) < 5: df_final = pd.read_csv(arquivo_baixado, sep=';')
                            except:
                                df_final = pd.read_csv(arquivo_baixado, sep=None, engine='python')
                        else:
                            df_final = pd.read_excel(arquivo_baixado)
                        
                        try: os.remove(arquivo_baixado)
                        except: pass
                    else:
                        st.error("Erro: Download não finalizado.")
                        
                except Exception as e:
                    st.error(f"Erro no Robô: {e}")
                    if 'driver' in locals(): driver.quit()

# ==============================================================================
# 3. MODO UPLOAD MANUAL
# ==============================================================================
else:
    uploaded_file = st.file_uploader("Faça o upload do Excel (.xlsx) ou CSV", type=['xlsx', 'csv'])
    if uploaded_file:
        if uploaded_file.name.endswith('.csv'):
            try:
                df_final = pd.read_csv(uploaded_file, sep=',')
                if len(df_final.columns) < 5: df_final = pd.read_csv(uploaded_file, sep=';')
            except:
                df_final = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            df_final = pd.read_excel(uploaded_file)

# ==============================================================================
# 4. PROCESSAMENTO E GERAÇÃO DE PDF (Sua Lógica Perfeita)
# ==============================================================================
if df_final is not None:
    st.divider()
    st.write("### ⚙️ Gerando Relatório PDF...")
    
    try:
        df = df_final
        
        # --- LÓGICA DE PROCESSAMENTO (IDÊNTICA AO COLAB) ---
        
        # 1. Seleção e Renomeação
        # Tenta índices fixos (como no seu script original)
        try:
            df_clean = df.iloc[:, [1, 2, 4, 5, 9, 13, 21, 52, 53]].copy()
            df_clean.columns = ['Nome', 'Categoria', 'Pgto', 'DataPagamento', 'Situacao', 'DataInscricao', 'Nasc', 'UF', 'Pais']
        except:
            st.error("As colunas do arquivo não correspondem ao padrão esperado (índices 1,2,4,5,9,13,21,52,53).")
            st.stop()

        df_clean = df_clean.dropna(subset=['Nome'])
        
        # 2. Normalização e Limpeza
        def norm(t): 
            if not isinstance(t, str): return ""
            return unicodedata.normalize('NFKD', str(t)).encode('ASCII', 'ignore').decode('ASCII').upper().strip()
            
        df_clean['UF_Norm'] = df_clean['UF'].apply(norm)
        df_clean['Pais'] = df_clean['Pais'].apply(norm)
        
        # 3. Datas
        df_clean['DataInscricao'] = pd.to_datetime(df_clean['DataInscricao'], dayfirst=True, errors='coerce')
        df_clean['DataPagamento'] = pd.to_datetime(df_clean['DataPagamento'], dayfirst=True, errors='coerce')
        
        def get_data_grafico(row):
            if str(row['Situacao']).lower() == 'pago' and pd.notnull(row['DataPagamento']): 
                return row['DataPagamento']
            return row['DataInscricao']
        
        df_clean['DataGrafico'] = df_clean.apply(get_data_grafico, axis=1)
        
        # 4. Idade
        def get_idade(d):
            try: 
                dt = d if isinstance(d, datetime) else datetime.strptime(str(d)[:10], "%d/%m/%Y")
                return (datetime.now() - dt).days // 365
            except: return -1
        
        df_clean['IdadeNum'] = df_clean['Nasc'].apply(get_idade)
        def faixas(i):
            if i < 0: return "N/I"
            if i < 25: return "< 25 Anos"
            if i <= 35: return "25 - 35 Anos"
            if i <= 45: return "36 - 45 Anos"
            if i <= 55: return "46 - 55 Anos"
            return "> 55 Anos"
        df_clean['FaixaEtaria'] = df_clean['IdadeNum'].apply(faixas)
        
        # 5. Regiões
        regioes = {"SP":"Sudeste","RJ":"Sudeste","MG":"Sudeste","ES":"Sudeste","PR":"Sul","SC":"Sul","RS":"Sul","BA":"Nordeste","PE":"Nordeste","CE":"Nordeste","DF":"Centro-Oeste","GO":"Centro-Oeste","AM":"Norte","PA":"Norte"}
        def get_reg(u): return regioes.get(u, "Outros") if len(u)==2 else "Outros"
        df_clean['Regiao'] = df_clean['UF_Norm'].apply(get_reg)
        
        # --- GERAÇÃO DE GRÁFICOS ---
        def gen_img(fig):
            buf = BytesIO(); fig.savefig(buf, format='png', dpi=100, transparent=True); plt.close(fig)
            return base64.b64encode(buf.getvalue()).decode('utf-8')

        # Pizza
        f1, a1 = plt.figure(figsize=(6,4)), plt.gca()
        plt.style.use('ggplot')
        v_reg = df_clean['Regiao'].value_counts()
        if len(v_reg)>5: 
            v_reg = v_reg.head(4)
            v_reg['Outros'] = len(df_clean) - v_reg.sum()
        a1.pie(v_reg, labels=v_reg.index, autopct='%1.0f%%')
        img_reg = gen_img(f1)

        # Barra
        f2, a2 = plt.figure(figsize=(6,4)), plt.gca()
        v_id = df_clean['FaixaEtaria'].value_counts().sort_index()
        v_id.plot(kind='bar', color='#3498db', ax=a2)
        plt.xticks(rotation=0)
        img_id = gen_img(f2)

        # Evolução
        df_clean_evo = df_clean.dropna(subset=['DataGrafico'])
        df_evo = df_clean_evo.set_index('DataGrafico').groupby([pd.Grouper(freq='W'), 'Situacao']).size().unstack(fill_value=0)
        
        f3, a3 = plt.figure(figsize=(10,4)), plt.gca()
        # Mapeamento de cores para garantir consistência
        cores = {'Pago': '#27ae60', 'Cortesia': '#f39c12', 'Em Aberto': '#c0392b', 'Cancelado': '#7f8c8d'}
        
        for c in df_evo.columns:
            # Tenta achar cor parcial (ex: "Pago" em "Pago (Cartão)")
            cor_uso = '#333'
            for k, v in cores.items():
                if k.lower() in str(c).lower(): cor_uso = v
            a3.plot(df_evo.index, df_evo[c], marker='.', color=cor_uso, label=c)
            
        a3.legend()
        a3.grid(True, alpha=0.3)
        
        # Formata Eixo X
        dates = df_evo.index
        lbls = []
        pm, py = None, None
        a3.set_xticks(dates)
        for d in dates:
            l = f"{d.day}"
            if pm != d.month:
                l += f"\n{d.strftime('%b')}"
                if py != d.year: l += f"\n{d.year}"
            lbls.append(l); pm=d.month; py=d.year
        a3.set_xticklabels(lbls, fontsize=8)
        img_evo = gen_img(f3)

        # --- TABELAS E PDF ---
        h_br = datetime.utcnow() - timedelta(hours=3)
        
        css = "body{font-family:sans-serif;color:#333} .card{border:1px solid #ddd;border-radius:8px;margin-bottom:15px;padding:10px;page-break-inside:avoid} .tit{font-size:20px;font-weight:bold} table{width:100%;border-collapse:collapse;font-size:11px} th{background:#eee;text-align:left;padding:5px} td{border-bottom:1px solid #eee;padding:5px} .img{width:100%;object-fit:contain;max-height:250px}"
        
        def make_tab(c):
            t = df_clean.groupby([c, 'Situacao']).size().unstack(fill_value=0)
            t['Total'] = t.sum(axis=1)
            t = t.sort_values('Total', ascending=False)
            h = "<table><thead><tr><th>Nome</th><th>Total</th><th>Pago</th><th>Cortesia</th><th>Aberto</th></tr></thead><tbody>"
            for i, r in t.iterrows():
                # Busca colunas de forma segura (case insensitive logic se necessário)
                p = 0; c_ = 0; a = 0
                for col in r.index:
                    if 'pago' in str(col).lower(): p += r[col]
                    elif 'cortesia' in str(col).lower(): c_ += r[col]
                    elif 'aberto' in str(col).lower(): a += r[col]
                
                h += f"<tr><td>{str(i)[:40]}</td><td><b>{r['Total']}</b></td><td style='color:green'>{p}</td><td style='color:orange'>{c_}</td><td style='color:red'>{a}</td></tr>"
            return h+"</tbody></table>"

        html = f"""<html><head><style>{css}</style></head><body>
        <div class='tit'>Relatório {con_event} {con_year}</div>
        <div style='font-size:10px;color:#777;margin-bottom:20px'>Gerado em: {h_br.strftime('%d/%m/%Y %H:%M')}</div>
        
        <div class='card'><h3>Evolução das Inscrições</h3><img src='data:image/png;base64,{img_evo}' class='img'></div>
        
        <div style='display:flex'>
            <div class='card' style='width:48%'><h3>Distribuição por Região</h3><img src='data:image/png;base64,{img_reg}' class='img'></div>
            <div class='card' style='width:48%;margin-left:2%'><h3>Faixa Etária</h3><img src='data:image/png;base64,{img_id}' class='img'></div>
        </div>
        
        <div class='card'><h3>Detalhamento por Categoria</h3>{make_tab('Categoria')}</div>
        <div class='card'><h3>Detalhamento por Estado (Brasil)</h3>{make_tab('UF_Norm')}</div>
        </body></html>"""

        pdf_file = BytesIO()
        HTML(string=html).write_pdf(pdf_file)
        
        st.success("✅ Relatório Processado com Sucesso!")
        
        # BOTÃO DE DOWNLOAD FINAL
        st.download_button(
            label="⬇️ BAIXAR PDF FINAL",
            data=pdf_file.getvalue(),
            file_name=f"Relatorio_{con_event.replace(' ','_')}_{con_year}.pdf",
            mime="application/pdf"
        )
        
    except Exception as e:
        st.error(f"Erro ao processar dados: {e}")

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

# Tenta importar Selenium
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    # Removemos o ChromeDriverManager para evitar o conflito de versões
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False

# Configuração da Página
st.set_page_config(page_title="Gerador de Relatórios", page_icon="📊", layout="wide")
warnings.filterwarnings('ignore')

# --- CSS ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; height: 50px; font-weight: bold; }
    .success-btn { background-color: #28a745; color: white; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Gerador de Relatório de Eventos")

# --- MENU LATERAL (OPÇÕES) ---
st.sidebar.header("Configuração")
modo_entrada = st.sidebar.radio("Como você quer obter os dados?", ("Fazer Upload do Excel", "Baixar Automaticamente (Robô)"))

# Variáveis globais para o fluxo
df_final = None
con_event = ""
con_year = ""

# ==============================================================================
# MODO 1: ROBÔ AUTOMÁTICO (CORRIGIDO)
# ==============================================================================
if modo_entrada == "Baixar Automaticamente (Robô)":
    if not HAS_SELENIUM:
        st.error("⚠️ As bibliotecas do Selenium não estão instaladas. Verifique o requirements.txt.")
    else:
        st.subheader("🤖 Acesso Automático ao Sistema")
        
        c1, c2 = st.columns(2)
        with c1:
            subdominio = st.text_input("Subdomínio (ex: ccm)", value="ccm")
            usuario = st.text_input("Usuário do Sistema")
        with c2:
            edicao = st.text_input("Edição (ex: dic2025)", value="dic2025")
            senha = st.text_input("Senha", type="password")
            
        con_event = edicao.upper()
        con_year = datetime.now().year # Padrão
        
        if st.button("🚀 INICIAR ROBÔ DE DOWNLOAD"):
            if not usuario or not senha:
                st.warning("Preencha usuário e senha!")
            else:
                status = st.empty()
                status.info("⏳ Iniciando navegador (Modo Compatibilidade Linux)...")
                
                try:
                    # --- CORREÇÃO DO ERRO DE VERSÃO ---
                    chrome_options = Options()
                    chrome_options.add_argument("--headless")
                    chrome_options.add_argument("--no-sandbox")
                    chrome_options.add_argument("--disable-dev-shm-usage")
                    chrome_options.add_argument("--disable-gpu")
                    
                    # Força o caminho do binário do Chromium no Linux
                    chrome_options.binary_location = "/usr/bin/chromium"
                    
                    # Define pasta de download
                    download_dir = os.getcwd()
                    prefs = {"download.default_directory": download_dir}
                    chrome_options.add_experimental_option("prefs", prefs)
                    
                    # Usa o Driver do Sistema (instalado pelo packages.txt)
                    # Isso evita o erro de versão 114 vs 144
                    service = Service("/usr/bin/chromedriver")
                    
                    driver = webdriver.Chrome(service=service, options=chrome_options)
                    
                    # 1. Login
                    status.info("🔑 Realizando login...")
                    url_login = f"https://{subdominio}.iweventos.com.br/sistema/not/acesso/login"
                    driver.get(url_login)
                    
                    # Tenta logar (compatível com ID ou Name)
                    try:
                        driver.find_element(By.NAME, "login").send_keys(usuario)
                    except:
                        driver.find_element(By.ID, "usuario").send_keys(usuario)
                        
                    try:
                        driver.find_element(By.NAME, "senha").send_keys(senha)
                        driver.find_element(By.NAME, "senha").submit()
                    except:
                        driver.find_element(By.ID, "senha").send_keys(senha)
                        driver.find_element(By.ID, "senha").submit()
                        
                    time.sleep(3)
                    
                    # 2. Acessar Relatório
                    status.info(f"📍 Acessando edição {edicao}...")
                    url_rel = f"https://{subdominio}.iweventos.com.br/sistema/{edicao}/relinscricoesexcel/inscricoes"
                    driver.get(url_rel)
                    
                    if "login" in driver.current_url:
                        raise Exception("Falha no login. Verifique as credenciais.")
                        
                    # 3. Marcar Checkboxes
                    status.info("☑️ Marcando opções do relatório...")
                    agrupadores = [
                        "agrupador_inscricao", "agrupador_dados_pessoais", "agrupador_dados_contato", 
                        "agrupador_dados_complementares", "agrupador_dados_correspondencia", 
                        "agrupador_transporte_ida", "agrupador_transporte_volta", 
                        "agrupador_hospedagem", "agrupador_cobranca"
                    ]
                    for classe in agrupadores:
                        try:
                            # Javascript é mais seguro para checkboxes escondidos ou estilizados
                            driver.execute_script(f"if(document.getElementsByClassName('{classe}')[0]) document.getElementsByClassName('{classe}')[0].click();")
                        except: pass
                        
                    # 4. Baixar
                    status.info("⬇️ Gerando Excel...")
                    driver.execute_script("document.getElementById('btGerar').click();")
                    
                    # Espera download (Loop inteligente)
                    arquivo_baixado = None
                    tempo_espera = 0
                    while tempo_espera < 60:
                        time.sleep(1)
                        tempo_espera += 1
                        
                        # Procura arquivos xlsx ou csv recentes
                        files = [f for f in os.listdir(download_dir) if f.endswith(('.xlsx', '.xls', '.csv'))]
                        if files:
                            # Ordena por data de modificação
                            files.sort(key=lambda x: os.path.getmtime(os.path.join(download_dir, x)), reverse=True)
                            candidato = os.path.join(download_dir, files[0])
                            
                            # Verifica se não é arquivo temporário do navegador (.crdownload)
                            if not candidato.endswith('.crdownload'):
                                arquivo_baixado = candidato
                                break
                                
                    driver.quit()
                    
                    if arquivo_baixado:
                        status.success(f"✅ Download concluído!")
                        # Lê o arquivo para memória
                        if arquivo_baixado.endswith('.csv'):
                            try:
                                df_final = pd.read_csv(arquivo_baixado, sep=',')
                                if len(df_final.columns) < 5: df_final = pd.read_csv(arquivo_baixado, sep=';')
                            except:
                                df_final = pd.read_csv(arquivo_baixado, sep=None, engine='python')
                        else:
                            df_final = pd.read_excel(arquivo_baixado)
                            
                        # Limpeza: remove o arquivo do servidor para não acumular
                        try:
                            os.remove(arquivo_baixado)
                        except: pass
                        
                    else:
                        st.error("O download não iniciou a tempo ou falhou.")
                        
                except Exception as e:
                    st.error(f"Erro no Robô: {e}")
                    if 'driver' in locals(): driver.quit()

# ==============================================================================
# MODO 2: UPLOAD MANUAL
# ==============================================================================
else:
    c1, c2 = st.columns(2)
    with c1: con_event = st.text_input("Nome do Evento", value="SOBED DAYS")
    with c2: con_year = st.text_input("Ano", value="2026")
    
    uploaded_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'])
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
# PROCESSAMENTO COMUM (GERA PDF)
# ==============================================================================
if df_final is not None:
    st.divider()
    st.write("### ⚙️ Gerando Relatório PDF...")
    
    try:
        df = df_final
        # Mapeamento
        df_clean = df.iloc[:, [1, 2, 4, 5, 9, 13, 21, 52, 53]].copy()
        df_clean.columns = ['Nome', 'Categoria', 'Pgto', 'DataPagamento', 'Situacao', 'DataInscricao', 'Nasc', 'UF', 'Pais']
        df_clean = df_clean.dropna(subset=['Nome'])
        df_clean = df_clean[df_clean['Nome'] != ""]

        # Funções Auxiliares
        def normalizar(txt):
            if not isinstance(txt, str): return ""
            nfkd = unicodedata.normalize('NFKD', txt)
            return "".join([c for c in nfkd if not unicodedata.combining(c)]).upper().strip()

        def calc_idade(data):
            try:
                d = data if isinstance(data, datetime) else datetime.strptime(str(data)[:10], "%d/%m/%Y")
                h = datetime.now()
                i = h.year - d.year - ((h.month, h.day) < (d.month, d.day))
                if i < 25: return "< 25 Anos"
                if i <= 35: return "25 - 35 Anos"
                if i <= 45: return "36 - 45 Anos"
                if i <= 55: return "46 - 55 Anos"
                return "> 55 Anos"
            except: return "N/I"

        def classificar(row):
            pg = str(row['Pgto']).lower()
            st = str(row['Situacao']).lower()
            if 'cortesia' in pg: return 'Cortesia'
            if 'pago' in st: return 'Pago'
            return 'Aberto'

        df_clean['UF_Norm'] = df_clean['UF'].apply(normalizar)
        df_clean['Pais'] = df_clean['Pais'].apply(normalizar)
        df_clean['Categoria'] = df_clean['Categoria'].apply(lambda x: str(x).strip().replace("Equipe Multidisciplinar", "Eq. Multi"))
        df_clean['FaixaEtaria'] = df_clean['Nasc'].apply(calc_idade)
        df_clean['Status'] = df_clean.apply(classificar, axis=1)

        # Datas
        df_clean['DataInscricao'] = pd.to_datetime(df_clean['DataInscricao'], dayfirst=True, errors='coerce')
        df_clean['DataPagamento'] = pd.to_datetime(df_clean['DataPagamento'], dayfirst=True, errors='coerce')

        def data_grafico(row):
            if row['Status'] == 'Pago' and pd.notnull(row['DataPagamento']):
                return row['DataPagamento']
            return row['DataInscricao']

        df_clean['DataGrafico'] = df_clean.apply(data_grafico, axis=1)
        df_grafico = df_clean.dropna(subset=['DataGrafico']).copy()

        # Regiões
        regioes_map = {
            "SP":"Sudeste", "SAO PAULO":"Sudeste", "RJ":"Sudeste", "RIO DE JANEIRO":"Sudeste", 
            "MG":"Sudeste", "MINAS GERAIS":"Sudeste", "ES":"Sudeste", "ESPIRITO SANTO":"Sudeste",
            "PR":"Sul", "PARANA":"Sul", "SC":"Sul", "SANTA CATARINA":"Sul", "RS":"Sul", "RIO GRANDE DO SUL":"Sul",
            "BA":"Nordeste", "BAHIA":"Nordeste", "PE":"Nordeste", "PERNAMBUCO":"Nordeste", 
            "CE":"Nordeste", "CEARA":"Nordeste", "MA":"Nordeste", "MARANHAO":"Nordeste", 
            "RN":"Nordeste", "RIO GRANDE DO NORTE":"Nordeste", "PB":"Nordeste", "PARAIBA":"Nordeste", 
            "AL":"Nordeste", "ALAGOAS":"Nordeste", "SE":"Nordeste", "SERGIPE":"Nordeste", 
            "PI":"Nordeste", "PIAUI":"Nordeste",
            "DF":"Centro-Oeste", "DISTRITO FEDERAL":"Centro-Oeste", "GO":"Centro-Oeste", "GOIAS":"Centro-Oeste", 
            "MT":"Centro-Oeste", "MATO GROSSO":"Centro-Oeste", "MS":"Centro-Oeste", "MATO GROSSO DO SUL":"Centro-Oeste",
            "AM":"Norte", "AMAZONAS":"Norte", "PA":"Norte", "PARA":"Norte", "AC":"Norte", "ACRE":"Norte", 
            "TO":"Norte", "TOCANTINS":"Norte", "RO":"Norte", "RONDONIA":"Norte", "RR":"Norte", "RORAIMA":"Norte", 
            "AP":"Norte", "AMAPA":"Norte"
        }
        df_clean['Regiao'] = df_clean['UF_Norm'].apply(lambda x: regioes_map.get(x, "Outros") if x and len(x)>1 else "Outros")

        def agrupar_regioes(series):
            if len(series)==0: return series.value_counts()
            c = series.value_counts()
            p = c/len(series)
            maior = c[p>=0.10]
            menor = c[p<0.10].sum()
            res = maior.copy()
            if menor > 0: res['Outros'] = res.get('Outros', 0) + menor
            return res

        # --- GRÁFICOS ---
        def fig_to_base64(fig):
            buf = BytesIO()
            fig.savefig(buf, format='png', dpi=120, transparent=True)
            plt.close(fig)
            return base64.b64encode(buf.getvalue()).decode('utf-8')

        # Pizza
        fig1, ax1 = plt.figure(figsize=(7, 5)), plt.gca()
        plt.style.use('ggplot')
        colors = ['#3498db', '#e74c3c', '#f1c40f', '#2ecc71', '#9b59b6', '#95a5a6']
        d_reg = agrupar_regioes(df_clean['Regiao'])
        ax1.pie(d_reg, labels=d_reg.index, autopct='%1.1f%%', startangle=90, colors=colors)
        img_reg = fig_to_base64(fig1)

        # Barras
        fig2, ax2 = plt.figure(figsize=(7, 5)), plt.gca()
        d_id = df_clean['FaixaEtaria'].value_counts().sort_index()
        d_id.plot(kind='bar', color='#3498db', ax=ax2)
        plt.xticks(rotation=0)
        ax2.bar_label(ax2.containers[0], padding=3)
        plt.ylim(top=max(d_id.values)*1.2 if len(d_id)>0 else 1)
        img_id = fig_to_base64(fig2)

        # Evolução
        df_evo = df_grafico.set_index('DataGrafico').groupby([pd.Grouper(freq='W'), 'Status']).size().unstack(fill_value=0)
        for c in ['Pago', 'Cortesia', 'Aberto']: 
            if c not in df_evo.columns: df_evo[c] = 0

        fig3, ax3 = plt.figure(figsize=(12, 5)), plt.gca()
        if 'Pago' in df_evo: ax3.plot(df_evo.index, df_evo['Pago'], marker='o', linewidth=2, color='#27ae60', label='Pagos')
        if 'Cortesia' in df_evo: ax3.plot(df_evo.index, df_evo['Cortesia'], marker='o', linewidth=2, color='#f39c12', label='Cortesia')
        if 'Aberto' in df_evo: ax3.plot(df_evo.index, df_evo['Aberto'], marker='o', linewidth=2, color='#c0392b', label='Aberto')

        ax3.legend(loc='upper left', frameon=True)
        ax3.grid(True, linestyle='--', alpha=0.5)
        
        dates = df_evo.index
        labels = []
        prev_month = None
        prev_year = None
        ax3.set_xticks(dates)
        for d in dates:
            label = f"{d.day}"
            if prev_month != d.month:
                label += f"\n{d.strftime('%b')}"
                ax3.axvline(d, color='#999', linestyle='--', linewidth=0.8, alpha=0.5)
                if prev_year != d.year:
                    label += f"\n{d.year}"
                    ax3.axvline(d, color='#444', linestyle='-', linewidth=1.2, alpha=0.7)
            prev_month = d.month
            prev_year = d.year
            labels.append(label)
        ax3.set_xticklabels(labels, fontsize=9)
        plt.tight_layout()
        img_evo = fig_to_base64(fig3)

        # --- DADOS TABELAS ---
        def criar_tab(df, col):
            r = df.groupby([col, 'Status']).size().unstack(fill_value=0)
            for c in ['Pago','Cortesia','Aberto']: 
                if c not in r.columns: r[c] = 0
            r['Total'] = r['Pago']+r['Cortesia']+r['Aberto']
            return r.sort_values('Total', ascending=False)

        tab_cat = criar_tab(df_clean, 'Categoria')
        tab_pais = criar_tab(df_clean, 'Pais')
        tab_id = criar_tab(df_clean, 'FaixaEtaria')
        tab_uf = criar_tab(df_clean[df_clean['Pais']=='BRASIL'], 'UF')

        tot = len(df_clean)
        pag = len(df_clean[df_clean['Status']=='Pago'])
        cor = len(df_clean[df_clean['Status']=='Cortesia'])
        abe = len(df_clean[df_clean['Status']=='Aberto'])
        h_br = datetime.utcnow() - timedelta(hours=3)
        data_str = h_br.strftime('%d/%m/%Y às %H:%M')

        # --- GERAÇÃO PDF ---
        def render_tab(df):
            h = '<table class="dt"><thead><tr><th>Nome</th><th class="n">Total</th><th class="n">Pagos</th><th class="n">Cort.</th><th class="n">Aberto</th></tr></thead><tbody>'
            for i, r in df.iterrows():
                n = str(i)[:40]
                if not n or n=='nan': n="N/I"
                h += f'<tr><td>{n}</td><td class="n b">{r["Total"]}</td><td class="n g">{r["Pago"]}</td><td class="n o">{r["Cortesia"]}</td><td class="n r">{r["Aberto"]}</td></tr>'
            return h + '</tbody></table>'

        def render_uf(df):
            h = '<table class="dt"><thead><tr><th>Estado (UF)</th><th class="n">Total</th><th class="n">Pagos</th><th class="n">Cort.</th><th class="n">Aberto</th></tr></thead><tbody>'
            for i, r in df.iterrows():
                u = str(i).strip()
                if not u or u=='nan': u="N/I"
                h += f'<tr><td>{u}</td><td class="n b">{r["Total"]}</td><td class="n g">{r["Pago"]}</td><td class="n o">{r["Cortesia"]}</td><td class="n r">{r["Aberto"]}</td></tr>'
            return h + '</tbody></table>'

        css = """
        @page { size: A4; margin: 1cm; }
        body { font-family: Helvetica, sans-serif; margin: 0; color: #333; }
        .head { padding: 15px 0; border-bottom: 2px solid #eee; margin-bottom: 20px; }
        .tit { font-size: 22px; font-weight: 700; }
        .meta { font-size: 11px; color: #777; margin-top: 5px; }
        .kpi-row { display: flex; justify-content: space-between; gap: 10px; margin-bottom: 25px; }
        .kpi { width: 23%; padding: 15px 5px; border-radius: 8px; color: white; text-align: center; }
        .kl { font-size: 10px; font-weight: bold; text-transform: uppercase; margin-bottom: 5px; opacity: 0.9; }
        .kv { font-size: 32px; font-weight: 800; }
        .card { border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 20px; page-break-inside: avoid; }
        .ch { padding: 12px 15px; border-bottom: 1px solid #eee; background: #f8f9fa; }
        .ch h3 { margin: 0; font-size: 15px; color: #444; text-transform: uppercase; }
        .cb { padding: 15px; text-align: center; }
        .row { display: flex; gap: 15px; margin-bottom: 10px; }
        .col { width: 48%; }
        .img { width: 100%; max-height: 300px; object-fit: contain; }
        .dt { width: 100%; border-collapse: collapse; font-size: 12px; }
        .dt th { background: #f8f9fa; padding: 10px; text-align: left; border-bottom: 2px solid #ddd; }
        .dt td { padding: 8px 10px; border-bottom: 1px solid #eee; }
        .dt tr:nth-child(even) { background: #fafafa; }
        .n { text-align: right; width: 50px; }
        .b { font-weight: bold; background: #f9f9f9; }
        .g { color: #27ae60; font-weight: bold; }
        .o { color: #d35400; font-weight: bold; }
        .r { color: #c0392b; font-weight: bold; }
        """

        html = f"""
        <!DOCTYPE html><html><head><style>{css}</style></head><body>
        <div class="head"><div class="tit">Visão Geral do Evento - {con_event} {con_year}</div><div class="meta">Gerado em: {data_str}</div></div>
        <div class="kpi-row">
            <div class="kpi" style="background:#3498db"><div class="kl">Total Inscritos</div><div class="kv">{tot}</div></div>
            <div class="kpi" style="background:#27ae60"><div class="kl">Pagos Confirmados</div><div class="kv">{pag}</div></div>
            <div class="kpi" style="background:#f39c12"><div class="kl">Cortesias</div><div class="kv">{cor}</div></div>
            <div class="kpi" style="background:#c0392b"><div class="kl">Em Aberto</div><div class="kv">{abe}</div></div>
        </div>
        <div class="card"><div class="ch"><h3>Evolução Semanal de Inscritos</h3></div><div class="cb"><img src="data:image/png;base64,{img_evo}" style="width:100%; max-height:300px;"></div></div>
        <div class="row">
            <div class="col card"><div class="ch"><h3>Distribuição por Região</h3></div><div class="cb"><img src="data:image/png;base64,{img_reg}" class="img"></div></div>
            <div class="col card"><div class="ch"><h3>Perfil Etário</h3></div><div class="cb"><img src="data:image/png;base64,{img_id}" class="img"></div></div>
        </div>
        <div class="card"><div class="ch"><h3>Detalhado por Categoria</h3></div><div class="cb" style="text-align:left; padding:0;">{render_tab(tab_cat)}</div></div>
        <div class="card"><div class="ch"><h3>Detalhado por Faixa Etária</h3></div><div class="cb" style="text-align:left; padding:0;">{render_tab(tab_id)}</div></div>
        <div class="row">
            <div class="col card"><div class="ch"><h3>Detalhado por País</h3></div><div class="cb" style="text-align:left; padding:0;">{render_tab(tab_pais)}</div></div>
            <div class="col card"><div class="ch"><h3>Detalhado por Estado (UF)</h3></div><div class="cb" style="text-align:left; padding:0;">{render_uf(tab_uf)}</div></div>
        </div>
        </body></html>
        """
        
        pdf_file = BytesIO()
        HTML(string=html).write_pdf(pdf_file)
        
        st.success("✅ Relatório Gerado com Sucesso!")
        st.download_button(
            label="⬇️ BAIXAR PDF",
            data=pdf_file.getvalue(),
            file_name=f"Relatorio_{con_event.replace(' ','_')}_{con_year}.pdf",
            mime="application/pdf"
        )
        
    except Exception as e:
        st.error(f"Erro ao processar arquivo: {e}")

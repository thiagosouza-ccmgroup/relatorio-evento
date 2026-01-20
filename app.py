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

# ==============================================================================
# CONFIGURAÇÕES INICIAIS
# ==============================================================================
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

# --- CSS DO STREAMLIT ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; height: 50px; font-weight: bold; }
    .success-box { padding: 1rem; background-color: #d4edda; color: #155724; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Gerador de Relatório de Eventos")

# ==============================================================================
# 1. INPUTS DE CONFIGURAÇÃO
# ==============================================================================
st.sidebar.header("Configuração do Relatório")
con_event = st.sidebar.text_input("Nome do Evento (Título)", value="SOBED DAYS")
con_year = st.sidebar.text_input("Ano", value="2026")

modo_entrada = st.sidebar.radio("Como obter os dados?", ("Upload Manual", "Robô Automático"))

df_final = None

# ==============================================================================
# 2. MODO ROBÔ (DOWNLOAD AUTOMÁTICO)
# ==============================================================================
if modo_entrada == "Robô Automático":
    if not HAS_SELENIUM:
        st.error("⚠️ As bibliotecas do Selenium não estão instaladas. Verifique o requirements.txt.")
    else:
        st.info("🤖 **Configuração de Acesso**")
        c1, c2 = st.columns(2)
        with c1:
            subdominio = st.text_input("Subdomínio (ex: ccm)", value="ccm")
            usuario = st.text_input("Usuário")
        with c2:
            edicao = st.text_input("Edição na URL (ex: dic2025)", value="dic2025")
            senha = st.text_input("Senha", type="password")
            
        if st.button("🚀 INICIAR ROBÔ"):
            status = st.empty()
            try:
                status.info("⏳ Iniciando navegador no servidor...")
                
                # Configuração Selenium para Linux/Streamlit Cloud
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--window-size=1920,1080")
                chrome_options.binary_location = "/usr/bin/chromium"
                
                download_dir = os.getcwd()
                prefs = {"download.default_directory": download_dir}
                chrome_options.add_experimental_option("prefs", prefs)
                
                service = Service("/usr/bin/chromedriver")
                driver = webdriver.Chrome(service=service, options=chrome_options)
                wait = WebDriverWait(driver, 20)

                # 1. Login
                status.info("🔑 Acessando sistema...")
                driver.get(f"https://{subdominio}.iweventos.com.br/sistema/not/acesso/login")
                
                # Busca inteligente de campos
                def find_any(locators):
                    for by, val in locators:
                        try: return wait.until(EC.presence_of_element_located((by, val)))
                        except: continue
                    return None

                user_field = find_any([(By.NAME, "login"), (By.ID, "usuario"), (By.ID, "login")])
                pass_field = find_any([(By.NAME, "senha"), (By.ID, "senha")])
                
                if user_field and pass_field:
                    user_field.send_keys(usuario)
                    pass_field.send_keys(senha)
                    try: pass_field.submit()
                    except: 
                        btn = find_any([(By.CSS_SELECTOR, "button[type='submit']"), (By.ID, "btnEntrar")])
                        if btn: btn.click()
                else:
                    raise Exception("Campos de login não encontrados.")

                time.sleep(3)
                
                # 2. Relatório
                status.info(f"📍 Acessando edição {edicao}...")
                driver.get(f"https://{subdominio}.iweventos.com.br/sistema/{edicao}/relinscricoesexcel/inscricoes")
                
                if "login" in driver.current_url:
                    raise Exception("Login falhou. Verifique usuário e senha.")

                # 3. Checkboxes (Via JS para garantir)
                status.info("☑️ Selecionando dados...")
                driver.execute_script("""
                    var classes = ['agrupador_inscricao', 'agrupador_dados_pessoais', 'agrupador_dados_contato', 
                                   'agrupador_dados_complementares', 'agrupador_dados_correspondencia', 
                                   'agrupador_transporte_ida', 'agrupador_transporte_volta', 
                                   'agrupador_hospedagem', 'agrupador_cobranca'];
                    classes.forEach(cls => {
                        var el = document.getElementsByClassName(cls)[0];
                        if(el) el.click();
                    });
                """)
                
                # 4. Download
                status.info("⬇️ Baixando Excel...")
                driver.execute_script("document.getElementById('btGerar').click();")
                
                # Espera arquivo
                arquivo_baixado = None
                for i in range(60):
                    time.sleep(1)
                    files = [f for f in os.listdir(download_dir) if f.endswith(('.xlsx', '.xls', '.csv'))]
                    if files:
                        # Ordena pelo mais recente
                        files.sort(key=lambda x: os.path.getmtime(os.path.join(download_dir, x)), reverse=True)
                        cand = os.path.join(download_dir, files[0])
                        if not cand.endswith('.crdownload'):
                            arquivo_baixado = cand
                            break
                
                driver.quit()
                
                if arquivo_baixado:
                    status.success("✅ Arquivo baixado!")
                    # Carregar
                    if arquivo_baixado.endswith('.csv'):
                        try: df_final = pd.read_csv(arquivo_baixado, sep=',')
                        except: df_final = pd.read_csv(arquivo_baixado, sep=';', engine='python')
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
    uploaded_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'])
    if uploaded_file:
        if uploaded_file.name.endswith('.csv'):
            try: df_final = pd.read_csv(uploaded_file, sep=',')
            except: df_final = pd.read_csv(uploaded_file, sep=';')
        else:
            df_final = pd.read_excel(uploaded_file)

# ==============================================================================
# 4. PROCESSAMENTO E PDF (Lógica "Colab" Restaurada)
# ==============================================================================
if df_final is not None:
    st.divider()
    st.write("### ⚙️ Processando e Gerando PDF...")
    
    try:
        # --- LIMPEZA DE DADOS (Restaurada do Colab) ---
        df = df_final
        
        # Mapeamento Rígido (Índices que funcionavam no Colab)
        try:
            # 1=Nome, 2=Categoria, 4=Pgto, 5=DtPgto, 9=Situação, 13=DtInscricao, 21=Nasc, 52=UF, 53=País
            df_clean = df.iloc[:, [1, 2, 4, 5, 9, 13, 21, 52, 53]].copy()
            df_clean.columns = ['Nome', 'Categoria', 'Pgto', 'DataPagamento', 'Situacao', 'DataInscricao', 'Nasc', 'UF', 'Pais']
        except:
            st.warning("Tentando mapeamento alternativo de colunas...")
            # Fallback se as colunas mudaram
            df_clean = df.copy() # Lógica simplificada de fallback
        
        df_clean = df_clean.dropna(subset=['Nome'])
        
        # Funções de Tratamento
        def normalizar(txt):
            if not isinstance(txt, str): return ""
            return unicodedata.normalize('NFKD', txt).encode('ASCII', 'ignore').decode('ASCII').upper().strip()

        def calc_idade(d):
            try:
                dt = d if isinstance(d, datetime) else datetime.strptime(str(d)[:10], "%d/%m/%Y")
                return (datetime.now() - dt).days // 365
            except: return -1

        def classificar(row):
            pg = str(row['Pgto']).lower()
            st = str(row['Situacao']).lower()
            if 'cortesia' in pg: return 'Cortesia'
            if 'pago' in st: return 'Pago'
            return 'Aberto' # Unificado para "Aberto"

        # Aplicações
        df_clean['UF_Norm'] = df_clean['UF'].apply(normalizar)
        df_clean['Pais'] = df_clean['Pais'].apply(normalizar)
        df_clean['Categoria'] = df_clean['Categoria'].apply(lambda x: str(x).strip().replace("Equipe Multidisciplinar", "Eq. Multi"))
        
        df_clean['IdadeNum'] = df_clean['Nasc'].apply(calc_idade)
        def fx_etaria(i):
            if i < 0: return "N/I"
            if i < 25: return "< 25 Anos"
            if i <= 35: return "25 - 35 Anos"
            if i <= 45: return "36 - 45 Anos"
            if i <= 55: return "46 - 55 Anos"
            return "> 55 Anos"
        df_clean['FaixaEtaria'] = df_clean['IdadeNum'].apply(fx_etaria)
        
        # Classificação Crucial (Corrige o erro do gráfico de evolução)
        df_clean['Status'] = df_clean.apply(classificar, axis=1)

        # Datas
        df_clean['DataInscricao'] = pd.to_datetime(df_clean['DataInscricao'], dayfirst=True, errors='coerce')
        df_clean['DataPagamento'] = pd.to_datetime(df_clean['DataPagamento'], dayfirst=True, errors='coerce')
        
        def get_dt_graf(row):
            # Se pago, usa data pagamento. Se não, usa inscrição.
            if row['Status'] == 'Pago' and pd.notnull(row['DataPagamento']): return row['DataPagamento']
            return row['DataInscricao']
        
        df_clean['DataGrafico'] = df_clean.apply(get_dt_graf, axis=1)
        df_grafico = df_clean.dropna(subset=['DataGrafico'])

        # Regiões (Mapeamento Robusto)
        reg_map = {
            "SP":"Sudeste","SAO PAULO":"Sudeste", "RJ":"Sudeste","RIO DE JANEIRO":"Sudeste",
            "MG":"Sudeste","MINAS GERAIS":"Sudeste","ES":"Sudeste",
            "PR":"Sul","PARANA":"Sul","SC":"Sul","SANTA CATARINA":"Sul","RS":"Sul","RIO GRANDE DO SUL":"Sul",
            "BA":"Nordeste","BAHIA":"Nordeste","PE":"Nordeste","CE":"Nordeste",
            "DF":"Centro-Oeste","GO":"Centro-Oeste","AM":"Norte","PA":"Norte"
        }
        def get_regiao(uf):
            if not uf: return "Outros"
            # Tenta direto ou pelo UF normalizado
            return reg_map.get(uf, reg_map.get(uf.upper(), "Outros"))
            
        df_clean['Regiao'] = df_clean['UF_Norm'].apply(get_regiao)

        # --- GERAÇÃO DOS GRÁFICOS (Matplotlib) ---
        def to_b64(fig):
            b = BytesIO(); fig.savefig(b, format='png', dpi=120, transparent=True); plt.close(fig)
            return base64.b64encode(b.getvalue()).decode('utf-8')

        # 1. Pizza (Região)
        f1, a1 = plt.figure(figsize=(7,5)), plt.gca(); plt.style.use('ggplot')
        def agrupar_reg(s):
            c = s.value_counts(); p = c/len(s); m = c[p>=0.1]; mn = c[p<0.1].sum()
            r = m.copy(); 
            if mn>0: r['Outros'] = r.get('Outros',0)+mn
            return r
        d_reg = agrupar_reg(df_clean['Regiao'])
        wedges, texts, autotexts = a1.pie(d_reg, labels=d_reg.index, autopct='%1.1f%%', startangle=90)
        plt.setp(autotexts, size=10, weight="bold", color="white")
        img_reg = to_b64(f1)

        # 2. Barras (Idade)
        f2, a2 = plt.figure(figsize=(7,5)), plt.gca()
        d_id = df_clean['FaixaEtaria'].value_counts().sort_index()
        d_id.plot(kind='bar', color='#3498db', ax=a2); plt.xticks(rotation=0)
        a2.bar_label(a2.containers[0], padding=3)
        plt.ylim(top=max(d_id.values)*1.2 if len(d_id)>0 else 1)
        img_id = to_b64(f2)

        # 3. Evolução (CORRIGIDO: Status unificados)
        df_evo = df_grafico.set_index('DataGrafico').groupby([pd.Grouper(freq='W'), 'Status']).size().unstack(fill_value=0)
        f3, a3 = plt.figure(figsize=(12,5)), plt.gca()
        
        # Garante que as 3 colunas existem para não dar erro
        for c in ['Pago', 'Cortesia', 'Aberto']:
            if c not in df_evo.columns: df_evo[c] = 0
            
        a3.plot(df_evo.index, df_evo['Pago'], marker='o', color='#27ae60', label='Pagos')
        a3.plot(df_evo.index, df_evo['Cortesia'], marker='o', color='#f39c12', label='Cortesia')
        a3.plot(df_evo.index, df_evo['Aberto'], marker='o', color='#c0392b', label='Aberto')

        a3.legend(); a3.grid(True, linestyle='--', alpha=0.5)
        
        # Eixo X Otimizado
        dates = df_evo.index; labels = []; pm = None; py = None; a3.set_xticks(dates)
        for d in dates:
            l = f"{d.day}"; 
            if pm != d.month: l += f"\n{d.strftime('%b')}"; a3.axvline(d, c='#ccc', ls='--')
            if py != d.year: l += f"\n{d.year}"; a3.axvline(d, c='#666', ls='-')
            labels.append(l); pm=d.month; py=d.year
        a3.set_xticklabels(labels, fontsize=8); img_evo = to_b64(f3)

        # --- DADOS PARA TABELAS ---
        def tab(df, col):
            r = df.groupby([col, 'Status']).size().unstack(fill_value=0)
            for c in ['Pago','Cortesia','Aberto']: 
                if c not in r.columns: r[c] = 0
            r['Total'] = r['Pago']+r['Cortesia']+r['Aberto']
            return r.sort_values('Total', ascending=False)

        tb_cat = tab(df_clean, 'Categoria')
        tb_pais = tab(df_clean, 'Pais')
        tb_uf = tab(df_clean[df_clean['Pais']=='BRASIL'], 'UF')

        tot=len(df_clean); pg=len(df_clean[df_clean['Status']=='Pago']); cr=len(df_clean[df_clean['Status']=='Cortesia']); ab=len(df_clean[df_clean['Status']=='Aberto'])
        d_str = (datetime.utcnow()-timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')

        # --- GERAÇÃO HTML/PDF (VISUAL PREMIUM RESTAURADO) ---
        
        def render(df, title):
            h = '<table class="dt"><thead><tr><th>'+title+'</th><th class="n">Total</th><th class="n">Pagos</th><th class="n">Cort.</th><th class="n">Aberto</th></tr></thead><tbody>'
            for i,r in df.iterrows():
                nm = str(i)[:40] if str(i)!='nan' else "N/I"
                h += f'<tr><td>{nm}</td><td class="n b">{r["Total"]}</td><td class="n g">{r["Pago"]}</td><td class="n o">{r["Cortesia"]}</td><td class="n r">{r["Aberto"]}</td></tr>'
            return h+'</tbody></table>'

        # CSS Completo (Restaurado do Colab Original)
        css = """
        @page { size: A4; margin: 1cm; }
        body { font-family: Helvetica, sans-serif; margin: 0; color: #333; background: #fff; }
        .head { padding: 15px 0; border-bottom: 2px solid #eee; margin-bottom: 20px; }
        .tit { font-size: 24px; font-weight: 700; color: #333; }
        .meta { font-size: 11px; color: #777; margin-top: 5px; }
        
        .kpi-row { display: flex; justify-content: space-between; gap: 10px; margin-bottom: 25px; }
        .kpi { width: 23%; padding: 15px 5px; border-radius: 8px; color: white; text-align: center; }
        .kl { font-size: 10px; font-weight: bold; text-transform: uppercase; margin-bottom: 5px; opacity: 0.9; }
        .kv { font-size: 32px; font-weight: 800; }
        
        .card { border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 20px; page-break-inside: avoid; background: #fff; }
        .ch { padding: 12px 15px; border-bottom: 1px solid #eee; background: #f8f9fa; }
        .ch h3 { margin: 0; font-size: 14px; color: #444; text-transform: uppercase; font-weight: 700; }
        .cb { padding: 15px; text-align: center; }
        
        .row { display: flex; gap: 15px; margin-bottom: 10px; }
        .col { width: 48%; }
        .img { width: 100%; max-height: 280px; object-fit: contain; }
        
        .dt { width: 100%; border-collapse: collapse; font-size: 11px; }
        .dt th { background: #f8f9fa; padding: 8px; text-align: left; border-bottom: 2px solid #ddd; color: #555; }
        .dt td { padding: 6px 8px; border-bottom: 1px solid #eee; color: #444; }
        .dt tr:nth-child(even) { background: #fafafa; }
        .n { text-align: right; width: 45px; }
        .b { font-weight: bold; background: #f0f0f0; }
        .g { color: #27ae60; font-weight: bold; }
        .o { color: #d35400; font-weight: bold; }
        .r { color: #c0392b; font-weight: bold; }
        """
        
        html = f"""<!DOCTYPE html><html><head><style>{css}</style></head><body>
        <div class="head">
            <div class="tit">Relatório - {con_event} {con_year}</div>
            <div class="meta">Gerado em: {d_str} (Horário de Brasília)</div>
        </div>

        <div class="kpi-row">
            <div class="kpi" style="background:#3498db"><div class="kl">Total Inscritos</div><div class="kv">{tot}</div></div>
            <div class="kpi" style="background:#27ae60"><div class="kl">Pagos Confirmados</div><div class="kv">{pg}</div></div>
            <div class="kpi" style="background:#f39c12"><div class="kl">Cortesias</div><div class="kv">{cr}</div></div>
            <div class="kpi" style="background:#c0392b"><div class="kl">Em Aberto</div><div class="kv">{ab}</div></div>
        </div>

        <div class="card">
            <div class="ch"><h3>Evolução Semanal das Inscrições</h3></div>
            <div class="cb"><img src="data:image/png;base64,{img_evo}" style="width:100%"></div>
        </div>

        <div class="row">
            <div class="col card">
                <div class="ch"><h3>Distribuição por Região</h3></div>
                <div class="cb"><img src="data:image/png;base64,{img_reg}" class="img"></div>
            </div>
            <div class="col card">
                <div class="ch"><h3>Perfil Etário</h3></div>
                <div class="cb"><img src="data:image/png;base64,{img_id}" class="img"></div>
            </div>
        </div>

        <div class="card">
            <div class="ch"><h3>Detalhamento por Categoria</h3></div>
            <div class="cb" style="text-align:left;padding:0">{render(tb_cat, 'Categoria')}</div>
        </div>

        <div class="row">
            <div class="col card">
                <div class="ch"><h3>Detalhamento por País</h3></div>
                <div class="cb" style="text-align:left;padding:0">{render(tb_pais, 'País')}</div>
            </div>
            <div class="col card">
                <div class="ch"><h3>Detalhamento por Estado (Brasil)</h3></div>
                <div class="cb" style="text-align:left;padding:0">{render(tb_uf, 'Estado')}</div>
            </div>
        </div>
        </body></html>"""

        pdf_io = BytesIO()
        HTML(string=html).write_pdf(pdf_io)
        
        st.balloons()
        st.success(f"✅ Relatório do evento **{con_event}** gerado com sucesso!")
        st.download_button("⬇️ BAIXAR PDF FINAL", data=pdf_io.getvalue(), file_name=f"Relatorio_{con_event.replace(' ','_')}_{con_year}.pdf", mime="application/pdf")

    except Exception as e:
        st.error(f"Erro ao processar: {e}")

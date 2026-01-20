import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
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

# Tenta importar Selenium
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

# --- CSS ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; height: 50px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Gerador de Relatório de Eventos")

# --- MENU LATERAL ---
st.sidebar.header("Configuração")
modo_entrada = st.sidebar.radio("Fonte dos Dados:", ("Upload Manual", "Robô de Download"))

df_final = None
con_event = ""
con_year = ""

# ==============================================================================
# MODO ROBÔ
# ==============================================================================
if modo_entrada == "Robô de Download":
    if not HAS_SELENIUM:
        st.error("⚠️ Selenium não instalado.")
    else:
        st.subheader("🤖 Robô de Acesso")
        
        c1, c2 = st.columns(2)
        with c1:
            subdominio = st.text_input("Subdomínio", value="ccm")
            usuario = st.text_input("Usuário")
        with c2:
            edicao = st.text_input("Edição", value="dic2025")
            senha = st.text_input("Senha", type="password")
            
        con_event = edicao.upper()
        con_year = datetime.now().year

        if st.button("🚀 INICIAR ROBÔ"):
            status = st.empty()
            
            try:
                status.info("⏳ Configurando navegador...")
                
                # Configuração Selenium
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
                wait = WebDriverWait(driver, 15) # Espera até 15s

                # 1. LOGIN
                url_login = f"https://{subdominio}.iweventos.com.br/sistema/not/acesso/login"
                status.info(f"🔑 Acessando login: {url_login}")
                driver.get(url_login)
                
                # Tenta encontrar campo de usuário de várias formas
                campo_user = None
                seletores_user = [
                    (By.NAME, "login"), 
                    (By.ID, "login"), 
                    (By.ID, "usuario"), 
                    (By.CSS_SELECTOR, "input[type='text']"),
                    (By.CSS_SELECTOR, "input[type='email']")
                ]
                
                for metodo, seletor in seletores_user:
                    try:
                        campo_user = wait.until(EC.presence_of_element_located((metodo, seletor)))
                        break # Achou!
                    except:
                        continue
                
                if not campo_user:
                    # Tira foto se falhar
                    driver.save_screenshot("erro_login.png")
                    st.image("erro_login.png", caption="Tela que o robô viu (Erro ao achar campo usuário)")
                    raise Exception("Não encontrei o campo de Login na página. Veja o print acima.")

                # Preenche Login
                campo_user.send_keys(usuario)
                
                # Procura e preenche Senha
                campo_pass = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                campo_pass.send_keys(senha)
                
                # Clica em entrar
                try:
                    btn_entrar = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                    btn_entrar.click()
                except:
                    campo_pass.submit()
                
                status.info("🔄 Aguardando redirecionamento...")
                time.sleep(5)
                
                # 2. RELATÓRIO
                url_rel = f"https://{subdominio}.iweventos.com.br/sistema/{edicao}/relinscricoesexcel/inscricoes"
                status.info(f"📍 Indo para relatório: {url_rel}")
                driver.get(url_rel)
                
                if "login" in driver.current_url:
                    driver.save_screenshot("erro_acesso.png")
                    st.image("erro_acesso.png")
                    raise Exception("Login falhou. O sistema redirecionou de volta para o login.")

                # 3. MARCAR OPÇÕES
                status.info("☑️ Selecionando dados...")
                # Script JS para garantir clique mesmo se elemento estiver oculto
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
                
                # 4. DOWNLOAD
                status.info("⬇️ Baixando Excel...")
                driver.execute_script("document.getElementById('btGerar').click();")
                
                # Loop de espera do arquivo
                arquivo_baixado = None
                for i in range(60):
                    time.sleep(1)
                    files = [f for f in os.listdir(download_dir) if f.endswith(('.xlsx', '.xls', '.csv'))]
                    if files:
                        files.sort(key=lambda x: os.path.getmtime(os.path.join(download_dir, x)), reverse=True)
                        candidato = os.path.join(download_dir, files[0])
                        if not candidato.endswith('.crdownload'):
                            arquivo_baixado = candidato
                            break
                
                driver.quit()
                
                if arquivo_baixado:
                    status.success("✅ Arquivo baixado com sucesso!")
                    if arquivo_baixado.endswith('.csv'):
                        try:
                            df_final = pd.read_csv(arquivo_baixado, sep=',')
                            if len(df_final.columns) < 5: df_final = pd.read_csv(arquivo_baixado, sep=';')
                        except:
                            df_final = pd.read_csv(arquivo_baixado, sep=None, engine='python')
                    else:
                        df_final = pd.read_excel(arquivo_baixado)
                    os.remove(arquivo_baixado)
                else:
                    st.error("Tempo limite de download excedido.")

            except Exception as e:
                st.error(f"Erro: {e}")
                if 'driver' in locals(): driver.quit()

# ==============================================================================
# MODO UPLOAD MANUAL
# ==============================================================================
else:
    c1, c2 = st.columns(2)
    with c1: con_event = st.text_input("Nome do Evento", value="SOBED DAYS")
    with c2: con_year = st.text_input("Ano", value="2026")
    uploaded_file = st.file_uploader("Arquivo", type=['xlsx', 'csv'])
    if uploaded_file:
        df_final = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file)

# ==============================================================================
# PROCESSAMENTO E PDF
# ==============================================================================
if df_final is not None:
    st.divider()
    st.write("### ⚙️ Gerando PDF...")
    try:
        df = df_final
        # Seleção de colunas e limpeza
        # Ajuste conforme índices reais do seu arquivo
        # Tenta mapear pelo nome se possível, senão pelo índice fixo
        try:
            # Estratégia Híbrida: Tenta pegar colunas importantes
            cols_needed = ['Nome', 'Categoria', 'Forma de Pagamento', 'Data de Pagamento', 'Situação', 'Data de Inscrição', 'Data de nascimento', 'Estado', 'País']
            # Se o arquivo baixado tiver esses nomes exatos, usamos eles. Senão, usamos índices.
            # Vou manter os índices do seu código original que funcionava
            df_clean = df.iloc[:, [1, 2, 4, 5, 9, 13, 21, 52, 53]].copy()
            df_clean.columns = ['Nome', 'Categoria', 'Pgto', 'DataPagamento', 'Situacao', 'DataInscricao', 'Nasc', 'UF', 'Pais']
        except:
            st.error("O layout do arquivo baixado está diferente do esperado. Verifique as colunas.")
            st.write(df.head()) # Mostra o cabeçalho para debug
            st.stop()

        df_clean = df_clean.dropna(subset=['Nome'])
        
        # ... (Mantendo sua lógica de tratamento de dados e geração de gráficos) ...
        # Normalização
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
            return 'Aberto'

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
        df_clean['Status'] = df_clean.apply(classificar, axis=1)

        # Datas
        df_clean['DataInscricao'] = pd.to_datetime(df_clean['DataInscricao'], dayfirst=True, errors='coerce')
        df_clean['DataPagamento'] = pd.to_datetime(df_clean['DataPagamento'], dayfirst=True, errors='coerce')
        
        def get_dt_graf(row):
            if row['Status'] == 'Pago' and pd.notnull(row['DataPagamento']): return row['DataPagamento']
            return row['DataInscricao']
        df_clean['DataGrafico'] = df_clean.apply(get_dt_graf, axis=1)
        df_grafico = df_clean.dropna(subset=['DataGrafico'])

        # Regiões
        reg_map = {"SP":"Sudeste","RJ":"Sudeste","MG":"Sudeste","ES":"Sudeste","PR":"Sul","SC":"Sul","RS":"Sul","BA":"Nordeste","PE":"Nordeste","CE":"Nordeste","DF":"Centro-Oeste","GO":"Centro-Oeste","AM":"Norte","PA":"Norte"}
        df_clean['Regiao'] = df_clean['UF_Norm'].apply(lambda x: reg_map.get(x, "Outros") if len(x)==2 else "Outros")

        def agrupar(s):
            c = s.value_counts(); p = c/len(s); m = c[p>=0.1]; mn = c[p<0.1].sum()
            r = m.copy(); 
            if mn>0: r['Outros'] = r.get('Outros',0)+mn
            return r

        # Gráficos
        def to_b64(fig):
            b = BytesIO(); fig.savefig(b, format='png', dpi=100, transparent=True); plt.close(fig)
            return base64.b64encode(b.getvalue()).decode('utf-8')

        # 1. Pizza
        f1, a1 = plt.figure(figsize=(7,5)), plt.gca(); plt.style.use('ggplot')
        d_reg = agrupar(df_clean['Regiao'])
        a1.pie(d_reg, labels=d_reg.index, autopct='%1.0f%%'); img_reg = to_b64(f1)

        # 2. Barra
        f2, a2 = plt.figure(figsize=(7,5)), plt.gca()
        d_id = df_clean['FaixaEtaria'].value_counts().sort_index()
        d_id.plot(kind='bar', color='#3498db', ax=a2); plt.xticks(rotation=0); a2.bar_label(a2.containers[0], padding=3)
        img_id = to_b64(f2)

        # 3. Evolução
        df_evo = df_grafico.set_index('DataGrafico').groupby([pd.Grouper(freq='W'), 'Status']).size().unstack(fill_value=0)
        f3, a3 = plt.figure(figsize=(12,5)), plt.gca()
        for c, color in [('Pago','#27ae60'), ('Cortesia','#f39c12'), ('Aberto','#c0392b')]:
            if c in df_evo.columns: a3.plot(df_evo.index, df_evo[c], marker='.', color=color, label=c)
        a3.legend(); a3.grid(True, alpha=0.3)
        dates = df_evo.index; labels = []; pm = None; py = None; a3.set_xticks(dates)
        for d in dates:
            l = f"{d.day}"; 
            if pm != d.month: l += f"\n{d.strftime('%b')}"; a3.axvline(d, c='#ccc', ls='--')
            if py != d.year: l += f"\n{d.year}"; a3.axvline(d, c='#666', ls='-')
            labels.append(l); pm=d.month; py=d.year
        a3.set_xticklabels(labels, fontsize=8); img_evo = to_b64(f3)

        # HTML
        def tab(df, col):
            r = df.groupby([col, 'Status']).size().unstack(fill_value=0)
            r['Total'] = r.sum(axis=1)
            return r.sort_values('Total', ascending=False)

        tb_cat = tab(df_clean, 'Categoria')
        tb_pais = tab(df_clean, 'Pais')
        tb_uf = tab(df_clean[df_clean['Pais']=='BRASIL'], 'UF')

        def render(df):
            h = '<table class="dt"><thead><tr><th>Nome</th><th>Total</th><th>Pagos</th><th>Cort.</th><th>Aberto</th></tr></thead><tbody>'
            for i,r in df.iterrows():
                p=r.get('Pago',0); c=r.get('Cortesia',0); a=r.get('Aberto',0)
                h += f'<tr><td>{str(i)[:40]}</td><td class="b">{r["Total"]}</td><td class="g">{p}</td><td class="o">{c}</td><td class="r">{a}</td></tr>'
            return h+'</tbody></table>'

        tot=len(df_clean); pg=len(df_clean[df_clean['Status']=='Pago']); cr=len(df_clean[df_clean['Status']=='Cortesia']); ab=len(df_clean[df_clean['Status']=='Aberto'])
        d_str = (datetime.utcnow()-timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')

        css = "body{font-family:Helvetica;color:#333}.head{padding:15px 0;border-bottom:2px solid #eee}.tit{font-size:22px;font-weight:700}.kpi-row{display:flex;justify-content:space-between;gap:10px;margin:25px 0}.kpi{width:23%;padding:15px 5px;border-radius:8px;color:#fff;text-align:center}.kl{font-size:10px;font-weight:bold;text-transform:uppercase}.kv{font-size:32px;font-weight:800}.card{border:1px solid #e0e0e0;border-radius:8px;margin-bottom:20px}.ch{padding:12px 15px;background:#f8f9fa;border-bottom:1px solid #eee}.ch h3{margin:0;font-size:15px;color:#444;text-transform:uppercase}.cb{padding:15px;text-align:center}.row{display:flex;gap:15px}.col{width:48%}.img{width:100%;max-height:300px;object-fit:contain}.dt{width:100%;border-collapse:collapse;font-size:12px}.dt th{background:#f8f9fa;padding:10px;text-align:left}.dt td{padding:8px 10px;border-bottom:1px solid #eee}.b{font-weight:bold}.g{color:#27ae60;font-weight:bold}.o{color:#d35400;font-weight:bold}.r{color:#c0392b;font-weight:bold}"
        
        html = f"""<!DOCTYPE html><html><head><style>{css}</style></head><body>
        <div class="head"><div class="tit">Relatório - {con_event} {con_year}</div><div class="meta">Gerado em: {d_str}</div></div>
        <div class="kpi-row">
            <div class="kpi" style="background:#3498db"><div class="kl">Total</div><div class="kv">{tot}</div></div>
            <div class="kpi" style="background:#27ae60"><div class="kl">Pagos</div><div class="kv">{pg}</div></div>
            <div class="kpi" style="background:#f39c12"><div class="kl">Cortesias</div><div class="kv">{cr}</div></div>
            <div class="kpi" style="background:#c0392b"><div class="kl">Aberto</div><div class="kv">{ab}</div></div>
        </div>
        <div class="card"><div class="ch"><h3>Evolução</h3></div><div class="cb"><img src="data:image/png;base64,{img_evo}" style="width:100%"></div></div>
        <div class="row">
            <div class="col card"><div class="ch"><h3>Região</h3></div><div class="cb"><img src="data:image/png;base64,{img_reg}" class="img"></div></div>
            <div class="col card"><div class="ch"><h3>Idade</h3></div><div class="cb"><img src="data:image/png;base64,{img_id}" class="img"></div></div>
        </div>
        <div class="card"><div class="ch"><h3>Categoria</h3></div><div class="cb" style="text-align:left;padding:0">{render(tb_cat)}</div></div>
        <div class="row">
            <div class="col card"><div class="ch"><h3>País</h3></div><div class="cb" style="text-align:left;padding:0">{render(tb_pais)}</div></div>
            <div class="col card"><div class="ch"><h3>Estados (BR)</h3></div><div class="cb" style="text-align:left;padding:0">{render(tb_uf)}</div></div>
        </div></body></html>"""

        pdf_io = BytesIO()
        HTML(string=html).write_pdf(pdf_io)
        
        st.balloons()
        st.success("✅ Relatório Gerado!")
        st.download_button("⬇️ BAIXAR PDF", data=pdf_io.getvalue(), file_name=f"Relatorio_{con_event}_{con_year}.pdf", mime="application/pdf")

    except Exception as e:
        st.error(f"Erro ao processar: {e}")

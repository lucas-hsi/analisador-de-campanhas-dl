import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
import google.generativeai as genai
import tempfile
import pdfkit
from datetime import date
import json
import time

# --- CONFIGURAÇÃO INICIAL ---
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# --- CONFIGURAÇÃO DA PÁGINA STREAMLIT ---
st.set_page_config(layout="wide", page_title="DL Diagnóstico Estratégico v2.0")
st.image("https://i.imgur.com/Qo5aR3j.png", width=150) # Adicionei um logo simples
st.markdown("<h1 style='color:#004aad;'>📊 DL Diagnóstico Estratégico v2.0</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='color:#444;'>Análise de Performance para Mercado Livre Ads</h4>", unsafe_allow_html=True)

# --- FUNÇÕES DE PROCESSAMENTO DE DADOS ---

# ==============================================================================
# COLE ESTA VERSÃO FINAL E ROBUSTA DA FUNÇÃO EM SEU CÓDIGO PRINCIPAL
# ==============================================================================
def carregar_anuncios(uploaded_file):
    """
    Lê o arquivo Excel, encontra dinamicamente o cabeçalho, limpa os dados
    e garante que os tipos numéricos estão corretos. Versão "à prova de balas".
    """
    try:
        # 1. Lê o arquivo sem assumir uma linha de cabeçalho fixa
        df = pd.read_excel(uploaded_file, sheet_name="Relatório de campanha", header=None)

        # 2. Encontra dinamicamente a linha que contém os cabeçalhos (procurando por 'Nome')
        header_row_index = -1
        for i in range(min(10, df.shape[0])): # Procura nas primeiras 10 linhas
            if 'Nome' in str(df.iloc[i].values):
                header_row_index = i
                break
        
        if header_row_index == -1:
            st.error("Erro Crítico: Não foi possível encontrar a linha de cabeçalho com a coluna 'Nome'. O formato do arquivo do Mercado Livre pode ter mudado.")
            st.stop()

        # 3. Define a linha encontrada como o cabeçalho e remove o lixo de cima
        df.columns = df.iloc[header_row_index]
        df = df.iloc[header_row_index + 1:].reset_index(drop=True)

        # 4. Agora, com o DataFrame limpo, prosseguimos com a lógica robusta
        # Renomeia as colunas para nosso padrão
        df = df.rename(columns={
            "Nome": "anuncio", "Status": "status_campanha", "Orçamento": "orcamento",
            "ACOS Objetivo": "acos_objetivo", "Impressões": "impressoes",
            "Cliques": "cliques", "Investimento\n(Moeda local)": "investimento",
            "CPC \n(Custo por clique)": "cpc", "CTR\n(Click through rate)": "ctr",
            "CVR\n(Conversion rate)": "cvr", "Receita\n(Moeda local)": "receita",
            "ACOS\n(Investimento / Receitas)": "acos", "ROAS\n(Receitas / Investimento)": "roas",
            "% de impressões perdidas por orçamento": "perda_orcamento",
            "% de impressões perdidas por classificação": "perda_classificacao"
        })

        # Filtra a linha "Total" que pode existir no final
        if 'anuncio' in df.columns:
            df = df[df["anuncio"].notna() & (df["anuncio"] != "Total")]
        
        # Seleciona apenas as colunas que vamos usar
        colunas_para_usar = [
            'anuncio', 'status_campanha', 'orcamento', 'acos_objetivo', 'impressoes',
            'cliques', 'investimento', 'cpc', 'ctr', 'cvr', 'receita', 'acos', 'roas',
            'perda_orcamento', 'perda_classificacao'
        ]
        colunas_existentes = [col for col in colunas_para_usar if col in df.columns]
        df = df[colunas_existentes]

        # Converte colunas para o tipo numérico correto
        colunas_numericas = [
            'orcamento', 'acos_objetivo', 'impressoes', 'cliques', 'investimento',
            'cpc', 'ctr', 'cvr', 'receita', 'acos', 'roas',
            'perda_orcamento', 'perda_classificacao'
        ]
        for coluna in colunas_numericas:
            if coluna in df.columns:
                df[coluna] = df[coluna].astype(str).str.replace(',', '.', regex=False).str.replace('%', '', regex=False)
                df[coluna] = pd.to_numeric(df[coluna], errors='coerce')

        df.fillna(0, inplace=True)
        return df.reset_index(drop=True)

    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao processar o arquivo: {e}")
        st.info("Verifique se o arquivo enviado é o relatório de campanhas correto e não está corrompido.")
        st.stop()

    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao processar o arquivo: {e}")
        st.info("Verifique se o arquivo enviado é o relatório de campanhas correto e não está corrompido.")
        st.stop()
    
    # --- FIM DA CORREÇÃO DE LÓGICA ---

    # Seleciona apenas as colunas que vamos usar
    colunas_para_usar = [
        'anuncio', 'status_campanha', 'orcamento', 'acos_objetivo', 'impressoes',
        'cliques', 'investimento', 'cpc', 'ctr', 'cvr', 'receita', 'acos', 'roas',
        'perda_orcamento', 'perda_classificacao'
    ]
    
    # Garante que só tentamos acessar colunas que realmente existem após a renomeação
    colunas_existentes = [col for col in colunas_para_usar if col in df.columns]
    df = df[colunas_existentes]

    # Converte colunas para o tipo numérico correto, tratando erros
    colunas_numericas = [
        'orcamento', 'acos_objetivo', 'impressoes', 'cliques', 'investimento',
        'cpc', 'ctr', 'cvr', 'receita', 'acos', 'roas',
        'perda_orcamento', 'perda_classificacao'
    ]
    for coluna in colunas_numericas:
         if coluna in df.columns: # Checagem extra de segurança
            df[coluna] = df[coluna].astype(str).str.replace(',', '.', regex=False).str.replace('%', '', regex=False)
            df[coluna] = pd.to_numeric(df[coluna], errors='coerce')

    df.fillna(0, inplace=True)
    return df.reset_index(drop=True)

# --- FUNÇÃO DE ANÁLISE COM GEMINI (O NOVO CÉREBRO) ---

# ==============================================================================
# ANALISE DE IA
# ==============================================================================
def analisar_anuncios_com_gemini(bloco_df):
    """Envia um bloco de anúncios para a API do Gemini e retorna uma análise estruturada e inteligente."""
    
    dados_str = ""
    for _, row in bloco_df.iterrows():
        dados_str += f"""- Anúncio: {row['anuncio']} | Impressões: {int(row['impressoes'])} | Cliques: {int(row['cliques'])} | CTR: {row['ctr']:.2f}% | CVR: {row['cvr']:.2f}% | Investimento: R${row['investimento']:.2f} | Receita: R${row['receita']:.2f} | ACOS: {row['acos']:.2f}% | ACOS Objetivo: {int(row['acos_objetivo'])}% | Perda Orçamento: {int(row['perda_orcamento'])}% | Perda Classificação: {int(row['perda_classificacao'])}%\n"""

    prompt = f"""
Você é um Diretor de Performance sênior da DL Auto Peças, especialista em Mercado Livre Ads. Sua análise deve ser estratégica, direta e focada em resultados financeiros para o dono da empresa.

Analise os dados dos anúncios abaixo. Para CADA UM, forneça uma análise completa.

**Regras da Análise:**
1.  **ACOS é Rei:** A métrica mais importante é o ACOS. Compare o ACOS real com o ACOS Objetivo.
2.  **Lucratividade:** Se ACOS <= ACOS Objetivo, a campanha é lucrativa. Se ACOS > ACOS Objetivo, não é.
3.  **Falta de Orçamento:** Se a campanha é lucrativa e a 'Perda Orçamento' for alta (>50%), a ação clara é aumentar o orçamento.
4.  **Problema de Classificação:** Se a 'Perda Classificação' for alta (>50%), o problema está no anúncio (preço, foto, título). A ação é otimizar o anúncio.
5.  **CTR vs CVR:** Um CTR alto com CVR baixo indica que o anúncio atrai cliques, mas a página do produto não converte (preço, frete, descrição).

**Formato da Resposta:**
Sua resposta DEVE ser um único bloco de código JSON, com uma chave principal "analises" contendo uma lista de objetos. Cada objeto deve ter as seguintes chaves:
- anuncio: (string) O nome exato do anúncio.
- status: (string) Escolha uma das três: "ESCALAR" (lucrativa e com potencial), "AJUSTAR" (problemas a corrigir) ou "PAUSAR" (prejuízo claro e sem potencial óbvio).
- motivo: (string) A razão principal para o status, citando as métricas chave (Ex: "ACOS de 5% está bem abaixo da meta de 10%").
- acao: (string) Uma ação prática e específica (Ex: "Aumentar orçamento em 30%." ou "Revisar o preço do produto pois o CVR está baixo.").
- receita: (float) O valor da receita do anúncio.
- investimento: (float) O valor do investimento.
- acos: (float) O valor do ACOS.

**Dados para Análise:**
---
{dados_str}
"""
    try:
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        
        # --- A GRANDE MUDANÇA ESTÁ AQUI ---
        # Configuração para forçar a resposta a ser determinística (sem criatividade)
        generation_config = genai.types.GenerationConfig(
            temperature=0.0
        )
        
        # Passamos a configuração na chamada da API
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        # --- FIM DA MUDANÇA ---

        cleaned_json_str = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_json_str)
    except Exception as e:
        st.error(f"Ocorreu um erro na chamada da API: {e}")
        st.code(prompt)
        return None

# --- FUNÇÕES DE GERAÇÃO DE RELATÓRIO (A NOVA APRESENTAÇÃO) ---

def gerar_relatorio_html(df):
    """Orquestra a análise e a criação do relatório HTML v2.0."""
    
    todas_as_analises = []
    for i in range(0, len(df), 3): # Blocos de 3 para não estourar os limites
        st.info(f"Analisando bloco {i//3 + 1} de {len(df)//3 + 1}...")
        bloco_df = df.iloc[i:i+3]
        resultado_json = analisar_anuncios_com_gemini(bloco_df)
        
        if resultado_json and "analises" in resultado_json:
            todas_as_analises.extend(resultado_json["analises"])
        
        # Pausa para não exceder limites da API (se não tiver billing ativado)
        # st.info("Pausa de 20s para respeitar os limites da API...")
        # time.sleep(20)

    if not todas_as_analises:
        st.warning("Nenhuma análise foi gerada pela IA.")
        return None

    # Processa os dados para o painel financeiro
    painel_financeiro = {"ESCALAR": {"qtd": 0, "investimento": 0, "receita": 0},
                         "AJUSTAR": {"qtd": 0, "investimento": 0, "receita": 0},
                         "PAUSAR": {"qtd": 0, "investimento": 0, "receita": 0}}
    
    for analise in todas_as_analises:
        status = analise.get("status", "AJUSTAR").upper()
        if status in painel_financeiro:
            painel_financeiro[status]["qtd"] += 1
            painel_financeiro[status]["investimento"] += analise.get("investimento", 0)
            painel_financeiro[status]["receita"] += analise.get("receita", 0)

    # Ordena as análises por status para o relatório
    ordem_status = {"ESCALAR": 0, "AJUSTAR": 1, "PAUSAR": 2}
    todas_as_analises.sort(key=lambda x: ordem_status.get(x.get("status", "AJUSTAR"), 3))

    # --- Inicia a construção do HTML ---
    html_parts = [f"""
<!DOCTYPE html><html lang='pt-BR'><head><meta charset='UTF-8'>
<style>
body {{font-family: Arial, sans-serif; font-size: 15px; padding: 40px; color: #333;}}
.card {{margin-bottom: 25px; padding: 22px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); border-left: 8px solid #ccc; break-inside: avoid;}}
.card-ESCALAR {{ background-color: #f0fff0; border-left-color: #2e7d32; }}
.card-AJUSTAR {{ background-color: #fffbeb; border-left-color: #f9a825; }}
.card-PAUSAR {{ background-color: #fff0f0; border-left-color: #c62828; }}
.badge {{display: inline-block; padding: 6px 14px; border-radius: 50px; font-size: 14px; font-weight: bold; color: #fff; margin-bottom: 15px;}}
.badge-ESCALAR {{ background-color: #2e7d32; }}
.badge-AJUSTAR {{ background-color: #f9a825; color: #fff; }}
.badge-PAUSAR {{ background-color: #c62828; }}
h1 {{ color: #004aad; text-align: center; }}
h2 {{ color: #004aad; border-bottom: 2px solid #004aad; padding-bottom: 10px; margin-top: 40px;}}
table {{width: 100%; border-collapse: collapse; margin-top: 20px;}}
th, td {{border: 1px solid #ddd; padding: 12px; text-align: left;}}
th {{background-color: #f2f2f2; font-weight: bold;}}
.metric-line {{ background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-top: 10px; border: 1px solid #e9ecef; }}
</style></head><body>
<h1>Relatório Estratégico de Performance</h1><p style="text-align: center;"><strong>DL Auto Peças | Data:</strong> {date.today().strftime("%d/%m/%Y")}</p>
<h2>📌 Painel Financeiro Executivo</h2>
<table><tr><th>Status</th><th>Qtd. Anúncios</th><th>Investimento Total</th><th>Receita Total</th><th>ACOS Médio</th></tr>
"""]
    for status, data in painel_financeiro.items():
        acos_medio = (data['investimento'] / data['receita'] * 100) if data['receita'] > 0 else 0
        cor_badge = f"badge-{status}"
        html_parts.append(f"<tr><td><span class='badge {cor_badge}'>{status}</span></td><td>{data['qtd']}</td><td>R$ {data['investimento']:.2f}</td><td>R$ {data['receita']:.2f}</td><td>{acos_medio:.2f}%</td></tr>")
    html_parts.append("</table>")

    status_atual = ""
    for analise in todas_as_analises:
        status = analise.get("status", "AJUSTAR").upper()
        if status != status_atual:
            status_atual = status
            html_parts.append(f"<h2>{status_atual}</h2>")
        
        receita_val = analise.get('receita', 0)
        investimento_val = analise.get('investimento', 0)
        acos_val = (investimento_val / receita_val * 100) if receita_val > 0 else 0
        
        html_parts.append(f"<div class='card card-{status}'>")
        html_parts.append(f"<div class='badge badge-{status}'>{status}</div>")
        html_parts.append(f"<p><strong>Anúncio:</strong> {analise.get('anuncio', 'N/A')}</p>")
        html_parts.append(f"<div class='metric-line'>Receita: <strong>R$ {receita_val:.2f}</strong> | Investimento: <strong>R$ {investimento_val:.2f}</strong> | ACOS: <strong>{acos_val:.2f}%</strong></div>")
        html_parts.append(f"<p><strong>Motivo da Análise:</strong> {analise.get('motivo', 'N/A')}</p>")
        html_parts.append(f"<p><strong>Ação Recomendada:</strong> {analise.get('acao', 'N/A')}</p>")
        html_parts.append("</div>")

    html_parts.append("</body></html>")
    return "\n".join(html_parts)

def gerar_pdf(html_string):
    """Converte a string HTML em um arquivo PDF e retorna o caminho."""
    try:
        temp_html = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        with open(temp_html.name, "w", encoding="utf-8") as f:
            f.write(html_string)
        options = {"encoding": "UTF-8", "enable-local-file-access": None,
                   "margin-top": "15mm", "margin-bottom": "15mm"}
        pdfkit.from_file(temp_html.name, temp_pdf.name, options=options)
        return temp_pdf.name
    except OSError as e:
        st.error("Erro ao gerar o PDF: O programa 'wkhtmltopdf' não foi encontrado.")
        st.info("Por favor, instale o wkhtmltopdf no seu sistema e garanta que ele esteja no PATH do sistema. Link para download: https://wkhtmltopdf.org/downloads.html")
        st.stop()


# --- INTERFACE E LÓGICA PRINCIPAL DO STREAMLIT ---
uploaded_file = st.file_uploader("📎 Envie o Excel do Mercado Livre Ads", type=["xlsx", "csv"])

if uploaded_file:
    if not api_key:
        st.error("API Key do Google não encontrada. Configure o arquivo .env com GOOGLE_API_KEY=SUA_CHAVE")
    else:
        df = carregar_anuncios(uploaded_file)
        st.markdown("### 📋 Prévia dos Dados Carregados")
        st.dataframe(df)

        if st.button("🚀 Gerar Diagnóstico v2.0"):
            with st.spinner("Analisando campanhas com a IA (v2.0) e montando o relatório... Isso pode levar alguns minutos."):
                html_report = gerar_relatorio_html(df)
            if html_report:
                with st.spinner("Gerando PDF..."):
                    path = gerar_pdf(html_report)
                st.success("✅ Diagnóstico Estratégico v2.0 gerado com sucesso!")
                with open(path, "rb") as f:
                    st.download_button(
                        label="📄 Baixar Relatório v2.0",
                        data=f,
                        file_name=f"diagnostico_dl_v2_{date.today().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf"
                    )

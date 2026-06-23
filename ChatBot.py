# CHATBOT ORÇAMENTISTA 

import re
import pandas as pd
import streamlit as st
import unicodedata
import webbrowser
import urllib.parse

from datetime import datetime
from difflib import get_close_matches

data_atualizacao = datetime(2025, 6, 19)

# LER ARQUIVO

@st.cache_data
def carregar_dados():
    return pd.read_csv("Produtos.csv")

df = carregar_dados()

# CORREÇÃO DE TEXTO

def normalizar_texto(texto):
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^\w\s]", "", texto)
    return texto

def corrigir_palavras(busca, lista_palavras):
    palavras = busca.split()
    palavras_corrigidas = []

    for p in palavras:
        match = get_close_matches(p, lista_palavras, n=1, cutoff=0.7)
        
        if match:
            palavras_corrigidas.append(match[0])
        else:
            palavras_corrigidas.append(p)

    return " ".join(palavras_corrigidas)

def corrigir_tokens_complexos(busca):
    busca = re.sub(r'sxh\s*(\d+)', r'sch \1', busca)
    busca = re.sub(r'sc\s*(\d+)', r'sch \1', busca)
    busca = re.sub(r'sh\s*(\d+)', r'sch \1', busca)
    busca = re.sub(r'dm\s*(\d+)', r'dn \1', busca)
    busca = re.sub(r'dn\s*(\d+)', r'dn \1', busca)
    return busca

# FUNÇÃO PRINCIPAL

def buscar_produtos(busca):

    if not busca or busca.strip() == "":
        return "⚠️ Digite uma busca válida."

    busca_original = busca
    busca_normalizada = normalizar_texto(busca)

    # PERGUNTA DE ATUALIZAÇÃO
    if "atualizacao" in busca_normalizada:
        desatualizado, dias = verificar_base()
        data_formatada = data_atualizacao.strftime("%d/%m/%Y")

        if desatualizado:
            return(f"📅 Última atualização: {data_formatada}\n\n"
                   f"<span style='color:red; font-weight:bold;'>⚠️ Base desatualizada há {dias} dias.</span>")
        else:
            return(f"📅 Última atualização: {data_formatada}\n\n✅ Base dentro do prazo."
                   f"<span style='color:green; font-weight:bold;'>✅ Base dentro do prazo.</span>")

    # BUSCA POR CÓDIGO
    match = re.search(r"\b[A-Z]{3,}\d{5,}\b", busca_original.upper())

    if match and " " not in busca_original:
        codigo = match.group()
        resultado = df[df['CODIGO'].astype(str) == codigo]

        if resultado.empty:
            return "❌ Código não encontrado."

        linha = resultado.iloc[0]

        return (
            f"🔹 **Código:** {linha['CODIGO']}\n\n"
            f"🔹 **Descrição:** {linha['DESCRICAO']}\n\n"
            f"💰 **Custo:** R$ {float(linha['CUSTO']):.2f}\n\n"
        )

    # PROCESSAMENTO
    busca = busca.lower()

    # remover aspas
    busca = busca.replace('"', ' ')

    # Separar DN + SCH grudado
    busca = re.sub(r"(dn\d+)(sch\d+)", r"\1 \2", busca)

    # Separar DN e número
    busca = re.sub(r"dn\s*(\d+)", r"dn \1", busca)

    # Separar SCH e número
    busca = re.sub(r"sch\s*(\d+)", r"sch \1", busca)

    # Corrigir erros de digitação
    busca = corrigir_tokens_complexos(busca)

    # Corrigir palavras simples
    busca = corrigir_palavras(busca, ["tubo", "dn", "sch", "304", "316"])

    # Limpar espaços
    busca = re.sub(r"\s+", " ", busca).strip()

    palavras = busca.split()

# FILTROS DE BUSCA

    filtro = pd.Series([True] * len(df), index=df.index)

    i = 0
    while i < len(palavras):
        p = palavras[i]

        if p == "dn" and i + 1 < len(palavras):
            dn_valor = palavras[i + 1].strip()
            filtro = filtro & (
                df["DN"]
                .astype(str)
                .str.replace('"', '', regex=False)
                .str.strip()
                == dn_valor
            )
            i += 2
            continue

        if p == "sch" and i + 1 < len(palavras):
            sch_valor = palavras[i + 1].strip()

            filtro = filtro & (
                df["SCH"]
                .astype(str)
                .str.strip()
                .str.extract(r"(\d+)")[0]
                == sch_valor
            )
            i += 2
            continue

        if p in ["304", "316"]:
            filtro = filtro & df["MATERIAL"].str.lower().str.contains(p, na=False)
            i += 1
            continue

        if p not in["dn", "sch"] and not p.isdigit():
            filtro = filtro & df["DESCRICAO"].str.lower().str.contains(p, na=False)
            i += 1
            continue

    resultado = df[filtro]

    # NÃO ENCONTRADO
    if resultado.empty:
        return {
            "status": "nao_encontrado",
            "busca": busca_original,
            "mensagem": "❌ Não encontrei esse item. Quer solicitar uma cotação?"
        }

    # RESULTADO
    resposta = ""

    for _, linha in resultado.iterrows():

        custo_raw = linha['CUSTO']

        try:
            custo = float(str(custo_raw).replace(',', '.').strip())
        except:
            custo = None

        if custo is None or custo <= 0:
            custo_texto = "⚠️ **Custo não disponível**"
        else:
            custo_texto = f"💰 **Custo:** R$ {custo:.2f}"

        resposta += (
            f"🔹 **Código:** {linha['CODIGO']}\n\n"
            f"📄 **Descrição:** {linha['DESCRICAO']}\n\n"
            f"{custo_texto}\n\n"
            f"---\n\n"
        )

    return resposta

# VERIFICAÇÃO BASE

def verificar_base():
    hoje = datetime.today()
    dias = (hoje - data_atualizacao).days
    return dias > 180, dias

# EMAIL AUTOMÁTICO

def abrir_email_outlook(busca):
    assunto = f"Solicitação de cotação - {busca}"

    corpo = (
        f"Olá,\n\n"
        f"Por gentileza, orçar conforme descrição abaixo:\n"
        f"{busca}\n\n"
        f"Agradeço desde já e aguardo o retorno.\n\n"
    )

    link = (
        f"mailto:l.luca@spray.com.br"
        f"?cc=wagner@spray.com.br;a.theodoro@spray.com.br;l.barros@spray.com.br"
        f"?subject={urllib.parse.quote(assunto)}"
        f"&body={urllib.parse.quote(corpo)}"
    )

    webbrowser.open(link)

# CHATBOT 

## LOGO 
col1, col2, col3 = st.columns([1,2,1])

with col2:
    st.image("LOGO.jpg", width=300)

## TÍTULO CENTRALIZADO
st.markdown(
    "<h1 style='text-align: center; color: #1f77b4;'>🏢 Sistema de Orçamentos</h1>",
    unsafe_allow_html=True
)

## SUBTÍTULO CENTRALIZADO
st.markdown(
    "<h3 style='text-align: center; color: gray;'>📊 Consulta Inteligente de Materiais</h3>",
    unsafe_allow_html=True
)

st.divider()

## BUSCA
prompt = st.chat_input("Digite sua busca...")

if "ultima_busca" not in st.session_state:
    st.session_state.ultima_busca = None

if "ultima_resposta" not in st.session_state:
    st.session_state.ultima_resposta = None

if prompt:
    st.session_state.ultima_busca = prompt
    st.session_state.ultima_resposta = buscar_produtos(prompt)

resposta = st.session_state.ultima_resposta

if st.session_state.ultima_busca:
    with st.chat_message("user"):
        st.markdown(st.session_state.ultima_busca)

## RESPOSTA
if resposta:
    with st.chat_message("assistant"):

        # NÃO ENCONTROU
        if isinstance(resposta, dict):
            st.error(resposta["mensagem"])

            if st.button("📧 Solicitar cotação"):
                abrir_email_outlook(st.session_state.ultima_busca)

        # RESPOSTA DE ATUALIZAÇÃO
        elif isinstance(resposta, str) and "Última atualização" in resposta:
            st.markdown(resposta, unsafe_allow_html=True)

        # RESPOSTA DE PRODUTO
        else:
            # VERIFICA BASE
            desatualizado, dias = verificar_base()

            # MOSTRA ALERTA SE DESATUALIZADA
            if desatualizado:
                st.markdown(
                    f"<div style='color:red; font-weight:bold;'>⚠️ Base de dados desatualizada há {dias} dias.</div>",
                    unsafe_allow_html=True
                )

            else:
                st.markdown(
                    "<div style='color:green; font-weight:bold;'>✅ Base de dados dentro do prazo.</div>",
                    unsafe_allow_html=True
                )

            # TÍTULO DO RESULTADO (AZUL)
            st.markdown(
                "<div style='color:#0b5394; font-weight:bold; font-size:18px;'>✅ Resultado encontrado:</div>",
                unsafe_allow_html=True
            )

            # RESULTADO FINAL
            st.markdown(resposta, unsafe_allow_html=True)

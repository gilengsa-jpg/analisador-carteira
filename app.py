import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Monitor Quantitativo de Carteira", layout="wide")

st.title("📊 Analisador de Carteira e Direcionamento Técnico")
st.markdown("Defina seu capital, os ativos e os percentuais alvo para analisar tendências e calcular a alocação.")

# ==========================================
# 1. ENTRADA DE DADOS (BARRA LATERAL)
# ==========================================
st.sidebar.header("⚙️ Parâmetros de Investimento")

capital_total = st.sidebar.number_input(
    "Capital Total para Investir (R$)",
    min_value=100.0,
    value=10000.0,
    step=500.0
)

periodo_dias = st.sidebar.selectbox(
    "Janela de Análise Histórica",
    options=[30, 60, 90, 180],
    index=2,
    format_func=lambda x: f"Últimos {x} dias"
)

tickers_padrao = "PETR4.SA, VALE3.SA, ITUB4.SA, WEGE3.SA, BBAS3.SA"
tickers_input = st.sidebar.text_input(
    "Ações (separadas por vírgula, com .SA)",
    value=tickers_padrao
)

lista_tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

st.sidebar.subheader("🎯 Percentual Alvo por Ação (%)")
pesos = {}
soma_pesos = 0.0

for tk in lista_tickers:
    peso_default = round(100.0 / len(lista_tickers), 1) if lista_tickers else 0.0
    p = st.sidebar.number_input(
        f"% {tk}",
        min_value=0.0,
        max_value=100.0,
        value=peso_default,
        step=1.0,
        key=f"peso_{tk}"
    )
    pesos[tk] = p
    soma_pesos += p

if abs(soma_pesos - 100.0) > 0.1:
    st.sidebar.warning(f"⚠️ A soma dos percentuais está em {soma_pesos:.1f}%. O ideal é fechar em 100%.")
else:
    st.sidebar.success("✅ Alocação fechada em 100%!")

# ==========================================
# 2. MOTOR DE CÁLCULO E INDICADORES
# ==========================================
def calcular_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

if st.button("🚀 Analisar Mercado e Calcular Alocação", type="primary"):
    if not lista_tickers:
        st.error("Informe pelo menos um ticker válido.")
    else:
        with st.spinner("Coletando cotações históricas e calculando indicadores..."):
            dados_raw = yf.download(lista_tickers, period="1y", progress=False)
            dados = dados_raw["Close"] if "Close" in dados_raw else dados_raw

            if isinstance(dados, pd.Series):
                dados = dados.to_frame(name=lista_tickers[0])

            resultados = []
            for tk in lista_tickers:
                if tk not in dados.columns:
                    continue
                serie = dados[tk].dropna()
                if len(serie) < 50:
                    continue

                serie_janela = serie.tail(periodo_dias)
                preco_atual = float(serie.iloc[-1])
                preco_inicio_janela = float(serie_janela.iloc[0])
                variacao_janela = ((preco_atual / preco_inicio_janela) - 1) * 100

                mm21 = float(serie.tail(21).mean())
                mm50 = float(serie.tail(50).mean())
                rsi_atual = float(calcular_rsi(serie).iloc[-1])

                if preco_atual > mm21 and mm21 > mm50 and rsi_atual < 70:
                    sinal = "🟢 COMPRA / ACUMULAR"
                    motivo = "Tendência de alta alinhada (Preço > MM21 > MM50) sem sobrecompra."
                elif rsi_atual >= 70:
                    sinal = "🟡 AGUARDAR / REALIZAR PARCIAL"
                    motivo = f"Ativo esticado (IFR em {rsi_atual:.1f} - zona de sobrecompra)."
                elif preco_atual < mm21 and preco_atual < mm50 and rsi_atual <= 32:
                    sinal = "🔵 OPORTUNIDADE DE REVERSÃO"
                    motivo = f"Queda acentuada com IFR sobrevendido ({rsi_atual:.1f})."
                else:
                    sinal = "🔴 CAUTELA / EVITAR COMPRA"
                    motivo = "Abaixo das médias de curto/médio prazo sem sinal de fundo."

                valor_alvo = capital_total * (pesos[tk] / 100.0)
                qtd_estimada = int(valor_alvo // preco_atual) if preco_atual > 0 else 0

                resultados.append({
                    "Ação": tk,
                    "Preço Atual (R$)": round(preco_atual, 2),
                    f"Var. {periodo_dias}d (%)": round(variacao_janela, 2),
                    "MM21 (R$)": round(mm21, 2),
                    "IFR (14d)": round(rsi_atual, 1),
                    "Peso (%)": pesos[tk],
                    "Alocação (R$)": round(valor_alvo, 2),
                    "Qtd. Ações": qtd_estimada,
                    "Direcionamento": sinal,
                    "Leitura Técnica": motivo
                })

            if resultados:
                df_resultado = pd.DataFrame(resultados)
                st.subheader("📋 Painel de Decisão e Alocação")
                st.dataframe(df_resultado, use_container_width=True, hide_index=True)

                st.subheader(f"📈 Desempenho Relativo nos Últimos {periodo_dias} Pregões (Base 100)")
                colunas_validas = [t for t in lista_tickers if t in dados.columns]
                if colunas_validas:
                    dados_norm = (dados[colunas_validas].tail(periodo_dias) / dados[colunas_validas].tail(periodo_dias).iloc[0]) * 100
                    st.line_chart(dados_norm)
            else:
                st.warning("Não foi possível obter histórico suficiente para os tickers informados.")

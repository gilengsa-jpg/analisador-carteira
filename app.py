import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Top 5 Ações & Evolução Histórica", layout="wide")

st.title("🏆 Analisador de Ações — Ranking, Seleção (até 5) e Evolução")
st.markdown(
    "O aplicativo avalia todo o universo informado, destaca as **5 melhores do dia**, "
    "permite escolher **até 5 ações dentre todas as analisadas** para investir e exibe o gráfico de evolução "
    "nos períodos de **30, 60, 90, 180, 240, 300 e 360 dias**."
)

# ==========================================
# 1. PARÂMETROS NA BARRA LATERAL
# ==========================================
st.sidebar.header("⚙️ Configurações de Análise e Capital")

capital_total = st.sidebar.number_input(
    "Capital Total Disponível (R$)",
    min_value=100.0,
    value=10000.0,
    step=500.0
)

universo_padrao = (
    "PETR4.SA, VALE3.SA, ITUB4.SA, BBDC4.SA, BBAS3.SA, "
    "WEGE3.SA, PRIO3.SA, RENT3.SA, EQTL3.SA, RADL3.SA, "
    "SBSP3.SA, ABEV3.SA, SUZB3.SA, CSAN3.SA, EMBR3.SA, "
    "RAIL3.SA, VIVT3.SA, CPLE6.SA, ENGIE3.SA, MULT3.SA"
)

tickers_input = st.sidebar.text_area(
    "Universo de Ações para Avaliar (separadas por vírgula)",
    value=universo_padrao,
    height=95
)

lista_tickers = list(dict.fromkeys([t.strip().upper() for t in tickers_input.split(",") if t.strip()]))

st.sidebar.subheader("⚖️ Pesos dos Critérios (Score)")
peso_tendencia = st.sidebar.slider("Tendência (MM21 / MM50)", 0, 50, 30)
peso_momentum = st.sidebar.slider("Momentum (Retorno 20d)", 0, 50, 25)
peso_risco = st.sidebar.slider("Baixa Volatilidade & Drawdown", 0, 50, 25)
peso_liquidez = st.sidebar.slider("Liquidez (Volume Financeiro)", 0, 50, 20)

if (peso_tendencia + peso_momentum + peso_risco + peso_liquidez) == 0:
    peso_tendencia = 100

# ==========================================
# 2. FUNÇÕES DE CÁLCULO E PONTUAÇÃO
# ==========================================
def calcular_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)

@st.cache_data(ttl=900)
def avaliar_universo(tickers, w_tend, w_mom, w_risco, w_liq):
    dados_raw = yf.download(
        tickers,
        period="2y",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        progress=False
    )
    if dados_raw is None or dados_raw.empty:
        return pd.DataFrame(), pd.DataFrame()

    w_sum = float(w_tend + w_mom + w_risco + w_liq)
    registros = []
    series_fechamento = {}

    for tk in tickers:
        try:
            if isinstance(dados_raw.columns, pd.MultiIndex):
                if tk not in dados_raw.columns.get_level_values(0):
                    continue
                df_tk = dados_raw[tk].dropna(how="all")
            else:
                df_tk = dados_raw.dropna(how="all")

            if "Close" not in df_tk.columns or len(df_tk["Close"].dropna()) < 50:
                continue

            close = df_tk["Close"].dropna()
            preco_atual = float(close.iloc[-1])
            if preco_atual <= 0:
                continue

            series_fechamento[tk] = close

            mm21 = float(close.tail(21).mean())
            mm50 = float(close.tail(50).mean())
            ret_20d = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) >= 21 else 0.0
            ret_5d = float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) >= 6 else 0.0
            rsi_14 = float(calcular_rsi(close, 14).iloc[-1])

            ret_diario = close.pct_change().dropna()
            vol_anual_pct = float(ret_diario.tail(21).std() * np.sqrt(252) * 100) if len(ret_diario) >= 21 else 40.0

            pico_60d = float(close.tail(60).max())
            drawdown_pct = float((preco_atual / pico_60d - 1) * 100) if pico_60d > 0 else 0.0

            if "Volume" in df_tk.columns:
                vol_fin_med = float((df_tk["Close"] * df_tk["Volume"]).tail(20).mean())
            else:
                vol_fin_med = 0.0

            score_tend = 0.0
            if preco_atual > mm21:
                score_tend += 45.0
            if mm21 > mm50:
                score_tend += 35.0
            if 35.0 <= rsi_14 <= 68.0:
                score_tend += 20.0
            elif rsi_14 > 75.0:
                score_tend -= 15.0
            score_tend = float(np.clip(score_tend, 0.0, 100.0))

            score_mom = float(np.clip(((ret_20d + 15.0) / 35.0) * 100.0, 0.0, 100.0))

            penalidade_vol = max(0.0, (vol_anual_pct - 15.0) * 1.6)
            penalidade_dd = max(0.0, abs(min(0.0, drawdown_pct)) * 2.0)
            score_risco = float(np.clip(100.0 - penalidade_vol - penalidade_dd, 0.0, 100.0))

            if vol_fin_med > 0:
                score_liq = float(np.clip((np.log10(max(vol_fin_med, 1.0)) - 5.0) / (7.3 - 5.0) * 100.0, 0.0, 100.0))
            else:
                score_liq = 50.0

            score_final = (
                score_tend * w_tend
                + score_mom * w_mom
                + score_risco * w_risco
                + score_liq * w_liq
            ) / w_sum

            if score_final >= 70 and rsi_14 < 72:
                recomendacao = "🟢 Forte Candidata"
            elif score_final >= 52:
                recomendacao = "🟡 Moderada / Seletiva"
            else:
                recomendacao = "🔴 Cautela"

            registros.append({
                "Ticker": tk,
                "Score": round(score_final, 1),
                "Recomendação": recomendacao,
                "Preço (R$)": round(preco_atual, 2),
                "Ret. 20d (%)": round(ret_20d, 2),
                "Ret. 5d (%)": round(ret_5d, 2),
                "MM21 (R$)": round(mm21, 2),
                "MM50 (R$)": round(mm50, 2),
                "IFR (14d)": round(rsi_14, 1),
                "Vol. Anual (%)": round(vol_anual_pct, 1),
                "Drawdown 60d (%)": round(drawdown_pct, 1),
                "Vol. Médio (R$ Mi)": round(vol_fin_med / 1e6, 1)
            })
        except Exception:
            continue

    if not registros:
        return pd.DataFrame(), pd.DataFrame()

    df = pd.DataFrame(registros).sort_values(by="Score", ascending=False).reset_index(drop=True)
    df.insert(0, "Rank", df.index + 1)
    df_precos = pd.DataFrame(series_fechamento).sort_index()
    return df, df_precos

# ==========================================
# 3. EXECUÇÃO DO RANKING
# ==========================================
if not lista_tickers:
    st.warning("Insira ao menos um ticker na barra lateral para avaliar.")
    st.stop()

with st.spinner("Avaliando ações e calculando o ranking do dia..."):
    df_ranking, df_precos = avaliar_universo(
        tuple(lista_tickers),
        peso_tendencia,
        peso_momentum,
        peso_risco,
        peso_liquidez
    )

if df_ranking.empty:
    st.error("Não foi possível obter dados de mercado suficientes para os tickers informados.")
    st.stop()

todos_tickers_ordenados = df_ranking["Ticker"].tolist()
top5_df = df_ranking.head(5).copy()
top5_tickers = top5_df["Ticker"].tolist()

st.subheader("🥇 Top 5 Ações do Dia (Sugestão do Ranking Multifatorial)")
st.dataframe(top5_df, use_container_width=True, hide_index=True)

with st.expander("📋 Ver Ranking Completo de Todas as Ações Analisadas"):
    st.dataframe(df_ranking, use_container_width=True, hide_index=True)

st.divider()

# ==========================================
# 4. CAMPO ESPECÍFICO: ESCOLHER ATÉ 5 AÇÕES DENTRE TODAS AS ANALISADAS
# ==========================================
st.subheader("🎯 Escolha Até 5 Ações para Investir (Dentre Todas as Analisadas)")

escolhidas = st.multiselect(
    "Selecione até 5 ações da lista completa avaliada (por padrão vêm as Top 5, mas você pode trocar por qualquer outra analisada):",
    options=todos_tickers_ordenados,
    default=top5_tickers,
    max_selections=5,
    help="Você pode remover alguma das Top 5 e incluir qualquer outra ação do universo analisado, respeitando o limite máximo de 5 ativos."
)

if escolhidas:
    modo_divisao = st.radio(
        "Como deseja distribuir o capital entre as ações escolhidas?",
        options=["Divisão igualitária (% igual)", "Percentuais personalizados"],
        horizontal=True
    )

    pesos_escolhidos = {}
    if modo_divisao == "Divisão igualitária (% igual)":
        peso_unit = round(100.0 / len(escolhidas), 2)
        for i, tk in enumerate(escolhidas):
            if i < len(escolhidas) - 1:
                pesos_escolhidos[tk] = peso_unit
            else:
                pesos_escolhidos[tk] = round(100.0 - peso_unit * (len(escolhidas) - 1), 2)
    else:
        cols = st.columns(len(escolhidas))
        peso_padrao = round(100.0 / len(escolhidas), 1)
        soma_p = 0.0
        for idx, tk in enumerate(escolhidas):
            with cols[idx]:
                val_p = st.number_input(
                    f"% {tk}",
                    min_value=0.0,
                    max_value=100.0,
                    value=peso_padrao,
                    step=1.0,
                    key=f"custom_{tk}"
                )
                pesos_escolhidos[tk] = val_p
                soma_p += val_p

        if abs(soma_p - 100.0) > 0.1:
            st.warning(f"⚠️ A soma dos percentuais está em {soma_p:.1f}%. Ajuste para fechar em 100%.")

    df_aloc = df_ranking[df_ranking["Ticker"].isin(escolhidas)].copy()
    df_aloc["Ordem_Escolha"] = df_aloc["Ticker"].apply(lambda x: escolhidas.index(x))
    df_aloc = df_aloc.sort_values("Ordem_Escolha").drop(columns=["Ordem_Escolha"])

    df_aloc["Peso (%)"] = df_aloc["Ticker"].map(pesos_escolhidos)
    df_aloc["Valor Alocado (R$)"] = (capital_total * (df_aloc["Peso (%)"] / 100.0)).round(2)
    df_aloc["Qtd. Estimada"] = np.floor(df_aloc["Valor Alocado (R$)"] / df_aloc["Preço (R$)"]).astype(int)
    df_aloc["Custo Estimado (R$)"] = (df_aloc["Qtd. Estimada"] * df_aloc["Preço (R$)"]).round(2)

    st.subheader("💼 Plano de Aplicação Selecionado")
    st.dataframe(
        df_aloc[[
            "Rank", "Ticker", "Score", "Recomendação", "Preço (R$)",
            "Peso (%)", "Valor Alocado (R$)", "Qtd. Estimada", "Custo Estimado (R$)"
        ]],
        use_container_width=True,
        hide_index=True
    )

    custo_total_est = float(df_aloc["Custo Estimado (R$)"].sum())
    caixa_restante = round(capital_total - custo_total_est, 2)

    col1, col2, col3 = st.columns(3)
    col1.metric("Capital Total", f"R$ {capital_total:,.2f}")
    col2.metric("Custo Estimado (Lote Unitário)", f"R$ {custo_total_est:,.2f}")
    col3.metric("Sobra / Caixa Estimado", f"R$ {caixa_restante:,.2f}")
else:
    st.info("Selecione de 1 a 5 ações na caixa acima para calcular a alocação.")

st.divider()

# ==========================================
# 5. GRÁFICO DE EVOLUÇÃO (ESCOLHIDAS OU TODAS AS ANALISADAS)
# ==========================================
st.subheader("📈 Gráfico de Evolução Histórica")

col_g1, col_g2, col_g3 = st.columns([2, 2, 2])

with col_g1:
    escopo_grafico = st.radio(
        "Quais ações exibir no gráfico?",
        options=["Apenas as ações que escolhi (até 5)", "Todas as ações analisadas"],
        horizontal=False
    )

with col_g2:
    periodo_dias = st.selectbox(
        "Período de Evolução (dias)",
        options=[30, 60, 90, 180, 240, 300, 360],
        index=2,
        format_func=lambda x: f"{x} dias"
    )

with col_g3:
    tipo_escala = st.radio(
        "Tipo de visualização",
        options=["Rentabilidade Acumulada (%)", "Base 100 (R$ 100 investidos)", "Preço Ajustado (R$)"],
        horizontal=False
    )

if escopo_grafico == "Apenas as ações que escolhi (até 5)":
    tickers_grafico = [t for t in escolhidas if t in df_precos.columns]
else:
    tickers_grafico = [t for t in todos_tickers_ordenados if t in df_precos.columns]

if not tickers_grafico:
    st.info("Selecione ao menos uma ação para visualizar o gráfico de evolução.")
else:
    data_fim = df_precos.index.max()
    data_inicio = data_fim - pd.Timedelta(days=periodo_dias)
    df_recorte = df_precos.loc[df_precos.index >= data_inicio, tickers_grafico].dropna(how="all")

    if len(df_recorte) < 2:
        st.warning("Histórico insuficiente para o período selecionado.")
    else:
        primeiro_valido = df_recorte.apply(lambda col: col.dropna().iloc[0] if not col.dropna().empty else np.nan)

        if tipo_escala == "Rentabilidade Acumulada (%)":
            df_plot = ((df_recorte / primeiro_valido) - 1.0) * 100.0
        elif tipo_escala == "Base 100 (R$ 100 investidos)":
            df_plot = (df_recorte / primeiro_valido) * 100.0
        else:
            df_plot = df_recorte

        st.line_chart(df_plot, use_container_width=True)

        ultimo_valido = df_recorte.apply(lambda col: col.dropna().iloc[-1] if not col.dropna().empty else np.nan)
        var_periodo = ((ultimo_valido / primeiro_valido) - 1.0) * 100.0
        df_var_periodo = pd.DataFrame({
            "Ticker": var_periodo.index,
            f"Preço Início (~{periodo_dias}d)": primeiro_valido.round(2).values,
            "Preço Atual (R$)": ultimo_valido.round(2).values,
            f"Variação no Período ({periodo_dias}d) %": var_periodo.round(2).values
        }).sort_values(by=f"Variação no Período ({periodo_dias}d) %", ascending=False)

        with st.expander(f"📊 Tabela de Desempenho no Período de {periodo_dias} Dias"):
            st.dataframe(df_var_periodo, use_container_width=True, hide_index=True)

st.caption(
    "Aviso: Ferramenta quantitativa/educacional baseada em indicadores históricos de mercado (yfinance). "
    "Não constitui recomendação personalizada de investimento nem garantia de rentabilidade."
)

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Analisador Quantitativo & Fundamentalista B3", layout="wide")

st.title("🏆 Analisador Avançado de Ações — Seleção para Compra (Técnica + Fundamentos + Risco)")
st.markdown(
    "O aplicativo combina **análise fundamentalista** (valuation, rentabilidade, dividendos e endividamento), "
    "**análise técnica** (tendência MM21/MM50/MM200, MACD e IFR), **gestão de risco** (volatilidade, drawdown e Sharpe) "
    "e **liquidez** para apontar as melhores oportunidades de compra do dia e permitir escolher **até 5 ações**."
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
    "RAIL3.SA, VIVT3.SA, CPLE6.SA, EGIE3.SA, MULT3.SA"
)

tickers_input = st.sidebar.text_area(
    "Universo de Ações para Avaliar (separadas por vírgula)",
    value=universo_padrao,
    height=95
)

lista_tickers = list(dict.fromkeys([t.strip().upper() for t in tickers_input.split(",") if t.strip()]))

st.sidebar.subheader("⚖️ Pesos dos Pilares de Análise")
peso_fundamentos = st.sidebar.slider("Fundamentos (P/L, ROE, DY, Dívida)", 0, 50, 35)
peso_tendencia = st.sidebar.slider("Tendência & Timing (MM21/50/200, MACD, IFR)", 0, 50, 30)
peso_risco = st.sidebar.slider("Risco & Retorno (Volatilidade, Drawdown, Sharpe)", 0, 50, 20)
peso_liquidez = st.sidebar.slider("Liquidez (Volume Médio Diário)", 0, 50, 15)

if (peso_fundamentos + peso_tendencia + peso_risco + peso_liquidez) == 0:
    peso_fundamentos = 50
    peso_tendencia = 50

st.sidebar.subheader("🛡️ Filtros de Proteção para Compra")
evitar_sobrecompra = st.sidebar.checkbox("Bloquear compra se IFR (14d) > 72 (sobrecomprada)", value=True)
exigir_tendencia_alta = st.sidebar.checkbox("Priorizar Preço acima da MM21 ou MM50", value=True)

# ==========================================
# 2. FUNÇÕES DE CÁLCULO TÉCNICO E FUNDAMENTALISTA
# ==========================================
def calcular_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)

def calcular_macd(series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    sinal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - sinal
    return float(macd.iloc[-1]), float(sinal.iloc[-1]), float(hist.iloc[-1])

def obter_fundamentos_seguros(ticker_obj):
    try:
        info = ticker_obj.info or {}
    except Exception:
        info = {}

    pl = info.get("trailingPE") or info.get("forwardPE")
    pvp = info.get("priceToBook")
    roe = info.get("returnOnEquity")
    dy = info.get("dividendYield")
    margem_liq = info.get("profitMargins")
    div_pl = info.get("debtToEquity")
    setor = info.get("sector") or "N/D"

    # Normaliza percentuais que vêm em decimal no yfinance
    roe_pct = float(roe * 100) if isinstance(roe, (int, float)) and not np.isnan(roe) else np.nan
    dy_pct = float(dy * 100) if isinstance(dy, (int, float)) and not np.isnan(dy) else np.nan
    if not np.isnan(dy_pct) and dy_pct > 50:
        # Caso o yfinance já retorne em %
        dy_pct = dy_pct / 100.0
    margem_pct = float(margem_liq * 100) if isinstance(margem_liq, (int, float)) and not np.isnan(margem_liq) else np.nan
    pl_val = float(pl) if isinstance(pl, (int, float)) and not np.isnan(pl) and pl > 0 else np.nan
    pvp_val = float(pvp) if isinstance(pvp, (int, float)) and not np.isnan(pvp) and pvp > 0 else np.nan
    div_pl_val = float(div_pl) if isinstance(div_pl, (int, float)) and not np.isnan(div_pl) else np.nan

    return {
        "Setor": setor,
        "P/L": pl_val,
        "P/VP": pvp_val,
        "ROE (%)": roe_pct,
        "DY (%)": dy_pct,
        "Margem Líq. (%)": margem_pct,
        "Dív./PL (%)": div_pl_val
    }

def pontuar_fundamentos(fund):
    notas = []

    # 1. P/L (ideal entre 4 e 16)
    pl = fund["P/L"]
    if not np.isnan(pl):
        if 4.0 <= pl <= 12.0:
            notas.append(95.0)
        elif 12.0 < pl <= 18.0:
            notas.append(75.0)
        elif 18.0 < pl <= 28.0:
            notas.append(50.0)
        else:
            notas.append(25.0)

    # 2. P/VP (ideal <= 2.2)
    pvp = fund["P/VP"]
    if not np.isnan(pvp):
        if pvp <= 1.2:
            notas.append(95.0)
        elif pvp <= 2.2:
            notas.append(75.0)
        elif pvp <= 3.5:
            notas.append(50.0)
        else:
            notas.append(30.0)

    # 3. ROE (ideal >= 15%)
    roe = fund["ROE (%)"]
    if not np.isnan(roe):
        if roe >= 20.0:
            notas.append(95.0)
        elif roe >= 14.0:
            notas.append(80.0)
        elif roe >= 8.0:
            notas.append(55.0)
        else:
            notas.append(20.0)

    # 4. Dividend Yield (ideal >= 5%)
    dy = fund["DY (%)"]
    if not np.isnan(dy):
        if dy >= 7.0:
            notas.append(95.0)
        elif dy >= 4.5:
            notas.append(78.0)
        elif dy >= 2.0:
            notas.append(55.0)
        else:
            notas.append(35.0)

    # 5. Margem Líquida
    mg = fund["Margem Líq. (%)"]
    if not np.isnan(mg):
        if mg >= 15.0:
            notas.append(90.0)
        elif mg >= 8.0:
            notas.append(70.0)
        elif mg > 0:
            notas.append(50.0)
        else:
            notas.append(15.0)

    if not notas:
        return 55.0  # Neutro caso o Yahoo Finance não retorne fundamentos do ativo
    return float(np.mean(notas))

@st.cache_data(ttl=900)
def avaliar_universo_completo(tickers, w_fund, w_tend, w_risco, w_liq, block_overbought, req_uptrend):
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

    w_sum = float(w_fund + w_tend + w_risco + w_liq)
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

            if "Close" not in df_tk.columns or len(df_tk["Close"].dropna()) < 60:
                continue

            close = df_tk["Close"].dropna()
            preco_atual = float(close.iloc[-1])
            if preco_atual <= 0:
                continue

            series_fechamento[tk] = close

            # Médias Móveis e Tendência
            mm21 = float(close.tail(21).mean())
            mm50 = float(close.tail(50).mean())
            mm200 = float(close.tail(200).mean()) if len(close) >= 200 else float(close.mean())

            ret_20d = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) >= 21 else 0.0
            ret_5d = float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) >= 6 else 0.0
            rsi_14 = float(calcular_rsi(close, 14).iloc[-1])
            macd_val, macd_sig, macd_hist = calcular_macd(close)

            # Risco e Retorno Ajustado
            ret_diario = close.pct_change().dropna()
            vol_anual_pct = float(ret_diario.tail(60).std() * np.sqrt(252) * 100) if len(ret_diario) >= 21 else 40.0
            ret_anual_est = float(ret_diario.tail(126).mean() * 252 * 100) if len(ret_diario) >= 60 else 0.0
            sharpe_est = float((ret_anual_est - 10.5) / vol_anual_pct) if vol_anual_pct > 0 else 0.0

            pico_60d = float(close.tail(60).max())
            drawdown_pct = float((preco_atual / pico_60d - 1) * 100) if pico_60d > 0 else 0.0

            if "Volume" in df_tk.columns:
                vol_fin_med = float((df_tk["Close"] * df_tk["Volume"]).tail(20).mean())
            else:
                vol_fin_med = 0.0

            # Fundamentos
            fund = obter_fundamentos_seguros(yf.Ticker(tk))
            score_fund = pontuar_fundamentos(fund)

            # Score Técnico + Timing de Entrada (0 a 100)
            score_tend = 0.0
            if preco_atual > mm21:
                score_tend += 25.0
            if mm21 > mm50:
                score_tend += 20.0
            if preco_atual > mm200:
                score_tend += 15.0
            if macd_val > macd_sig and macd_hist > 0:
                score_tend += 15.0
            # Timing pelo IFR: zona ideal de compra entre 40 e 66
            if 40.0 <= rsi_14 <= 66.0:
                score_tend += 25.0
            elif 30.0 <= rsi_14 < 40.0 and preco_atual >= mm21 * 0.97:
                score_tend += 18.0
            elif rsi_14 > 72.0:
                score_tend -= 20.0
            score_tend = float(np.clip(score_tend, 0.0, 100.0))

            # Score Risco & Sharpe (0 a 100)
            penalidade_vol = max(0.0, (vol_anual_pct - 18.0) * 1.4)
            penalidade_dd = max(0.0, abs(min(0.0, drawdown_pct)) * 1.8)
            bonus_sharpe = float(np.clip(sharpe_est * 15.0, -15.0, 25.0))
            score_risco = float(np.clip(85.0 - penalidade_vol - penalidade_dd + bonus_sharpe, 0.0, 100.0))

            # Score Liquidez (0 a 100)
            if vol_fin_med > 0:
                score_liq = float(np.clip((np.log10(max(vol_fin_med, 1.0)) - 5.0) / (7.3 - 5.0) * 100.0, 0.0, 100.0))
            else:
                score_liq = 50.0

            score_final = (
                score_fund * w_fund
                + score_tend * w_tend
                + score_risco * w_risco
                + score_liq * w_liq
            ) / w_sum

            # Diagnóstico Objetivo de Compra
            motivos = []
            if score_fund >= 72:
                motivos.append("Fundamentos sólidos")
            if preco_atual > mm21 and mm21 > mm50:
                motivos.append("Tendência de alta alinhada")
            elif preco_atual > mm21:
                motivos.append("Acima da MM21")
            if macd_val > macd_sig:
                motivos.append("MACD comprador")
            if 40.0 <= rsi_14 <= 66.0:
                motivos.append("IFR em ponto saudável")
            elif rsi_14 > 72.0:
                motivos.append("Esticada (IFR > 72)")
            if preco_atual < mm21 and preco_atual < mm50:
                motivos.append("Abaixo das médias")

            apto_compra = True
            if block_overbought and rsi_14 > 72.0:
                apto_compra = False
            if req_uptrend and (preco_atual < mm21 and preco_atual < mm50):
                apto_compra = False

            if apto_compra and score_final >= 68:
                sinal_compra = "🟢 COMPRA FORTE"
            elif apto_compra and score_final >= 56:
                sinal_compra = "🟡 COMPRA MODERADA"
            elif rsi_14 > 72.0 and score_final >= 60:
                sinal_compra = "🟠 AGUARDAR CORREÇÃO (Esticada)"
            else:
                sinal_compra = "🔴 NÃO COMPRAR / CAUTELA"

            # Stop técnico sugerido (2x ATR aproximado via volatilidade diária) e Alvo referência
            vol_diaria = vol_anual_pct / 100.0 / np.sqrt(252)
            stop_sugerido = round(preco_atual * (1.0 - 2.5 * vol_diaria), 2)
            alvo_sugerido = round(preco_atual * (1.0 + 4.5 * vol_diaria), 2)

            registros.append({
                "Ticker": tk,
                "Score Geral": round(score_final, 1),
                "Indicação de Compra": sinal_compra,
                "Motivo Principal": " | ".join(motivos[:3]) if motivos else "Neutro",
                "Preço (R$)": round(preco_atual, 2),
                "Stop Ref. (R$)": stop_sugerido,
                "Alvo Ref. (R$)": alvo_sugerido,
                "Score Fund.": round(score_fund, 1),
                "Score Técn.": round(score_tend, 1),
                "P/L": round(fund["P/L"], 1) if not np.isnan(fund["P/L"]) else None,
                "ROE (%)": round(fund["ROE (%)"], 1) if not np.isnan(fund["ROE (%)"]) else None,
                "DY (%)": round(fund["DY (%)"], 1) if not np.isnan(fund["DY (%)"]) else None,
                "MM21 (R$)": round(mm21, 2),
                "MM50 (R$)": round(mm50, 2),
                "IFR (14d)": round(rsi_14, 1),
                "MACD": "Alta" if macd_val > macd_sig else "Baixa",
                "Vol. Anual (%)": round(vol_anual_pct, 1),
                "Drawdown 60d (%)": round(drawdown_pct, 1),
                "Vol. Médio (R$ Mi)": round(vol_fin_med / 1e6, 1),
                "Apto_Compra": apto_compra
            })
        except Exception:
            continue

    if not registros:
        return pd.DataFrame(), pd.DataFrame()

    df = pd.DataFrame(registros)
    # Ordena priorizando ativos aptos à compra e depois pelo maior Score Geral
    df = df.sort_values(by=["Apto_Compra", "Score Geral"], ascending=[False, False]).reset_index(drop=True)
    df.insert(0, "Rank", df.index + 1)
    df_precos = pd.DataFrame(series_fechamento).sort_index()
    return df, df_precos

# ==========================================
# 3. EXECUÇÃO DO RANKING DE COMPRA
# ==========================================
if not lista_tickers:
    st.warning("Insira ao menos um ticker na barra lateral para avaliar.")
    st.stop()

with st.spinner("Executando análise fundamentalista, técnica e de risco das ações..."):
    df_ranking, df_precos = avaliar_universo_completo(
        tuple(lista_tickers),
        peso_fundamentos,
        peso_tendencia,
        peso_risco,
        peso_liquidez,
        evitar_sobrecompra,
        exigir_tendencia_alta
    )

if df_ranking.empty:
    st.error("Não foi possível obter dados suficientes para os tickers informados.")
    st.stop()

df_exibicao = df_ranking.drop(columns=["Apto_Compra"])
todos_tickers_ordenados = df_exibicao["Ticker"].tolist()
top5_df = df_exibicao.head(5).copy()
top5_tickers = top5_df["Ticker"].tolist()

st.subheader("🥇 Top 5 Melhores Oportunidades de Compra Hoje")
st.dataframe(top5_df, use_container_width=True, hide_index=True)

with st.expander("📋 Ver Análise Completa de Todas as Ações Avaliadas"):
    st.dataframe(df_exibicao, use_container_width=True, hide_index=True)

st.divider()

# ==========================================
# 4. ESCOLHA DE ATÉ 5 AÇÕES DENTRE TODAS AS ANALISADAS
# ==========================================
st.subheader("🎯 Escolha Até 5 Ações para Investir (Dentre Todas as Analisadas)")

escolhidas = st.multiselect(
    "Selecione até 5 ações dentre todas as analisadas (por padrão vêm as Top 5 sugeridas para compra):",
    options=todos_tickers_ordenados,
    default=top5_tickers,
    max_selections=5
)

if escolhidas:
    modo_divisao = st.radio(
        "Distribuição do capital entre as ações escolhidas:",
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

    df_aloc = df_exibicao[df_exibicao["Ticker"].isin(escolhidas)].copy()
    df_aloc["Ordem_Escolha"] = df_aloc["Ticker"].apply(lambda x: escolhidas.index(x))
    df_aloc = df_aloc.sort_values("Ordem_Escolha").drop(columns=["Ordem_Escolha"])

    df_aloc["Peso (%)"] = df_aloc["Ticker"].map(pesos_escolhidos)
    df_aloc["Valor Alocado (R$)"] = (capital_total * (df_aloc["Peso (%)"] / 100.0)).round(2)
    df_aloc["Qtd. Estimada"] = np.floor(df_aloc["Valor Alocado (R$)"] / df_aloc["Preço (R$)"]).astype(int)
    df_aloc["Custo Estimado (R$)"] = (df_aloc["Qtd. Estimada"] * df_aloc["Preço (R$)"]).round(2)

    st.subheader("💼 Plano de Compra e Gestão de Risco Selecionado")
    st.dataframe(
        df_aloc[[
            "Rank", "Ticker", "Score Geral", "Indicação de Compra", "Motivo Principal",
            "Preço (R$)", "Stop Ref. (R$)", "Alvo Ref. (R$)",
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
    st.info("Selecione de 1 a 5 ações na caixa acima para montar o plano de compra.")

st.divider()

# ==========================================
# 5. GRÁFICO DE EVOLUÇÃO (30 A 360 DIAS)
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
    "Aviso: Ferramenta quantitativa e fundamentalista de apoio à decisão baseada em dados públicos (yfinance). "
    "Não constitui recomendação individual de investimento nem garantia de rentabilidade."
)

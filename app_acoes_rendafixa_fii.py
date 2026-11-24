import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Super Analisador de Carteira (Ações + FIIs + Renda Fixa)", layout="wide")

st.title("📊 Super Analisador Integrado — Ações, FIIs e Renda Fixa")
st.markdown(
    "Painel unificado para avaliar **Ações** (fundamentos + técnica + risco), **Fundos Imobiliários (FIIs)** "
    "e **Renda Fixa**, destacando as melhores oportunidades de cada classe, permitindo montar uma carteira "
    "combinada com sugestão de alocação por perfil (**Conservador**, **Moderado** ou **Agressivo**), "
    "ajuste livre de percentuais, **Lucro com Cotas**, **Lucro Bruto e Líquido com Dividendos**, "
    "**Lucro Líquido após Impostos** e **evolução histórica de 30 a 360 dias**."
)

# ==========================================
# 1. BARRA LATERAL UNIFICADA
# ==========================================
st.sidebar.header("⚙️ Parâmetros Gerais e Macro")

capital_total = st.sidebar.number_input(
    "Capital Total Disponível (R$)",
    min_value=100.0,
    value=10000.0,
    step=500.0
)

horizonte_meses = st.sidebar.slider(
    "Horizonte da Simulação (meses)",
    min_value=1,
    max_value=60,
    value=12,
    step=1
)

taxa_selic_cdi = st.sidebar.number_input(
    "SELIC / CDI de Referência (% a.a.)",
    min_value=1.0,
    max_value=30.0,
    value=13.25,
    step=0.25
)

ipca_projetado = st.sidebar.number_input(
    "IPCA Projetado (% a.a.)",
    min_value=0.5,
    max_value=20.0,
    value=4.5,
    step=0.25
)

with st.sidebar.expander("📈 Configurar Universo de AÇÕES", expanded=False):
    acoes_padrao = (
        "PETR4.SA, VALE3.SA, ITUB4.SA, BBDC4.SA, BBAS3.SA, "
        "WEGE3.SA, PRIO3.SA, RENT3.SA, EQTL3.SA, RADL3.SA, "
        "SBSP3.SA, ABEV3.SA, SUZB3.SA, CSAN3.SA, EMBR3.SA"
    )
    acoes_input = st.text_area("Tickers de Ações", value=acoes_padrao, height=80)
    peso_fund = st.slider("Peso Fundamentos (Ações)", 0, 50, 35)
    peso_tend = st.slider("Peso Técnica/Timing (Ações)", 0, 50, 30)
    peso_risco = st.slider("Peso Risco/Sharpe (Ações)", 0, 50, 20)
    peso_liq = st.slider("Peso Liquidez (Ações)", 0, 50, 15)
    ir_gc_acao = st.number_input("IR Ganho de Capital na Venda de Ações (%)", 0.0, 35.0, 15.0, 1.0)
    ir_div_acao = st.number_input("IR sobre Dividendos / Proventos de Ações (%)", 0.0, 35.0, 0.0, 0.5)
    evitar_sobrecompra = st.checkbox("Bloquear compra se IFR > 72", value=True)
    exigir_tendencia_alta = st.checkbox("Priorizar Preço > MM21 ou MM50", value=True)

with st.sidebar.expander("🏢 Configurar Universo de FIIs", expanded=False):
    fiis_padrao = (
        "KNCR11.SA, XPML11.SA, HGLG11.SA, XPLG11.SA, MXRF11.SA, "
        "BPML11.SA, VISC11.SA, RECR11.SA, HGBS11.SA, CPTS11.SA"
    )
    fiis_input = st.text_area("Tickers de FIIs", value=fiis_padrao, height=70)
    ir_gc_fii = st.number_input("IR Ganho de Capital na Venda de FII (%)", 0.0, 35.0, 20.0, 1.0)
    ir_div_fii = st.number_input("IR sobre Dividendos / Proventos de FII (%)", 0.0, 35.0, 0.0, 0.5)

with st.sidebar.expander("🏦 Configurar Opções de RENDA FIXA", expanded=False):
    rf_default = pd.DataFrame([
        {"Produto": "Tesouro Selic", "Tipo": "Pós-fixado (SELIC)", "Taxa_aa": round(taxa_selic_cdi, 2), "Isento_IR": False, "Prazo_Dias": 365, "Liquidez_Dias": 1, "Risco_Score": 98.0},
        {"Produto": "CDB Liquidez Diária 100% CDI", "Tipo": "Pós-fixado (CDI)", "Taxa_aa": round(taxa_selic_cdi, 2), "Isento_IR": False, "Prazo_Dias": 365, "Liquidez_Dias": 1, "Risco_Score": 82.0},
        {"Produto": "LCI / LCA Isenta", "Tipo": "Isento IR", "Taxa_aa": round(taxa_selic_cdi * 0.86, 2), "Isento_IR": True, "Prazo_Dias": 365, "Liquidez_Dias": 90, "Risco_Score": 80.0},
        {"Produto": "Tesouro IPCA+ (Juro Real)", "Tipo": "IPCA + Juros", "Taxa_aa": round(ipca_projetado + 6.5, 2), "Isento_IR": False, "Prazo_Dias": 730, "Liquidez_Dias": 2, "Risco_Score": 90.0},
        {"Produto": "CDB Médio Prazo (115% CDI)", "Tipo": "Pós-fixado (CDI)", "Taxa_aa": round(taxa_selic_cdi * 1.15, 2), "Isento_IR": False, "Prazo_Dias": 365, "Liquidez_Dias": 365, "Risco_Score": 76.0},
    ])
    df_rf_input = st.sidebar.data_editor(rf_default, num_rows="dynamic", use_container_width=True, key="rf_editor_unified")

lista_acoes = list(dict.fromkeys([t.strip().upper() for t in acoes_input.split(",") if t.strip()]))
lista_fiis = list(dict.fromkeys([t.strip().upper() for t in fiis_input.split(",") if t.strip()]))
if (peso_fund + peso_tend + peso_risco + peso_liq) == 0:
    peso_fund, peso_tend = 50, 50

# ==========================================
# 2. PERFIS DE ALOCAÇÃO POR CLASSE DE ATIVO
# ==========================================
PERFIS_ALOCACAO = {
    "Conservador": {"Renda Fixa": 65.0, "FII": 20.0, "Ação": 15.0},
    "Moderado": {"Renda Fixa": 40.0, "FII": 25.0, "Ação": 35.0},
    "Agressivo": {"Renda Fixa": 15.0, "FII": 25.0, "Ação": 60.0},
}

def calcular_pesos_sugeridos(itens, perfil_nome):
    base_classes = PERFIS_ALOCACAO.get(perfil_nome, PERFIS_ALOCACAO["Moderado"])
    itens_por_classe = {"Renda Fixa": [], "FII": [], "Ação": []}
    for classe, nome in itens:
        if classe in itens_por_classe:
            itens_por_classe[classe].append((classe, nome))

    peso_classes_ativas = sum(base_classes[c] for c, lst in itens_por_classe.items() if lst)
    if peso_classes_ativas <= 0:
        peso_classes_ativas = 100.0

    sugestao = {}
    for classe, lst in itens_por_classe.items():
        if not lst:
            continue
        pct_classe = (base_classes[classe] / peso_classes_ativas) * 100.0
        pct_unit = round(pct_classe / len(lst), 1)
        for i, item in enumerate(lst):
            if i < len(lst) - 1:
                sugestao[item] = pct_unit
            else:
                sugestao[item] = round(pct_classe - pct_unit * (len(lst) - 1), 1)

    if sugestao:
        diff = round(100.0 - sum(sugestao.values()), 1)
        ultimo_item = list(sugestao.keys())[-1]
        sugestao[ultimo_item] = round(sugestao[ultimo_item] + diff, 1)
    return sugestao

# ==========================================
# 3. FUNÇÕES AUXILIARES (TÉCNICA, FUNDAMENTOS E IR)
# ==========================================
def aliquota_ir_regressiva(dias):
    if dias <= 180:
        return 0.225
    elif dias <= 360:
        return 0.200
    elif dias <= 720:
        return 0.175
    return 0.150

def calcular_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50.0)

def calcular_macd(series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    sinal = macd.ewm(span=9, adjust=False).mean()
    return float(macd.iloc[-1]), float(sinal.iloc[-1]), float((macd - sinal).iloc[-1])

def obter_fundamentos_seguros(ticker_obj):
    try:
        info = ticker_obj.info or {}
    except Exception:
        info = {}
    pl = info.get("trailingPE") or info.get("forwardPE")
    pvp = info.get("priceToBook")
    roe = info.get("returnOnEquity")
    dy = info.get("dividendYield")
    mg = info.get("profitMargins")
    roe_pct = float(roe * 100) if isinstance(roe, (int, float)) and not np.isnan(roe) else np.nan
    dy_pct = float(dy * 100) if isinstance(dy, (int, float)) and not np.isnan(dy) else np.nan
    if not np.isnan(dy_pct) and dy_pct > 50:
        dy_pct = dy_pct / 100.0
    mg_pct = float(mg * 100) if isinstance(mg, (int, float)) and not np.isnan(mg) else np.nan
    return {
        "P/L": float(pl) if isinstance(pl, (int, float)) and not np.isnan(pl) and pl > 0 else np.nan,
        "P/VP": float(pvp) if isinstance(pvp, (int, float)) and not np.isnan(pvp) and pvp > 0 else np.nan,
        "ROE (%)": roe_pct,
        "DY (%)": dy_pct,
        "Margem (%)": mg_pct
    }

def pontuar_fundamentos(fund):
    notas = []
    pl, pvp, roe, dy, mg = fund["P/L"], fund["P/VP"], fund["ROE (%)"], fund["DY (%)"], fund["Margem (%)"]
    if not np.isnan(pl):
        notas.append(95.0 if 4 <= pl <= 12 else (75.0 if pl <= 18 else (50.0 if pl <= 28 else 25.0)))
    if not np.isnan(pvp):
        notas.append(95.0 if pvp <= 1.2 else (75.0 if pvp <= 2.2 else (50.0 if pvp <= 3.5 else 30.0)))
    if not np.isnan(roe):
        notas.append(95.0 if roe >= 20 else (80.0 if roe >= 14 else (55.0 if roe >= 8 else 20.0)))
    if not np.isnan(dy):
        notas.append(95.0 if dy >= 7 else (78.0 if dy >= 4.5 else (55.0 if dy >= 2 else 35.0)))
    if not np.isnan(mg):
        notas.append(90.0 if mg >= 15 else (70.0 if mg >= 8 else (50.0 if mg > 0 else 15.0)))
    return float(np.mean(notas)) if notas else 55.0

# ==========================================
# 4. MOTORES DE ANÁLISE (AÇÕES, FIIs E RENDA FIXA)
# ==========================================
@st.cache_data(ttl=900)
def avaliar_acoes(tickers, w_fund, w_tend, w_risco, w_liq, block_ob, req_up, cap_ref, meses_ref, aliq_gc_acao, aliq_div_acao):
    if not tickers:
        return pd.DataFrame(), pd.DataFrame()
    raw = yf.download(tickers, period="2y", interval="1d", group_by="ticker", auto_adjust=True, progress=False)
    if raw is None or raw.empty:
        return pd.DataFrame(), pd.DataFrame()
    w_sum = float(w_fund + w_tend + w_risco + w_liq)
    regs, precos = [], {}
    for tk in tickers:
        try:
            df_tk = raw[tk].dropna(how="all") if isinstance(raw.columns, pd.MultiIndex) else raw.dropna(how="all")
            if "Close" not in df_tk.columns or len(df_tk["Close"].dropna()) < 60:
                continue
            close = df_tk["Close"].dropna()
            preco = float(close.iloc[-1])
            if preco <= 0:
                continue
            precos[tk] = close
            mm21 = float(close.tail(21).mean())
            mm50 = float(close.tail(50).mean())
            mm200 = float(close.tail(200).mean()) if len(close) >= 200 else float(close.mean())
            rsi = float(calcular_rsi(close, 14).iloc[-1])
            macd_v, macd_s, macd_h = calcular_macd(close)
            ret_d = close.pct_change().dropna()
            vol_a = float(ret_d.tail(60).std() * np.sqrt(252) * 100) if len(ret_d) >= 21 else 40.0
            ret_a = float(np.clip(ret_d.tail(126).mean() * 252 * 100, -15.0, 30.0)) if len(ret_d) >= 60 else 8.0
            sharpe = float((ret_a - 10.5) / vol_a) if vol_a > 0 else 0.0
            dd_60 = float((preco / float(close.tail(60).max()) - 1) * 100)
            vol_fin = float((df_tk["Close"] * df_tk["Volume"]).tail(20).mean()) if "Volume" in df_tk.columns else 0.0

            tk_obj = yf.Ticker(tk)
            fund = obter_fundamentos_seguros(tk_obj)
            sc_fund = pontuar_fundamentos(fund)
            sc_tend = 0.0
            if preco > mm21: sc_tend += 25.0
            if mm21 > mm50: sc_tend += 20.0
            if preco > mm200: sc_tend += 15.0
            if macd_v > macd_s and macd_h > 0: sc_tend += 15.0
            if 40 <= rsi <= 66: sc_tend += 25.0
            elif 30 <= rsi < 40 and preco >= mm21 * 0.97: sc_tend += 18.0
            elif rsi > 72: sc_tend -= 20.0
            sc_tend = float(np.clip(sc_tend, 0.0, 100.0))

            sc_risco = float(np.clip(85.0 - max(0.0, (vol_a - 18.0) * 1.4) - abs(min(0.0, dd_60)) * 1.8 + np.clip(sharpe * 15.0, -15.0, 25.0), 0.0, 100.0))
            sc_liq = float(np.clip((np.log10(max(vol_fin, 1.0)) - 5.0) / 2.3 * 100.0, 0.0, 100.0)) if vol_fin > 0 else 50.0
            sc_final = (sc_fund * w_fund + sc_tend * w_tend + sc_risco * w_risco + sc_liq * w_liq) / w_sum

            apto = True
            if block_ob and rsi > 72: apto = False
            if req_up and (preco < mm21 and preco < mm50): apto = False
            sinal = "🟢 COMPRA FORTE" if (apto and sc_final >= 68) else ("🟡 COMPRA MODERADA" if (apto and sc_final >= 56) else ("🟠 AGUARDAR CORREÇÃO" if rsi > 72 else "🔴 CAUTELA"))

            vol_dia = vol_a / 100.0 / np.sqrt(252)
            stop_ref = round(preco * (1.0 - 2.5 * vol_dia), 2)
            alvo_ref = round(preco * (1.0 + 4.5 * vol_dia), 2)

            # Lucro com cotas (líquido de IR quando positivo)
            gc_bruto = cap_ref * ((1.0 + (ret_a / 100.0)) ** (meses_ref / 12.0) - 1.0)
            lucro_cotas_rs = gc_bruto - max(0.0, gc_bruto) * (aliq_gc_acao / 100.0)

            # Verifica se há dividendos reais nos últimos 12m ou DY fundamentalista positivo
            dy_12m_real = np.nan
            try:
                divs_a = tk_obj.dividends
                if divs_a is not None and not divs_a.empty:
                    soma_da = float(divs_a[divs_a.index >= (divs_a.index.max() - pd.Timedelta(days=365))].sum())
                    if soma_da > 0:
                        dy_12m_real = (soma_da / preco) * 100.0
            except Exception:
                pass

            dy_valido = dy_12m_real if not np.isnan(dy_12m_real) else fund["DY (%)"]
            tem_dividendos = bool(not np.isnan(dy_valido) and dy_valido > 0)

            if tem_dividendos:
                div_bruto_rs = cap_ref * ((1.0 + dy_valido / 100.0) ** (meses_ref / 12.0) - 1.0)
                div_liq_rs = div_bruto_rs - max(0.0, div_bruto_rs) * (aliq_div_acao / 100.0)
            else:
                div_bruto_rs = 0.0
                div_liq_rs = 0.0

            lucro_liq_rs = lucro_cotas_rs + div_liq_rs

            regs.append({
                "Ticker": tk,
                "Score": round(sc_final, 1),
                "Indicação": sinal,
                "Preço (R$)": round(preco, 2),
                "Stop Ref. (R$)": stop_ref,
                "Alvo Ref. (R$)": alvo_ref,
                f"Lucro Cotas {meses_ref}m (R$)": round(lucro_cotas_rs, 2),
                f"Lucro Bruto Div. {meses_ref}m (R$)": round(div_bruto_rs, 2) if tem_dividendos else None,
                f"Lucro Líq. Div. {meses_ref}m (R$)": round(div_liq_rs, 2) if tem_dividendos else None,
                f"Lucro Líq. {meses_ref}m (R$)": round(lucro_liq_rs, 2),
                "P/L": round(fund["P/L"], 1) if not np.isnan(fund["P/L"]) else None,
                "ROE (%)": round(fund["ROE (%)"], 1) if not np.isnan(fund["ROE (%)"]) else None,
                "DY (%)": round(dy_valido, 1) if tem_dividendos else None,
                "MM21 (R$)": round(mm21, 2),
                "IFR (14d)": round(rsi, 1),
                "Vol. Anual (%)": round(vol_a, 1),
                "Apto": apto
            })
        except Exception:
            continue
    if not regs:
        return pd.DataFrame(), pd.DataFrame()
    df = pd.DataFrame(regs).sort_values(by=["Apto", "Score"], ascending=[False, False]).reset_index(drop=True)
    df.insert(0, "Rank", df.index + 1)
    return df, pd.DataFrame(precos).sort_index()

@st.cache_data(ttl=900)
def avaliar_fiis(tickers, cap_ref, meses_ref, aliq_gc, aliq_div):
    if not tickers:
        return pd.DataFrame(), pd.DataFrame()
    raw = yf.download(tickers, period="2y", interval="1d", group_by="ticker", auto_adjust=True, progress=False)
    if raw is None or raw.empty:
        return pd.DataFrame(), pd.DataFrame()
    regs, precos = [], {}
    for tk in tickers:
        try:
            df_tk = raw[tk].dropna(how="all") if isinstance(raw.columns, pd.MultiIndex) else raw.dropna(how="all")
            if "Close" not in df_tk.columns or len(df_tk["Close"].dropna()) < 40:
                continue
            close = df_tk["Close"].dropna()
            preco = float(close.iloc[-1])
            if preco <= 0:
                continue
            precos[tk] = close
            mm21 = float(close.tail(21).mean())
            mm50 = float(close.tail(50).mean())
            ret_d = close.pct_change().dropna()
            vol_a = float(ret_d.tail(60).std() * np.sqrt(252) * 100) if len(ret_d) >= 20 else 25.0
            dd_180 = float((preco / float(close.tail(180).max()) - 1) * 100)

            dy_12m = np.nan
            tem_dividendos = False
            try:
                divs = yf.Ticker(tk).dividends
                if divs is not None and not divs.empty:
                    soma_d = float(divs[divs.index >= (divs.index.max() - pd.Timedelta(days=365))].sum())
                    if soma_d > 0:
                        dy_12m = (soma_d / preco) * 100.0
                        tem_dividendos = True
            except Exception:
                pass

            ret_a_hist = float(np.clip(ret_d.tail(126).mean() * 252, -0.10, 0.18)) if len(ret_d) >= 40 else 0.04
            gc_bruto = cap_ref * ((1.0 + ret_a_hist) ** (meses_ref / 12.0) - 1.0)
            lucro_cotas_fii = gc_bruto - max(0.0, gc_bruto) * (aliq_gc / 100.0)

            if tem_dividendos and not np.isnan(dy_12m) and dy_12m > 0:
                div_bruto_fii = cap_ref * ((1.0 + dy_12m / 100.0) ** (meses_ref / 12.0) - 1.0)
                div_liq_fii = div_bruto_fii - max(0.0, div_bruto_fii) * (aliq_div / 100.0)
            else:
                div_bruto_fii = 0.0
                div_liq_fii = 0.0

            lucro_liq_fii = lucro_cotas_fii + div_liq_fii

            sc_renda = float(np.clip(((dy_12m - 4.0) / 10.0) * 100.0, 0.0, 100.0)) if not np.isnan(dy_12m) else 60.0
            sc_estab = float(np.clip(100.0 - max(0.0, (vol_a - 12.0) * 2.5) - abs(min(0.0, dd_180)) * 1.2, 0.0, 100.0))
            sc_tend = float(np.clip((50.0 if preco >= mm21 * 0.98 else 0.0) + (30.0 if mm21 >= mm50 * 0.98 else 0.0) + (20.0 if -18.0 <= dd_180 <= -2.0 else 0.0), 0.0, 100.0))
            sc_final = 0.40 * sc_renda + 0.30 * sc_estab + 0.30 * sc_tend

            regs.append({
                "Ticker": tk,
                "Score": round(sc_final, 1),
                "Preço (R$)": round(preco, 2),
                "DY 12m Est. (%)": round(dy_12m, 2) if tem_dividendos else None,
                f"Lucro Cotas {meses_ref}m (R$)": round(lucro_cotas_fii, 2),
                f"Lucro Bruto Div. {meses_ref}m (R$)": round(div_bruto_fii, 2) if tem_dividendos else None,
                f"Lucro Líq. Div. {meses_ref}m (R$)": round(div_liq_fii, 2) if tem_dividendos else None,
                f"Lucro Líq. {meses_ref}m (R$)": round(lucro_liq_fii, 2),
                "Vol. Anual (%)": round(vol_a, 1),
                "Drawdown 180d (%)": round(dd_180, 1),
                "MM21 (R$)": round(mm21, 2)
            })
        except Exception:
            continue
    if not regs:
        return pd.DataFrame(), pd.DataFrame()
    df = pd.DataFrame(regs).sort_values(by="Score", ascending=False).reset_index(drop=True)
    df.insert(0, "Rank", df.index + 1)
    return df, pd.DataFrame(precos).sort_index()

def avaliar_renda_fixa(df_rf, selic_ref, ipca_ref, cap_ref, meses_ref):
    if df_rf is None or df_rf.empty:
        return pd.DataFrame()
    regs = []
    for _, row in df_rf.iterrows():
        try:
            prod = str(row.get("Produto", "RF")).strip()
            tipo = str(row.get("Tipo", "Renda Fixa")).strip()
            taxa_b = float(row.get("Taxa_aa", selic_ref))
            isento = bool(row.get("Isento_IR", False))
            prazo_d = max(1, int(float(row.get("Prazo_Dias", meses_ref * 30))))
            liq_d = float(row.get("Liquidez_Dias", 30))
            risco_sc = float(np.clip(float(row.get("Risco_Score", 80.0)), 0.0, 100.0))

            dias_ef = max(prazo_d, int(round(meses_ref * 30.4375)))
            aliq = 0.0 if isento else aliquota_ir_regressiva(dias_ef)
            lucro_bruto = cap_ref * ((1.0 + taxa_b / 100.0) ** (meses_ref / 12.0) - 1.0)
            lucro_liq = lucro_bruto - max(0.0, lucro_bruto) * aliq
            taxa_liq_ef = ((1.0 + lucro_liq / cap_ref) ** (12.0 / max(meses_ref, 1)) - 1.0) * 100.0 if cap_ref > 0 else 0.0
            ganho_real = ((1.0 + taxa_liq_ef / 100.0) / (1.0 + ipca_ref / 100.0) - 1.0) * 100.0

            sc_ret = float(np.clip(((taxa_liq_ef - (selic_ref * 0.65)) / 8.0) * 100.0, 0.0, 100.0))
            sc_liq = float(np.clip(100.0 - (np.log10(max(liq_d, 1.0)) / 3.0) * 80.0, 15.0, 100.0))
            sc_final = 0.55 * sc_ret + 0.25 * risco_sc + 0.20 * sc_liq

            regs.append({
                "Produto": prod,
                "Tipo": tipo,
                "Score": round(sc_final, 1),
                "Taxa Bruta (% a.a.)": round(taxa_b, 2),
                "IR Est. (%)": round(aliq * 100.0, 1),
                f"Lucro Líq. {meses_ref}m (R$)": round(lucro_liq, 2),
                "Taxa Líq. (% a.a.)": round(taxa_liq_ef, 2),
                "Ganho Real (% a.a.)": round(ganho_real, 2),
                "Liquidez (dias)": int(liq_d)
            })
        except Exception:
            continue
    if not regs:
        return pd.DataFrame()
    df = pd.DataFrame(regs).sort_values(by="Score", ascending=False).reset_index(drop=True)
    df.insert(0, "Rank", df.index + 1)
    return df

# ==========================================
# 5. EXECUÇÃO UNIFICADA
# ==========================================
with st.spinner("Analisando Ações, FIIs e Renda Fixa simultaneamente..."):
    df_acoes, precos_acoes = avaliar_acoes(
        tuple(lista_acoes), peso_fund, peso_tend, peso_risco, peso_liq,
        evitar_sobrecompra, exigir_tendencia_alta, capital_total, horizonte_meses,
        ir_gc_acao, ir_div_acao
    )
    df_fiis, precos_fiis = avaliar_fiis(
        tuple(lista_fiis), capital_total, horizonte_meses, ir_gc_fii, ir_div_fii
    )
    df_rf = avaliar_renda_fixa(df_rf_input, taxa_selic_cdi, ipca_projetado, capital_total, horizonte_meses)

col_lucro = f"Lucro Líq. {horizonte_meses}m (R$)"
col_lucro_cotas = f"Lucro Cotas {horizonte_meses}m (R$)"
col_div_bruto = f"Lucro Bruto Div. {horizonte_meses}m (R$)"
col_div_liq = f"Lucro Líq. Div. {horizonte_meses}m (R$)"

# ==========================================
# 6. ABAS ORGANIZADAS EM UM ÚNICO APP
# ==========================================
aba_resumo, aba_pers, aba_acoes, aba_fiis, aba_rf, aba_graficos = st.tabs([
    "🎯 Carteira Unificada",
    "🎚️ Percentuais Personalizados (por Perfil)",
    "📈 Ações (Top 5 & Completa)",
    "🏢 FIIs (Top 2 & Completa)",
    "🏦 Renda Fixa (Top 2 & Completa)",
    "📊 Evolução Histórica (30 a 360d)"
])

df_acoes_vis = df_acoes.drop(columns=["Apto"]) if not df_acoes.empty else pd.DataFrame()

with aba_resumo:
    st.subheader("🏆 Melhores Oportunidades Destacadas Hoje")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**📈 Top 5 Ações**")
        if not df_acoes_vis.empty:
            st.dataframe(
                df_acoes_vis[["Rank", "Ticker", "Score", "Preço (R$)", col_lucro_cotas, col_div_bruto, col_div_liq, col_lucro]].head(5),
                use_container_width=True,
                hide_index=True
            )
    with c2:
        st.markdown("**🏢 Top 2 FIIs**")
        if not df_fiis.empty:
            st.dataframe(
                df_fiis[["Rank", "Ticker", "Score", "Preço (R$)", col_lucro_cotas, col_div_bruto, col_div_liq, col_lucro]].head(2),
                use_container_width=True,
                hide_index=True
            )
    with c3:
        st.markdown("**🏦 Top 2 Renda Fixa**")
        if not df_rf.empty:
            st.dataframe(
                df_rf[["Rank", "Produto", "Score", "Taxa Líq. (% a.a.)", col_lucro]].head(2),
                use_container_width=True,
                hide_index=True
            )

    st.divider()
    st.subheader("💼 Seleção de Ativos para a Carteira")
    s1, s2, s3 = st.columns(3)
    with s1:
        sel_acoes = st.multiselect(
            "Ações (até 5):",
            options=df_acoes_vis["Ticker"].tolist() if not df_acoes_vis.empty else [],
            default=df_acoes_vis["Ticker"].head(3).tolist() if not df_acoes_vis.empty else [],
            max_selections=5
        )
    with s2:
        sel_fiis = st.multiselect(
            "FIIs (até 2):",
            options=df_fiis["Ticker"].tolist() if not df_fiis.empty else [],
            default=df_fiis["Ticker"].head(2).tolist() if not df_fiis.empty else [],
            max_selections=2
        )
    with s3:
        sel_rf = st.multiselect(
            "Renda Fixa (até 2):",
            options=df_rf["Produto"].tolist() if not df_rf.empty else [],
            default=df_rf["Produto"].head(2).tolist() if not df_rf.empty else [],
            max_selections=2
        )

    itens_carteira = [("Ação", a) for a in sel_acoes] + [("FII", f) for f in sel_fiis] + [("Renda Fixa", r) for r in sel_rf]

    if itens_carteira:
        modo_peso = st.radio("Distribuição do capital:", ["Divisão igualitária (% igual)", "Usar percentuais da aba Personalizados"], horizontal=True)
        pesos = {}
        if modo_peso == "Divisão igualitária (% igual)":
            p_eq = round(100.0 / len(itens_carteira), 2)
            for i, it in enumerate(itens_carteira):
                pesos[it] = p_eq if i < len(itens_carteira) - 1 else round(100.0 - p_eq * (len(itens_carteira) - 1), 2)
        else:
            perfil_padrao = st.session_state.get("perfil_selecionado", "Moderado")
            sug_padrao = calcular_pesos_sugeridos(itens_carteira, perfil_padrao)
            for it in itens_carteira:
                chave_p = f"pers_{it[0]}_{it[1]}_{perfil_padrao}"
                pesos[it] = float(st.session_state.get(chave_p, sug_padrao.get(it, 0.0)))

        linhas_unif = []
        for classe, nome in itens_carteira:
            p = pesos.get((classe, nome), 0.0)
            val_aloc = round(capital_total * (p / 100.0), 2)
            if classe == "Ação":
                r = df_acoes_vis[df_acoes_vis["Ticker"] == nome].iloc[0]
                pr = float(r["Preço (R$)"])
                qtd = int(val_aloc // pr) if pr > 0 else 0
                custo_ef = qtd * pr
                fator = custo_ef / max(capital_total, 1.0)
                cotas_ef = round(float(r[col_lucro_cotas]) * fator, 2)
                div_b_ef = round(float(r[col_div_bruto]) * fator, 2) if pd.notna(r[col_div_bruto]) else None
                div_l_ef = round(float(r[col_div_liq]) * fator, 2) if pd.notna(r[col_div_liq]) else None
                lucro_ef = round(float(r[col_lucro]) * fator, 2)
                linhas_unif.append({
                    "Classe": "Ação", "Ativo": nome, "Score": r["Score"], "Peso (%)": p,
                    "Alocado (R$)": val_aloc, "Detalhe / Qtd.": f"{qtd} ações | Stop R$ {r['Stop Ref. (R$)']}",
                    col_lucro_cotas: cotas_ef, col_div_bruto: div_b_ef, col_div_liq: div_l_ef, col_lucro: lucro_ef
                })
            elif classe == "FII":
                r = df_fiis[df_fiis["Ticker"] == nome].iloc[0]
                pr = float(r["Preço (R$)"])
                qtd = int(val_aloc // pr) if pr > 0 else 0
                custo_ef = qtd * pr
                fator = custo_ef / max(capital_total, 1.0)
                cotas_ef = round(float(r[col_lucro_cotas]) * fator, 2)
                div_b_ef = round(float(r[col_div_bruto]) * fator, 2) if pd.notna(r[col_div_bruto]) else None
                div_l_ef = round(float(r[col_div_liq]) * fator, 2) if pd.notna(r[col_div_liq]) else None
                lucro_ef = round(float(r[col_lucro]) * fator, 2)
                linhas_unif.append({
                    "Classe": "FII", "Ativo": nome, "Score": r["Score"], "Peso (%)": p,
                    "Alocado (R$)": val_aloc, "Detalhe / Qtd.": f"{qtd} cotas (~R$ {pr:.2f})",
                    col_lucro_cotas: cotas_ef, col_div_bruto: div_b_ef, col_div_liq: div_l_ef, col_lucro: lucro_ef
                })
            else:
                r = df_rf[df_rf["Produto"] == nome].iloc[0]
                lucro_ef = round(float(r[col_lucro]) * (val_aloc / max(capital_total, 1.0)), 2)
                linhas_unif.append({
                    "Classe": "Renda Fixa", "Ativo": nome, "Score": r["Score"], "Peso (%)": p,
                    "Alocado (R$)": val_aloc, "Detalhe / Qtd.": f"Taxa líq. {r['Taxa Líq. (% a.a.)']}% | IR {r['IR Est. (%)']}%",
                    col_lucro_cotas: None, col_div_bruto: None, col_div_liq: None, col_lucro: lucro_ef
                })

        df_unif = pd.DataFrame(linhas_unif)
        st.dataframe(df_unif, use_container_width=True, hide_index=True)
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Capital Total", f"R$ {capital_total:,.2f}")
        m2.metric(f"Lucro Cotas ({horizonte_meses}m)", f"R$ {df_unif[col_lucro_cotas].dropna().sum():,.2f}")
        m3.metric(f"Lucro Bruto Div. ({horizonte_meses}m)", f"R$ {df_unif[col_div_bruto].dropna().sum():,.2f}")
        m4.metric(f"Lucro Líq. Div. ({horizonte_meses}m)", f"R$ {df_unif[col_div_liq].dropna().sum():,.2f}")
        m5.metric(f"Lucro Líq. Total ({horizonte_meses}m)", f"R$ {df_unif[col_lucro].sum():,.2f}")

with aba_pers:
    st.subheader("🎚️ Percentuais Personalizados com Sugestão por Perfil")
    st.markdown(
        "Escolha o perfil de risco para receber uma sugestão automática de percentuais entre **Renda Fixa**, "
        "**Fundos Imobiliários (FIIs)** e **Ações** — e altere qualquer percentual livremente quando quiser."
    )

    perfil_escolhido = st.radio(
        "Selecione seu perfil de investidor (você pode mudar a qualquer momento):",
        options=["Conservador", "Moderado", "Agressivo"],
        index=1,
        horizontal=True,
        key="perfil_selecionado"
    )

    ref_perfil = PERFIS_ALOCACAO[perfil_escolhido]
    p_col1, p_col2, p_col3 = st.columns(3)
    p_col1.metric("Sugestão Renda Fixa", f"{ref_perfil['Renda Fixa']:.0f}%")
    p_col2.metric("Sugestão Fundos (FIIs)", f"{ref_perfil['FII']:.0f}%")
    p_col3.metric("Sugestão Ações", f"{ref_perfil['Ação']:.0f}%")

    if not itens_carteira:
        st.info("Selecione ao menos um ativo na aba Carteira Unificada para personalizar os percentuais.")
    else:
        sugestao_ativos = calcular_pesos_sugeridos(itens_carteira, perfil_escolhido)
        if st.button("↩️ Restaurar Sugestão Automática do Perfil", key=f"reset_{perfil_escolhido}"):
            for it, val_s in sugestao_ativos.items():
                st.session_state[f"pers_{it[0]}_{it[1]}_{perfil_escolhido}"] = float(val_s)
            st.rerun()

        cols_pers = st.columns(min(len(itens_carteira), 4))
        pesos_pers = {}
        soma_pers = 0.0
        for idx, (classe, nome) in enumerate(itens_carteira):
            chave_input = f"pers_{classe}_{nome}_{perfil_escolhido}"
            if chave_input not in st.session_state:
                st.session_state[chave_input] = float(sugestao_ativos.get((classe, nome), 0.0))
            with cols_pers[idx % 4]:
                v_pers = st.number_input(
                    f"% {nome} ({classe})",
                    min_value=0.0,
                    max_value=100.0,
                    step=1.0,
                    key=chave_input
                )
                pesos_pers[(classe, nome)] = float(v_pers)
                soma_pers += float(v_pers)

        if abs(soma_pers - 100.0) > 0.1:
            st.warning(f"⚠️ A soma dos percentuais personalizados está em {soma_pers:.1f}%. Ajuste para fechar em 100%.")
        else:
            st.success("✅ Percentuais somam 100,0%.")

        linhas_pers = []
        for classe, nome in itens_carteira:
            p_item = pesos_pers[(classe, nome)]
            val_aloc = round(capital_total * (p_item / 100.0), 2)
            if classe == "Ação":
                r = df_acoes_vis[df_acoes_vis["Ticker"] == nome].iloc[0]
                pr = float(r["Preço (R$)"])
                qtd = int(val_aloc // pr) if pr > 0 else 0
                custo_ef = qtd * pr
                fator = custo_ef / max(capital_total, 1.0)
                cotas_ef = round(float(r[col_lucro_cotas]) * fator, 2)
                div_b_ef = round(float(r[col_div_bruto]) * fator, 2) if pd.notna(r[col_div_bruto]) else None
                div_l_ef = round(float(r[col_div_liq]) * fator, 2) if pd.notna(r[col_div_liq]) else None
                lucro_ef = round(float(r[col_lucro]) * fator, 2)
                linhas_pers.append({
                    "Classe": "Ação", "Ativo": nome, "Sugestão Perfil (%)": sugestao_ativos.get((classe, nome), 0.0),
                    "Seu Percentual (%)": p_item, "Valor Alocado (R$)": val_aloc,
                    "Qtd. Est.": f"{qtd} ações",
                    col_lucro_cotas: cotas_ef, col_div_bruto: div_b_ef, col_div_liq: div_l_ef, col_lucro: lucro_ef
                })
            elif classe == "FII":
                r = df_fiis[df_fiis["Ticker"] == nome].iloc[0]
                pr = float(r["Preço (R$)"])
                qtd = int(val_aloc // pr) if pr > 0 else 0
                custo_ef = qtd * pr
                fator = custo_ef / max(capital_total, 1.0)
                cotas_ef = round(float(r[col_lucro_cotas]) * fator, 2)
                div_b_ef = round(float(r[col_div_bruto]) * fator, 2) if pd.notna(r[col_div_bruto]) else None
                div_l_ef = round(float(r[col_div_liq]) * fator, 2) if pd.notna(r[col_div_liq]) else None
                lucro_ef = round(float(r[col_lucro]) * fator, 2)
                linhas_pers.append({
                    "Classe": "FII", "Ativo": nome, "Sugestão Perfil (%)": sugestao_ativos.get((classe, nome), 0.0),
                    "Seu Percentual (%)": p_item, "Valor Alocado (R$)": val_aloc,
                    "Qtd. Est.": f"{qtd} cotas",
                    col_lucro_cotas: cotas_ef, col_div_bruto: div_b_ef, col_div_liq: div_l_ef, col_lucro: lucro_ef
                })
            else:
                r = df_rf[df_rf["Produto"] == nome].iloc[0]
                lucro_ef = round(float(r[col_lucro]) * (val_aloc / max(capital_total, 1.0)), 2)
                linhas_pers.append({
                    "Classe": "Renda Fixa", "Ativo": nome, "Sugestão Perfil (%)": sugestao_ativos.get((classe, nome), 0.0),
                    "Seu Percentual (%)": p_item, "Valor Alocado (R$)": val_aloc,
                    "Qtd. Est.": f"Taxa líq. {r['Taxa Líq. (% a.a.)']}%",
                    col_lucro_cotas: None, col_div_bruto: None, col_div_liq: None, col_lucro: lucro_ef
                })

        df_pers_tab = pd.DataFrame(linhas_pers)
        st.dataframe(df_pers_tab, use_container_width=True, hide_index=True)
        mp1, mp2, mp3, mp4 = st.columns(4)
        mp1.metric(f"Lucro Cotas ({horizonte_meses}m)", f"R$ {df_pers_tab[col_lucro_cotas].dropna().sum():,.2f}")
        mp2.metric(f"Lucro Bruto Div. ({horizonte_meses}m)", f"R$ {df_pers_tab[col_div_bruto].dropna().sum():,.2f}")
        mp3.metric(f"Lucro Líq. Div. ({horizonte_meses}m)", f"R$ {df_pers_tab[col_div_liq].dropna().sum():,.2f}")
        mp4.metric(f"Lucro Líq. Total ({horizonte_meses}m)", f"R$ {df_pers_tab[col_lucro].sum():,.2f}")

with aba_acoes:
    st.subheader("📈 Análise Completa das Ações")
    if not df_acoes_vis.empty:
        st.dataframe(df_acoes_vis, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma ação carregada.")

with aba_fiis:
    st.subheader("🏢 Análise Completa dos Fundos Imobiliários")
    if not df_fiis.empty:
        st.dataframe(df_fiis, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum FII carregado.")

with aba_rf:
    st.subheader("🏦 Análise Completa de Renda Fixa (com IR Regressivo)")
    if not df_rf.empty:
        st.dataframe(df_rf, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma opção de Renda Fixa configurada.")

with aba_graficos:
    st.subheader("📊 Evolução Histórica — Ações e FIIs")
    precos_todos = pd.concat([precos_acoes, precos_fiis], axis=1)
    precos_todos = precos_todos.loc[:, ~precos_todos.columns.duplicated()]
    if not precos_todos.empty:
        cg1, cg2, cg3 = st.columns(3)
        with cg1:
            escopo_g = st.radio("Ativos no gráfico:", ["Apenas selecionados na carteira", "Todos os analisados (Ações + FIIs)"])
        with cg2:
            dias_g = st.selectbox("Período (dias):", [30, 60, 90, 180, 240, 300, 360], index=2)
        with cg3:
            escala_g = st.radio("Visualização:", ["Rentabilidade (%)", "Base 100", "Preço (R$)"])

        escolhidos_var = [t for t in (sel_acoes + sel_fiis) if t in precos_todos.columns]
        tks_g = escolhidos_var if escopo_g == "Apenas selecionados na carteira" else precos_todos.columns.tolist()
        if tks_g:
            dt_ini = precos_todos.index.max() - pd.Timedelta(days=dias_g)
            rec = precos_todos.loc[precos_todos.index >= dt_ini, tks_g].dropna(how="all")
            if len(rec) >= 2:
                prim = rec.apply(lambda c: c.dropna().iloc[0] if not c.dropna().empty else np.nan)
                if escala_g == "Rentabilidade (%)":
                    df_p = ((rec / prim) - 1.0) * 100.0
                elif escala_g == "Base 100":
                    df_p = (rec / prim) * 100.0
                else:
                    df_p = rec
                st.line_chart(df_p, use_container_width=True)
        else:
            st.info("Selecione ao menos uma ação ou FII na aba Carteira Unificada.")

st.caption(
    "Aviso: Ferramenta quantitativa e educacional de apoio à decisão. Sugestões de perfil e cálculos fiscais são estimativas "
    "simplificadas e não constituem recomendação personalizada de investimento ou consultoria tributária."
)

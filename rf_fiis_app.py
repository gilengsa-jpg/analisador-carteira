import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Analisador Renda Fixa & FIIs", layout="wide")

st.title("🏛️ Analisador de Renda Fixa e Fundos Imobiliários (FIIs)")
st.markdown(
    "Avalia um universo de **FIIs** (via dados de mercado e proventos) e **opções de Renda Fixa** "
    "(cenário de referência/taxas editáveis ou títulos/ETFs de renda fixa), destacando **as 2 melhores opções de Renda Fixa** "
    "e **as 2 melhores opções de FIIs** para você escolher e alocar seu capital — pronto para rodar direto do GitHub no Streamlit."
)

# ==========================================
# 1. PARÂMETROS NA BARRA LATERAL
# ==========================================
st.sidebar.header("⚙️ Capital e Cenário Macro")

capital_total = st.sidebar.number_input(
    "Capital Total Disponível (R$)",
    min_value=100.0,
    value=10000.0,
    step=500.0
)

taxa_selic_cdi = st.sidebar.number_input(
    "Taxa SELIC / CDI de Referência (% a.a.)",
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

st.sidebar.subheader("📌 Universos de Avaliação")
fiis_padrao = (
    "KNCR11.SA, XPML11.SA, HGLG11.SA, XPLG11.SA, MXRF11.SA, "
    "BPML11.SA, VISC11.SA, RECR11.SA, HGBS11.SA, CPTS11.SA"
)
fiis_input = st.sidebar.text_area("FIIs (separados por vírgula)", value=fiis_padrao, height=75)
lista_fiis = list(dict.fromkeys([t.strip().upper() for t in fiis_input.split(",") if t.strip()]))

st.sidebar.markdown("**Opções de Renda Fixa (editáveis — taxa % a.a. ou indexador):**")
rf_default = pd.DataFrame([
    {"Produto": "Tesouro Selic", "Tipo": "Pós-fixado (SELIC)", "Taxa_aa": round(taxa_selic_cdi, 2), "Isento_IR": False, "Liquidez_Dias": 1, "Risco_Score": 98.0},
    {"Produto": "CDB Liquidez Diária 100% CDI", "Tipo": "Pós-fixado (CDI)", "Taxa_aa": round(taxa_selic_cdi, 2), "Isento_IR": False, "Liquidez_Dias": 1, "Risco_Score": 82.0},
    {"Produto": "LCI / LCA Prefixada ou Pós", "Tipo": "Isento IR", "Taxa_aa": round(taxa_selic_cdi * 0.86, 2), "Isento_IR": True, "Liquidez_Dias": 90, "Risco_Score": 80.0},
    {"Produto": "Tesouro IPCA+ (Juro Real)", "Tipo": "IPCA + Juros", "Taxa_aa": round(ipca_projetado + 6.5, 2), "Isento_IR": False, "Liquidez_Dias": 2, "Risco_Score": 90.0},
    {"Produto": "CDB Médio Prazo (115% CDI)", "Tipo": "Pós-fixado (CDI)", "Taxa_aa": round(taxa_selic_cdi * 1.15, 2), "Isento_IR": False, "Liquidez_Dias": 365, "Risco_Score": 76.0},
])
df_rf_input = st.sidebar.data_editor(rf_default, num_rows="dynamic", use_container_width=True, key="rf_editor")

# ==========================================
# 2. AVALIAÇÃO DE RENDA FIXA (TOP 2)
# ==========================================
def avaliar_renda_fixa(df_rf, selic_ref, ipca_ref):
    if df_rf is None or df_rf.empty:
        return pd.DataFrame()
    linhas = []
    for _, row in df_rf.iterrows():
        try:
            prod = str(row.get("Produto", "Ativo RF")).strip()
            tipo = str(row.get("Tipo", "Renda Fixa")).strip()
            taxa_bruta = float(row.get("Taxa_aa", selic_ref))
            isento = bool(row.get("Isento_IR", False))
            liq_dias = float(row.get("Liquidez_Dias", 30))
            risco_sc = float(np.clip(float(row.get("Risco_Score", 80.0)), 0.0, 100.0))

            # Estimativa simples de IR regressivo (~17,5% médio em horizonte intermediário) se não isento
            aliquota_ir = 0.0 if isento else 0.175
            taxa_liq = taxa_bruta * (1.0 - aliquota_ir)
            ganho_real = ((1.0 + taxa_liq / 100.0) / (1.0 + ipca_ref / 100.0) - 1.0) * 100.0

            # Score RF: retorno líquido/real (55%) + segurança (25%) + liquidez (20%)
            score_ret = float(np.clip(((taxa_liq - (selic_ref * 0.65)) / 8.0) * 100.0, 0.0, 100.0))
            score_liq = float(np.clip(100.0 - (np.log10(max(liq_dias, 1.0)) / 3.0) * 80.0, 15.0, 100.0))
            score_final = 0.55 * score_ret + 0.25 * risco_sc + 0.20 * score_liq

            linhas.append({
                "Produto": prod,
                "Tipo": tipo,
                "Score": round(score_final, 1),
                "Taxa Bruta (% a.a.)": round(taxa_bruta, 2),
                "Taxa Líq. Est. (% a.a.)": round(taxa_liq, 2),
                "Ganho Real Est. (% a.a.)": round(ganho_real, 2),
                "Isento IR": "Sim" if isento else "Não",
                "Liquidez (dias)": int(liq_dias),
                "Segurança": round(risco_sc, 0)
            })
        except Exception:
            continue
    if not linhas:
        return pd.DataFrame()
    df = pd.DataFrame(linhas).sort_values(by="Score", ascending=False).reset_index(drop=True)
    df.insert(0, "Rank", df.index + 1)
    return df

# ==========================================
# 3. AVALIAÇÃO DE FIIs (TOP 2)
# ==========================================
@st.cache_data(ttl=900)
def avaliar_fiis(tickers):
    if not tickers:
        return pd.DataFrame(), pd.DataFrame()
    dados_raw = yf.download(tickers, period="1y", interval="1d", group_by="ticker", auto_adjust=True, progress=False)
    if dados_raw is None or dados_raw.empty:
        return pd.DataFrame(), pd.DataFrame()

    registros = []
    series_precos = {}
    for tk in tickers:
        try:
            if isinstance(dados_raw.columns, pd.MultiIndex):
                if tk not in dados_raw.columns.get_level_values(0):
                    continue
                df_tk = dados_raw[tk].dropna(how="all")
            else:
                df_tk = dados_raw.dropna(how="all")

            if "Close" not in df_tk.columns or len(df_tk["Close"].dropna()) < 40:
                continue

            close = df_tk["Close"].dropna()
            preco_atual = float(close.iloc[-1])
            if preco_atual <= 0:
                continue

            series_precos[tk] = close
            mm21 = float(close.tail(21).mean())
            mm50 = float(close.tail(50).mean())
            ret_60d = float((close.iloc[-1] / close.iloc[-60] - 1) * 100) if len(close) >= 60 else 0.0
            ret_diario = close.pct_change().dropna()
            vol_anual = float(ret_diario.tail(60).std() * np.sqrt(252) * 100) if len(ret_diario) >= 20 else 25.0
            pico_180d = float(close.tail(180).max())
            dd_180d = float((preco_atual / pico_180d - 1) * 100) if pico_180d > 0 else 0.0

            # Proventos / Dividendos dos últimos 12 meses via yfinance
            dy_12m_pct = np.nan
            try:
                t_obj = yf.Ticker(tk)
                divs = t_obj.dividends
                if divs is not None and not divs.empty:
                    corte_1a = divs.index.max() - pd.Timedelta(days=365)
                    soma_divs_12m = float(divs[divs.index >= corte_1a].sum())
                    if soma_divs_12m > 0:
                        dy_12m_pct = (soma_divs_12m / preco_atual) * 100.0
            except Exception:
                pass

            # Pontuação FII: Renda/DY (40%) + Estabilidade/Volatilidade (30%) + Tendência/Preço (30%)
            if not np.isnan(dy_12m_pct):
                score_renda = float(np.clip(((dy_12m_pct - 4.0) / 10.0) * 100.0, 0.0, 100.0))
            else:
                score_renda = 60.0

            score_estab = float(np.clip(100.0 - max(0.0, (vol_anual - 12.0) * 2.5) - abs(min(0.0, dd_180d)) * 1.2, 0.0, 100.0))
            score_tend = 0.0
            if preco_atual >= mm21 * 0.98:
                score_tend += 50.0
            if mm21 >= mm50 * 0.98:
                score_tend += 30.0
            if -18.0 <= dd_180d <= -2.0:
                score_tend += 20.0
            score_tend = float(np.clip(score_tend, 0.0, 100.0))

            score_final = 0.40 * score_renda + 0.30 * score_estab + 0.30 * score_tend

            registros.append({
                "Ticker": tk,
                "Score": round(score_final, 1),
                "Preço (R$)": round(preco_atual, 2),
                "DY 12m Est. (%)": round(dy_12m_pct, 2) if not np.isnan(dy_12m_pct) else None,
                "Ret. 60d (%)": round(ret_60d, 2),
                "Vol. Anual (%)": round(vol_anual, 1),
                "Drawdown 180d (%)": round(dd_180d, 1),
                "MM21 (R$)": round(mm21, 2)
            })
        except Exception:
            continue

    if not registros:
        return pd.DataFrame(), pd.DataFrame()

    df = pd.DataFrame(registros).sort_values(by="Score", ascending=False).reset_index(drop=True)
    df.insert(0, "Rank", df.index + 1)
    df_precos = pd.DataFrame(series_precos).sort_index()
    return df, df_precos

# ==========================================
# 4. EXIBIÇÃO DO RANKING E SUGESTÃO (2 RF + 2 FIIs)
# ==========================================
df_rf_rank = avaliar_renda_fixa(df_rf_input, taxa_selic_cdi, ipca_projetado)
with st.spinner("Avaliando FIIs e calculando rankings de Renda Fixa e FIIs..."):
    df_fii_rank, df_fii_precos = avaliar_fiis(tuple(lista_fiis))

col_top1, col_top2 = st.columns(2)
with col_top1:
    st.subheader("🏦 Top 2 — Renda Fixa")
    if not df_rf_rank.empty:
        top2_rf = df_rf_rank.head(2)
        st.dataframe(top2_rf, use_container_width=True, hide_index=True)
        with st.expander("Ver todas as opções de Renda Fixa avaliadas"):
            st.dataframe(df_rf_rank, use_container_width=True, hide_index=True)
    else:
        top2_rf = pd.DataFrame()
        st.info("Adicione opções de Renda Fixa na barra lateral.")

with col_top2:
    st.subheader("🏢 Top 2 — Fundos Imobiliários (FIIs)")
    if not df_fii_rank.empty:
        top2_fii = df_fii_rank.head(2)
        st.dataframe(top2_fii, use_container_width=True, hide_index=True)
        with st.expander("Ver todos os FIIs avaliados"):
            st.dataframe(df_fii_rank, use_container_width=True, hide_index=True)
    else:
        top2_fii = pd.DataFrame()
        st.info("Não foi possível carregar dados de FIIs no momento.")

st.divider()

# ==========================================
# 5. ESCOLHA E ALOCAÇÃO (ATÉ 2 RF + ATÉ 2 FIIs)
# ==========================================
st.subheader("🎯 Escolha Suas Opções para Investir")
c_sel1, c_sel2 = st.columns(2)

opcoes_rf_all = df_rf_rank["Produto"].tolist() if not df_rf_rank.empty else []
default_rf = top2_rf["Produto"].tolist() if not top2_rf.empty else []

opcoes_fii_all = df_fii_rank["Ticker"].tolist() if not df_fii_rank.empty else []
default_fii = top2_fii["Ticker"].tolist() if not top2_fii.empty else []

with c_sel1:
    rf_escolhidas = st.multiselect(
        "Renda Fixa (até 2 opções):",
        options=opcoes_rf_all,
        default=default_rf,
        max_selections=2
    )

with c_sel2:
    fiis_escolhidos = st.multiselect(
        "Fundos Imobiliários (até 2 opções):",
        options=opcoes_fii_all,
        default=default_fii,
        max_selections=2
    )

selecao_combinada = [("Renda Fixa", item) for item in rf_escolhidas] + [("FII", item) for item in fiis_escolhidos]

if selecao_combinada:
    st.markdown("**Distribuição do Capital (%) entre os itens escolhidos:**")
    cols_p = st.columns(len(selecao_combinada))
    peso_padrao = round(100.0 / len(selecao_combinada), 1)
    pesos = {}
    soma_p = 0.0
    for idx, (classe, nome) in enumerate(selecao_combinada):
        with cols_p[idx]:
            p_val = st.number_input(
                f"% {nome} ({classe})",
                min_value=0.0,
                max_value=100.0,
                value=peso_padrao,
                step=5.0,
                key=f"peso_{classe}_{nome}"
            )
            pesos[(classe, nome)] = p_val
            soma_p += p_val

    if abs(soma_p - 100.0) > 0.1:
        st.warning(f"⚠️ A soma dos percentuais está em {soma_p:.1f}%. Ajuste para fechar em 100%.")

    linhas_plano = []
    for classe, nome in selecao_combinada:
        p = pesos[(classe, nome)]
        valor_aloc = round(capital_total * (p / 100.0), 2)
        if classe == "Renda Fixa":
            row_rf = df_rf_rank[df_rf_rank["Produto"] == nome].iloc[0]
            taxa_liq = float(row_rf["Taxa Líq. Est. (% a.a.)"])
            rend_12m = round(valor_aloc * (taxa_liq / 100.0), 2)
            linhas_plano.append({
                "Classe": "Renda Fixa",
                "Ativo / Produto": nome,
                "Score": row_rf["Score"],
                "Peso (%)": p,
                "Valor Alocado (R$)": valor_aloc,
                "Ref. / Qtd.": f"Taxa líq. ~{taxa_liq:.2f}% a.a.",
                "Renda/Retorno Est. 12m (R$)": rend_12m
            })
        else:
            row_fii = df_fii_rank[df_fii_rank["Ticker"] == nome].iloc[0]
            preco_fii = float(row_fii["Preço (R$)"])
            qtd_fii = int(valor_aloc // preco_fii) if preco_fii > 0 else 0
            dy_fii = float(row_fii["DY 12m Est. (%)"]) if pd.notna(row_fii["DY 12m Est. (%)"]) else 8.0
            renda_12m = round((qtd_fii * preco_fii) * (dy_fii / 100.0), 2)
            linhas_plano.append({
                "Classe": "FII",
                "Ativo / Produto": nome,
                "Score": row_fii["Score"],
                "Peso (%)": p,
                "Valor Alocado (R$)": valor_aloc,
                "Ref. / Qtd.": f"{qtd_fii} cotas (~R$ {preco_fii:.2f})",
                "Renda/Retorno Est. 12m (R$)": renda_12m
            })

    df_plano = pd.DataFrame(linhas_plano)
    st.subheader("💼 Plano de Alocação Combinado (Renda Fixa + FIIs)")
    st.dataframe(df_plano, use_container_width=True, hide_index=True)
    st.metric("Retorno / Renda Estimada em 12 Meses", f"R$ {df_plano['Renda/Retorno Est. 12m (R$)'].sum():,.2f}")

st.divider()

# ==========================================
# 6. EVOLUÇÃO HISTÓRICA DOS FIIs (30 A 360 DIAS)
# ==========================================
st.subheader("📈 Evolução Histórica das Cotas de FIIs")
if not df_fii_precos.empty:
    c_g1, c_g2 = st.columns(2)
    with c_g1:
        escopo_fii_graf = st.radio(
            "Quais FIIs exibir no gráfico?",
            options=["Apenas os FIIs escolhidos", "Todos os FIIs avaliados"]
        )
    with c_g2:
        periodo_fii = st.selectbox(
            "Período (dias)",
            options=[30, 60, 90, 180, 240, 300, 360],
            index=3
        )

    tks_graf = [t for t in (fiis_escolhidos if escopo_fii_graf == "Apenas os FIIs escolhidos" else opcoes_fii_all) if t in df_fii_precos.columns]
    if tks_graf:
        dt_ini = df_fii_precos.index.max() - pd.Timedelta(days=periodo_fii)
        rec = df_fii_precos.loc[df_fii_precos.index >= dt_ini, tks_graf].dropna(how="all")
        if len(rec) >= 2:
            prim = rec.apply(lambda c: c.dropna().iloc[0] if not c.dropna().empty else np.nan)
            plot_df = ((rec / prim) - 1.0) * 100.0
            st.line_chart(plot_df, use_container_width=True)

st.caption(
    "Aviso: Ferramenta educacional e quantitativa de apoio à análise. Taxas de renda fixa variam conforme emissor, 
    "prazo e isenção fiscal; não constitui recomendação personalizada de investimento nem garantia de rentabilidade."
)

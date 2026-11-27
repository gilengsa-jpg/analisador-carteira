import io
from pathlib import Path
from datetime import date
import urllib.request
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import openpyxl

st.set_page_config(page_title="Carteira Unificada & Retorno dos Investimentos", layout="wide")

# Caminhos de busca automática:
# 1) Na mesma pasta do rf_fiis_app.py no repositório do GitHub / Streamlit Cloud
# 2) Caminho local do Windows (caso rode localmente)
CAMINHO_REPO = Path(__file__).resolve().parent / "carteira_unificada_Investimentos.xlsx"
CAMINHO_WINDOWS = Path(r"C:\Users\Gil\OneDrive\1.00-Ideias\aplicação em ações\carteira_unificada_Investimentos.xlsx")

def normalizar_url_github(url: str) -> str:
    """Converte link comum do GitHub (/blob/...) em link direto de download (raw)."""
    url = url.strip()
    if "github.com" in url and "/blob/" in url:
        url = url.replace("https://github.com/", "https://raw.githubusercontent.com/").replace("/blob/", "/")
    return url

@st.cache_data(ttl=300)
def baixar_planilha_github(url_raw: str) -> bytes:
    req = urllib.request.Request(url_raw, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()

def obter_fonte_excel(arquivo_upload, url_github: str):
    """Retorna (fonte_bytes_ou_path, descricao_origem, caminho_gravacao_local_ou_None)."""
    if arquivo_upload is not None:
        return io.BytesIO(arquivo_upload.getvalue()), f"Upload manual: `{arquivo_upload.name}`", None

    if url_github.strip():
        url_norm = normalizar_url_github(url_github)
        dados_bytes = baixar_planilha_github(url_norm)
        return io.BytesIO(dados_bytes), f"GitHub (URL remota): `{url_norm}`", None

    if CAMINHO_REPO.exists():
        return CAMINHO_REPO, f"Repositório GitHub / Pasta do App: `{CAMINHO_REPO.name}`", CAMINHO_REPO

    if CAMINHO_WINDOWS.exists():
        return CAMINHO_WINDOWS, f"Pasta Local Windows: `{CAMINHO_WINDOWS}`", CAMINHO_WINDOWS

    return None, None, None

def carregar_dados_planilha(fonte_excel):
    if isinstance(fonte_excel, io.BytesIO):
        fonte_excel.seek(0)
    wb = openpyxl.load_workbook(fonte_excel, data_only=True)
    ws = wb["Carteira_Unificada"]

    opcao_escolhida = str(ws["B4"].value or "Divisão igualitária").strip()
    capital_planilha = float(ws["E4"].value or 100000.0)
    data_aplicacao_raw = ws["H4"].value

    if isinstance(fonte_excel, io.BytesIO):
        fonte_excel.seek(0)
    df_cart = pd.read_excel(fonte_excel, sheet_name="Carteira_Unificada", header=5)
    df_cart = df_cart[df_cart["Ativo"].notna()].copy()
    df_cart = df_cart[~df_cart["Classe"].astype(str).str.upper().eq("TOTAL")].copy()

    if isinstance(fonte_excel, io.BytesIO):
        fonte_excel.seek(0)
    df_pers = pd.read_excel(fonte_excel, sheet_name="Personalizados", header=2)
    df_pers = df_pers[df_pers["Ativo"].notna()].copy()
    df_pers = df_pers[~df_pers["Classe"].astype(str).str.upper().str.startswith("TOTAL")].copy()

    n_ativos = len(df_cart)
    if opcao_escolhida == "Divisão igualitária" and n_ativos > 0:
        df_cart["Peso_Efetivo (%)"] = round(100.0 / n_ativos, 2)
    elif opcao_escolhida in ("Conservador", "Moderado", "Agressivo"):
        col_perfil = f"{opcao_escolhida} (%)"
        mapa_pesos = dict(zip(
            df_pers["Ativo"].astype(str).str.strip(),
            pd.to_numeric(df_pers[col_perfil], errors="coerce").fillna(0.0)
        ))
        df_cart["Peso_Efetivo (%)"] = df_cart["Ativo"].astype(str).str.strip().map(mapa_pesos).fillna(0.0)
    else:
        df_cart["Peso_Efetivo (%)"] = pd.to_numeric(df_cart["Peso (%)"], errors="coerce").fillna(round(100.0 / max(n_ativos, 1), 2))

    df_cart["Alocado_Efetivo (R$)"] = (capital_planilha * (df_cart["Peso_Efetivo (%)"] / 100.0)).round(2)

    params_macro = {}
    if "Parametros_Macro" in wb.sheetnames:
        if isinstance(fonte_excel, io.BytesIO):
            fonte_excel.seek(0)
        df_pm = pd.read_excel(fonte_excel, sheet_name="Parametros_Macro", header=2)
        for _, r in df_pm.iterrows():
            if pd.notna(r.get("Parâmetro")) and pd.notna(r.get("Valor (Editável)")):
                params_macro[str(r["Parâmetro"]).strip()] = float(r["Valor (Editável)"])

    return {
        "opcao_escolhida": opcao_escolhida,
        "capital_planilha": capital_planilha,
        "data_aplicacao": str(data_aplicacao_raw)[:10] if data_aplicacao_raw else "2026-01-02",
        "df_carteira": df_cart,
        "df_personalizados": df_pers,
        "params_macro": params_macro,
    }

def gerar_excel_atualizado_bytes(fonte_original, nova_opcao: str, novo_capital: float, nova_data_str: str, df_editado: pd.DataFrame) -> bytes:
    """Atualiza a planilha preservando estilos/fórmulas e retorna os bytes para download (ideal para Streamlit Cloud/GitHub)."""
    if isinstance(fonte_original, io.BytesIO):
        fonte_original.seek(0)
    wb = openpyxl.load_workbook(fonte_original)
    ws = wb["Carteira_Unificada"]
    ws["B4"] = nova_opcao
    ws["E4"] = float(novo_capital)
    ws["H4"] = nova_data_str

    for i, (_, row) in enumerate(df_editado.iterrows(), start=7):
        if i > 13:
            break
        ws[f"C{i}"] = str(row.get("Data_Compra", nova_data_str))[:10]
        ws[f"D{i}"] = float(row.get("Preco_Compra_RS", 0.0))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()

@st.cache_data(ttl=600)
def buscar_cotacao_e_proventos_periodo(ticker: str, data_inicio_str: str):
    """Consulta cotação histórica na data de compra (pregão mais próximo), cotação atual e proventos até a data corrente."""
    try:
        dt_ini = pd.to_datetime(data_inicio_str)
        dt_busca_ini = (dt_ini - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
        hist = yf.download(ticker, start=dt_busca_ini, progress=False, auto_adjust=False)
        if hist is None or hist.empty:
            return None, None, 0.0, None

        if isinstance(hist.columns, pd.MultiIndex):
            close_s = hist["Close"][ticker].dropna()
        else:
            close_s = hist["Close"].dropna()

        if close_s.empty:
            return None, None, 0.0, None

        idx_naive = close_s.index.tz_localize(None) if close_s.index.tz is not None else close_s.index
        close_s.index = idx_naive

        pos_ou_igual = close_s[close_s.index >= dt_ini]
        if not pos_ou_igual.empty:
            preco_data_compra = float(pos_ou_igual.iloc[0])
            data_pregao_compra = pos_ou_igual.index[0].strftime("%Y-%m-%d")
        else:
            preco_data_compra = float(close_s.iloc[0])
            data_pregao_compra = close_s.index[0].strftime("%Y-%m-%d")

        preco_atual = float(close_s.iloc[-1])

        proventos_por_cota = 0.0
        try:
            tk_obj = yf.Ticker(ticker)
            divs = tk_obj.dividends
            if divs is not None and not divs.empty:
                divs_idx = divs.index.tz_localize(None) if divs.index.tz is not None else divs.index
                divs.index = divs_idx
                proventos_por_cota = float(divs[divs.index >= dt_ini].sum())
        except Exception:
            proventos_por_cota = 0.0

        return preco_data_compra, preco_atual, proventos_por_cota, data_pregao_compra
    except Exception:
        return None, None, 0.0, None

# ==========================================
# CABEÇALHO E CONEXÃO COM GITHUB / PLANILHA
# ==========================================
st.title("🏛️ Painel Unificado de Investimentos — Ações, FIIs e Renda Fixa")
st.markdown(
    "Lê a base **`carteira_unificada_Investimentos.xlsx`** diretamente do repositório **GitHub** (ou upload), "
    "calcula quanto você teria na **data corrente** na aba **Retorno dos Investimentos** e mantém as abas "
    "de **Carteira Unificada**, **Percentuais Personalizados**, **Análise de FIIs & Renda Fixa** e **Evolução Histórica**."
)

st.sidebar.header("🐙 Fonte GitHub / Planilha Base")
url_github_input = st.sidebar.text_input(
    "URL do arquivo no GitHub (opcional se estiver no mesmo repo):",
    value="",
    placeholder="https://github.com/usuario/repo/blob/main/carteira_unificada_Investimentos.xlsx"
)
arquivo_upload = st.sidebar.file_uploader(
    "Ou envie uma versão local (.xlsx):",
    type=["xlsx"]
)

try:
    fonte_excel, origem_str, caminho_gravacao = obter_fonte_excel(arquivo_upload, url_github_input)
except Exception as e:
    st.error(f"Erro ao acessar a planilha no GitHub: {e}")
    st.stop()

if fonte_excel is None:
    st.warning(
        "⚠️ Arquivo `carteira_unificada_Investimentos.xlsx` não encontrado no repositório do GitHub. "
        "Suba o arquivo `.xlsx` na mesma pasta do `rf_fiis_app.py` no GitHub, informe a URL na barra lateral ou faça upload."
    )
    st.stop()

st.sidebar.success(f"Conectado: {origem_str}")
dados_planilha = carregar_dados_planilha(fonte_excel)

# ==========================================
# PARÂMETROS MACRO NA BARRA LATERAL
# ==========================================
st.sidebar.header("⚙️ Capital, Prazo e Cenário Macro")
capital_total = st.sidebar.number_input(
    "Capital Total Disponível (R$)",
    min_value=100.0,
    value=float(dados_planilha["capital_planilha"]),
    step=500.0
)

horizonte_meses = st.sidebar.slider(
    "Horizonte da Simulação Futura (meses)",
    min_value=1,
    max_value=60,
    value=int(dados_planilha["params_macro"].get("Horizonte da Simulação (meses)", 12)),
    step=1
)

taxa_selic_cdi = st.sidebar.number_input(
    "Taxa SELIC / CDI de Referência (% a.a.)",
    min_value=1.0,
    max_value=30.0,
    value=float(dados_planilha["params_macro"].get("Taxa SELIC / CDI de Referência (% a.a.)", 13.25)),
    step=0.25
)

ipca_projetado = st.sidebar.number_input(
    "IPCA Projetado (% a.a.)",
    min_value=0.5,
    max_value=20.0,
    value=float(dados_planilha["params_macro"].get("IPCA Projetado (% a.a.)", 4.50)),
    step=0.25
)

ir_ganho_capital_fii = st.sidebar.number_input(
    "IR sobre Ganho de Capital na Venda de FII (%)",
    min_value=0.0,
    max_value=35.0,
    value=float(dados_planilha["params_macro"].get("IR Ganho de Capital FII (%)", 20.0)),
    step=1.0
)

# ==========================================
# FUNÇÕES DE AVALIAÇÃO RF E FIIs (MANTIDAS)
# ==========================================
def aliquota_ir_regressiva(dias):
    if dias <= 180:
        return 0.225
    elif dias <= 360:
        return 0.200
    elif dias <= 720:
        return 0.175
    else:
        return 0.150

def avaliar_renda_fixa(df_rf, selic_ref, ipca_ref, cap_ref, meses_ref):
    if df_rf is None or df_rf.empty:
        return pd.DataFrame()
    linhas = []
    for _, row in df_rf.iterrows():
        try:
            prod = str(row.get("Produto", "Ativo RF")).strip()
            tipo = str(row.get("Tipo", "Renda Fixa")).strip()
            taxa_bruta = float(row.get("Taxa_aa", selic_ref))
            isento = bool(row.get("Isento_IR", False))
            prazo_dias = max(1, int(float(row.get("Prazo_Dias", meses_ref * 30))))
            liq_dias = float(row.get("Liquidez_Dias", 30))
            risco_sc = float(np.clip(float(row.get("Risco_Score", 80.0)), 0.0, 100.0))

            dias_efetivos = max(prazo_dias, int(round(meses_ref * 30.4375)))
            aliq_ir = 0.0 if isento else aliquota_ir_regressiva(dias_efetivos)

            fator_bruto = (1.0 + taxa_bruta / 100.0) ** (meses_ref / 12.0)
            lucro_bruto = cap_ref * (fator_bruto - 1.0)
            imposto_rf = max(0.0, lucro_bruto) * aliq_ir
            lucro_liq_rs = lucro_bruto - imposto_rf
            taxa_liq_efetiva = ((1.0 + lucro_liq_rs / cap_ref) ** (12.0 / max(meses_ref, 1)) - 1.0) * 100.0 if cap_ref > 0 else 0.0
            ganho_real = ((1.0 + taxa_liq_efetiva / 100.0) / (1.0 + ipca_ref / 100.0) - 1.0) * 100.0

            score_ret = float(np.clip(((taxa_liq_efetiva - (selic_ref * 0.65)) / 8.0) * 100.0, 0.0, 100.0))
            score_liq = float(np.clip(100.0 - (np.log10(max(liq_dias, 1.0)) / 3.0) * 80.0, 15.0, 100.0))
            score_final = 0.55 * score_ret + 0.25 * risco_sc + 0.20 * score_liq

            linhas.append({
                "Produto": prod,
                "Tipo": tipo,
                "Score": round(score_final, 1),
                "Taxa Bruta (% a.a.)": round(taxa_bruta, 2),
                "IR Est. (%)": round(aliq_ir * 100.0, 1),
                f"Lucro Líquido {meses_ref}m (R$)": round(lucro_liq_rs, 2),
                "Taxa Líq. Est. (% a.a.)": round(taxa_liq_efetiva, 2),
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

@st.cache_data(ttl=900)
def avaliar_fiis(tickers, cap_ref, meses_ref, aliq_gc_fii):
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

            dy_efetivo = dy_12m_pct if not np.isnan(dy_12m_pct) else 8.0
            rend_isentos_rs = cap_ref * ((1.0 + dy_efetivo / 100.0) ** (meses_ref / 12.0) - 1.0)
            ret_anual_hist = float(np.clip(ret_diario.tail(126).mean() * 252, -0.10, 0.18)) if len(ret_diario) >= 40 else 0.04
            ganho_cota_bruto = cap_ref * ((1.0 + ret_anual_hist) ** (meses_ref / 12.0) - 1.0)
            ir_cota_rs = max(0.0, ganho_cota_bruto) * (aliq_gc_fii / 100.0)
            lucro_liq_fii_rs = rend_isentos_rs + (ganho_cota_bruto - ir_cota_rs)

            score_renda = float(np.clip(((dy_12m_pct - 4.0) / 10.0) * 100.0, 0.0, 100.0)) if not np.isnan(dy_12m_pct) else 60.0
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
                f"Lucro Líquido {meses_ref}m (R$)": round(lucro_liq_fii_rs, 2),
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
# ABAS DO PAINEL
# ==========================================
aba_retorno, aba_carteira, aba_pers, aba_fiis_rf, aba_evolucao = st.tabs([
    "💰 Retorno dos Investimentos",
    "🎯 Carteira Unificada",
    "⚖️ Percentuais Personalizados",
    "🏢 FIIs & Renda Fixa (Análise)",
    "📈 Evolução Histórica (30 a 360d)"
])

# ------------------------------------------
# ABA 1: RETORNO DOS INVESTIMENTOS
# ------------------------------------------
with aba_retorno:
    st.subheader(f"💰 Retorno Real dos Investimentos até a Data Corrente ({date.today().strftime('%d/%m/%Y')})")
    st.caption(
        "Compara a data e o preço de compra registrados na planilha `carteira_unificada_Investimentos.xlsx` "
        "com as cotações atuais de mercado (`yfinance`) e proventos pagos no período."
    )

    df_base = dados_planilha["df_carteira"].copy()
    opcoes_estrategia = ["Conservador", "Moderado", "Agressivo", "Divisão igualitária"]
    idx_padrao = opcoes_estrategia.index(dados_planilha["opcao_escolhida"]) if dados_planilha["opcao_escolhida"] in opcoes_estrategia else 3

    c_cfg1, c_cfg2, c_cfg3 = st.columns(3)
    with c_cfg1:
        estrategia_ativa = st.selectbox("Estratégia de Distribuição:", options=opcoes_estrategia, index=idx_padrao)
    with c_cfg2:
        data_aplic_input = st.text_input("Data Base da Aplicação (AAAA-MM-DD):", value=dados_planilha["data_aplicacao"])
    with c_cfg3:
        st.metric("Data Corrente (Execução)", date.today().strftime("%d/%m/%Y"))

    df_pers_ref = dados_planilha["df_personalizados"]
    n_at = len(df_base)
    if estrategia_ativa == "Divisão igualitária" and n_at > 0:
        df_base["Peso_Calculado (%)"] = round(100.0 / n_at, 2)
    else:
        col_p = f"{estrategia_ativa} (%)"
        mapa_p = dict(zip(df_pers_ref["Ativo"].astype(str).str.strip(), pd.to_numeric(df_pers_ref[col_p], errors="coerce").fillna(0.0)))
        df_base["Peso_Calculado (%)"] = df_base["Ativo"].astype(str).str.strip().map(mapa_p).fillna(0.0)

    df_base["Valor_Investido (R$)"] = (capital_total * (df_base["Peso_Calculado (%)"] / 100.0)).round(2)

    linhas_retorno = []
    with st.spinner("Consultando cotações na data de compra e valores atuais..."):
        for _, row in df_base.iterrows():
            classe = str(row["Classe"]).strip()
            ativo = str(row["Ativo"]).strip()
            dt_compra_row = str(row.get("Data_Compra", data_aplic_input))[:10]
            preco_planilha = float(row.get("Preco_Compra_RS", 0.0) or 0.0)
            valor_investido = float(row["Valor_Investido (R$)"])
            peso_pct = float(row["Peso_Calculado (%)"])

            dt_ini_dt = pd.to_datetime(dt_compra_row, errors="coerce")
            if pd.isna(dt_ini_dt):
                dt_ini_dt = pd.to_datetime(data_aplic_input, errors="coerce")
            dias_corridos = max(1, (pd.Timestamp(date.today()) - dt_ini_dt).days)

            if classe in ("Ação", "FII"):
                p_hist, p_atual, prov_cota, dt_pregao = buscar_cotacao_e_proventos_periodo(ativo, dt_ini_dt.strftime("%Y-%m-%d"))
                preco_compra_efetivo = p_hist if (p_hist is not None and p_hist > 0) else preco_planilha
                preco_atual_efetivo = p_atual if (p_atual is not None and p_atual > 0) else preco_compra_efetivo

                qtd = int(valor_investido // preco_compra_efetivo) if preco_compra_efetivo > 0 else 0
                capital_efetivo_aplicado = round(qtd * preco_compra_efetivo, 2)
                troco_caixa = round(valor_investido - capital_efetivo_aplicado, 2)

                valor_posicao_hoje = round(qtd * preco_atual_efetivo, 2)
                proventos_recebidos = round(qtd * prov_cota, 2)
                valor_total_hoje = round(valor_posicao_hoje + proventos_recebidos + troco_caixa, 2)
                lucro_rs = round(valor_total_hoje - valor_investido, 2)
                rentab_pct = round(((valor_total_hoje / valor_investido) - 1.0) * 100.0, 2) if valor_investido > 0 else 0.0

                linhas_retorno.append({
                    "Classe": classe,
                    "Ativo": ativo,
                    "Data Compra": dt_pregao or dt_ini_dt.strftime("%Y-%m-%d"),
                    "Dias": dias_corridos,
                    "Peso (%)": peso_pct,
                    "Investido (R$)": valor_investido,
                    "Qtd.": qtd,
                    "Preço Compra (R$)": round(preco_compra_efetivo, 2),
                    "Preço Hoje (R$)": round(preco_atual_efetivo, 2),
                    "Proventos (R$)": proventos_recebidos,
                    "Valor Hoje (R$)": valor_total_hoje,
                    "Lucro / Prejuízo (R$)": lucro_rs,
                    "Retorno (%)": rentab_pct,
                })
            else:
                fator_dia = (1.0 + taxa_selic_cdi / 100.0) ** (dias_corridos / 365.0)
                bruto_rf = valor_investido * (fator_dia - 1.0)
                aliq_rf = aliquota_ir_regressiva(dias_corridos)
                liq_rf = bruto_rf * (1.0 - aliq_rf)
                valor_total_hoje = round(valor_investido + liq_rf, 2)
                lucro_rs = round(liq_rf, 2)
                rentab_pct = round(((valor_total_hoje / valor_investido) - 1.0) * 100.0, 2) if valor_investido > 0 else 0.0

                linhas_retorno.append({
                    "Classe": classe,
                    "Ativo": ativo,
                    "Data Compra": dt_ini_dt.strftime("%Y-%m-%d"),
                    "Dias": dias_corridos,
                    "Peso (%)": peso_pct,
                    "Investido (R$)": valor_investido,
                    "Qtd.": 1,
                    "Preço Compra (R$)": valor_investido,
                    "Preço Hoje (R$)": valor_total_hoje,
                    "Proventos (R$)": 0.0,
                    "Valor Hoje (R$)": valor_total_hoje,
                    "Lucro / Prejuízo (R$)": lucro_rs,
                    "Retorno (%)": rentab_pct,
                })

    df_retorno = pd.DataFrame(linhas_retorno)

    total_investido = float(df_retorno["Investido (R$)"].sum())
    total_hoje = float(df_retorno["Valor Hoje (R$)"].sum())
    total_lucro = float(df_retorno["Lucro / Prejuízo (R$)"].sum())
    total_proventos = float(df_retorno["Proventos (R$)"].sum())
    retorno_geral_pct = ((total_hoje / total_investido) - 1.0) * 100.0 if total_investido > 0 else 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Capital Total Aplicado", f"R$ {total_investido:,.2f}")
    m2.metric("Patrimônio Atual (Hoje)", f"R$ {total_hoje:,.2f}", delta=f"{retorno_geral_pct:+.2f}%")
    m3.metric("Lucro / Prejuízo Acumulado", f"R$ {total_lucro:,.2f}")
    m4.metric("Proventos Acumulados", f"R$ {total_proventos:,.2f}")

    st.dataframe(df_retorno, use_container_width=True, hide_index=True)
    st.bar_chart(df_retorno.set_index("Ativo")[["Investido (R$)", "Valor Hoje (R$)"]], use_container_width=True)

# ------------------------------------------
# ABA 2: CARTEIRA UNIFICADA
# ------------------------------------------
with aba_carteira:
    st.subheader("🎯 Carteira Unificada Salva na Planilha")
    st.caption(
        "Altere datas ou preços de compra abaixo e baixe a planilha atualizada para substituir no seu repositório GitHub."
    )

    df_editavel = st.data_editor(
        dados_planilha["df_carteira"][["Classe", "Ativo", "Data_Compra", "Preco_Compra_RS", "Score", "Peso_Efetivo (%)", "Alocado_Efetivo (R$)", "Detalhe / Qtd."]],
        use_container_width=True,
        hide_index=True,
        key="editor_carteira_salva"
    )

    excel_atualizado_bytes = gerar_excel_atualizado_bytes(
        fonte_excel, estrategia_ativa, capital_total, data_aplic_input, df_editavel
    )

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        st.download_button(
            label="📥 Baixar Planilha Atualizada (carteira_unificada_Investimentos.xlsx)",
            data=excel_atualizado_bytes,
            file_name="carteira_unificada_Investimentos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    with col_b2:
        if caminho_gravacao is not None and st.button("💾 Salvar Direto no Disco Local"):
            with open(caminho_gravacao, "wb") as f_out:
                f_out.write(excel_atualizado_bytes)
            st.success(f"Salvo diretamente em `{caminho_gravacao}`!")

# ------------------------------------------
# ABA 3: PERCENTUAIS PERSONALIZADOS
# ------------------------------------------
with aba_pers:
    st.subheader("⚖️ Percentuais Personalizados por Perfil (Conservador, Moderado, Agressivo)")
    st.dataframe(dados_planilha["df_personalizados"], use_container_width=True, hide_index=True)

# ------------------------------------------
# ABA 4: ANÁLISE DE FIIs E RENDA FIXA
# ------------------------------------------
with aba_fiis_rf:
    st.subheader("🏢 Ranking de Oportunidades — Renda Fixa e FIIs")
    rf_default = pd.DataFrame([
        {"Produto": "Tesouro Selic", "Tipo": "Pós-fixado (SELIC)", "Taxa_aa": round(taxa_selic_cdi, 2), "Isento_IR": False, "Prazo_Dias": 365, "Liquidez_Dias": 1, "Risco_Score": 98.0},
        {"Produto": "CDB Liquidez Diária 100% CDI", "Tipo": "Pós-fixado (CDI)", "Taxa_aa": round(taxa_selic_cdi, 2), "Isento_IR": False, "Prazo_Dias": 365, "Liquidez_Dias": 1, "Risco_Score": 82.0},
        {"Produto": "LCI / LCA Prefixada ou Pós", "Tipo": "Isento IR", "Taxa_aa": round(taxa_selic_cdi * 0.86, 2), "Isento_IR": True, "Prazo_Dias": 365, "Liquidez_Dias": 90, "Risco_Score": 80.0},
        {"Produto": "Tesouro IPCA+ (Juro Real)", "Tipo": "IPCA + Juros", "Taxa_aa": round(ipca_projetado + 6.5, 2), "Isento_IR": False, "Prazo_Dias": 730, "Liquidez_Dias": 2, "Risco_Score": 90.0},
    ])
    df_rf_rank = avaliar_renda_fixa(rf_default, taxa_selic_cdi, ipca_projetado, capital_total, horizonte_meses)
    fiis_lista = ["KNCR11.SA", "XPML11.SA", "HGLG11.SA", "XPLG11.SA", "MXRF11.SA", "VISC11.SA", "RECR11.SA", "CPTS11.SA"]
    df_fii_rank, df_fii_precos = avaliar_fiis(tuple(fiis_lista), capital_total, horizonte_meses, ir_ganho_capital_fii)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Top Renda Fixa**")
        st.dataframe(df_rf_rank, use_container_width=True, hide_index=True)
    with c2:
        st.markdown("**Top FIIs**")
        st.dataframe(df_fii_rank, use_container_width=True, hide_index=True)

# ------------------------------------------
# ABA 5: EVOLUÇÃO HISTÓRICA (30 A 360 DIAS)
# ------------------------------------------
with aba_evolucao:
    st.subheader("📈 Evolução Histórica dos Ativos da Carteira (30 a 360 dias)")
    ativos_rv = dados_planilha["df_carteira"][dados_planilha["df_carteira"]["Classe"].isin(["Ação", "FII"])]["Ativo"].tolist()
    periodo_dias = st.selectbox("Período (dias):", options=[30, 60, 90, 180, 240, 300, 360], index=3)
    if ativos_rv:
        raw_hist = yf.download(ativos_rv, period="1y", interval="1d", group_by="ticker", auto_adjust=True, progress=False)
        series_dict = {}
        for tk in ativos_rv:
            try:
                s = raw_hist[tk]["Close"].dropna() if isinstance(raw_hist.columns, pd.MultiIndex) else raw_hist["Close"].dropna()
                if not s.empty:
                    series_dict[tk] = s
            except Exception:
                continue
        if series_dict:
            df_h = pd.DataFrame(series_dict).sort_index()
            dt_corte = df_h.index.max() - pd.Timedelta(days=periodo_dias)
            rec = df_h.loc[df_h.index >= dt_corte].dropna(how="all")
            if len(rec) >= 2:
                prim = rec.apply(lambda c: c.dropna().iloc[0] if not c.dropna().empty else np.nan)
                st.line_chart(((rec / prim) - 1.0) * 100.0, use_container_width=True)

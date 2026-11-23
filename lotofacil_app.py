import streamlit as st
import pandas as pd
import numpy as np
import requests
import io

st.set_page_config(page_title="Analisador Estatístico Lotofácil (Walk-Forward)", layout="wide")

st.title("🍀 Analisador Estatístico Walk-Forward — Lotofácil")
st.markdown(
    "Avalia os concursos históricos em **validação sequencial (walk-forward)**: parte do concurso mais antigo da janela, "
    "testa múltiplas táticas estatísticas no concurso seguinte e recalibra os pesos a cada novo sorteio até o concurso atual. "
    "Ao final, seleciona **10 dezenas fixas** e distribui as **15 dezenas restantes em 3 jogos exclusivos (5 cada)**, "
    "cobrindo **todas as 25 dezenas do volante**."
)

# ==========================================
# 1. PARÂMETROS NA BARRA LATERAL
# ==========================================
st.sidebar.header("⚙️ Configuração da Análise")

janela_concursos = st.sidebar.selectbox(
    "Quantidade de últimos concursos para analisar:",
    options=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
    index=4,  # Padrão: 50 concursos
    help="Escolha de 10 em 10 até os últimos 100 concursos."
)

fonte_dados = st.sidebar.radio(
    "Fonte dos resultados da Lotofácil:",
    options=["Automática (API Caixa / Espelhos)", "Colar ou Enviar CSV manualmente"]
)

texto_manual = ""
arquivo_csv = None
if fonte_dados == "Colar ou Enviar CSV manualmente":
    arquivo_csv = st.sidebar.file_uploader("Enviar arquivo CSV (Concurso + 15 dezenas)", type=["csv", "txt"])
    texto_manual = st.sidebar.text_area(
        "Ou cole os resultados (1 concurso por linha, 15 dezenas separadas por espaço, vírgula ou traço):",
        height=140,
        placeholder="Ex:\n3250: 01 02 04 05 07 09 10 12 14 15 18 20 21 23 25\n3251: 02 03 05 06 08 10 11 13 15 16 19 20 22 24 25"
    )

iniciar = st.sidebar.button("🚀 Iniciar Análise Walk-Forward", type="primary", use_container_width=True)

# ==========================================
# 2. COLETA E PARSER DOS CONCURSOS
# ==========================================
def parse_linhas_manuais(txt, uploaded_file):
    conteudo = ""
    if uploaded_file is not None:
        conteudo = uploaded_file.getvalue().decode("utf-8", errors="ignore")
    elif txt:
        conteudo = txt
    if not conteudo.strip():
        return pd.DataFrame()

    registros = []
    idx_auto = 1
    for linha in conteudo.strip().splitlines():
        nums = [int(x) for x in pd.Series(linha).str.findall(r"\d+").iloc[0]]
        if len(nums) >= 16:
            conc = nums[0]
            dezenas = sorted(list(dict.fromkeys([n for n in nums[1:] if 1 <= n <= 25])))[:15]
        else:
            conc = idx_auto
            dezenas = sorted(list(dict.fromkeys([n for n in nums if 1 <= n <= 25])))[:15]
        if len(dezenas) == 15:
            registros.append({"Concurso": conc, "Data": "", "Dezenas": dezenas})
            idx_auto += 1
    if not registros:
        return pd.DataFrame()
    df = pd.DataFrame(registros).drop_duplicates(subset=["Concurso"]).sort_values("Concurso").reset_index(drop=True)
    return df

@st.cache_data(ttl=1800)
def buscar_concursos_api(qtd_desejada):
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    # Tentativa 1: API Pública Espelho Lotofácil (Loterias Caixa JSON)
    urls_lote = [
        "https://loteriascaixa-api.herokuapp.com/api/lotofacil",
        "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil"
    ]
    for url in urls_lote:
        try:
            r = requests.get(url, headers=headers, timeout=12, verify=False)
            if r.status_code == 200:
                dados = r.json()
                if isinstance(dados, list) and len(dados) >= 5:
                    regs = []
                    for item in dados:
                        conc = int(item.get("concurso") or item.get("numero") or 0)
                        dezs_raw = item.get("dezenas") or item.get("listaDezenas") or []
                        dezs = sorted([int(d) for d in dezs_raw if 1 <= int(d) <= 25])
                        dt = str(item.get("data") or item.get("dataApuracao") or "")
                        if conc > 0 and len(dezs) == 15:
                            regs.append({"Concurso": conc, "Data": dt, "Dezenas": dezs})
                    if len(regs) >= 5:
                        df = pd.DataFrame(regs).drop_duplicates(subset=["Concurso"]).sort_values("Concurso").reset_index(drop=True)
                        return df.tail(qtd_desejada).reset_index(drop=True), "API Loterias Caixa (Histórico Completo)"
                elif isinstance(dados, dict) and (dados.get("numero") or dados.get("concurso")):
                    ultimo_num = int(dados.get("numero") or dados.get("concurso"))
                    regs = []
                    inicio = max(1, ultimo_num - qtd_desejada + 1)
                    for c_num in range(inicio, ultimo_num + 1):
                        rc = requests.get(f"{url}/{c_num}", headers=headers, timeout=6, verify=False)
                        if rc.status_code == 200:
                            it = rc.json()
                            dezs_raw = it.get("listaDezenas") or it.get("dezenas") or []
                            dezs = sorted([int(d) for d in dezs_raw if 1 <= int(d) <= 25])
                            dt = str(it.get("dataApuracao") or it.get("data") or "")
                            if len(dezs) == 15:
                                regs.append({"Concurso": c_num, "Data": dt, "Dezenas": dezs})
                    if len(regs) >= 5:
                        df = pd.DataFrame(regs).sort_values("Concurso").reset_index(drop=True)
                        return df, "API Oficial Caixa (Consulta Sequencial)"
        except Exception:
            continue

    return pd.DataFrame(), "Falha na coleta online"

# ==========================================
# 3. MOTOR WALK-FORWARD DE TÁTICAS (1 A 25)
# ==========================================
PRIMOS = {2, 3, 5, 7, 11, 13, 17, 19, 23}
MOLDURA = {1, 2, 3, 4, 5, 6, 10, 11, 15, 16, 20, 21, 22, 23, 24, 25}
FIBONACCI = {1, 2, 3, 5, 8, 13, 21}

def pontuar_taticas_no_passo(historico_df):
    """
    Dado todo o histórico até o concurso t-1, calcula a pontuação de cada dezena (1..25)
    segundo 6 táticas estatísticas distintas.
    """
    n_hist = len(historico_df)
    todas_dezenas = list(range(1, 26))
    ultimo_sorteio = set(historico_df.iloc[-1]["Dezenas"])

    # Frequência acumulada na janela disponível até t-1
    freq_total = {d: 0 for d in todas_dezenas}
    for dezs in historico_df["Dezenas"]:
        for d in dezs:
            freq_total[d] += 1

    # Frequência recente (últimos 5 concursos até t-1)
    rec_df = historico_df.tail(min(5, n_hist))
    freq_rec = {d: 0 for d in todas_dezenas}
    for dezs in rec_df["Dezenas"]:
        for d in dezs:
            freq_rec[d] += 1

    # Atraso atual (quantos concursos seguidos sem sair até t-1)
    atraso = {d: 0 for d in todas_dezenas}
    for d in todas_dezenas:
        cnt = 0
        for dezs in reversed(historico_df["Dezenas"].tolist()):
            if d in dezs:
                break
            cnt += 1
        atraso[d] = cnt

    # Matriz de transição (se saiu em t-1, qual a probabilidade histórica de repetir em t?)
    trans_saiu = {d: [0, 0] for d in todas_dezenas}      # [vezes_que_repetiu, vezes_que_saiu_antes]
    trans_nao_saiu = {d: [0, 0] for d in todas_dezenas}  # [vezes_que_veio, vezes_que_faltou_antes]
    lista_hist = historico_df["Dezenas"].tolist()
    if len(lista_hist) >= 2:
        for i in range(len(lista_hist) - 1):
            s_ant = set(lista_hist[i])
            s_prox = set(lista_hist[i + 1])
            for d in todas_dezenas:
                if d in s_ant:
                    trans_saiu[d][1] += 1
                    if d in s_prox:
                        trans_saiu[d][0] += 1
                else:
                    trans_nao_saiu[d][1] += 1
                    if d in s_prox:
                        trans_nao_saiu[d][0] += 1

    taticas_scores = {
        "T1_Frequencia_Historica": {},
        "T2_Momento_Recente_5c": {},
        "T3_Reversao_Atraso": {},
        "T4_Cadeia_Markov_Transicao": {},
        "T5_Repeticao_Ultimo_Sorteio": {},
        "T6_Equilibrio_Estrutural": {},
    }

    for d in todas_dezenas:
        # T1: Frequência relativa histórica
        taticas_scores["T1_Frequencia_Historica"][d] = freq_total[d] / max(n_hist, 1)

        # T2: Momento quente (últimos 5 concursos)
        taticas_scores["T2_Momento_Recente_5c"][d] = freq_rec[d] / max(len(rec_df), 1)

        # T3: Reversão à média por atraso
        taticas_scores["T3_Reversao_Atraso"][d] = min(atraso[d] / 5.0, 1.5)

        # T4: Probabilidade condicional de transição (Markov 1ª ordem)
        if d in ultimo_sorteio:
            num, den = trans_saiu[d]
            prob = (num + 0.6) / (den + 1.0)
        else:
            num, den = trans_nao_saiu[d]
            prob = (num + 0.6) / (den + 1.0)
        taticas_scores["T4_Cadeia_Markov_Transicao"][d] = prob

        # T5: Tendência de repetição (na Lotofácil, ~9 dezenas repetem do concurso anterior)
        taticas_scores["T5_Repeticao_Ultimo_Sorteio"][d] = 0.62 if d in ultimo_sorteio else 0.38

        # T6: Equilíbrio estrutural (Moldura, Primos, Fibonacci + frequência)
        bonus_est = 0.0
        if d in MOLDURA: bonus_est += 0.35
        if d in PRIMOS: bonus_est += 0.25
        if d in FIBONACCI: bonus_est += 0.20
        taticas_scores["T6_Equilibrio_Estrutural"][d] = bonus_est + 0.20 * (freq_total[d] / max(n_hist, 1))

    return taticas_scores

def executar_walk_forward(df_concursos):
    """
    Parte do concurso mais antigo e avança passo a passo até o concurso mais recente.
    Em cada etapa t, usa os concursos 0..t-1 para prever o concurso t, mede os acertos
    de cada tática (Top 15 dezenas da tática vs. resultado real em t) e atualiza a eficiência.
    """
    n = len(df_concursos)
    nomes_taticas = [
        "T1_Frequencia_Historica",
        "T2_Momento_Recente_5c",
        "T3_Reversao_Atraso",
        "T4_Cadeia_Markov_Transicao",
        "T5_Repeticao_Ultimo_Sorteio",
        "T6_Equilibrio_Estrutural",
    ]
    acertos_taticas = {t: [] for t in nomes_taticas}
    historico_passos = []

    for t in range(1, n):
        hist_ate_agora = df_concursos.iloc[:t]
        real_t = set(df_concursos.iloc[t]["Dezenas"])
        conc_t = int(df_concursos.iloc[t]["Concurso"])

        scores_t = pontuar_taticas_no_passo(hist_ate_agora)
        passo_info = {"Concurso Testado": conc_t, "Base Anterior": f"{t} conc."}

        for tat in nomes_taticas:
            top15_tat = sorted(scores_t[tat].keys(), key=lambda x: (-scores_t[tat][x], x))[:15]
            hits = len(set(top15_tat).intersection(real_t))
            acertos_taticas[tat].append(hits)
            passo_info[tat] = hits

        historico_passos.append(passo_info)

    # Pesos aprendidos por cada tática com base na média de acertos + bônus para acertos >= 11
    resumo_taticas = []
    pesos_aprendidos = {}
    for tat in nomes_taticas:
        arr = np.array(acertos_taticas[tat], dtype=float)
        media_hits = float(arr.mean()) if len(arr) > 0 else 9.0
        premiados = int(np.sum(arr >= 11))
        max_hits = int(arr.max()) if len(arr) > 0 else 0
        # Peso exponencial suave para valorizar as táticas que mais acertaram na sequência
        peso = max(0.05, (media_hits - 7.5) ** 2 + premiados * 0.25)
        pesos_aprendidos[tat] = peso
        resumo_taticas.append({
            "Tática Avaliada": tat,
            "Média Acertos (em 15)": round(media_hits, 2),
            "Máx. Acertos": max_hits,
            "Testes com 11+ pts": premiados,
            "Peso Aprendido": round(peso, 3)
        })

    soma_pesos = sum(pesos_aprendidos.values())
    for tat in pesos_aprendidos:
        pesos_aprendidos[tat] /= soma_pesos

    df_resumo_tat = pd.DataFrame(resumo_taticas).sort_values("Média Acertos (em 15)", ascending=False).reset_index(drop=True)
    df_resumo_tat["Importância (%)"] = (df_resumo_tat["Peso Aprendido"] / df_resumo_tat["Peso Aprendido"].sum() * 100).round(1)

    # Projeção final para o PRÓXIMO concurso usando TODOS os n concursos e os pesos aprendidos
    scores_finais_step = pontuar_taticas_no_passo(df_concursos)
    ranking_dezenas = []
    for d in range(1, 26):
        score_d = 0.0
        for tat in nomes_taticas:
            # Normaliza cada tática entre 0 e 1 antes de ponderar
            vals_tat = list(scores_finais_step[tat].values())
            vmin, vmax = min(vals_tat), max(vals_tat)
            norm = (scores_finais_step[tat][d] - vmin) / (vmax - vmin) if vmax > vmin else 0.5
            score_d += norm * pesos_aprendidos[tat]
        ranking_dezenas.append({
            "Dezena": d,
            "Score Walk-Forward": round(score_d * 100, 2),
            "Freq. na Janela": sum(1 for dezs in df_concursos["Dezenas"] if d in dezs),
            "Saiu no Último?": "Sim" if d in set(df_concursos.iloc[-1]["Dezenas"]) else "Não"
        })

    df_rank_dez = pd.DataFrame(ranking_dezenas).sort_values(
        by=["Score Walk-Forward", "Freq. na Janela", "Dezena"],
        ascending=[False, False, True]
    ).reset_index(drop=True)
    df_rank_dez.insert(0, "Posição", df_rank_dez.index + 1)

    # ==========================================
    # MONTAGEM DOS 3 JOGOS (10 FIXAS + 5 EXCLUSIVAS CADA = 25 DEZENAS)
    # ==========================================
    todas_ordenadas = df_rank_dez["Dezena"].tolist()
    fixas_10 = sorted(todas_ordenadas[:10])
    restantes_15 = todas_ordenadas[10:]  # Exatamente 15 dezenas restantes (posições 11 a 25)

    # Distribui as 15 restantes em 3 grupos exclusivos de 5 dezenas
    excl_jogo1 = sorted(restantes_15[0:5])
    excl_jogo2 = sorted(restantes_15[5:10])
    excl_jogo3 = sorted(restantes_15[10:15])

    jogo_1 = sorted(fixas_10 + excl_jogo1)
    jogo_2 = sorted(fixas_10 + excl_jogo2)
    jogo_3 = sorted(fixas_10 + excl_jogo3)

    return {
        "df_resumo_tat": df_resumo_tat,
        "df_passos": pd.DataFrame(historico_passos),
        "df_rank_dez": df_rank_dez,
        "fixas_10": fixas_10,
        "excl_1": excl_jogo1,
        "excl_2": excl_jogo2,
        "excl_3": excl_jogo3,
        "jogo_1": jogo_1,
        "jogo_2": jogo_2,
        "jogo_3": jogo_3,
    }

def formatar_dezenas(lista):
    return " - ".join(f"{d:02d}" for d in lista)

# ==========================================
# 4. EXECUÇÃO AO CLICAR NO BOTÃO
# ==========================================
if "resultado_wf" not in st.session_state:
    st.session_state["resultado_wf"] = None

if iniciar:
    with st.spinner(f"Executando análise walk-forward nos últimos {janela_concursos} concursos..."):
        if fonte_dados == "Colar ou Enviar CSV manualmente":
            df_conc = parse_linhas_manuais(texto_manual, arquivo_csv)
            if not df_conc.empty:
                df_conc = df_conc.tail(janela_concursos).reset_index(drop=True)
            origem_txt = "Entrada Manual / CSV"
        else:
            df_conc, origem_txt = buscar_concursos_api(janela_concursos)

        if df_conc is None or len(df_conc) < 5:
            st.error(
                "⚠️ Não foi possível carregar os concursos online no momento ou há menos de 5 concursos válidos. "
                "Selecione **Colar ou Enviar CSV manualmente** na barra lateral para colar os resultados da Lotofácil."
            )
        else:
            res = executar_walk_forward(df_conc)
            res["df_conc"] = df_conc
            res["origem"] = origem_txt
            st.session_state["resultado_wf"] = res

res = st.session_state["resultado_wf"]

if res is None:
    st.info("👈 Escolha a quantidade de concursos (10 a 100) na barra lateral e clique em **🚀 Iniciar Análise Walk-Forward**.")
else:
    df_conc = res["df_conc"]
    c_ini = int(df_conc.iloc[0]["Concurso"])
    c_fim = int(df_conc.iloc[-1]["Concurso"])
    st.success(f"✅ Análise concluída! Fonte: **{res['origem']}** | Concursos avaliados: **{c_ini} até {c_fim}** ({len(df_conc)} sorteios).")

    # ==========================================
    # EXIBIÇÃO DOS 3 JOGOS SUGERIDOS (FECHAMENTO 25 DEZENAS)
    # ==========================================
    st.subheader("🎯 Sugestão Final — 3 Jogos Cobrindo Todas as 25 Dezenas")
    st.markdown(f"**🔒 10 Dezenas Fixas (repetem nos 3 jogos):** `{formatar_dezenas(res['fixas_10'])}`")

    col_j1, col_j2, col_j3 = st.columns(3)
    with col_j1:
        st.info(
            f"**JOGO 1 (15 dezenas)**\n\n"
            f"`{formatar_dezenas(res['jogo_1'])}`\n\n"
            f"**5 Exclusivas:** `{formatar_dezenas(res['excl_1'])}`"
        )
    with col_j2:
        st.info(
            f"**JOGO 2 (15 dezenas)**\n\n"
            f"`{formatar_dezenas(res['jogo_2'])}`\n\n"
            f"**5 Exclusivas:** `{formatar_dezenas(res['excl_2'])}`"
        )
    with col_j3:
        st.info(
            f"**JOGO 3 (15 dezenas)**\n\n"
            f"`{formatar_dezenas(res['jogo_3'])}`\n\n"
            f"**5 Exclusivas:** `{formatar_dezenas(res['excl_3'])}`"
        )

    # Verificação matemática automática da cobertura das 25 dezenas
    uniao_25 = sorted(list(set(res["jogo_1"]) | set(res["jogo_2"]) | set(res["jogo_3"])))
    inter_12 = sorted(list(set(res["jogo_1"]) & set(res["jogo_2"])))
    inter_13 = sorted(list(set(res["jogo_1"]) & set(res["jogo_3"])))
    inter_23 = sorted(list(set(res["jogo_2"]) & set(res["jogo_3"])))
    st.caption(
        f"Conferência estrutural: Total de dezenas distintas cobertas = {len(uniao_25)}/25 | "
        f"Repetidas entre Jogo 1 e 2 = {len(inter_12)} | Jogo 1 e 3 = {len(inter_13)} | Jogo 2 e 3 = {len(inter_23)}."
    )

    st.divider()

    aba1, aba2, aba3, aba4 = st.tabs([
        "🧠 Eficiência das Táticas (Walk-Forward)",
        "🔢 Ranking das 25 Dezenas",
        "📜 Passo a Passo Concurso a Concurso",
        "🗂️ Base de Concursos Carregada"
    ])

    with aba1:
        st.subheader("Desempenho das Táticas na Validação Sequencial")
        st.dataframe(res["df_resumo_tat"], use_container_width=True, hide_index=True)
        st.bar_chart(res["df_resumo_tat"].set_index("Tática Avaliada")["Média Acertos (em 15)"])

    with aba2:
        st.subheader("Pontuação Final das 25 Dezenas (1 a 10 = Fixas | 11 a 25 = Exclusivas)")
        df_rk = res["df_rank_dez"].copy()
        df_rk["Papel nos 3 Jogos"] = [
            "🔒 Fixa (Todos)" if i < 10 else ("🎲 Exclusiva Jogo 1" if i < 15 else ("🎲 Exclusiva Jogo 2" if i < 20 else "🎲 Exclusiva Jogo 3"))
            for i in range(len(df_rk))
        ]
        st.dataframe(df_rk, use_container_width=True, hide_index=True)

    with aba3:
        st.subheader("Histórico de Testes Sequenciais (Concurso Antigo -> Mais Recente)")
        st.dataframe(res["df_passos"], use_container_width=True, hide_index=True)

    with aba4:
        st.subheader("Concursos Utilizados na Janela")
        df_show_c = df_conc.copy()
        df_show_c["Dezenas Sorteadas"] = df_show_c["Dezenas"].apply(formatar_dezenas)
        st.dataframe(df_show_c[["Concurso", "Data", "Dezenas Sorteadas"]], use_container_width=True, hide_index=True)

st.caption(
    "Aviso: Lotofácil é um jogo de azar com sorteios independentes. Esta ferramenta realiza análise estatística histórica "
    "e fechamento combinatório de 25 dezenas apenas para fins de estudo e entretenimento, sem garantia de premiação."
)

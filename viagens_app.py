import streamlit as st
import pandas as pd
import numpy as np
import datetime
import calendar
import urllib.parse
import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

st.set_page_config(
    page_title="Comparador de Voos Reais & Buscador de Pacotes — BHZ",
    page_icon="✈️",
    layout="wide"
)

# ==============================================================================
# 1. CATÁLOGO DE AEROPORTOS E DESTINOS
# ==============================================================================
DESTINOS_CATALOGO = {
    "Fortaleza (FOR) — CE": {"iata": "FOR", "cidade": "Fortaleza", "slug": "fortaleza", "regiao": "Nordeste"},
    "Porto de Galinhas / Recife (REC) — PE": {"iata": "REC", "cidade": "Recife", "slug": "recife", "regiao": "Nordeste"},
    "Maceió (MCZ) — AL": {"iata": "MCZ", "cidade": "Maceio", "slug": "maceio", "regiao": "Nordeste"},
    "Salvador (SSA) — BA": {"iata": "SSA", "cidade": "Salvador", "slug": "salvador", "regiao": "Nordeste"},
    "Porto Seguro (BPS) — BA": {"iata": "BPS", "cidade": "Porto Seguro", "slug": "porto-seguro", "regiao": "Nordeste"},
    "Natal (NAT) — RN": {"iata": "NAT", "cidade": "Natal", "slug": "natal", "regiao": "Nordeste"},
    "São Paulo (GRU/CGH) — SP": {"iata": "GRU", "cidade": "Sao Paulo", "slug": "sao-paulo", "regiao": "Sudeste"},
    "Rio de Janeiro (GIG/SDU) — RJ": {"iata": "GIG", "cidade": "Rio de Janeiro", "slug": "rio-de-janeiro", "regiao": "Sudeste"},
    "Florianópolis (FLN) — SC": {"iata": "FLN", "cidade": "Florianopolis", "slug": "florianopolis", "regiao": "Sul"},
    "Foz do Iguaçu (IGU) — PR": {"iata": "IGU", "cidade": "Foz do Iguacu", "slug": "foz-do-iguacu", "regiao": "Sul"},
    "Lisboa (LIS) — Portugal": {"iata": "LIS", "cidade": "Lisboa", "slug": "lisboa", "regiao": "Europa"},
    "Madri (MAD) — Espanha": {"iata": "MAD", "cidade": "Madri", "slug": "madri", "regiao": "Europa"},
    "Orlando (MCO) — EUA": {"iata": "MCO", "cidade": "Orlando", "slug": "orlando", "regiao": "América do Norte"},
    "Santiago (SCL) — Chile": {"iata": "SCL", "cidade": "Santiago", "slug": "santiago", "regiao": "América do Sul"},
    "Buenos Aires (EZE) — Argentina": {"iata": "EZE", "cidade": "Buenos Aires", "slug": "buenos-aires", "regiao": "América do Sul"},
}

ORIGENS_BH = {
    "Confins — Tancredo Neves (CNF)": "CNF",
    "Belo Horizonte — Todos (BHZ)": "BHZ",
    "Pampulha (PLU)": "PLU",
}

PLATAFORMAS_BUSCA = [
    {"nome": "Google Flights", "tipo": "Só Voo", "obs": "Abre já preenchido com origem, destino, ida/volta e passageiros"},
    {"nome": "Skyscanner", "tipo": "Só Voo", "obs": "Abre com trecho, datas e passageiros preenchidos"},
    {"nome": "Kayak", "tipo": "Só Voo", "obs": "Abre com trecho, datas e adultos preenchidos"},
    {"nome": "Decolar (Voos)", "tipo": "Só Voo", "obs": "Abre busca direta de voos ida e volta"},
    {"nome": "ViajaNet (Voos)", "tipo": "Só Voo", "obs": "Abre busca direta de voos ida e volta"},
    {"nome": "Azul Linhas Aéreas", "tipo": "Só Voo", "obs": "Site oficial Azul (Hub Confins CNF)"},
    {"nome": "GOL Linhas Aéreas", "tipo": "Só Voo", "obs": "Site oficial GOL Linhas Aéreas"},
    {"nome": "LATAM Airlines", "tipo": "Só Voo", "obs": "Abre busca de voos ida e volta LATAM"},
    {"nome": "MaxMilhas", "tipo": "Só Voo", "obs": "Abre busca de emissões com milhas"},
    {"nome": "Decolar (Pacotes)", "tipo": "Pacote (Voo + Hotel)", "obs": "Página oficial de Pacotes Decolar"},
    {"nome": "Azul Viagens (Pacotes)", "tipo": "Pacote (Voo + Hotel)", "obs": "Página oficial Azul Viagens Pacotes"},
    {"nome": "ViajaNet (Pacotes)", "tipo": "Pacote (Voo + Hotel)", "obs": "Página oficial de Pacotes ViajaNet"},
    {"nome": "LATAM Travel (Pacotes)", "tipo": "Pacote (Voo + Hotel)", "obs": "Página oficial LATAM Travel Pacotes"},
    {"nome": "Expedia (Pacotes)", "tipo": "Pacote (Voo + Hotel)", "obs": "Página oficial Expedia Pacotes"},
    {"nome": "Booking.com (Hospedagem)", "tipo": "Hospedagem", "obs": "Abre destino, check-in, check-out e hóspedes preenchidos"},
]

# ==============================================================================
# 2. GERADOR DE LINKS OFICIAIS REAIS (COM PARÂMETROS REAIS SUPORTADOS)
# ==============================================================================
def gerar_link_plataforma(plataforma, tipo, origem_iata, dest_info, dt_ida, dt_volta, adultos, criancas):
    dest_iata = dest_info["iata"]
    ida_iso = dt_ida.strftime("%Y-%m-%d")
    volta_iso = dt_volta.strftime("%Y-%m-%d")
    ida_yymmdd = dt_ida.strftime("%y%m%d")
    volta_yymmdd = dt_volta.strftime("%y%m%d")
    cidade_q = urllib.parse.quote(dest_info["cidade"])
    orig_gf = "CNF" if origem_iata == "BHZ" else origem_iata

    if "Google Flights" in plataforma:
        pax_txt = f"{adultos} adults" + (f" {criancas} children" if criancas > 0 else "")
        q = urllib.parse.quote(f"Flights from {orig_gf} to {dest_iata} on {ida_iso} through {volta_iso} for {pax_txt}")
        return f"https://www.google.com/travel/flights?q={q}&curr=BRL&hl=pt-BR"
    elif "Skyscanner" in plataforma:
        return f"https://www.skyscanner.com.br/transporte/passagens-aereas/{orig_gf.lower()}/{dest_iata.lower()}/{ida_yymmdd}/{volta_yymmdd}/?adults={adultos}&children={criancas}"
    elif "Kayak" in plataforma:
        chd_part = f"/{criancas}children" if criancas > 0 else ""
        return f"https://www.kayak.com.br/flights/{orig_gf}-{dest_iata}/{ida_iso}/{volta_iso}/{adultos}adults{chd_part}"
    elif "Decolar (Pacotes)" in plataforma:
        return "https://www.decolar.com/pacotes/"
    elif "Decolar (Voos)" in plataforma:
        return f"https://www.decolar.com/shop/flights/results/roundtrip/{orig_gf}/{dest_iata}/{ida_iso}/{volta_iso}/{adultos}/{criancas}/0"
    elif "ViajaNet (Pacotes)" in plataforma:
        return "https://www.viajanet.com.br/pacotes"
    elif "ViajaNet (Voos)" in plataforma:
        return f"https://www.viajanet.com.br/busca/passagens/voos#/{orig_gf}/{dest_iata}/RT/{ida_iso}/{volta_iso}/-/-/{adultos}/{criancas}/0"
    elif "Azul Viagens" in plataforma:
        return "https://www.azulviagens.com.br/packages/"
    elif "Azul Linhas" in plataforma:
        return "https://www.voeazul.com.br/br/pt/home"
    elif "GOL" in plataforma:
        return "https://www.voegol.com.br/"
    elif "LATAM Travel" in plataforma:
        return "https://www.latamairlines.com/br/pt/pacotes-viagens"
    elif "LATAM Airlines" in plataforma:
        return f"https://www.latamairlines.com/br/pt/oferta-voos?origin={orig_gf}&destination={dest_iata}&outbound={ida_iso}T12%3A00%3A00.000Z&inbound={volta_iso}T12%3A00%3A00.000Z&adt={adultos}&chd={criancas}&trip=RT"
    elif "Booking" in plataforma:
        return f"https://www.booking.com/searchresults.pt-br.html?ss={cidade_q}&checkin={ida_iso}&checkout={volta_iso}&group_adults={adultos}&group_children={criancas}"
    elif "Expedia" in plataforma:
        return "https://www.expedia.com.br/Pacotes"
    elif "MaxMilhas" in plataforma:
        return f"https://www.maxmilhas.com.br/busca-passagens-aereas/RT/{orig_gf}/{dest_iata}/{ida_iso}/{volta_iso}/{adultos}/{criancas}/0/EC"
    return f"https://www.google.com/travel/flights?curr=BRL&hl=pt-BR"

# ==============================================================================
# 3. CONSULTA DE PREÇOS REAIS (IDA E VOLTA) VIA GOOGLE FLIGHTS (FAST-FLIGHTS)
# ==============================================================================
def _extrair_valor_brl(preco_str):
    if preco_str is None:
        return None
    s = str(preco_str).strip()
    limpo = "".join(ch for ch in s if ch.isdigit() or ch in ",.")
    if not limpo:
        return None
    if "." in limpo and "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    elif "." in limpo:
        partes = limpo.split(".")
        if len(partes[-1]) == 3:
            limpo = "".join(partes)
    elif "," in limpo:
        partes = limpo.split(",")
        if len(partes[-1]) == 3:
            limpo = "".join(partes)
        else:
            limpo = limpo.replace(",", ".")
    try:
        val = float(limpo)
        return val if val >= 80.0 else None
    except Exception:
        return None

@st.cache_data(ttl=1800, show_spinner=False)
def consultar_tarifas_reais_ida_volta(origem_iata, dest_iata, dt_ida, dt_volta, adultos, criancas, classe_cabine):
    """
    Busca exclusivamente tarifas REAIS de Ida e Volta no Google Flights via fast-flights
    para o número exato de viajantes (adultos + crianças).
    Nunca inventa nem estima valores.
    """
    try:
        from fast_flights import FlightData, Passengers, get_flights
    except ImportError:
        return [], "Biblioteca 'fast-flights' não instalada (adicione fast-flights no requirements.txt)."

    mapa_classe = {"Econômica": "economy", "Executiva": "business", "Primeira Classe": "first"}
    orig_consulta = "CNF" if origem_iata == "BHZ" else origem_iata

    try:
        res = get_flights(
            flight_data=[
                FlightData(date=dt_ida.strftime("%Y-%m-%d"), from_airport=orig_consulta, to_airport=dest_iata),
                FlightData(date=dt_volta.strftime("%Y-%m-%d"), from_airport=dest_iata, to_airport=orig_consulta),
            ],
            trip="round-trip",
            seat=mapa_classe.get(classe_cabine, "economy"),
            passengers=Passengers(adults=int(adultos), children=int(criancas)),
            fetch_mode="fallback",
        )
    except Exception as exc:
        return [], f"Falha ou bloqueio temporário na consulta ao vivo: {exc}"

    if not res or not getattr(res, "flights", None):
        return [], "O Google Flights não retornou tarifas ao vivo para essa combinação no momento."

    lista_reais = []
    for fl in res.flights:
        val = _extrair_valor_brl(getattr(fl, "price", None))
        if val is not None:
            lista_reais.append({
                "Companhia Aérea": str(getattr(fl, "name", "Não informada")),
                "Preço Total Real Ida e Volta (R$)": round(val, 2),
                "Paradas": str(getattr(fl, "stops", "-")),
                "Duração do Voo": str(getattr(fl, "duration", "-")),
                "Partida": str(getattr(fl, "departure", "-")),
                "Chegada": str(getattr(fl, "arrival", "-")),
            })

    if not lista_reais:
        return [], "As tarifas retornadas não continham preço numérico legível."

    lista_reais.sort(key=lambda x: x["Preço Total Real Ida e Volta (R$)"])
    return lista_reais, "OK"

# ==============================================================================
# 4. EXPORTAÇÃO EXCEL (.XLSX) APENAS COM DADOS REAIS E LINKS OFICIAIS
# ==============================================================================
def gerar_excel_real(df_voos_reais, df_plataformas, origem_label, dest_nome, dt_ida, dt_volta, total_pessoas):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Tarifas_Reais_Ida_Volta"

    azul_escuro = "0F294A"
    azul_medio = "1E4E8C"
    verde_claro = "DCFCE7"
    cinza_zebra = "F8FAFC"
    borda_cor = "CBD5E1"

    f_titulo = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    f_sub = Font(name="Calibri", size=10, italic=True, color="E2E8F0")
    f_cab = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    f_body = Font(name="Calibri", size=10, color="1E293B")
    f_bold = Font(name="Calibri", size=10, bold=True, color="1E293B")
    f_link = Font(name="Calibri", size=10, underline="single", color="1D4ED8")

    fill_titulo = PatternFill("solid", fgColor=azul_escuro)
    fill_sub = PatternFill("solid", fgColor=azul_medio)
    fill_zebra = PatternFill("solid", fgColor=cinza_zebra)
    fill_top = PatternFill("solid", fgColor=verde_claro)
    lado = Side(style="thin", color=borda_cor)
    borda = Border(left=lado, right=lado, top=lado, bottom=lado)

    ws.merge_cells("A1:I1")
    ws["A1"] = f"TARIFAS REAIS IDA E VOLTA — {origem_label.upper()} -> {dest_nome.upper()}"
    ws["A1"].font = f_titulo
    ws["A1"].fill = fill_titulo
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:I2")
    ws["A2"] = f"Ida: {dt_ida.strftime('%d/%m/%Y')} | Volta: {dt_volta.strftime('%d/%m/%Y')} | Viajantes: {total_pessoas} pessoa(s) | Fonte: Google Flights"
    ws["A2"].font = f_sub
    ws["A2"].fill = fill_sub
    ws["A2"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[2].height = 20

    if not df_voos_reais.empty:
        cols = list(df_voos_reais.columns)
        for c_i, h in enumerate(cols, start=1):
            c = ws.cell(row=4, column=c_i, value=h)
            c.font = f_cab
            c.fill = fill_titulo
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = borda
        for r_i, row in df_voos_reais.iterrows():
            for c_i, col_n in enumerate(cols, start=1):
                cel = ws.cell(row=r_i + 5, column=c_i, value=row[col_n])
                cel.border = borda
                cel.font = f_bold if "Preço" in col_n else f_body
                if r_i == 0:
                    cel.fill = fill_top
                elif r_i % 2 == 1:
                    cel.fill = fill_zebra
                if "Preço" in col_n:
                    cel.number_format = "R$ #,##0.00"
    else:
        ws["A4"] = "Nenhuma tarifa ao vivo foi retornada na consulta."

    ws_p = wb.create_sheet("Links_Oficiais")
    cols_p = list(df_plataformas.columns)
    for c_i, h in enumerate(cols_p, start=1):
        c = ws_p.cell(row=1, column=c_i, value=h)
        c.font = f_cab
        c.fill = fill_titulo
        c.alignment = Alignment(horizontal="center")
        c.border = borda
    for r_i, row in df_plataformas.iterrows():
        for c_i, col_n in enumerate(cols_p, start=1):
            cel = ws_p.cell(row=r_i + 2, column=c_i, value=row[col_n])
            cel.border = borda
            if col_n == "Link Direto":
                cel.hyperlink = str(row[col_n])
                cel.value = "Abrir Site"
                cel.font = f_link

    for aba in wb.worksheets:
        for col in aba.columns:
            ltr = get_column_letter(col[0].column)
            max_l = max((len(str(c.value or "")) for c in col if c.row > 2), default=14)
            aba.column_dimensions[ltr].width = min(max(max_l + 4, 14), 42)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()

# ==============================================================================
# 5. INTERFACE STREAMLIT
# ==============================================================================
st.title("✈️ Buscador de Voos Reais (Ida e Volta) & Pacotes — Saindo de BH")
st.markdown(
    "Consulta **tarifas reais de Ida e Volta** diretamente no **Google Flights** (via `fast-flights`) para o número exato de viajantes "
    "e fornece os **links reais** de **Voos**, **Pacotes (Voo + Hotel)** e **Hospedagem** nas principais plataformas.\n\n"
    "🔒 **Sem preços inventados:** Este aplicativo exibe **exclusivamente** preços reais retornados na consulta ao vivo para **Ida e Volta**. "
    "Nenhum valor estimado ou fictício é gerado."
)

st.sidebar.header("🛫 Origem, Destino e Viajantes")
origem_label = st.sidebar.selectbox("Aeroporto de Origem (BH):", list(ORIGENS_BH.keys()), index=0)
origem_iata = ORIGENS_BH[origem_label]

dest_nome = st.sidebar.selectbox("Destino desejado:", list(DESTINOS_CATALOGO.keys()), index=0)
dest_info = DESTINOS_CATALOGO[dest_nome]

qtd_pessoas_total = st.sidebar.number_input(
    "Quantidade Total de Pessoas:",
    min_value=1,
    max_value=9,
    value=2,
    step=1,
    help="Todas as consultas buscam o valor total de Ida e Volta para essa quantidade exata de pessoas."
)
criancas = st.sidebar.number_input(
    "Dessas, quantas são crianças (2 a 11 anos)?",
    min_value=0,
    max_value=max(0, int(qtd_pessoas_total) - 1),
    value=0,
    step=1
)
adultos = max(1, int(qtd_pessoas_total) - int(criancas))
classe_cabine = st.sidebar.selectbox("Classe:", ["Econômica", "Executiva", "Primeira Classe"], index=0)

st.sidebar.divider()
st.sidebar.header("📅 Datas (Ida e Volta)")
modo_data = st.sidebar.radio(
    "Modo de busca:",
    options=["Data Específica (Ida e Volta)", "Varredura de Melhores Datas no Mês"],
)

hoje = datetime.date.today()
if modo_data == "Data Específica (Ida e Volta)":
    dt_ida_esp = st.sidebar.date_input("Data de Ida", value=hoje + datetime.timedelta(days=30), min_value=hoje)
    dt_volta_esp = st.sidebar.date_input(
        "Data de Volta",
        value=hoje + datetime.timedelta(days=37),
        min_value=dt_ida_esp + datetime.timedelta(days=1)
    )
    duracao_dias = (dt_volta_esp - dt_ida_esp).days
else:
    meses_nomes = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    opcoes_meses = []
    for offset in range(1, 13):
        m = ((hoje.month - 1 + offset) % 12) + 1
        y = hoje.year + ((hoje.month - 1 + offset) // 12)
        opcoes_meses.append((f"{meses_nomes[m]}/{y}", y, m))
    mes_sel_label = st.sidebar.selectbox("Mês/Ano:", [x[0] for x in opcoes_meses], index=0)
    _, ano_sel, mes_sel = [x for x in opcoes_meses if x[0] == mes_sel_label][0]
    duracao_dias = st.sidebar.slider("Duração da viagem (dias):", min_value=2, max_value=21, value=7)

testar_duracoes_vizinhas = st.sidebar.checkbox(
    "Testar durações vizinhas reais (ex: 5 dias vs 7 dias)",
    value=True,
    help="Consulta tarifas reais para durações próximas na mesma data de embarque para identificar economia real."
)

buscar_btn = st.sidebar.button("🔍 Consultar Tarifas Reais (Ida e Volta)", type="primary", use_container_width=True)

if "busca_real_state" not in st.session_state:
    st.session_state["busca_real_state"] = None

if buscar_btn:
    with st.spinner("Consultando tarifas reais de Ida e Volta no Google Flights..."):
        if modo_data == "Data Específica (Ida e Volta)":
            voos_lista, status_msg = consultar_tarifas_reais_ida_volta(
                origem_iata, dest_info["iata"], dt_ida_esp, dt_volta_esp, adultos, criancas, classe_cabine
            )
            dt_ida_escolhida = dt_ida_esp
            dt_volta_escolhida = dt_volta_esp
            curva_mes = []
        else:
            ultimo_dia = calendar.monthrange(ano_sel, mes_sel)[1]
            dias_candidatos = [d for d in [3, 9, 15, 21, 26] if d <= ultimo_dia]
            melhor_lista = []
            menor_total_mes = float("inf")
            dt_ida_escolhida = datetime.date(ano_sel, mes_sel, dias_candidatos[0])
            dt_volta_escolhida = dt_ida_escolhida + datetime.timedelta(days=duracao_dias)
            status_msg = "Nenhuma data futura disponível no mês selecionado."
            curva_mes = []

            for d_num in dias_candidatos:
                d_i = datetime.date(ano_sel, mes_sel, d_num)
                if d_i < hoje:
                    continue
                d_v = d_i + datetime.timedelta(days=duracao_dias)
                v_dia, st_dia = consultar_tarifas_reais_ida_volta(
                    origem_iata, dest_info["iata"], d_i, d_v, adultos, criancas, classe_cabine
                )
                status_msg = st_dia
                if v_dia:
                    menor_p = v_dia[0]["Preço Total Real Ida e Volta (R$)"]
                    curva_mes.append({
                        "Data Ida": d_i,
                        "Data Volta": d_v.strftime("%d/%m/%Y"),
                        "Menor Preço Real Ida e Volta (R$)": menor_p,
                        "Companhia": v_dia[0]["Companhia Aérea"],
                    })
                    if menor_p < menor_total_mes:
                        menor_total_mes = menor_p
                        melhor_lista = v_dia
                        dt_ida_escolhida = d_i
                        dt_volta_escolhida = d_v

            voos_lista = melhor_lista

        alerta_duracao = None
        if voos_lista and testar_duracoes_vizinhas:
            preco_ref_atual = voos_lista[0]["Preço Total Real Ida e Volta (R$)"]
            for d_alt in [d for d in [5, 6, 8] if d != duracao_dias]:
                d_v_alt = dt_ida_escolhida + datetime.timedelta(days=d_alt)
                v_alt, _ = consultar_tarifas_reais_ida_volta(
                    origem_iata, dest_info["iata"], dt_ida_escolhida, d_v_alt, adultos, criancas, classe_cabine
                )
                if v_alt:
                    p_alt = v_alt[0]["Preço Total Real Ida e Volta (R$)"]
                    eco = preco_ref_atual - p_alt
                    if eco >= 150.0:
                        if alerta_duracao is None or p_alt < alerta_duracao["preco_alt"]:
                            alerta_duracao = {
                                "dur_orig": duracao_dias,
                                "dur_alt": d_alt,
                                "volta_alt": d_v_alt.strftime("%d/%m/%Y"),
                                "preco_orig": preco_ref_atual,
                                "preco_alt": p_alt,
                                "economia": eco,
                                "cia": v_alt[0]["Companhia Aérea"],
                            }

        st.session_state["busca_real_state"] = {
            "voos_lista": voos_lista,
            "status_msg": status_msg,
            "dt_ida": dt_ida_escolhida,
            "dt_volta": dt_volta_escolhida,
            "curva_mes": curva_mes,
            "alerta_duracao": alerta_duracao,
            "origem_label": origem_label,
            "origem_iata": origem_iata,
            "dest_nome": dest_nome,
            "dest_info": dest_info,
            "adultos": adultos,
            "criancas": criancas,
            "total_pessoas": int(adultos + criancas),
        }

state = st.session_state["busca_real_state"]

if state is None:
    st.info("👈 Configure **Origem**, **Destino**, **Quantidade de Pessoas** e **Datas (Ida e Volta)** na barra lateral e clique em **🔍 Consultar Tarifas Reais (Ida e Volta)**.")
else:
    total_pax = state["total_pessoas"]
    dt_i = state["dt_ida"]
    dt_v = state["dt_volta"]
    dur_ef = (dt_v - dt_i).days

    st.info(
        f"📌 **Dados da Pesquisa (Ida e Volta — {total_pax} {'Pessoa' if total_pax == 1 else 'Pessoas'}):** "
        f"**{state['origem_label']}** ➡️ **{state['dest_nome']}** | "
        f"Ida: **{dt_i.strftime('%d/%m/%Y')}** | Volta: **{dt_v.strftime('%d/%m/%Y')}** ({dur_ef} dias)"
    )

    if state["alerta_duracao"] is not None:
        al = state["alerta_duracao"]
        st.success(
            f"💡 **Economia Real Encontrada ao Ajustar Duração ({al['dur_orig']} → {al['dur_alt']} dias, volta em {al['volta_alt']}):** "
            f"O menor voo real **Ida e Volta** para **{total_pax} pessoa(s)** cai de **R$ {al['preco_orig']:,.2f}** "
            f"para **R$ {al['preco_alt']:,.2f}** ({al['cia']}) — economia real de **R$ {al['economia']:,.2f}**!"
        )

    voos_reais = state["voos_lista"]
    st.subheader(f"🛫 Tarifas Reais Encontradas — Ida e Volta para {total_pax} {'Pessoa' if total_pax == 1 else 'Pessoas'}")

    if not voos_reais:
        st.warning(
            f"⚠️ Não foi possível obter preços ao vivo nesta tentativa ({state['status_msg']}). "
            "Nenhum preço simulado foi gerado. Abra o link direto do **Google Flights**, **Skyscanner** ou **Decolar** na tabela abaixo "
            "(que já abrem com origem, destino e datas preenchidos)."
        )
        df_voos_show = pd.DataFrame()
    else:
        df_voos_show = pd.DataFrame(voos_reais)
        df_voos_show.insert(0, "Trecho", "Ida e Volta")
        df_voos_show.insert(1, "Viajantes", f"{total_pax} pessoa(s)")
        df_voos_show["Por Pessoa (Média R$)"] = (df_voos_show["Preço Total Real Ida e Volta (R$)"] / total_pax).round(2)

        m1, m2, m3 = st.columns(3)
        m1.metric(
            f"Menor Preço Real Ida e Volta ({total_pax} pax)",
            f"R$ {df_voos_show['Preço Total Real Ida e Volta (R$)'].min():,.2f}"
        )
        m2.metric(
            "Média por Pessoa (Ida e Volta)",
            f"R$ {(df_voos_show['Preço Total Real Ida e Volta (R$)'].min() / total_pax):,.2f}"
        )
        m3.metric("Companhia Mais Barata", df_voos_show.iloc[0]["Companhia Aérea"])

        st.dataframe(
            df_voos_show,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Preço Total Real Ida e Volta (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Por Pessoa (Média R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            },
        )

    if state["curva_mes"]:
        st.subheader("📈 Menores Preços Reais Ida e Volta Encontrados no Mês")
        df_c = pd.DataFrame(state["curva_mes"]).sort_values("Data Ida")
        st.line_chart(df_c.set_index("Data Ida")[["Menor Preço Real Ida e Volta (R$)"]], use_container_width=True)
        st.dataframe(df_c, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("🔗 Links Reais das Plataformas (Voos, Pacotes e Hospedagem)")
    st.caption(
        "Os buscadores de voos (Google Flights, Skyscanner, Kayak, Decolar Voos, ViajaNet Voos, LATAM, MaxMilhas) e Booking "
        "abrem já com origem, destino, datas e viajantes preenchidos. Para Pacotes (Voo + Hotel), os links abrem a página oficial de pacotes de cada operadora."
    )

    linhas_plat = []
    for p in PLATAFORMAS_BUSCA:
        link_p = gerar_link_plataforma(
            p["nome"], p["tipo"], state["origem_iata"], state["dest_info"],
            dt_i, dt_v, state["adultos"], state["criancas"]
        )
        linhas_plat.append({
            "Plataforma": p["nome"],
            "Modalidade": p["tipo"],
            "Trecho": "Ida e Volta",
            "Viajantes": f"{total_pax} pessoa(s)",
            "Observação": p["obs"],
            "Link Direto": link_p,
        })
    df_plat_show = pd.DataFrame(linhas_plat)

    st.dataframe(
        df_plat_show,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Link Direto": st.column_config.LinkColumn("Link Direto", display_text="Abrir Site"),
        },
    )

    xlsx_bytes = gerar_excel_real(
        df_voos_show, df_plat_show, state["origem_label"], state["dest_nome"], dt_i, dt_v, total_pax
    )
    st.download_button(
        label="📥 Exportar Tarifas Reais e Links para Excel (.xlsx)",
        data=xlsx_bytes,
        file_name=f"voos_reais_{state['origem_iata']}_{state['dest_info']['iata']}_{dt_i.strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )

st.caption(
    "Nota: Apenas preços reais retornados pelo Google Flights são exibidos. Para pacotes Voo + Hotel, consulte os links oficiais "
    "das operadoras informando o trecho de Ida e Volta e a quantidade de viajantes acima."
)

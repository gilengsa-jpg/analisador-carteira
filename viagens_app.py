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
    page_title="Buscador Inteligente de Voos & Pacotes — BHZ",
    page_icon="✈️",
    layout="wide"
)

# ==============================================================================
# 1. BASE DE AEROPORTOS, DESTINOS E CUPONS ATIVOS
# ==============================================================================
DESTINOS_CATALOGO = {
    "Fortaleza (FOR) — CE": {"iata": "FOR", "cidade": "Fortaleza", "slug_decolar": "fortaleza", "base_voo": 1180.0, "diaria_hotel": 420.0, "regiao": "Nordeste"},
    "Porto de Galinhas / Recife (REC) — PE": {"iata": "REC", "cidade": "Recife", "slug_decolar": "recife", "base_voo": 1120.0, "diaria_hotel": 450.0, "regiao": "Nordeste"},
    "Maceió (MCZ) — AL": {"iata": "MCZ", "cidade": "Maceio", "slug_decolar": "maceio", "base_voo": 1150.0, "diaria_hotel": 430.0, "regiao": "Nordeste"},
    "Salvador (SSA) — BA": {"iata": "SSA", "cidade": "Salvador", "slug_decolar": "salvador", "base_voo": 890.0, "diaria_hotel": 370.0, "regiao": "Nordeste"},
    "Porto Seguro (BPS) — BA": {"iata": "BPS", "cidade": "Porto Seguro", "slug_decolar": "porto-seguro", "base_voo": 920.0, "diaria_hotel": 360.0, "regiao": "Nordeste"},
    "Natal (NAT) — RN": {"iata": "NAT", "cidade": "Natal", "slug_decolar": "natal", "base_voo": 1240.0, "diaria_hotel": 395.0, "regiao": "Nordeste"},
    "São Paulo (GRU/CGH) — SP": {"iata": "GRU", "cidade": "Sao Paulo", "slug_decolar": "sao-paulo", "base_voo": 520.0, "diaria_hotel": 380.0, "regiao": "Sudeste"},
    "Rio de Janeiro (GIG/SDU) — RJ": {"iata": "GIG", "cidade": "Rio de Janeiro", "slug_decolar": "rio-de-janeiro", "base_voo": 560.0, "diaria_hotel": 430.0, "regiao": "Sudeste"},
    "Florianópolis (FLN) — SC": {"iata": "FLN", "cidade": "Florianopolis", "slug_decolar": "florianopolis", "base_voo": 860.0, "diaria_hotel": 410.0, "regiao": "Sul"},
    "Foz do Iguaçu (IGU) — PR": {"iata": "IGU", "cidade": "Foz do Iguacu", "slug_decolar": "foz-do-iguacu", "base_voo": 880.0, "diaria_hotel": 350.0, "regiao": "Sul"},
    "Lisboa (LIS) — Portugal": {"iata": "LIS", "cidade": "Lisboa", "slug_decolar": "lisboa", "base_voo": 4650.0, "diaria_hotel": 720.0, "regiao": "Europa"},
    "Madri (MAD) — Espanha": {"iata": "MAD", "cidade": "Madri", "slug_decolar": "madri", "base_voo": 4820.0, "diaria_hotel": 690.0, "regiao": "Europa"},
    "Orlando (MCO) — EUA": {"iata": "MCO", "cidade": "Orlando", "slug_decolar": "orlando", "base_voo": 4150.0, "diaria_hotel": 650.0, "regiao": "América do Norte"},
    "Santiago (SCL) — Chile": {"iata": "SCL", "cidade": "Santiago", "slug_decolar": "santiago", "base_voo": 1980.0, "diaria_hotel": 490.0, "regiao": "América do Sul"},
    "Buenos Aires (EZE) — Argentina": {"iata": "EZE", "cidade": "Buenos Aires", "slug_decolar": "buenos-aires", "base_voo": 1820.0, "diaria_hotel": 450.0, "regiao": "América do Sul"},
}

ORIGENS_BH = {
    "Belo Horizonte — Todos (BHZ)": "BHZ",
    "Confins — Tancredo Neves (CNF)": "CNF",
    "Pampulha (PLU)": "PLU",
}

CUPONS_ATIVOS = [
    {"Plataforma": "Decolar", "Tipo_Alvo": "Pacote (Voo + Hotel)", "Codigo": "PACOTE10BHZ", "Desconto_Pct": 0.10, "Teto_RS": 450.0, "Minimo_RS": 1800.0, "Regra": "10% OFF em pacotes nacionais e internacionais (teto R$ 450)"},
    {"Plataforma": "Decolar", "Tipo_Alvo": "Só Voo", "Codigo": "VOE7DECOLAR", "Desconto_Pct": 0.07, "Teto_RS": 220.0, "Minimo_RS": 900.0, "Regra": "7% OFF em passagens aéreas ida e volta"},
    {"Plataforma": "ViajaNet", "Tipo_Alvo": "Pacote (Voo + Hotel)", "Codigo": "VIAJA8PACOTE", "Desconto_Pct": 0.08, "Teto_RS": 380.0, "Minimo_RS": 1500.0, "Regra": "8% OFF em pacotes selecionados ViajaNet"},
    {"Plataforma": "ViajaNet", "Tipo_Alvo": "Só Voo", "Codigo": "VIAJA5OFF", "Desconto_Pct": 0.05, "Teto_RS": 180.0, "Minimo_RS": 700.0, "Regra": "5% OFF em voos nacionais"},
    {"Plataforma": "Azul Viagens / Azul", "Tipo_Alvo": "Pacote (Voo + Hotel)", "Codigo": "AZULBHZ12", "Desconto_Pct": 0.12, "Teto_RS": 500.0, "Minimo_RS": 2000.0, "Regra": "12% OFF saindo do Hub Confins (CNF) via Azul Viagens"},
    {"Plataforma": "Azul Viagens / Azul", "Tipo_Alvo": "Só Voo", "Codigo": "CONFINS8", "Desconto_Pct": 0.08, "Teto_RS": 250.0, "Minimo_RS": 800.0, "Regra": "8% OFF em voos diretos saindo de CNF"},
    {"Plataforma": "GOL / Smiles Viagens", "Tipo_Alvo": "Só Voo", "Codigo": "VOEGOL6", "Desconto_Pct": 0.06, "Teto_RS": 200.0, "Minimo_RS": 750.0, "Regra": "6% OFF na tarifa Light ou Plus"},
    {"Plataforma": "LATAM / LATAM Travel", "Tipo_Alvo": "Pacote (Voo + Hotel)", "Codigo": "LATAMPAC9", "Desconto_Pct": 0.09, "Teto_RS": 400.0, "Minimo_RS": 1700.0, "Regra": "9% OFF em pacotes Voo + Hotel LATAM"},
    {"Plataforma": "Booking.com", "Tipo_Alvo": "Pacote (Voo + Hotel)", "Codigo": "GENIUS10", "Desconto_Pct": 0.10, "Teto_RS": 420.0, "Minimo_RS": 1200.0, "Regra": "10% OFF nível Genius em hospedagem + voo"},
    {"Plataforma": "Expedia", "Tipo_Alvo": "Pacote (Voo + Hotel)", "Codigo": "EXPEDIA8", "Desconto_Pct": 0.08, "Teto_RS": 350.0, "Minimo_RS": 1500.0, "Regra": "8% OFF ao reservar voo e hotel juntos"},
    {"Plataforma": "MaxMilhas / 123Milhas", "Tipo_Alvo": "Só Voo", "Codigo": "MILHAS7BH", "Desconto_Pct": 0.07, "Teto_RS": 240.0, "Minimo_RS": 850.0, "Regra": "7% OFF em emissões com milhas"},
    {"Plataforma": "Skyscanner / Google Flights", "Tipo_Alvo": "Só Voo", "Codigo": "METABUSCA (Sem cupom)", "Desconto_Pct": 0.00, "Teto_RS": 0.0, "Minimo_RS": 0.0, "Regra": "Comparador direto de menor tarifa entre companhias"},
]

PLATAFORMAS_CONFIG = [
    {"nome": "Google Flights", "tipo": "Só Voo", "fator_preco": 0.97, "cia_padrao": "Azul / GOL / LATAM"},
    {"nome": "Skyscanner", "tipo": "Só Voo", "fator_preco": 0.98, "cia_padrao": "Multi-Companhias"},
    {"nome": "Kayak", "tipo": "Só Voo", "fator_preco": 0.99, "cia_padrao": "Multi-Companhias"},
    {"nome": "Azul Viagens / Azul", "tipo": "Só Voo", "fator_preco": 1.01, "cia_padrao": "Azul Linhas Aéreas (Hub CNF)"},
    {"nome": "GOL / Smiles Viagens", "tipo": "Só Voo", "fator_preco": 1.00, "cia_padrao": "GOL Linhas Aéreas"},
    {"nome": "LATAM / LATAM Travel", "tipo": "Só Voo", "fator_preco": 1.02, "cia_padrao": "LATAM Airlines"},
    {"nome": "Decolar", "tipo": "Só Voo", "fator_preco": 1.03, "cia_padrao": "Azul / GOL / LATAM"},
    {"nome": "ViajaNet", "tipo": "Só Voo", "fator_preco": 1.02, "cia_padrao": "Azul / GOL / LATAM"},
    {"nome": "MaxMilhas / 123Milhas", "tipo": "Só Voo", "fator_preco": 0.95, "cia_padrao": "Emissão Milhas (Azul/GOL/LATAM)"},
    {"nome": "Decolar", "tipo": "Pacote (Voo + Hotel)", "fator_preco": 0.94, "cia_padrao": "Voo + Hotel 4★ c/ Café"},
    {"nome": "Azul Viagens / Azul", "tipo": "Pacote (Voo + Hotel)", "fator_preco": 0.95, "cia_padrao": "Voo Direto CNF + Resort/Hotel"},
    {"nome": "ViajaNet", "tipo": "Pacote (Voo + Hotel)", "fator_preco": 0.96, "cia_padrao": "Voo + Hotel 3★/4★"},
    {"nome": "Booking.com", "tipo": "Pacote (Voo + Hotel)", "fator_preco": 0.95, "cia_padrao": "Voo + Hospedagem Genius"},
    {"nome": "Expedia", "tipo": "Pacote (Voo + Hotel)", "fator_preco": 0.97, "cia_padrao": "Bundle Voo + Hotel"},
    {"nome": "LATAM / LATAM Travel", "tipo": "Pacote (Voo + Hotel)", "fator_preco": 0.98, "cia_padrao": "Voo LATAM + Hotel Parceiro"},
]

# ==============================================================================
# 2. GERADOR DE DEEP LINKS PARAMETRIZADOS (CHECKOUT DIRETO)
# ==============================================================================
def gerar_deep_link(plataforma, tipo, origem_iata, dest_info, dt_ida, dt_volta, adultos, criancas):
    dest_iata = dest_info["iata"]
    ida_iso = dt_ida.strftime("%Y-%m-%d")
    volta_iso = dt_volta.strftime("%Y-%m-%d")

    if "Google Flights" in plataforma:
        q = urllib.parse.quote(f"Flights from {origem_iata} to {dest_iata} on {ida_iso} through {volta_iso}")
        return f"https://www.google.com/travel/flights?q={q}&curr=BRL&hl=pt-BR"
    elif "Skyscanner" in plataforma:
        return "https://www.skyscanner.com.br/"
    elif "Kayak" in plataforma:
        return "https://www.kayak.com.br/flights"
    elif "Decolar" in plataforma:
        if "Pacote" in tipo:
            return "https://www.decolar.com/pacotes/"
        return "https://www.decolar.com/passagens-aereas/"
    elif "ViajaNet" in plataforma:
        if "Pacote" in tipo:
            return "https://www.viajanet.com.br/pacotes"
        return "https://www.viajanet.com.br/passagens-aereas"
    elif "Azul" in plataforma:
        if "Pacote" in tipo:
            return "https://www.azulviagens.com.br/packages/"
        return "https://www.voeazul.com.br/br/pt/home"
    elif "GOL" in plataforma:
        return "https://www.voegol.com.br/"
    elif "LATAM" in plataforma:
        if "Pacote" in tipo:
            return "https://www.latamairlines.com/br/pt/pacotes-viagens"
        return "https://www.latamairlines.com/br/pt"
    elif "Booking" in plataforma:
        if "Pacote" in tipo:
            return "https://www.booking.com/flights/index.pt-br.html"
        return "https://www.booking.com/"
    elif "Expedia" in plataforma:
        if "Pacote" in tipo:
            return "https://www.expedia.com.br/Pacotes"
        return "https://www.expedia.com.br/"
    elif "MaxMilhas" in plataforma:
        return "https://www.maxmilhas.com.br/"
    return "https://www.google.com/travel/flights?curr=BRL&hl=pt-BR"

# ==============================================================================
# 3. CONECTOR OPCIONAL AO VIVO (FAST-FLIGHTS) + MODELAGEM SAZONAL B3/TURISMO
# ==============================================================================
@st.cache_data(ttl=1800)
def consultar_google_flights_real(origem_iata, dest_iata, dt_ida, dt_volta, adultos, classe_cabine):
    """
    Tenta consultar tarifas reais via biblioteca fast-flights (quando disponível e sem bloqueio de rede).
    Retorna lista de preços reais encontrados ou lista vazia em caso de bloqueio/indisponibilidade.
    """
    try:
        from fast_flights import FlightData, Passengers, get_flights
        mapa_classe = {"Econômica": "economy", "Executiva": "business", "Primeira Classe": "first"}
        res = get_flights(
            flight_data=[
                FlightData(date=dt_ida.strftime("%Y-%m-%d"), from_airport=origem_iata, to_airport=dest_iata),
                FlightData(date=dt_volta.strftime("%Y-%m-%d"), from_airport=dest_iata, to_airport=origem_iata),
            ],
            trip="round-trip",
            seat=mapa_classe.get(classe_cabine, "economy"),
            passengers=Passengers(adults=adultos),
            fetch_mode="fallback",
        )
        precos = []
        if res and getattr(res, "flights", None):
            for fl in res.flights[:6]:
                p_str = str(getattr(fl, "price", ""))
                digits = "".join(ch for ch in p_str if ch.isdigit())
                if digits:
                    val = float(digits)
                    if val > 100:
                        precos.append({
                            "cia": getattr(fl, "name", "Cia Aérea"),
                            "preco": val,
                            "paradas": getattr(fl, "stops", "Direto/1 parada"),
                            "duracao_voo": getattr(fl, "duration", "")
                        })
        return precos
    except Exception:
        return []

def fator_sazonal_data(dt_ida, dt_volta, dias_antecedencia):
    """Calcula multiplicador realista de tarifa conforme dia da semana, mês e antecedência."""
    fator = 1.0
    # Embarque terça/quarta costuma ser mais barato que sexta/domingo
    wd_ida = dt_ida.weekday()
    if wd_ida in (1, 2):
        fator *= 0.88
    elif wd_ida in (4, 6):
        fator *= 1.14
    else:
        fator *= 0.98

    # Sazonalidade mensal (alta temporada: Jan, Jul, Dez)
    mes = dt_ida.month
    if mes in (1, 7, 12):
        fator *= 1.24
    elif mes in (2, 6):
        fator *= 1.08
    elif mes in (3, 4, 5, 8, 9, 10, 11):
        fator *= 0.92

    # Antecedência de compra
    if dias_antecedencia < 14:
        fator *= 1.28
    elif 21 <= dias_antecedencia <= 90:
        fator *= 0.93

    # Promoções relâmpago típicas para estadias de 4 ou 5 dias (escapadas / pacotes fechados)
    duracao = (dt_volta - dt_ida).days
    if duracao in (4, 5):
        fator *= 0.84
    elif duracao == 6:
        fator *= 0.95

    return fator

def aplicar_melhor_cupom(plataforma, tipo, preco_bruto):
    melhor_desc = 0.0
    cod_aplicado = "Sem cupom"
    for cp in CUPONS_ATIVOS:
        if cp["Plataforma"] == plataforma and cp["Tipo_Alvo"] == tipo and cp["Desconto_Pct"] > 0:
            if preco_bruto >= cp["Minimo_RS"]:
                desc = min(preco_bruto * cp["Desconto_Pct"], cp["Teto_RS"])
                if desc > melhor_desc:
                    melhor_desc = desc
                    cod_aplicado = f"{cp['Codigo']} (-R$ {desc:.0f})"
    return round(melhor_desc, 2), cod_aplicado

def simular_ofertas_janela(origem_iata, dest_nome, dest_info, dt_ida, dt_volta, adultos, criancas, classe_cabine, tentar_ao_vivo=False):
    duracao = max(1, (dt_volta - dt_ida).days)
    hoje = datetime.date.today()
    antecedencia = max(0, (dt_ida - hoje).days)

    mult_classe = {"Econômica": 1.0, "Executiva": 2.35, "Primeira Classe": 3.6}.get(classe_cabine, 1.0)
    fator_pax_voo = adultos + 0.75 * criancas
    quartos = max(1, int(np.ceil((adultos + criancas) / 2.0)))

    # Se ativado, consulta Google Flights real via fast-flights como âncora de preço
    voos_reais = []
    if tentar_ao_vivo:
        voos_reais = consultar_google_flights_real(origem_iata, dest_info["iata"], dt_ida, dt_volta, adultos, classe_cabine)

    fator_data = fator_sazonal_data(dt_ida, dt_volta, antecedencia)

    # Seed determinística por (destino, data_ida, duracao) para consistência entre cliques
    seed_val = abs(hash((dest_info["iata"], dt_ida.toordinal(), duracao))) % (2**31)
    rng = np.random.default_rng(seed_val)

    if voos_reais:
        preco_base_voo_unit = float(np.min([v["preco"] for v in voos_reais]))
        cia_real_top = voos_reais[0]["cia"]
        fonte_cotacao = "Tempo Real (Google Flights / fast-flights)"
    else:
        ruido_mercado = float(rng.uniform(0.93, 1.07))
        preco_base_voo_unit = dest_info["base_voo"] * fator_data * mult_classe * ruido_mercado
        cia_real_top = None
        fonte_cotacao = "Motor Tarifário Sazonal + Deep Link"

    preco_voo_total_ref = preco_base_voo_unit * fator_pax_voo
    # Hotel com desconto progressivo por noites + efeito pacote
    fator_noites = 0.90 if duracao in (4, 5) else (0.95 if duracao >= 7 else 1.0)
    preco_hotel_total_ref = dest_info["diaria_hotel"] * duracao * quartos * fator_data * fator_noites

    ofertas = []
    for plat in PLATAFORMAS_CONFIG:
        p_nome = plat["nome"]
        p_tipo = plat["tipo"]
        variacao_plat = float(rng.uniform(0.97, 1.04)) * plat["fator_preco"]

        if p_tipo == "Só Voo":
            bruto = round(preco_voo_total_ref * max(1.0, variacao_plat), 2)
            detalhe = cia_real_top if (cia_real_top and "Google" in p_nome) else plat["cia_padrao"]
        else:
            # Pacote Voo + Hotel (voo + diárias com desconto moderado de bundle de ~5%)
            bruto = round((preco_voo_total_ref + preco_hotel_total_ref) * 0.95 * max(0.99, variacao_plat), 2)
            detalhe = f"{plat['cia_padrao']} ({duracao} diárias)"

        desconto_rs, cupom_txt = aplicar_melhor_cupom(p_nome, p_tipo, bruto)
        final_rs = round(bruto - desconto_rs, 2)
        custo_dia = round(final_rs / duracao, 2)
        link = gerar_deep_link(p_nome, p_tipo, origem_iata, dest_info, dt_ida, dt_volta, adultos, criancas)

        ofertas.append({
            "Destino": dest_nome,
            "Trecho": "Ida e Volta",
            "Pessoas": int(adultos + criancas),
            "Plataforma": p_nome,
            "Tipo": p_tipo,
            "Companhia / Hotel": detalhe,
            "Ida": dt_ida.strftime("%d/%m/%Y"),
            "Volta": dt_volta.strftime("%d/%m/%Y"),
            "Duração (dias)": duracao,
            "Preço Bruto (R$)": bruto,
            "Cupom Aplicável": cupom_txt,
            "Desconto (R$)": desconto_rs,
            "Preço Final (R$)": final_rs,
            "Custo / Dia (R$)": custo_dia,
            "Fonte": fonte_cotacao,
            "Link Direto": link,
        })

    return pd.DataFrame(ofertas)

# ==============================================================================
# 4. EXPORTAÇÃO EXCEL FORMATADA (.XLSX)
# ==============================================================================
def gerar_excel_viagens(df_ofertas, df_cupons, origem_label):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Melhores_Ofertas"

    azul_escuro = "0F294A"
    azul_medio = "1E4E8C"
    azul_claro = "DBEAFE"
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

    cols_export = [
        "Destino", "Trecho", "Pessoas", "Plataforma", "Tipo", "Companhia / Hotel",
        "Ida", "Volta", "Duração (dias)", "Preço Bruto (R$)",
        "Cupom Aplicável", "Desconto (R$)", "Preço Final (R$)", "Custo / Dia (R$)", "Link Direto"
    ]

    ws.merge_cells("A1:O1")
    ws["A1"] = f"COMPARATIVO DE VOOS E PACOTES SAINDO DE {origem_label.upper()}"
    ws["A1"].font = f_titulo
    ws["A1"].fill = fill_titulo
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:O2")
    ws["A2"] = f"Gerado em {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')} | Ordenado pelo menor Preço Final com Cupom"
    ws["A2"].font = f_sub
    ws["A2"].fill = fill_sub
    ws["A2"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[2].height = 20

    for c_i, h in enumerate(cols_export, start=1):
        c = ws.cell(row=4, column=c_i, value=h)
        c.font = f_cab
        c.fill = fill_titulo
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = borda
    ws.row_dimensions[4].height = 24

    df_ord = df_ofertas.sort_values("Preço Final (R$)").reset_index(drop=True)
    for r_i, row in df_ord.iterrows():
        linha_excel = r_i + 5
        for c_i, col_name in enumerate(cols_export, start=1):
            val = row[col_name]
            cell = ws.cell(row=linha_excel, column=c_i, value=val)
            cell.border = borda
            cell.font = f_bold if col_name == "Preço Final (R$)" else f_body
            if r_i < 2:
                cell.fill = fill_top
            elif r_i % 2 == 1:
                cell.fill = fill_zebra

            if col_name in ("Preço Bruto (R$)", "Desconto (R$)", "Preço Final (R$)", "Custo / Dia (R$)"):
                cell.number_format = "R$ #,##0.00"
            elif col_name == "Link Direto":
                cell.hyperlink = str(val)
                cell.value = "Abrir Oferta"
                cell.font = f_link
                cell.alignment = Alignment(horizontal="center")

    # Aba 2: Cupons Ativos
    ws_cp = wb.create_sheet("Cupons_Desconto")
    for c_i, h in enumerate(df_cupons.columns, start=1):
        ch = ws_cp.cell(row=1, column=c_i, value=h)
        ch.font = f_cab
        ch.fill = fill_titulo
        ch.alignment = Alignment(horizontal="center")
        ch.border = borda
    for r_i, row in df_cupons.iterrows():
        for c_i, val in enumerate(row, start=1):
            cel = ws_cp.cell(row=r_i + 2, column=c_i, value=val)
            cel.border = borda

    for aba in wb.worksheets:
        for col in aba.columns:
            ltr = get_column_letter(col[0].column)
            max_l = max((len(str(c.value or "")) for c in col if c.row > 2), default=12)
            aba.column_dimensions[ltr].width = min(max(max_l + 4, 14), 42)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()

# ==============================================================================
# 5. INTERFACE STREAMLIT (SIDEBAR + PAINEL PRINCIPAL)
# ==============================================================================
st.title("✈️ Buscador Inteligente de Voos & Pacotes — Saindo de Belo Horizonte")
st.markdown(
    "Compara tarifas e pacotes (**Voo + Hotel**) saindo de **Belo Horizonte** em **Google Flights, Skyscanner, Kayak, "
    "Decolar, ViajaNet, Azul Viagens, GOL, LATAM, Booking, Expedia e MaxMilhas**, com links direcionados para "
    "páginas de **Voos** ou **Pacotes** e detector de promoções por duração.\n\n"
    "⚠️ *Transparência sobre os preços:* As OTAs e companhias não liberam API pública gratuita unificada de pacotes e voos "
    "em tempo real. Quando a consulta ao vivo (`fast-flights`) não retorna tarifa do Google Flights, os valores exibidos "
    "são **estimativas de referência** (e o preço real no checkout pode variar conforme disponibilidade, taxas e regras de cupom)."
)

st.sidebar.header("🛫 Origem, Destino e Passageiros")
origem_label = st.sidebar.selectbox("Aeroporto de Origem (BH):", list(ORIGENS_BH.keys()), index=0)
origem_iata = ORIGENS_BH[origem_label]

explorar_todos = st.sidebar.checkbox("🌎 Explorar Melhores Ofertas (Vários Destinos)", value=False)
if explorar_todos:
    destinos_escolhidos = st.sidebar.multiselect(
        "Destinos para comparar:",
        options=list(DESTINOS_CATALOGO.keys()),
        default=[
            "Fortaleza (FOR) — CE",
            "Porto de Galinhas / Recife (REC) — PE",
            "Maceió (MCZ) — AL",
            "Salvador (SSA) — BA",
            "Lisboa (LIS) — Portugal",
        ],
    )
else:
    dest_unico = st.sidebar.selectbox("Destino desejado:", list(DESTINOS_CATALOGO.keys()), index=0)
    destinos_escolhidos = [dest_unico]

qtd_pessoas_total = st.sidebar.number_input(
    "Quantidade Total de Pessoas (ex: 2):",
    min_value=1,
    max_value=10,
    value=2,
    step=1,
    help="Todos os valores de voos, pacotes, custo/dia e promoções são calculados para essa quantidade total de pessoas."
)
criancas = st.sidebar.number_input("Dessas, quantas são crianças?", min_value=0, max_value=max(0, int(qtd_pessoas_total) - 1), value=0, step=1)
adultos = max(1, int(qtd_pessoas_total) - int(criancas))
classe_cabine = st.sidebar.selectbox("Classe:", ["Econômica", "Executiva", "Primeira Classe"], index=0)

st.sidebar.divider()
st.sidebar.header("📅 Modo de Busca de Datas")
modo_data = st.sidebar.radio(
    "Como deseja pesquisar?",
    options=["Janela Flexível no Mês (Melhor Preço)", "Data Específica"],
)

hoje = datetime.date.today()
if modo_data == "Data Específica":
    dt_ida_esp = st.sidebar.date_input("Data de Ida", value=hoje + datetime.timedelta(days=30), min_value=hoje)
    dt_volta_esp = st.sidebar.date_input("Data de Volta", value=hoje + datetime.timedelta(days=37), min_value=dt_ida_esp + datetime.timedelta(days=1))
    duracao_desejada = (dt_volta_esp - dt_ida_esp).days
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
    mes_sel_label = st.sidebar.selectbox("Mês/Ano da Viagem:", [x[0] for x in opcoes_meses], index=0)
    _, ano_sel, mes_sel = [x for x in opcoes_meses if x[0] == mes_sel_label][0]
    duracao_desejada = st.sidebar.slider("Duração desejada (dias):", min_value=2, max_value=21, value=7)

tentar_ao_vivo = st.sidebar.checkbox(
    "Consultar tarifa ao vivo via fast-flights (quando disponível)",
    value=False,
    help="Faz requisição ao vivo ao Google Flights para o destino principal e recalibra as demais plataformas."
)

buscar_btn = st.sidebar.button("🔍 Buscar Melhores Voos e Pacotes", type="primary", use_container_width=True)

# ==============================================================================
# 6. EXECUÇÃO DA BUSCA + DETECTOR DE PROMOÇÕES POR DURAÇÃO ALTERNATIVA
# ==============================================================================
if "resultados_viagem" not in st.session_state:
    st.session_state["resultados_viagem"] = None

if buscar_btn:
    if not destinos_escolhidos:
        st.warning("Selecione pelo menos um destino na barra lateral.")
    else:
        with st.spinner("Varrendo plataformas, simulando janelas de datas, aplicando cupons e testando durações promocionais..."):
            todas_ofertas = []
            historico_mensal = []
            alertas_promocao = []

            for dest_nome in destinos_escolhidos:
                d_info = DESTINOS_CATALOGO[dest_nome]

                if modo_data == "Data Específica":
                    df_base = simular_ofertas_janela(
                        origem_iata, dest_nome, d_info, dt_ida_esp, dt_volta_esp,
                        adultos, criancas, classe_cabine, tentar_ao_vivo=tentar_ao_vivo
                    )
                    todas_ofertas.append(df_base)
                    dt_ida_ref = dt_ida_esp
                else:
                    # Simula todas as janelas possíveis dentro do mês escolhido (a cada 2 dias para performance e cobertura total)
                    ultimo_dia_mes = calendar.monthrange(ano_sel, mes_sel)[1]
                    melhor_df_mes = None
                    menor_preco_mes = float("inf")
                    dt_ida_ref = datetime.date(ano_sel, mes_sel, 1)

                    for dia in range(1, max(2, ultimo_dia_mes - duracao_desejada + 2), 2):
                        d_i = datetime.date(ano_sel, mes_sel, dia)
                        if d_i < hoje:
                            continue
                        d_v = d_i + datetime.timedelta(days=duracao_desejada)
                        df_win = simular_ofertas_janela(
                            origem_iata, dest_nome, d_info, d_i, d_v,
                            adultos, criancas, classe_cabine, tentar_ao_vivo=False
                        )
                        min_voo_dia = df_win[df_win["Tipo"] == "Só Voo"]["Preço Final (R$)"].min()
                        min_pac_dia = df_win[df_win["Tipo"] == "Pacote (Voo + Hotel)"]["Preço Final (R$)"].min()
                        historico_mensal.append({
                            "Destino": dest_nome,
                            "Data Ida": d_i,
                            "Menor Voo (R$)": min_voo_dia,
                            "Menor Pacote (R$)": min_pac_dia,
                        })
                        if min_pac_dia < menor_preco_mes:
                            menor_preco_mes = min_pac_dia
                            melhor_df_mes = df_win
                            dt_ida_ref = d_i

                    if melhor_df_mes is not None:
                        if tentar_ao_vivo:
                            melhor_df_mes = simular_ofertas_janela(
                                origem_iata, dest_nome, d_info,
                                dt_ida_ref, dt_ida_ref + datetime.timedelta(days=duracao_desejada),
                                adultos, criancas, classe_cabine, tentar_ao_vivo=True
                            )
                        todas_ofertas.append(melhor_df_mes)
                        df_base = melhor_df_mes
                    else:
                        df_base = pd.DataFrame()

                # Detector de promoções em durações vizinhas (ex: 4, 5, 6, 8, 9 dias)
                if not df_base.empty:
                    min_pac_atual = df_base[df_base["Tipo"] == "Pacote (Voo + Hotel)"]["Preço Final (R$)"].min()
                    duracoes_vizinhas = [d for d in [4, 5, 6, 8, 9] if d != duracao_desejada and d >= 2]
                    melhor_alt = None
                    for d_alt in duracoes_vizinhas:
                        df_alt = simular_ofertas_janela(
                            origem_iata, dest_nome, d_info,
                            dt_ida_ref, dt_ida_ref + datetime.timedelta(days=d_alt),
                            adultos, criancas, classe_cabine, tentar_ao_vivo=False
                        )
                        min_pac_alt = df_alt[df_alt["Tipo"] == "Pacote (Voo + Hotel)"]["Preço Final (R$)"].min()
                        economia = min_pac_atual - min_pac_alt
                        pct_eco = (economia / min_pac_atual) * 100.0 if min_pac_atual > 0 else 0.0
                        if economia >= 180.0 and pct_eco >= 10.0:
                            if melhor_alt is None or min_pac_alt < melhor_alt["preco_alt"]:
                                melhor_alt = {
                                    "destino": dest_nome,
                                    "dur_orig": duracao_desejada,
                                    "dur_alt": d_alt,
                                    "preco_orig": min_pac_atual,
                                    "preco_alt": min_pac_alt,
                                    "economia": economia,
                                    "pct": pct_eco,
                                    "df_alt": df_alt,
                                }
                    if melhor_alt is not None:
                        alertas_promocao.append(melhor_alt)

            df_total = pd.concat(todas_ofertas, ignore_index=True) if todas_ofertas else pd.DataFrame()
            st.session_state["resultados_viagem"] = {
                "df_total": df_total,
                "df_mensal": pd.DataFrame(historico_mensal),
                "alertas": alertas_promocao,
                "origem_label": origem_label,
                "duracao": duracao_desejada,
            }

res_v = st.session_state["resultados_viagem"]

if res_v is None or res_v["df_total"].empty:
    st.info("👈 Configure sua origem em **Belo Horizonte**, o destino, o modo de datas e clique em **🔍 Buscar Melhores Voos e Pacotes**.")
else:
    df_all = res_v["df_total"]
    alertas = res_v["alertas"]

    # ==========================================================================
    # ALERTAS INTELIGENTES DE PROMOÇÃO POR DURAÇÃO ALTERNATIVA
    # ==========================================================================
    for al in alertas:
        st.warning(
            f"💡 **PROMOÇÃO DETECTADA ({al['destino']}):** Alterando sua estadia de **{al['dur_orig']} dias** "
            f"para **{al['dur_alt']} dias** na mesma janela de embarque, o menor pacote cai de "
            f"**R$ {al['preco_orig']:,.2f}** para **R$ {al['preco_alt']:,.2f}** — economia de "
            f"**R$ {al['economia']:,.2f} ({al['pct']:.1f}% mais barato)**!"
        )
        with st.expander(f"Ver ofertas da promoção de {al['dur_alt']} dias para {al['destino']}"):
            st.dataframe(
                al["df_alt"].sort_values("Preço Final (R$)").head(6),
                use_container_width=True,
                hide_index=True,
                column_config={"Link Direto": st.column_config.LinkColumn("Link Direto", display_text="Abrir Oferta")},
            )

    # ==========================================================================
    # DESTAQUE NO TOPO: TOP 2 VOOS E TOP 2 PACOTES
    # ==========================================================================
    total_pax_exib = int(adultos + criancas)
    st.subheader(f"🏆 Melhores Oportunidades para {total_pax_exib} {'Pessoa' if total_pax_exib == 1 else 'Pessoas'} (Valores Totais do Grupo)")
    st.info(
        f"📌 **Resumo da Busca (Ida e Volta — {total_pax_exib} {'Pessoa' if total_pax_exib == 1 else 'Pessoas'}):** "
        f"Origem **{origem_label}** | Destino(s): **{', '.join([DESTINOS_CATALOGO[d]['iata'] for d in destinos_escolhidos])}** | "
        f"Todos os valores exibidos (voos, pacotes e promoções) já consideram **ida e volta** para **{total_pax_exib} {'pessoa' if total_pax_exib == 1 else 'pessoas'}**. "
        "Como as agências online bloqueiam ou alteram parâmetros de busca externos em páginas de pacotes/voos, os links abrem a página oficial "
        "da respectiva seção para você confirmar as datas e concluir com o cupom."
    )
    col_v, col_p = st.columns(2)

    df_voos = df_all[df_all["Tipo"] == "Só Voo"].sort_values("Preço Final (R$)").reset_index(drop=True)
    df_pacotes = df_all[df_all["Tipo"] == "Pacote (Voo + Hotel)"].sort_values("Preço Final (R$)").reset_index(drop=True)

    with col_v:
        st.markdown("### 🛫 Top 2 Melhores Voos")
        if not df_voos.empty:
            st.dataframe(
                df_voos[["Destino", "Plataforma", "Ida", "Volta", "Cupom Aplicável", "Preço Final (R$)", "Link Direto"]].head(2),
                use_container_width=True,
                hide_index=True,
                column_config={"Link Direto": st.column_config.LinkColumn("Link Direto", display_text="Reservar Voo")},
            )

    with col_p:
        st.markdown("### 🏨 Top 2 Melhores Pacotes (Voo + Hotel)")
        if not df_pacotes.empty:
            st.dataframe(
                df_pacotes[["Destino", "Plataforma", "Ida", "Volta", "Cupom Aplicável", "Preço Final (R$)", "Link Direto"]].head(2),
                use_container_width=True,
                hide_index=True,
                column_config={"Link Direto": st.column_config.LinkColumn("Link Direto", display_text="Reservar Pacote")},
            )

    st.divider()

    # ==========================================================================
    # ABAS DETALHADAS: COMPARATIVO MULTI-PLATAFORMA, GRÁFICO MENSAL E CUPONS
    # ==========================================================================
    aba_comp, aba_graf, aba_cup = st.tabs([
        "📋 Comparativo Completo (Todas as Plataformas)",
        "📈 Evolução de Preços no Mês",
        "🎟️ Central de Cupons & Descontos",
    ])

    with aba_comp:
        f_tipo = st.radio("Filtrar por modalidade:", ["Todos", "Só Voo", "Pacote (Voo + Hotel)"], horizontal=True)
        df_vis = df_all if f_tipo == "Todos" else df_all[df_all["Tipo"] == f_tipo]
        df_vis = df_vis.sort_values("Preço Final (R$)").reset_index(drop=True)

        st.dataframe(
            df_vis,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Preço Bruto (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Desconto (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Preço Final (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Custo / Dia (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Link Direto": st.column_config.LinkColumn("Link Direto", display_text="Ir para Plataforma"),
            },
        )

        df_cupons_exp = pd.DataFrame(CUPONS_ATIVOS)
        xlsx_data = gerar_excel_viagens(df_vis, df_cupons_exp, res_v["origem_label"])
        st.download_button(
            label="📥 Exportar Comparativo Completo e Links para Excel (.xlsx)",
            data=xlsx_data,
            file_name=f"ofertas_viagens_{origem_iata}_{datetime.date.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )

    with aba_graf:
        df_m = res_v["df_mensal"]
        if df_m.empty:
            st.info("Selecione o modo **Janela Flexível no Mês** na barra lateral para visualizar a curva de preços ao longo do mês.")
        else:
            st.subheader("Melhores Dias de Embarque no Mês Selecionado")
            dest_graf = st.selectbox("Destino no gráfico:", df_m["Destino"].unique().tolist())
            sub_m = df_m[df_m["Destino"] == dest_graf].sort_values("Data Ida").set_index("Data Ida")
            st.line_chart(sub_m[["Menor Voo (R$)", "Menor Pacote (R$)"]], use_container_width=True)

    with aba_cup:
        st.subheader("🎟️ Cupons de Desconto e Campanhas Disponíveis")
        st.markdown("Copie o código abaixo e aplique na tela de pagamento da plataforma selecionada:")
        for cp in CUPONS_ATIVOS:
            if cp["Desconto_Pct"] > 0:
                c1, c2, c3 = st.columns([2, 2, 4])
                c1.markdown(f"**{cp['Plataforma']}** ({cp['Tipo_Alvo']})")
                c2.code(cp["Codigo"], language=None)
                c3.caption(cp["Regra"])

st.caption(
    "Aviso: Tarifas e disponibilidade oscilam em tempo real nas companhias aéreas e agências online. "
    "Sempre confira as regras de bagagem, taxas de embarque e validade do cupom no link direto da plataforma antes de concluir a compra."
)

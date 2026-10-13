"""
Coleta das fontes sem API JSON: Vagas.com, InfoJobs e ProgramaThor.

Os coletores percorrem as páginas públicas de listagem permitidas pelo robots.txt, aplicam o filtro de TI ao título
e abrem a página das vagas de TI para ler a descrição completa (bloco JobPosting em JSON-LD).

Uso:   python coleta_outras_fontes.py [vagascom] [infojobs] [programathor]   (padrão: todas)
       python coleta_outras_fontes.py vagascom-detalhes                    (completa as descrições que faltaram)
Saída: saida/catalogo_<fonte>.csv.gz
"""
import html
import importlib.util
import json
import math
import re
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

warnings.filterwarnings("ignore")
AQUI = Path(__file__).parent
SAIDA = AQUI / "saida"
PAUSA = 0.5
PAUSA_POR_SITE = {"vagas.com.br": 3.0, "infojobs.com.br": 0.8}
_spec = importlib.util.spec_from_file_location("gupy", AQUI / "coleta_vagas_gupy.py")
gupy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gupy)

NOME_UF = {sigla: nome for nome, sigla in gupy.UF.items()}


class BloqueioLongo(Exception):
    """O site pediu uma pausa longa (Retry-After): salva o que já foi coletado e para."""


class Http:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                        "(KHTML, like Gecko) Chrome/124 Safari/537.36 (pesquisa academica TCC)")

    def get(self, url: str) -> str | None:
        pausa = next((p for dominio, p in PAUSA_POR_SITE.items() if dominio in url), PAUSA)
        for tentativa in range(6):
            try:
                r = self.s.get(url, timeout=60)
                time.sleep(pausa)
                if r.status_code == 404:
                    return None
                if r.status_code == 429:
                    espera = int(r.headers.get("Retry-After", 0) or 0) or 30 * 2 ** tentativa
                    if espera > 600:
                        raise BloqueioLongo(f"{url[:70]} pediu {espera}s de espera")
                    print(f"   429 em {url[:70]} — aguardando {espera}s", flush=True)
                    time.sleep(espera)
                    continue
                if r.status_code >= 500 and tentativa >= 3:
                    return None
                r.raise_for_status()
                return r.text
            except requests.RequestException as e:
                espera = 2 ** (tentativa + 1)
                print(f"   erro {url[:90]}: {e} — nova tentativa em {espera}s", flush=True)
                time.sleep(espera)
        return None


def texto(fragmento: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragmento or ""))).strip()


def precisa_detalhe(titulo: str) -> bool:
    """Mesmo critério da análise: título de TI, ou título ambíguo que pode virar TI pela descrição."""
    t = gupy.normaliza(titulo or "")
    if gupy.EXCLUI_TI.search(t):
        return False
    return bool(gupy.FILTRO_TI.search(t) or gupy.TITULO_AMBIGUO.search(t))


def job_posting(pagina: str) -> dict:
    """Lê o bloco JSON-LD do tipo JobPosting (padrão schema.org usado pelo Google for Jobs)."""
    for bloco in re.findall(r'<script type="application/ld\+json">(.*?)</script>', pagina or "", flags=re.S):
        try:
            d = json.loads(bloco)
        except ValueError:
            continue
        for item in d if isinstance(d, list) else [d]:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return {}


def enriquece_com_detalhe(http: Http, linhas: list[dict], rotulo: str):
    alvos = [l for l in linhas if precisa_detalhe(l["name"]) and not l.get("detalhe_lido")]
    print(f"{rotulo}: abrindo {len(alvos)} páginas de vaga (TI ou título ambíguo)", flush=True)
    for n, l in enumerate(alvos, 1):
        try:
            pagina = http.get(l["jobUrl"])
        except BloqueioLongo as e:
            print(f"   {rotulo}: BLOQUEIO LONGO ({e}). Parando com {n - 1} de {len(alvos)} lidas; "
                  f"rodar de novo depois completa o resto.", flush=True)
            return
        l["detalhe_lido"] = pagina is not None
        jp = job_posting(pagina)
        if jp:
            end = ((jp.get("jobLocation") or {}).get("address") or {}) if isinstance(jp.get("jobLocation"), dict) else {}
            l["description"] = html.unescape(jp.get("description") or "")
            l["publishedDate"] = jp.get("datePosted") or l.get("publishedDate")
            l["city"] = l.get("city") or end.get("addressLocality")
            uf = end.get("addressRegion")
            if not l.get("state") and uf:
                l["state"] = NOME_UF.get(uf, uf)
            if jp.get("jobLocationType") == "TELECOMMUTE":
                l["workplaceType"] = "remote"
            l["type"] = l.get("type") or (jp.get("employmentType") if isinstance(jp.get("employmentType"), str) else None)
        if n % 100 == 0:
            print(f"   {n}/{len(alvos)}", flush=True)


def _local(txt: str, sep: str) -> tuple[str | None, str | None]:
    """'Belo Horizonte - MG' / 'Vilhena / RO' -> (cidade, estado por extenso)."""
    m = re.match(rf"^(.*?)\s*{sep}\s*([A-Z]{{2}})\b", txt or "")
    return (m.group(1).strip(), NOME_UF.get(m.group(2))) if m else (None, None)


def _modelo(txt: str) -> str | None:
    t = (txt or "").lower()
    return "remote" if re.search(r"remot|home office", t) else "hybrid" if "híbrid" in t else \
        "on-site" if "presencial" in t else None


# Vagas.com
def coleta_vagascom(http: Http) -> pd.DataFrame:
    linhas, pagina = {}, 1
    while True:
        try:
            h = http.get(f"https://www.vagas.com.br/vagas-de-*?pagina={pagina}")
        except BloqueioLongo as e:
            print(f"   Vagas.com: BLOQUEIO LONGO na listagem ({e}); ficando com o que já foi lido", flush=True)
            break
        cards = re.findall(r'<li class="vaga[^"]*">(.*?)</li>', h or "", flags=re.S)
        if not cards:
            break
        for c in cards:
            m = re.search(r'data-id-vaga="(\d+)" title="([^"]*)"[^>]*href="([^"]+)"', c)
            if not m:
                continue
            local = texto((re.search(r'class="vaga-local">(.*?)(?:<div class="tooltip|</div>)', c, flags=re.S) or [None, ""])[1])
            cidade, estado = _local(local, "/")
            data = (re.search(r'data-publicacao">.*?(\d{2}/\d{2}/\d{4})', c, flags=re.S) or [None, None])[1]
            linhas[m.group(1)] = {
                "fonte": "Vagas.com", "id": f"vagascom-{m.group(1)}", "name": html.unescape(m.group(2)),
                "description": texto((re.search(r'class="detalhes">(.*?)</div>', c, flags=re.S) or [None, ""])[1]),
                "careerPageName": texto((re.search(r'class="emprVaga">(.*?)</span>', c, flags=re.S) or [None, ""])[1]),
                "city": cidade, "state": estado, "country": "Brasil", "workplaceType": _modelo(local),
                "type": None, "publishedDate": datetime.strptime(data, "%d/%m/%Y").strftime("%Y-%m-%d") if data else None,
                "jobUrl": "https://www.vagas.com.br" + m.group(3),
                "nivel_fonte": texto((re.search(r'class="nivelVaga">(.*?)</span>', c, flags=re.S) or [None, ""])[1]),
            }
        if pagina % 20 == 0:
            print(f"   Vagas.com página {pagina} — {len(linhas)} vagas", flush=True)
        pagina += 1
    print(f"Vagas.com: {len(linhas)} vagas no catálogo ({pagina - 1} páginas)", flush=True)
    lista = list(linhas.values())
    # a listagem é gravada antes de abrir as páginas das vagas
    pd.DataFrame(lista).to_csv(SAIDA / "catalogo_vagascom_parcial.csv.gz", sep=";", index=False,
                               encoding="utf-8", compression="gzip")
    enriquece_com_detalhe(http, lista, "Vagas.com")
    return pd.DataFrame(lista)


# InfoJobs
def _infojobs_pagina(h: str) -> list[dict]:
    out = []
    for m in re.finditer(r'<div id="vacancy(\d+)"[^>]*data-href="([^"]+)"(.*?)(?=<div id="vacancy\d+"|$)', h or "", flags=re.S):
        c = m.group(3)[:6000]
        titulo = texto((re.search(r'js_vacancyTitle">(.*?)</h2>', c, flags=re.S) or [None, ""])[1])
        empresa = texto((re.search(r'<a class="text-body text-decoration-none"[^>]*>(.*?)(?:<span onclick|</a>)', c, flags=re.S) or [None, ""])[1])
        local = texto((re.search(r'<div class="mb-8">(.*?)<span hidden', c, flags=re.S) or [None, ""])[1])
        data = (re.search(r'js_date" data-value="(\d{4}/\d{2}/\d{2})', c) or [None, None])[1]
        cidade, estado = _local(local, "-")
        out.append({
            "fonte": "InfoJobs", "id": f"infojobs-{m.group(1)}", "name": titulo, "description": "",
            "careerPageName": empresa, "city": cidade, "state": estado, "country": "Brasil",
            "workplaceType": _modelo(texto(c)), "type": None,
            "publishedDate": data.replace("/", "-") if data else None,
            "jobUrl": "https://www.infojobs.com.br" + m.group(2),
        })
    return out


def _infojobs_busca(http: Http, base: str, linhas: dict, rotulo: str):
    sep = "&" if "?" in base else "?"
    h = http.get(base)
    total = int((re.search(r'id="resumeVacancies">\s*<span[^>]*>\s*([\d.]+)', h or "") or [None, "0"])[1].replace(".", ""))
    # percorre todas as páginas indicadas pelo total, porque vagas remotas se repetem entre estados
    paginas, antes = max(1, math.ceil(total / 20)), len(linhas)
    for p in range(1, paginas + 1):
        if p > 1:
            h = http.get(f"{base}{sep}Page={p}")
        vagas = _infojobs_pagina(h)
        if not vagas:
            break
        for l in vagas:
            linhas.setdefault(l["id"], l)
        if p % 500 == 0:
            print(f"      {rotulo}: página {p}/{paginas} (acumulado {len(linhas)})", flush=True)
    print(f"   InfoJobs {rotulo:32s} total={total:6d}  +{len(linhas) - antes} novas (acumulado {len(linhas)})", flush=True)


INFOJOBS_LIMITE = 9900   # a listagem só pagina até cerca de 9.980 vagas
# filtros usados, em ordem, para dividir uma listagem grande demais
INFOJOBS_FACETAS = ["facetCategory1", "facetManagerialLevel", "facetWorkingHours", "facetContractWorkType"]


def _infojobs_total(h: str) -> int:
    return int((re.search(r'id="resumeVacancies">\s*<span[^>]*>\s*([\d.]+)', h or "") or [None, "0"])[1].replace(".", ""))


def _infojobs_faceta(h: str, faceta: str) -> list[tuple[str, int]]:
    """(url relativa, quantidade) de cada opção de um filtro lateral da página."""
    i = (h or "").find(f'id="{faceta}"')
    if i < 0:
        return []
    fim = h.find('id="facet', i + 10)
    trecho = h[i:fim if fim > 0 else i + 40000]
    itens = re.findall(r'data-url="([^"]+)".*?<span class="text-truncate">\s*[^<]*?\s*</span>\s*<span>\s*(?:&nbsp;)?\s*'
                       r'\(([\d.]+)\)', trecho, flags=re.S)
    return [(html.unescape(u).replace("?page=100", "").replace("&page=100", ""), int(c.replace(".", ""))) for u, c in itens]


def _infojobs_fatia(http: Http, url: str, linhas: dict, rotulo: str, facetas: list[str], nivel: int = 0):
    h = http.get(url)
    total = _infojobs_total(h)
    if total <= INFOJOBS_LIMITE or not facetas:
        if total > INFOJOBS_LIMITE:
            print(f"   AVISO: {rotulo} tem {total} vagas e não há mais filtro para dividir; coleta parcial", flush=True)
        _infojobs_busca(http, url, linhas, rotulo)
        return
    opcoes = _infojobs_faceta(h, facetas[0])
    soma = sum(c for _, c in opcoes)
    print(f"{'   ' * nivel}   {rotulo}: {total} vagas > limite; dividindo por {facetas[0]} "
          f"({len(opcoes)} opções, soma {soma})", flush=True)
    if not opcoes:
        return _infojobs_fatia(http, url, linhas, rotulo, facetas[1:], nivel)
    for u, _ in opcoes:
        _infojobs_fatia(http, requests.compat.urljoin("https://www.infojobs.com.br/", u), linhas,
                        f"{rotulo} > {u.split('?')[-1] if '?' in u else u.split('-em-')[0].replace('empregos-de-', '')}",
                        facetas[1:], nivel + 1)


# Páginas de listagem por estado (o Rio de Janeiro tem endereço próprio)
INFOJOBS_ESTADOS = [f"empregos-em-{s}.aspx" for s in (
    "acre", "alagoas", "amapa", "amazonas", "bahia", "ceara", "distrito-federal", "espirito-santo", "goias", "maranhao",
    "mato-grosso", "mato-grosso-do-sul", "minas-gerais", "para", "paraiba", "parana", "pernambuco", "piaui",
    "rio-grande-do-norte", "rio-grande-do-sul", "rondonia", "roraima", "santa-catarina", "sao-paulo", "sergipe",
    "tocantins")] + ["vagas-de-emprego-em-rio-de-janeiro.aspx"]


def coleta_infojobs(http: Http) -> pd.DataFrame:
    """Catálogo inteiro (todos os estados, todas as páginas) + área de TI. Só abre a página das vagas de TI.
    Reaproveita a coleta anterior: vagas cuja página já foi lida não são abertas de novo."""
    linhas = {}
    parcial = SAIDA / "catalogo_infojobs_parcial.csv.gz"
    progresso_arq = SAIDA / "infojobs_progresso.json"
    progresso = json.loads(progresso_arq.read_text(encoding="utf-8")) if progresso_arq.exists() else {}
    retomando = bool(progresso.get("estados_concluidos")) and parcial.exists()
    # listagem não traz descrição: descrição preenchida = página da vaga já lida
    for arq in ([parcial] if retomando else []) + [SAIDA / "catalogo_infojobs.csv.gz"]:
        if not arq.exists():
            continue
        for l in pd.read_csv(arq, sep=";", compression="gzip", dtype=str, keep_default_na=False).to_dict("records"):
            lido = l.get("detalhe_lido") == "True" or len(l.get("description") or "") > 50
            if lido:
                l["detalhe_lido"] = True
            if lido or arq == parcial:
                linhas.setdefault(l["id"], l)
    print(f"InfoJobs: {len(linhas)} vagas carregadas ({'retomando' if retomando else 'reaproveitando páginas já lidas'})",
          flush=True)

    if progresso.get("area_ti"):
        area_ti = set(progresso["area_ti"])
    else:
        antes = set(linhas)
        _infojobs_busca(http, "https://www.infojobs.com.br/empregos-de-informatica-ti-telecomunicacoes.aspx", linhas,
                        "área Informática/TI/Telecom")
        area_ti = set(linhas) - antes | {i for i, l in linhas.items() if l.get("infojobs_area_ti") == "True"}
        progresso["area_ti"] = sorted(area_ti)
    feitos = set(progresso.get("estados_concluidos", []))
    for pagina_estado in INFOJOBS_ESTADOS:
        if pagina_estado in feitos:
            continue
        _infojobs_fatia(http, "https://www.infojobs.com.br/" + pagina_estado, linhas,
                        pagina_estado.replace(".aspx", "").replace("empregos-em-", "").replace("vagas-de-emprego-em-", ""),
                        INFOJOBS_FACETAS)
        pd.DataFrame(linhas.values()).to_csv(parcial, sep=";", index=False, encoding="utf-8", compression="gzip")
        feitos.add(pagina_estado)
        progresso["estados_concluidos"] = sorted(feitos)
        progresso_arq.write_text(json.dumps(progresso), encoding="utf-8")
    for i, l in linhas.items():
        l["infojobs_area_ti"] = i in area_ti
    print(f"InfoJobs: {len(linhas)} vagas no catálogo (todos os estados + área TI)", flush=True)
    lista = list(linhas.values())
    enriquece_com_detalhe(http, lista, "InfoJobs")
    return pd.DataFrame(lista)


# ProgramaThor
def coleta_programathor(http: Http) -> pd.DataFrame:
    linhas, pagina, paginas_vencidas = {}, 1, 0
    while paginas_vencidas < 2:
        h = http.get("https://programathor.com.br/jobs" + ("" if pagina == 1 else f"/page/{pagina}"))
        cards = re.findall(r'<a href="(/jobs/(\d+)[^"]*)">(.*?)</a>', h or "", flags=re.S)
        if not cards:
            break
        ativas = 0
        for url, jid, corpo in cards:
            partes = [p for p in (texto(x) for x in re.split(r"<[^>]+>", corpo)) if p]
            # selos antes do título
            while partes and re.match(r"^(?:VAGA EXTERNA|NOVA|DESTAQUE|URGENTE|📍.*)$", partes[0], re.I):
                partes = partes[1:]
            if not partes or "Vencida" in partes[:2]:
                continue
            ativas += 1
            titulo, empresa, local = (partes + [None, None, None])[:3]
            resto = partes[3:]
            porte = next((p for p in resto if re.search(r"empresa|startup", p, re.I)), None)
            salario = next((p for p in resto if p.startswith("Até R$") or "R$" in p), None)
            nivel = next((p for p in resto if p in ("Estágio", "Júnior", "Pleno", "Sênior", "Especialista", "Trainee")), None)
            contrato = next((p for p in resto if p in ("CLT", "PJ", "Estágio", "Freelancer", "Temporário")), None)
            tags = [p for p in resto if p not in (porte, salario, nivel, contrato) and not p.startswith("Não Aceito")
                    and not p.startswith("Aceito")]
            local_limpo = re.sub(r"\s*\(.*\)", "", local or "").strip()
            cidade, estado = _local(local_limpo, "/")
            if not cidade and local_limpo and not re.search(r"remot", local_limpo, re.I):
                cidade = local_limpo
                estado = "São Paulo" if local_limpo == "São Paulo" else None
            linhas[jid] = {
                "fonte": "ProgramaThor", "id": f"programathor-{jid}", "name": titulo,
                # sem página de detalhe: a descrição é o cartão da vaga
                "description": "Requisitos e qualificações: " + ", ".join(tags),
                "careerPageName": empresa, "city": cidade, "state": estado, "country": "Brasil",
                "workplaceType": _modelo(local) or ("on-site" if cidade else None), "type": contrato, "publishedDate": None,
                "jobUrl": "https://programathor.com.br" + url,
                "nivel_fonte": nivel, "salario_fonte": salario, "porte_empresa": porte, "tags_fonte": "; ".join(tags),
            }
        paginas_vencidas = paginas_vencidas + 1 if ativas == 0 else 0
        pagina += 1
    print(f"ProgramaThor: {len(linhas)} vagas ativas ({pagina - 1} páginas lidas)", flush=True)
    return pd.DataFrame(linhas.values())


def completa_vagascom(http: Http) -> pd.DataFrame:
    """Só abre as páginas de vaga que faltaram (o site bloqueia ~24 h depois de ~120 páginas, mesmo com 3 s de pausa;
    reler a listagem gastaria a cota). Pausa de 15 s por página."""
    PAUSA_POR_SITE["vagas.com.br"] = 15.0
    df = pd.read_csv(SAIDA / "catalogo_vagascom.csv.gz", sep=";", dtype=str, keep_default_na=False)
    lista = df.drop(columns=["coletado_em"], errors="ignore").to_dict("records")
    for l in lista:
        l["detalhe_lido"] = str(l.get("detalhe_lido")) == "True"
    enriquece_com_detalhe(http, lista, "Vagas.com (completando)")
    return pd.DataFrame(lista)


COLETORES = {"vagascom": coleta_vagascom, "infojobs": coleta_infojobs, "programathor": coleta_programathor,
             "vagascom-detalhes": completa_vagascom}

if __name__ == "__main__":
    SAIDA.mkdir(exist_ok=True)
    http = Http()
    for nome in (sys.argv[1:] or ["vagascom", "infojobs", "programathor"]):
        df = COLETORES[nome](http)
        df["coletado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        destino = SAIDA / f"catalogo_{nome.removesuffix('-detalhes')}.csv.gz"
        df.to_csv(destino, sep=";", index=False, encoding="utf-8", compression="gzip")
        print(f"Salvo: {destino} ({len(df)} vagas)\n", flush=True)

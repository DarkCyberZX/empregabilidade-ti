"""
Coleta das fontes menores que têm API JSON pública: Remotar, Trampos e repositórios de vagas no GitHub.

    Remotar  api.remotar.com.br/jobs?page=N — vagas remotas (50 por página, só ativas).
             Agrega vagas de outras plataformas (campo integrationSource), por isso pode
             repetir vagas de outras fontes; a junção final remove duplicatas.
    Trampos  trampos.co/api/v2/opportunities?page=N — rota usada pelo próprio site.
             Foco em comunicação/criação; poucas vagas de TI.
    GitHub   API oficial do GitHub, issues abertas dos repositórios em que a comunidade
             brasileira publica vagas de TI (frontendbr/vagas, backend-br/vagas...).

Uso:   python coleta_apis_menores.py [remotar] [trampos] [github]   (padrão: todas)
Saída: saida/catalogo_<fonte>.csv.gz, no mesmo esquema de colunas da Gupy.
"""
import base64
import html
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

SAIDA = Path(__file__).parent / "saida"
PAUSA = 0.5
UF_NOME = {"AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
           "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso",
           "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
           "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
           "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina",
           "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins"}
REPOS_GITHUB = ["frontendbr/vagas", "backend-br/vagas", "qa-brasil/vagas", "react-brasil/vagas", "androiddevbr/vagas",
                "CocoaHeadsBrasil/vagas", "phpdevbr/vagas", "vuejs-br/vagas", "dotnetdevbr/vagas"]

S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (pesquisa academica TCC)"


def get_json(url: str, params: dict | None = None):
    for tentativa in range(4):
        try:
            r = S.get(url, params=params, timeout=60)
            time.sleep(PAUSA)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            espera = 2 ** (tentativa + 1)
            print(f"   erro {url}: {e} — nova tentativa em {espera}s", flush=True)
            time.sleep(espera)
    return None


def sem_html(t: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t or ""))).strip()


def _tags(lista, chave):
    return [((x.get(chave) or {}).get("name") or "") for x in (lista or [])]


def id_origem(link: str) -> str | None:
    """ID da vaga na plataforma de origem, quando a Remotar só republica: permite remover a duplicata
    por ID exato na junção. Gupy: .../job/<base64 de {"jobId":N,...}>; Sólides: .../vaga/N."""
    link = link or ""
    m = re.search(r"gupy\.io/jobs?/([A-Za-z0-9+/=_-]+)", link)
    if m:
        try:
            dados = base64.urlsafe_b64decode(m.group(1) + "=" * (-len(m.group(1)) % 4)).decode("utf-8", "ignore")
            jid = re.search(r'"jobId"\s*:\s*(\d+)', dados)
            if jid:
                return f"gupy-{jid.group(1)}"
        except ValueError:
            pass
        m2 = re.search(r"gupy\.io/jobs?/(\d+)", link)
        return f"gupy-{m2.group(1)}" if m2 else None
    m = re.search(r"solides\.com\.br/vaga/(\d+)", link)
    return f"solides-{m.group(1)}" if m else None


# Remotar
def coleta_remotar() -> pd.DataFrame:
    primeira = get_json("https://api.remotar.com.br/jobs", {"page": 1})
    ultima, total = primeira["meta"]["last_page"], primeira["meta"]["total"]
    vagas = {v["id"]: v for v in primeira["data"]}
    for p in range(2, ultima + 1):
        for v in (get_json("https://api.remotar.com.br/jobs", {"page": p}) or {}).get("data", []):
            vagas.setdefault(v["id"], v)
    print(f"Remotar: API anuncia {total}; coletadas {len(vagas)}", flush=True)
    linhas = []
    for v in vagas.values():
        tags = [re.sub(r"^\W+", "", t).strip() for t in _tags(v.get("jobTags"), "tag")]
        requisitos = [r.get("description", "") for r in (v.get("jobRequirements") or [])]
        empresa = (v.get("company") or {}).get("name") or v.get("companyDisplayName")
        linhas.append({
            "fonte": "Remotar", "id": f"remotar-{v['id']}", "name": v.get("title"),
            "description": sem_html(v.get("description")) + " Requisitos e qualificações: " + " ".join(requisitos),
            "careerPageName": empresa, "city": v.get("city"), "state": UF_NOME.get(v.get("state"), v.get("state")),
            "country": "Brasil", "workplaceType": {"remote": "remote", "hybrid": "hybrid"}.get(v.get("type"), "remote"),
            "type": next((t for t in tags if t in ("CLT", "PJ", "Estágio", "Freelancer", "Cooperado")), None),
            "publishedDate": (v.get("createdAt") or "")[:10], "jobUrl": f"https://remotar.com.br/job/{v['id']}",
            "remotar_categorias": "; ".join(_tags(v.get("jobCategories"), "category")),
            "remotar_tags": "; ".join(tags), "remotar_origem": v.get("integrationSource"),
            "remotar_link_original": v.get("externalLink"), "id_origem": id_origem(v.get("externalLink")),
        })
    return pd.DataFrame(linhas)


# Trampos
def coleta_trampos() -> pd.DataFrame:
    primeira = get_json("https://trampos.co/api/v2/opportunities", {"page": 1})
    paginas, total = primeira["pagination"]["total_pages"], primeira["pagination"]["total"]
    ops = {o["id"]: o for o in primeira["opportunities"]}
    for p in range(2, paginas + 1):
        for o in (get_json("https://trampos.co/api/v2/opportunities", {"page": p}) or {}).get("opportunities", []):
            ops.setdefault(o["id"], o)
    print(f"Trampos: API anuncia {total}; coletadas {len(ops)}", flush=True)
    linhas = []
    for o in ops.values():
        det = (get_json(f"https://trampos.co/api/v2/opportunities/{o['id']}") or {}).get("opportunity", {}) \
            if o.get("category_slug") in ("ti", "dados", "projetos") else {}
        linhas.append({
            "fonte": "Trampos", "id": f"trampos-{o['id']}", "name": o.get("name"),
            "description": sem_html(" ".join(str(det.get(k) or "") for k in ("description", "prerequisite", "desirable"))),
            "careerPageName": (o.get("company") or {}).get("name") or o.get("custom_company_name"),
            "city": o.get("city"), "state": UF_NOME.get(o.get("state"), o.get("state")), "country": "Brasil",
            "workplaceType": "hybrid" if o.get("hybrid") else ("remote" if (o.get("city") or "").lower().startswith("remot") else "on-site"),
            "type": o.get("type_name"), "publishedDate": (o.get("published_at") or "")[:10],
            "jobUrl": f"https://trampos.co/oportunidades/{o['id']}", "trampos_categoria": o.get("category_name"),
        })
    return pd.DataFrame(linhas)


# GitHub
def coleta_github() -> pd.DataFrame:
    linhas = []
    for repo in REPOS_GITHUB:
        pagina, n = 1, 0
        while True:
            issues = get_json(f"https://api.github.com/repos/{repo}/issues",
                              {"state": "open", "per_page": 100, "page": pagina}) or []
            for i in issues:
                if "pull_request" in i:
                    continue
                titulo, rotulos = i.get("title") or "", [l["name"] for l in i.get("labels", [])]
                uf = next((x for x in rotulos if x.upper() in UF_NOME), None) or \
                    (re.search(r"\b(" + "|".join(UF_NOME) + r")\b", titulo) or [None, None])[1]
                linhas.append({
                    "fonte": "GitHub (" + repo.split("/")[0] + ")", "id": f"github-{repo}-{i['number']}",
                    "name": re.sub(r"^\s*(\[[^\]]*\]\s*)+", "", titulo).strip() or titulo,
                    "description": i.get("body") or "", "careerPageName": None, "city": None,
                    "state": UF_NOME.get((uf or "").upper()), "country": "Brasil",
                    "workplaceType": "remote" if re.search(r"remot", titulo + " ".join(rotulos), re.I) else
                    "hybrid" if re.search(r"h[ií]brid", titulo + " ".join(rotulos), re.I) else None,
                    "type": next((x for x in rotulos if x.upper() in ("CLT", "PJ", "ESTÁGIO", "FREELA")), None),
                    "publishedDate": (i.get("created_at") or "")[:10], "jobUrl": i.get("html_url"),
                    "github_rotulos": "; ".join(rotulos), "github_titulo_original": titulo,
                })
                n += 1
            if len(issues) < 100:
                break
            pagina += 1
        print(f"GitHub {repo}: {n} vagas abertas", flush=True)
    return pd.DataFrame(linhas)


COLETORES = {"remotar": coleta_remotar, "trampos": coleta_trampos, "github": coleta_github}

if __name__ == "__main__":
    SAIDA.mkdir(exist_ok=True)
    for nome in (sys.argv[1:] or list(COLETORES)):
        df = COLETORES[nome]()
        df["coletado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        destino = SAIDA / f"catalogo_{nome}.csv.gz"
        df.to_csv(destino, sep=";", index=False, encoding="utf-8", compression="gzip")
        print(f"Salvo: {destino} ({len(df)} vagas)\n", flush=True)

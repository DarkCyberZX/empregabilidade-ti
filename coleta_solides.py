"""
Coleta do catálogo inteiro do portal público Sólides Vagas (vagas.solides.com.br).

A página de busca do portal consome a rota pública /api/vacancies (JSON, sem login);
o robots.txt do portal libera tudo (User-agent: * / Allow: /). A rota aceita no máximo
20 vagas por página e pagina até o fim sem limite, então basta percorrer todas as páginas.

Uso:   python coleta_solides.py
Saída: saida/catalogo_solides.csv.gz  (uma linha por vaga, já no esquema comum das fontes)
"""
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

API = "https://vagas.solides.com.br/api/vacancies"
TAKE = 20            # acima disso a rota devolve 500
PAUSA = 0.35
SAIDA = Path(__file__).parent / "saida"

MODELO = {"remoto": "remote", "hibrido": "hybrid", "híbrido": "hybrid", "presencial": "on-site"}


def _get(s: requests.Session, params: dict) -> dict:
    for tentativa in range(5):
        try:
            r = s.get(API, params=params, timeout=60)
            r.raise_for_status()
            time.sleep(PAUSA)
            return r.json()
        except (requests.RequestException, ValueError) as e:
            espera = 2 ** (tentativa + 1)
            print(f"   erro página {params.get('page')}: {e} — nova tentativa em {espera}s", flush=True)
            time.sleep(espera)
    raise RuntimeError(f"falha persistente em {params}")


def _nomes(lista) -> str:
    return "; ".join(x.get("name", "") for x in (lista or []) if x.get("name"))


def para_esquema_comum(v: dict) -> dict:
    """Converte a vaga da Sólides para as colunas que a análise usa (mesmos nomes da Gupy)."""
    estado, cidade = v.get("state") or {}, v.get("city") or {}
    return {
        "fonte": "Sólides",
        "id": f"solides-{v['id']}",
        "name": v.get("title"),
        "description": v.get("description"),
        "careerPageName": v.get("companyName"),
        "city": cidade.get("name"),
        "state": estado.get("name"),
        "country": "Brasil",
        "workplaceType": MODELO.get((v.get("jobType") or "").lower()),
        "type": _nomes(v.get("recruitmentContractType")),       # CLT, PJ, Estágio...
        "publishedDate": v.get("createdAt"),
        "jobUrl": f"https://vagas.solides.com.br/vaga/{v['id']}",
        # campos estruturados próprios da Sólides
        "solides_areas": _nomes(v.get("occupationAreas")),
        "solides_senioridade": _nomes(v.get("seniority")),
        "solides_escolaridade": _nomes(v.get("education")),
        "solides_hard_skills": _nomes(v.get("hardSkills")),
        "solides_idiomas": _nomes(v.get("language")),
    }


def coleta() -> pd.DataFrame:
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (pesquisa academica TCC)"
    primeira = _get(s, {"page": 1, "take": TAKE})
    total, paginas = primeira["count"], primeira["totalPages"]
    print(f"Sólides: API anuncia {total} vagas em {paginas} páginas", flush=True)
    vagas = {v["id"]: v for v in primeira["data"]}
    for p in range(2, paginas + 1):
        for v in _get(s, {"page": p, "take": TAKE}).get("data", []):
            vagas.setdefault(v["id"], v)
        if p % 200 == 0:
            print(f"   página {p}/{paginas} — {len(vagas)} vagas", flush=True)
    print(f"Sólides: coletadas {len(vagas)} de {total} ({100 * len(vagas) / total:.1f}%)", flush=True)
    df = pd.DataFrame(para_esquema_comum(v) for v in vagas.values())
    df["coletado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return df


if __name__ == "__main__":
    SAIDA.mkdir(exist_ok=True)
    df = coleta()
    destino = SAIDA / "catalogo_solides.csv.gz"
    df.to_csv(destino, sep=";", index=False, encoding="utf-8", compression="gzip")
    print(f"Salvo: {destino} ({len(df)} vagas)")

"""
Análises complementares sobre a base de vagas de TI: famílias de cargo, competências que aparecem juntas, recorte
regional (Nordeste e Alagoas) e consistência entre plataformas.

Uso:     python analises_complementares.py
Entrada: saida/vagas_ti_multifontes.xlsx (gerado por analise_multifontes.py)
Saída:   saida/analises_complementares.xlsx
"""
import re
from itertools import combinations
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).parent
ORIGEM = AQUI / "saida" / "vagas_ti_multifontes.xlsx"
SAIDA = AQUI / "saida" / "analises_complementares.xlsx"

ENTRADA = ["Aprendiz", "Estágio", "Trainee", "Júnior"]

# Família de cargo pelo título; a primeira regra que casar define a família.
FAMILIAS = [
    ("Segurança da informação", r"seguran[cç]a d[ae] (?:informa|ti\b|sistemas|redes|aplica|dados|cloud|infra)|ciberseg|"
                                r"cyber|security|\bsoc\b|pentest|\bsiem\b|appsec|red team|blue team|\bgrc\b|\biam\b|"
                                r"\bsecops\b|devsecops|forense|seguran[cç]a (?:ofensiva|defensiva|cibern)|resposta a incidentes|"
                                r"\bciber|threat|\bcsirt\b|\bsoar\b|seg info|conten[cç][aã]o de incidentes"),
    ("Dados e IA", r"dados|\bdata\b(?! ?center)|\bbi\b|business intelligence|analytics|power ?bi|cientista|"
                   r"machine learning|\bml\b|\bdba\b|\betl\b|estat[ií]stic|informa[cç][oõ]es gerenciais|\bmis\b|"
                   r"vis[aã]o computacional"),
    ("Qualidade e testes", r"\bqa\b|\bq\.a\b|qualidade de software|testes?\b|quality assurance|\btester\b|testador"),
    ("UX/UI e design", r"\bux\b|\bui\b|designer|web design"),
    ("Desenvolvimento de software", r"desenvolv|developer|programador|software|full.?stack|front.?end|back.?end|"
                                    r"\bmobile\b|\bandroid\b|\bios\b|\bjava\b|python|\.net\b|\bphp\b|\breact\b|\bnode|"
                                    r"golang|\bdevs?\b|tech lead|engineering manager|abap|cobol|mainframe|wordpress|"
                                    r"low.?code|\brpa\b|automa[cç][aã]o de processos|power (?:platform|automate)|"
                                    r"sistemas embarcados|tech ?lead|technical lead|teach lead|firmware|\bsw\b"),
    ("Dados e IA", r"\bia\b|\bai\b|intelig[eê]ncia artificial|\bllms?\b|genai|\bgen ?ia\b|\bb\.i\b"),
    ("Sistemas corporativos e ERP", r"\bsap\b|\berp\b|totvs|protheus|salesforce|\btasy\b|\bcrm\b|servicenow|funcional|"
                                    r"implanta|sistemas?\b|\bitsm\b|service ?now"),
    ("Infraestrutura, redes e nuvem", r"infra|redes?\b|network|cloud|nuvem|devops|\bsre\b|linux|\bnoc\b|data ?center|"
                                      r"telecom|vmware|backup|plataforma|\baws\b|azure|sysadmin|"
                                      r"administrador de (?:rede|ambiente)|site reliability|cabeamento|virtualiza|observab|servidores|"
                                      r"storage|finops|openshift|ansible|dynatrace|middleware|cisco|endpoint|"
                                      r"digital workplace|\bitam\b|asset management"),
    ("Suporte técnico", r"suporte|help.?desk|service.?desk|t[eé]cnic[oa]|field|atendimento|\bn[1-3]\b|microinform|"
                        r"manuten[cç]|inform[aá]tica|support|laborat|sustenta[cç][aã]o"),
    ("Dados e IA", r"\bsql\b|\bdbre\b"),
    ("Produto, projetos e gestão", r"product|produto|\bp\.?o\b|\(po\)|scrum|[aá]gil|projetos?|\bpmo\b|gerente|coordena|"
                                   r"gestor|gest[aã]o|head|diretor|governan|business partner|neg[oó]cios|requisitos|"
                                   r"l[ií]der|lideran|supervisor|transforma[cç][aã]o digital|arquitet|architect|director|manager"),
]
FAMILIAS_RX = [(nome, re.compile(rx, re.I)) for nome, rx in FAMILIAS]
ORDEM_FAMILIAS = list(dict.fromkeys(nome for nome, _ in FAMILIAS)) + ["TI geral (título genérico)"]


def familia(titulo: str) -> str:
    for nome, rx in FAMILIAS_RX:
        if rx.search(titulo):
            return nome
    return "TI geral (título genérico)"


def pct(parte, total) -> float:
    return round(100 * parte / total, 1) if total else 0.0


def carrega():
    v = pd.read_excel(ORIGEM, sheet_name="vagas")
    comp = pd.read_excel(ORIGEM, sheet_name="competencias")
    tipo = dict(zip(comp["competencia"], comp["tipo"].str.startswith("Técnica")))
    v["lista"] = v["competencias"].fillna("").map(lambda s: [c.strip() for c in s.split(";") if c.strip()])
    v["tecnicas"] = v["lista"].map(lambda l: [c for c in l if tipo.get(c)])
    v["familia"] = v["name"].map(familia)
    v["entrada"] = v["nivel"].isin(ENTRADA)
    return v, tipo


def mais_citadas(grupo: pd.DataFrame, n: int = 3) -> str:
    cont = pd.Series([c for l in grupo["tecnicas"] for c in l]).value_counts().head(n)
    return "; ".join(f"{c} ({pct(q, len(grupo))}%)" for c, q in cont.items())


def resumo(grupo: pd.DataFrame) -> dict:
    com_nivel = grupo[grupo["nivel"] != "Não informado"]
    vinculo = grupo[grupo["vinculo"] != "Não informado"]
    return {
        "vagas": len(grupo),
        "% entrada (com nível)": pct(com_nivel["entrada"].sum(), len(com_nivel)),
        "% sem nível": pct((grupo["nivel"] == "Não informado").sum(), len(grupo)),
        "% remoto": pct((grupo["modelo_trabalho"] == "Remoto").sum(), len(grupo)),
        "% presencial": pct((grupo["modelo_trabalho"] == "Presencial").sum(), len(grupo)),
        "% menciona graduação": pct(grupo["exige_diploma"].sum(), len(grupo)),
        "% cita inglês": pct(grupo["exige_ingles"].sum(), len(grupo)),
        "% pede experiência": pct(grupo["pede_experiencia"].sum(), len(grupo)),
        "% PJ (contratação informada)": pct((vinculo["vinculo"] == "PJ").sum(), len(vinculo)),
        "média de técnicas": round(grupo["qtd_hard"].mean(), 2),
        "técnicas mais citadas": mais_citadas(grupo),
    }


def familias(v: pd.DataFrame) -> pd.DataFrame:
    linhas = [{"família": f, "% do total": pct((v["familia"] == f).sum(), len(v)), **resumo(v[v["familia"] == f])}
              for f in ORDEM_FAMILIAS]
    return pd.DataFrame(linhas).sort_values("vagas", ascending=False)


def coocorrencia(v: pd.DataFrame, minimo: int = 150) -> pd.DataFrame:
    """Pares de competências técnicas citados na mesma vaga; lift = frequência observada ÷ esperada se independentes."""
    n = len(v)
    freq = pd.Series([c for l in v["tecnicas"] for c in l]).value_counts()
    pares = pd.Series([p for l in v["tecnicas"] for p in combinations(sorted(set(l)), 2)]).value_counts()
    linhas = []
    for (a, b), juntas in pares[pares >= minimo].items():
        menor, maior = (a, b) if freq[a] <= freq[b] else (b, a)
        linhas.append({"competência A": menor, "competência B": maior, "vagas com as duas": int(juntas),
                       "% das vagas com A que citam B": pct(juntas, freq[menor]),
                       "lift": round(juntas * n / (freq[a] * freq[b]), 2)})
    return pd.DataFrame(linhas).sort_values("vagas com as duas", ascending=False)


def regional(v: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    grupos = {"Brasil (todas)": v, "Sudeste": v[v["regiao"] == "Sudeste"], "Sul": v[v["regiao"] == "Sul"],
              "Nordeste": v[v["regiao"] == "Nordeste"], "Centro-Oeste": v[v["regiao"] == "Centro-Oeste"],
              "Norte": v[v["regiao"] == "Norte"], "Alagoas": v[v["uf"] == "AL"],
              "Remotas (todo o país)": v[v["modelo_trabalho"] == "Remoto"]}
    tabela = pd.DataFrame([{"recorte": k, **resumo(g)} for k, g in grupos.items()])
    ne = v[v["regiao"] == "Nordeste"]
    ufs_ne = ne["uf"].value_counts().rename_axis("UF").reset_index(name="vagas")
    ufs_ne["% do Nordeste"] = (100 * ufs_ne["vagas"] / len(ne)).round(1)
    al = v[v["uf"] == "AL"][["name", "careerPageName", "city", "nivel", "modelo_trabalho", "vinculo", "familia", "fonte"]]
    return tabela, ufs_ne, al.sort_values(["familia", "name"])


def familias_por_regiao(v: pd.DataFrame) -> pd.DataFrame:
    t = pd.crosstab(v["familia"], v["regiao"], normalize="columns").mul(100).round(1)
    return t[[c for c in ["Sudeste", "Sul", "Nordeste", "Centro-Oeste", "Norte", "Remoto / sem UF"] if c in t]]


def plataformas(v: pd.DataFrame, tipo: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    taxas = {}
    for p, g in v.groupby("fonte"):
        cont = pd.Series([c for l in g["lista"] for c in l]).value_counts()
        taxas[p] = (100 * cont / len(g)).reindex(list(tipo)).fillna(0)
    t = pd.DataFrame(taxas)
    t["tipo"] = [("Técnica" if tipo[c] else "Comportamental") for c in t.index]
    corr = []
    nomes = [c for c in t.columns if c != "tipo"]
    for a, b in combinations(nomes, 2):
        top_a = set(t[a].nlargest(10).index)
        top_b = set(t[b].nlargest(10).index)
        corr.append({"plataformas": f"{a} x {b}",
                     "correlação de Spearman (82 competências)": round(t[a].rank().corr(t[b].rank()), 2),
                     "competências em comum no top 10": len(top_a & top_b)})
    return t.round(1).sort_values(nomes[0], ascending=False), pd.DataFrame(corr)


def main():
    v, tipo = carrega()
    fam = familias(v)
    co = coocorrencia(v)
    reg, ufs_ne, al = regional(v)
    fam_reg = familias_por_regiao(v)
    plat, plat_corr = plataformas(v, tipo)
    with pd.ExcelWriter(SAIDA, engine="openpyxl") as w:
        fam.to_excel(w, sheet_name="familias", index=False)
        co.to_excel(w, sheet_name="coocorrencia", index=False)
        reg.to_excel(w, sheet_name="regional", index=False)
        fam_reg.to_excel(w, sheet_name="familias_por_regiao")
        ufs_ne.to_excel(w, sheet_name="ufs_nordeste", index=False)
        al.to_excel(w, sheet_name="vagas_alagoas", index=False)
        plat.to_excel(w, sheet_name="competencias_por_plataforma")
        plat_corr.to_excel(w, sheet_name="consistencia_plataformas", index=False)
        v[["id", "name", "familia"]].to_excel(w, sheet_name="familia_por_vaga", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 20, "display.max_colwidth", 80)
    print(fam.to_string(index=False), "\n")
    print(co.head(20).to_string(index=False), "\n")
    print(reg.to_string(index=False), "\n")
    print(fam_reg.to_string(), "\n")
    print(ufs_ne.to_string(index=False), "\n")
    print(plat_corr.to_string(index=False))
    print(f"\nSalvo: {SAIDA}")


if __name__ == "__main__":
    main()

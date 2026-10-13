"""
Validação da identificação das vagas de TI por leitura humana.

Uso:
    python validacao.py gerar        sorteia as amostras e grava validacao/validacao_vagas.xlsx
    python validacao.py resultado    lê a planilha preenchida e calcula a precisão e a perda estimada

Amostras (semente 2026):
    aceitas     100 vagas da base final: é vaga de TI? a família de cargo está correta?
    rejeitadas  100 anúncios fora da base cujo título tem termos ligados a TI: é vaga de TI?
    experiencia 100 vagas júnior marcadas como "menciona experiência": é exigência, desejo ou o que a vaga oferece?
                e 50 vagas júnior sem a marcação: o anúncio exige experiência?
"""
import math
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from coleta_vagas_gupy import RE_EXPERIENCIA  # noqa: E402

AQUI = Path(__file__).parent
SAIDA = AQUI / "saida"
PLANILHA = AQUI / "validacao" / "validacao_vagas.xlsx"
SEMENTE, TAMANHO = 2026, 100
TERMOS_TI = re.compile(r"\bti\b|t\.i\b|tecnologia|inform[aá]tica|sistemas?|software|dados|\bdata\b|desenvolv|programa|"
                       r"suporte|redes?\b|infraestrutura|seguran[cç]a|cloud|digital|\bia\b|automa[cç][aã]o|analytics", re.I)
COLUNAS_RESPOSTA = ["É vaga de TI? (sim, não ou limítrofe)", "Observação"]


def trecho(texto, n=600) -> str:
    texto = re.sub(r"<[^>]+>", " ", str(texto or ""))
    return re.sub(r"\s+", " ", texto).strip()[:n]


def amostra_aceitas() -> pd.DataFrame:
    v = pd.read_excel(SAIDA / "vagas_ti_multifontes.xlsx", sheet_name="vagas")
    fam = pd.read_excel(SAIDA / "analises_complementares.xlsx", sheet_name="familia_por_vaga")[["id", "familia"]]
    a = v.merge(fam, on="id").sample(TAMANHO, random_state=SEMENTE)
    a = pd.DataFrame({"id": a["id"], "plataforma": a["fonte"], "título": a["name"], "empresa": a["careerPageName"],
                      "família atribuída": a["familia"], "nível atribuído": a["nivel"], "link": a["jobUrl"],
                      "início da descrição": a["description"].map(trecho)})
    for c in COLUNAS_RESPOSTA[:1] + ["A família está correta? (sim ou não)"] + COLUNAS_RESPOSTA[1:]:
        a[c] = ""
    return a


def amostra_rejeitadas() -> tuple[pd.DataFrame, int]:
    base = set(pd.read_excel(SAIDA / "vagas_ti_multifontes.xlsx", sheet_name="vagas", usecols=["id"])["id"])
    partes = []
    for fonte, nome in [("gupy", "Gupy"), ("solides", "Sólides"), ("infojobs", "InfoJobs")]:
        c = pd.read_csv(SAIDA / f"catalogo_{fonte}.csv.gz", sep=";", compression="gzip", low_memory=False,
                        usecols=lambda col: col in {"id", "name", "careerPageName", "jobUrl", "description", "country"})
        if fonte == "gupy":
            c = c[c["country"].isna() | (c["country"] == "Brasil")]
            c["id"] = "gupy-" + c["id"].astype(str)
        c["plataforma"] = nome
        partes.append(c)
    cat = pd.concat(partes, ignore_index=True)
    fora = cat[~cat["id"].isin(base) & cat["name"].fillna("").str.contains(TERMOS_TI)]
    r = fora.sample(TAMANHO, random_state=SEMENTE)
    r = pd.DataFrame({"id": r["id"], "plataforma": r["plataforma"], "título": r["name"], "empresa": r["careerPageName"],
                      "link": r["jobUrl"], "início da descrição": r["description"].map(trecho)})
    for c in COLUNAS_RESPOSTA:
        r[c] = ""
    return r, len(fora)


def frases_experiencia(texto, limite=2) -> str:
    frases = re.split(r"(?<=[.;!?])\s+|\n|•|·", re.sub(r"<[^>]+>", " ", str(texto or "")))
    achadas = [f.strip() for f in frases if RE_EXPERIENCIA.search(f.lower())]
    return " | ".join(achadas[:limite])[:700]


def amostra_experiencia() -> tuple[pd.DataFrame, pd.DataFrame]:
    v = pd.read_excel(SAIDA / "vagas_ti_multifontes.xlsx", sheet_name="vagas")
    jr = v[v["nivel"] == "Júnior"]
    com = jr[jr["pede_experiencia"]].sample(TAMANHO, random_state=SEMENTE)
    sem = jr[~jr["pede_experiencia"]].sample(TAMANHO // 2, random_state=SEMENTE)
    com = pd.DataFrame({"id": com["id"], "plataforma": com["fonte"], "título": com["name"], "link": com["jobUrl"],
                        "frase(s) com experiência": com["description"].map(frases_experiencia),
                        "Classificação (exige, desejável, oferece ou outro)": "", "Observação": ""})
    sem = pd.DataFrame({"id": sem["id"], "plataforma": sem["fonte"], "título": sem["name"], "link": sem["jobUrl"],
                        "início da descrição": sem["description"].map(lambda t: trecho(t, 900)),
                        "O anúncio exige experiência? (sim ou não)": "", "Observação": ""})
    return com, sem


def gerar():
    aceitas = amostra_aceitas()
    rejeitadas, universo = amostra_rejeitadas()
    exp_com, exp_sem = amostra_experiencia()
    instrucoes = pd.DataFrame({"Instruções": [
        "Leia o título e, se necessário, a descrição ou o link de cada vaga e preencha as colunas em branco.",
        "É vaga de TI: 'sim' se o trabalho é de tecnologia da informação; 'não' se é de outra área; 'limítrofe' se "
        "mistura as duas (por exemplo, um cargo de negócio que usa um sistema).",
        "A família está correta (aba aceitas): 'sim' se a família atribuída descreve a função; 'não' caso contrário, "
        "indicando na observação a família certa.",
        f"Aba rejeitadas: anúncios que ficaram fora da base, sorteados entre {universo} cujo título tem termos ligados "
        "a TI. Serve para estimar quantas vagas de TI o filtro deixou de fora.",
        "Aba experiencia_marcadas: vagas júnior em que a regra marcou menção a experiência. Classifique a frase: "
        "'exige' (experiência pedida como requisito), 'desejável' (diferencial ou desejável), 'oferece' (experiência "
        "que a vaga proporciona, como 'você vai adquirir experiência') ou 'outro'. Na dúvida, abra o link.",
        "Aba experiencia_sem_marca: vagas júnior sem a marcação. Responda 'sim' se o anúncio exige experiência prévia "
        "(a regra deixou passar) e 'não' caso contrário.",
        "Depois de preencher, salve a planilha e rode: python validacao.py resultado"]})
    PLANILHA.parent.mkdir(exist_ok=True)
    with pd.ExcelWriter(PLANILHA, engine="openpyxl") as w:
        instrucoes.to_excel(w, sheet_name="instrucoes", index=False)
        aceitas.to_excel(w, sheet_name="aceitas", index=False)
        rejeitadas.to_excel(w, sheet_name="rejeitadas", index=False)
        exp_com.to_excel(w, sheet_name="experiencia_marcadas", index=False)
        exp_sem.to_excel(w, sheet_name="experiencia_sem_marca", index=False)
        pd.DataFrame({"universo_rejeitadas": [universo]}).to_excel(w, sheet_name="parametros", index=False)
    print(f"Salvo: {PLANILHA} ({len(aceitas)} aceitas, {len(rejeitadas)} rejeitadas de um universo de {universo}, "
          f"{len(exp_com)} + {len(exp_sem)} vagas júnior para a experiência)")


def wilson(sucessos: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = sucessos / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    margem = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return 100 * (centro - margem), 100 * (centro + margem)


def resultado():
    x = pd.ExcelFile(PLANILHA)
    aceitas, rejeitadas = x.parse("aceitas"), x.parse("rejeitadas")
    universo = int(x.parse("parametros")["universo_rejeitadas"].iloc[0])
    col = COLUNAS_RESPOSTA[0]
    for nome, df in [("aceitas", aceitas), ("rejeitadas", rejeitadas)]:
        vazias = df[col].isna().sum()
        if vazias:
            sys.exit(f"Faltam {vazias} respostas na aba {nome}.")
    ra = aceitas[col].str.strip().str.lower().value_counts()
    sim, n = int(ra.get("sim", 0)), len(aceitas)
    lo, hi = wilson(sim, n)
    print(f"Aceitas: {dict(ra)} | precisão {100 * sim / n:.1f}% (IC 95%: {lo:.1f}% a {hi:.1f}%)")
    fam = aceitas.loc[aceitas[col].str.strip().str.lower() == "sim", "A família está correta? (sim ou não)"]
    fam_ok = (fam.str.strip().str.lower() == "sim").sum()
    print(f"Família correta: {fam_ok} de {len(fam)} vagas de TI ({100 * fam_ok / len(fam):.1f}%)")
    rr = rejeitadas[col].str.strip().str.lower().value_counts()
    ti, m = int(rr.get("sim", 0)), len(rejeitadas)
    lo, hi = wilson(ti, m)
    print(f"Rejeitadas: {dict(rr)} | {100 * ti / m:.1f}% eram de TI (IC 95%: {lo:.1f}% a {hi:.1f}%) | "
          f"perda estimada: {round(universo * ti / m)} vagas (de {round(universo * lo / 100)} a {round(universo * hi / 100)})")
    if "experiencia_marcadas" not in x.sheet_names:
        return
    com, sem = x.parse("experiencia_marcadas"), x.parse("experiencia_sem_marca")
    c1, c2 = "Classificação (exige, desejável, oferece ou outro)", "O anúncio exige experiência? (sim ou não)"
    if com[c1].isna().any() or sem[c2].isna().any():
        sys.exit("Faltam respostas nas abas de experiência.")
    v = pd.read_excel(SAIDA / "vagas_ti_multifontes.xlsx", sheet_name="vagas", usecols=["nivel", "pede_experiencia"])
    taxa = v.loc[v["nivel"] == "Júnior", "pede_experiencia"].mean()
    rc = com[c1].str.strip().str.lower().value_counts()
    exige, n = int(rc.get("exige", 0)), len(com)
    lo, hi = wilson(exige, n)
    rs = sem[c2].str.strip().str.lower().value_counts()
    falta, k = int(rs.get("sim", 0)), len(sem)
    lo2, hi2 = wilson(falta, k)
    print(f"Experiência no júnior: menção em {100 * taxa:.1f}% | marcadas {dict(rc)}: exigem {100 * exige / n:.1f}% "
          f"(IC 95%: {lo:.1f}% a {hi:.1f}%) | sem marca: exigem {100 * falta / k:.1f}% (IC 95%: {lo2:.1f}% a {hi2:.1f}%)")
    print(f"Vagas júnior que exigem experiência (estimativa): {100 * (taxa * exige / n + (1 - taxa) * falta / k):.1f}%")


if __name__ == "__main__":
    {"gerar": gerar, "resultado": resultado}[sys.argv[1] if len(sys.argv) > 1 else "gerar"]()

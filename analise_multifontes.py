"""
Análise consolidada das vagas de TI: junta os catálogos das fontes, aplica o filtro de TI e o dicionário de
competências, completa o nível de senioridade e remove as vagas repetidas entre plataformas.

Uso:
    python analise_multifontes.py                       Gupy, Sólides e InfoJobs
    python analise_multifontes.py --incluir-remotar     inclui a Remotar
    python analise_multifontes.py --incluir-pequenas    inclui ProgramaThor, Trampos e GitHub
    python analise_multifontes.py --excluir=infojobs    exclui uma ou mais fontes

Entrada: saida/catalogo_<fonte>.csv.gz
Saída:   saida/vagas_ti_multifontes.xlsx e saida/multi_*.png
"""
import importlib.util
import re
import sys
import unicodedata
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
AQUI = Path(__file__).parent
SAIDA = AQUI / "saida"
_spec = importlib.util.spec_from_file_location("gupy", AQUI / "coleta_vagas_gupy.py")
gupy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gupy)

# a ordem define a prioridade na remoção de repetições
FONTES_PRINCIPAIS = ["gupy", "solides", "infojobs"]
# a Remotar republica vagas de outras plataformas e mantém anúncios já encerrados
FONTES_REMOTAR = ["remotar"]
# fontes com poucas vagas de TI
FONTES_PEQUENAS = ["programathor", "trampos", "github"]
EXCLUIR = {f for a in sys.argv if a.startswith("--excluir=") for f in a.split("=", 1)[1].split(",")}
FONTES = [f for f in (FONTES_PRINCIPAIS + (FONTES_REMOTAR if "--incluir-remotar" in sys.argv else [])
                      + (FONTES_PEQUENAS if "--incluir-pequenas" in sys.argv else [])) if f not in EXCLUIR]
GITHUB_MAX_DIAS = 365

NIVEL_FONTE = [(r"est[aá]gi", "Estágio"), (r"trainee", "Trainee"), (r"aprendiz", "Aprendiz"),
               (r"j[uú]nior", "Júnior"), (r"pleno", "Pleno"), (r"s[eê]nior", "Sênior"),
               (r"especialista|coordena|supervis|ger[eê]ncia|diretoria|lideran", "Especialista/Liderança")]


def sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", t or "") if not unicodedata.combining(c))


def chave_vaga(titulo, empresa) -> str | None:
    if not isinstance(empresa, str) or not empresa.strip() or empresa.strip().lower() == "confidencial":
        return None
    norm = lambda s: re.sub(r"[^a-z0-9]+", "", sem_acento(str(s)).lower().replace("(a)", ""))
    return norm(titulo) + "|" + norm(empresa)


def carrega() -> tuple[pd.DataFrame, list[dict]]:
    partes, resumo = [], []
    for f in FONTES:
        arq = SAIDA / f"catalogo_{f}.csv.gz"
        if not arq.exists():
            print(f"(sem {arq.name}; fonte pulada)")
            continue
        df = pd.read_csv(arq, sep=";", compression="gzip", low_memory=False)
        if f == "gupy":
            df["fonte"] = "Gupy"
            df["id"] = "gupy-" + df["id"].astype(str)
        if f == "github":
            limite = (datetime.now() - timedelta(days=GITHUB_MAX_DIAS)).strftime("%Y-%m-%d")
            df = df[df["publishedDate"].fillna("") >= limite]
        df["fonte_arquivo"] = f
        resumo.append({"fonte": f, "catalogo_coletado": len(df)})
        partes.append(df)
    tudo = pd.concat(partes, ignore_index=True)
    # cópias da Remotar de vagas já coletadas na origem
    if "id_origem" in tudo:
        copia = (tudo["fonte_arquivo"] == "remotar") & tudo["id_origem"].isin(set(tudo["id"]))
        for r in resumo:
            if r["fonte"] == "remotar":
                r["republicadas_removidas"] = int(copia.sum())
        print(f"Remotar: {int(copia.sum())} vagas eram republicação de vagas já coletadas na Gupy/Sólides (removidas)")
        tudo = tudo[~copia]
    return tudo, resumo


# "Nível hierárquico" da InfoJobs: só os valores que indicam a senioridade
RE_NIVEL_INFOJOBS = re.compile(r"n[ií]vel hier[aá]rquico:\s*(.+?)\s+(?:lugar de trabalho|n[uú]mero de vagas)", re.I)
NIVEL_INFOJOBS = {"estagiário": "Estágio", "trainee": "Trainee", "coordenador": "Especialista/Liderança",
                  "gerente": "Especialista/Liderança", "supervisor": "Especialista/Liderança",
                  "encarregado": "Especialista/Liderança"}

# Nível declarado na descrição ("Buscamos um(a) Analista de Sistemas Júnior", "Nível: Pleno")
_NIV = r"(j[uú]nior|jr\.?|pleno|plena|s[eê]nior|sr\.?)(?![\w/])"
_PAL = r"[\wçãõáéíóúâêô/&.()+#-]+"
_CARGO = (r"(?:analista|desenvolvedor(?:\(a\)|a)?|engenheir[oa](?:\(a\))?|cientista|t[eé]cnic[oa]|assistente|"
          r"consultor(?:\(a\)|a)?|programador(?:\(a\)|a)?|administrador(?:\(a\)|a)?|product (?:owner|manager)|devops|designer|"
          r"developer|engineer|dba|suporte)")
RE_NIVEL_DESCRICAO = [re.compile(p, re.I) for p in (
    r"(?:vaga|oportunidade|posi[cç][aã]o|cargo)\s+(?:de|para)\s+(?:" + _PAL + r"\s+){0,6}?" + _NIV,
    r"(?:buscamos|procuramos|contratando|contrata|estamos (?:em busca|buscando|procurando|contratando)|selecionando|recrutando|"
    r"est[aá] em busca|[aà] procura)\s+(?:de\s+)?(?:um[a]?\s+|por\s+)?(?:" + _PAL + r"\s+){0,6}?" + _NIV,
    r"(?:n[ií]vel|senioridade|n[ií]vel de senioridade|n[ií]vel do cargo)\s*[:\-–]\s*" + _NIV,
    r"\b" + _CARGO + r"\b(?:\s+" + _PAL + r"){0,5}?\s+" + _NIV,
)]
# descartados: faixas de níveis, outros usos das palavras e trechos que não tratam do nível da vaga
RE_NIVEL_FAIXA = re.compile(r"^\s*(?:/\s*(?:pleno|s[eê]nior|especialista)|(?:e|ou|a)\s+(?:ou\s+)?(?:pleno|s[eê]nior)|avan[cç]ad)", re.I)
RE_NIVEL_FALSO = re.compile(r"pleno (?:funcionamento|desenvolvimento|exerc|atendimento|uso|dom[ií]nio|conhecimento|"
                            r"crescimento|potencial|acesso|gozo|direito)|s[eê]nior (?:sistemas|erp|hcm|x\b|rh)|erp s[eê]nior|"
                            r"mega/s[eê]nior", re.I)
RE_NIVEL_CONTEXTO = re.compile(r"(?:orient|mentor|apoi|treina|lider|gest[aã]o de|coorden|desenvolv(?:er|imento de)|acompanh|"
                               r"forma[cç][aã]o de|supervis|experi[eê]ncia|n[aã]o [eé] necess|crescimento|interface)[^.\n]{0,60}$", re.I)
# descrições conferidas manualmente que não correspondem ao título ou citam mais de um nível
NIVEL_DESCRICAO_DESCARTADO = {"gupy-12432230", "gupy-12432231", "gupy-11639952", "gupy-1736791", "infojobs-11954489"}
NIVEL_DESCRICAO = {"j": "Júnior", "p": "Pleno", "s": "Sênior"}


def nivel_na_descricao(desc: str) -> str | None:
    for rx in RE_NIVEL_DESCRICAO:
        for m in rx.finditer(desc):
            if (RE_NIVEL_FAIXA.search(desc[m.end():m.end() + 20]) or RE_NIVEL_FALSO.search(desc[max(0, m.start() - 5):m.end() + 25])
                    or RE_NIVEL_CONTEXTO.search(desc[max(0, m.start() - 60):m.start()])):
                continue
            return NIVEL_DESCRICAO[m.group(m.lastindex).lower()[0]]
    return None


def completa_nivel(df: pd.DataFrame) -> pd.DataFrame:
    """Completa o nível ausente no título com o campo da plataforma ou com a descrição; registra a origem."""
    campos = [c for c in ("nivel_fonte", "solides_senioridade", "remotar_tags") if c in df]
    df["origem_nivel"] = df["nivel"].map(lambda n: "Não informado" if n == "Não informado" else "Título")
    for i in df.index[df["nivel"] == "Não informado"]:
        texto = " ".join(str(df.at[i, c]) for c in campos if isinstance(df.at[i, c], str)).lower()
        for padrao, rotulo in NIVEL_FONTE:
            if re.search(padrao, texto):
                df.at[i, "nivel"], df.at[i, "origem_nivel"] = rotulo, "Campo da plataforma"
                break
        else:
            desc = str(df.at[i, "description"] or "")
            m = RE_NIVEL_INFOJOBS.search(desc) if df.at[i, "fonte_arquivo"] == "infojobs" else None
            if m and m.group(1).strip().lower() in NIVEL_INFOJOBS:
                df.at[i, "nivel"], df.at[i, "origem_nivel"] = NIVEL_INFOJOBS[m.group(1).strip().lower()], "Campo da plataforma"
            elif df.at[i, "id"] not in NIVEL_DESCRICAO_DESCARTADO and (rot := nivel_na_descricao(desc)):
                df.at[i, "nivel"], df.at[i, "origem_nivel"] = rot, "Descrição"
    return df


def remove_duplicatas(df: pd.DataFrame) -> pd.DataFrame:
    """Remove vagas repetidas entre plataformas (mesmo título e empresa), mantendo a fonte de maior prioridade."""
    df = df.copy()
    df["_prio"] = df["fonte_arquivo"].map({f: i for i, f in enumerate(FONTES)})
    df["_chave"] = [chave_vaga(t, e) or f"id:{i}" for t, e, i in zip(df["name"], df["careerPageName"], df["id"])]
    fontes = df.groupby("_chave")["fonte"].agg(lambda s: "; ".join(sorted(set(s))))
    melhor = df.groupby("_chave")["_prio"].transform("min")
    df = df[df["_prio"] == melhor]
    df["fontes"] = df["_chave"].map(fontes)
    df["n_fontes"] = df["fontes"].str.count(";") + 1
    return df.drop(columns=["_prio", "_chave"])


RE_SUPERIOR = re.compile(r"gradua|tecn[oó]logo|p[oó]s", re.I)
RE_BASICO = re.compile(r"m[eé]dio|t[eé]cnico|fundamental", re.I)


def usa_campos_solides(catalogo: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta à descrição o campo de hard skills da Sólides."""
    if "solides_hard_skills" not in catalogo:
        return catalogo
    m = (catalogo["fonte_arquivo"] == "solides") & catalogo["solides_hard_skills"].fillna("").ne("")
    catalogo.loc[m, "description"] = (catalogo.loc[m, "description"].fillna("") + "<p>Requisitos e qualificações: "
                                      + catalogo.loc[m, "solides_hard_skills"].str.replace(";", ",") + "</p>")
    return catalogo


def escolaridade_solides(ti: pd.DataFrame) -> pd.DataFrame:
    """Conta como menção a graduação a vaga da Sólides que exige apenas nível superior."""
    if "solides_escolaridade" not in ti:
        return ti
    esc = ti["solides_escolaridade"].fillna("")
    so_superior = (ti["fonte_arquivo"] == "solides") & esc.str.contains(RE_SUPERIOR) & ~esc.str.contains(RE_BASICO)
    ti.loc[so_superior, "exige_diploma"] = True
    return ti


def alerta(ti: pd.DataFrame) -> pd.Series:
    desc = ti["description"].fillna("").str.lower()
    motivos = pd.DataFrame({
        "TI pela descrição (título ambíguo ou genérico)": ti["criterio_ti"] != "título",
        "descrição curta (competências podem faltar)": desc.str.len() < 300,
        "sem seções: comportamentais lidas no texto inteiro": ~desc.str.contains(gupy.RE_INI_RESP),
    })
    return motivos.apply(lambda r: "; ".join(m for m, v in r.items() if v), axis=1)


def main():
    catalogo, resumo = carrega()
    print(f"Catálogo combinado: {len(catalogo)} vagas de {len(resumo)} fontes" + (f" (excluídas: {sorted(EXCLUIR)})" if EXCLUIR else ""))
    ti = gupy.enriquece(usa_campos_solides(catalogo))
    ti = escolaridade_solides(completa_nivel(ti))
    ti["alerta"] = alerta(ti)
    unicas = remove_duplicatas(ti)

    for r in resumo:
        r["vagas_ti"] = int((ti["fonte_arquivo"] == r["fonte"]).sum())
        r["%_ti_no_catalogo"] = round(100 * r["vagas_ti"] / r["catalogo_coletado"], 1) if r["catalogo_coletado"] else 0
        r["vagas_ti_unicas_mantidas"] = int((unicas["fonte_arquivo"] == r["fonte"]).sum())
    res = pd.DataFrame(resumo)
    res.loc[len(res)] = {"fonte": "TOTAL", "catalogo_coletado": res["catalogo_coletado"].sum(),
                         "vagas_ti": res["vagas_ti"].sum(), "%_ti_no_catalogo": None,
                         "vagas_ti_unicas_mantidas": len(unicas)}

    comp, kpis, niv, uf = gupy.tabelas(unicas)
    # percentual de vagas que citam cada competência, por fonte
    cols = [c for c in unicas if c.startswith(("hard::", "soft::"))]
    por_fonte = (unicas.groupby("fonte")[cols].mean().T * 100).round(1)
    por_fonte.index = [c.split("::")[1] for c in por_fonte.index]
    por_fonte.insert(0, "TODAS", (unicas[cols].mean() * 100).round(1).values)
    por_fonte = por_fonte.sort_values("TODAS", ascending=False)
    n_por_fonte = unicas["fonte"].value_counts()
    por_fonte.columns = [f"{c} (n={n_por_fonte.get(c, len(unicas))})" for c in por_fonte.columns]

    col_vagas = ["id", "fonte", "fontes", "n_fontes", "name", "careerPageName", "criterio_ti", "nivel", "origem_nivel", "vinculo",
                 "city", "uf", "regiao", "modelo_trabalho", "publishedDate", "exige_diploma", "exige_diploma_concluido",
                 "aceita_cursando", "exige_ingles", "pede_experiencia", "qtd_hard", "qtd_soft", "competencias",
                 "alerta", "jobUrl", "description"]
    col_vagas += [c for c in ("solides_hard_skills", "solides_escolaridade", "tags_fonte", "remotar_categorias",
                              "infojobs_area_ti") if c in unicas]
    destino = SAIDA / "vagas_ti_multifontes.xlsx"
    with pd.ExcelWriter(destino, engine="openpyxl") as w:
        res.to_excel(w, sheet_name="resumo_fontes", index=False)
        unicas[col_vagas].to_excel(w, sheet_name="vagas", index=False)
        comp.to_excel(w, sheet_name="competencias", index=False)
        por_fonte.to_excel(w, sheet_name="competencias_por_fonte")
        kpis.to_excel(w, sheet_name="kpis", index=False)
        niv.to_excel(w, sheet_name="nivel", index=False)
        uf.to_excel(w, sheet_name="uf", index=False)
    gupy.graficos(unicas, comp, prefixo="multi_", rotulo=f"{len(resumo)} fontes")

    print(res.to_string(index=False))
    print(f"\nVagas de TI únicas (todas as fontes): {len(unicas)}  |  duplicatas removidas: {len(ti) - len(unicas)}")
    print(kpis.to_string(index=False))
    print(f"\nSalvo: {destino}")


if __name__ == "__main__":
    main()

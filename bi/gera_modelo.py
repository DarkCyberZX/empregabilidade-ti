"""
Modelo dimensional (esquema estrela) para o painel no Power BI, gerado a partir da análise de vagas
(../saida/vagas_ti_multifontes.xlsx, produzida por analise_multifontes.py). Não coleta nada: só reorganiza.

Saída: bi/modelo_vagas_ti.xlsx, uma aba por tabela:
  fVagas            fato: uma linha por vaga de TI, com as chaves das dimensões e os indicadores (0 ou 1)
  fVagaCompetencia  ponte: um par vaga x competência para cada competência encontrada na vaga
  dCompetencia      as 82 competências do dicionário (técnica ou comportamental)
  dLocal            cidade, UF, estado e região
  dNivel            nível de senioridade, ordem de exibição e se é vaga de entrada (aprendiz, estágio, trainee, júnior)
  dVinculo          forma de contratação e se ela é informada pela plataforma
  dModelo           modelo de trabalho (presencial, híbrido, remoto)
  dPlataforma       plataforma, forma de acesso e tamanho do catálogo coletado

Relacionamentos no Power BI:
  dLocal, dNivel, dVinculo, dModelo, dPlataforma (1) -> fVagas (*), pelas chaves sk_*
  fVagas (1) -> fVagaCompetencia (*), por id_vaga, com filtro nos dois sentidos (escolher uma competência filtra as vagas)
  dCompetencia (1) -> fVagaCompetencia (*), por sk_competencia

Ao final, recalcula os indicadores da aba "kpis" e a contagem das competências a partir das tabelas do modelo e
confere que batem com a análise; se algo não bater, o script para sem gravar.

Uso: python bi/gera_modelo.py
"""
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).parent
ORIGEM = AQUI.parent / "saida" / "vagas_ti_multifontes.xlsx"
SAIDA = AQUI / "modelo_vagas_ti.xlsx"

ESTADO = {"AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
          "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso",
          "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
          "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
          "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
          "SE": "Sergipe", "TO": "Tocantins"}
ORDEM_NIVEL = ["Aprendiz", "Estágio", "Trainee", "Júnior", "Pleno", "Sênior", "Especialista/Liderança", "Não informado"]
ENTRADA = {"Aprendiz", "Estágio", "Trainee", "Júnior"}        # mesma definição do indicador "vagas de entrada"
ORDEM_MODELO = ["Presencial", "Híbrido", "Remoto", "Não informado"]
PLATAFORMA = {"gupy": ("Gupy", "API do portal público de vagas"),
              "solides": ("Sólides", "API do portal público de vagas"),
              "infojobs": ("InfoJobs", "Páginas públicas de listagem e de vaga")}


def dimensao(valores: pd.Series, nome: str, ordem: list | None = None) -> pd.DataFrame:
    """Tabela de dimensão com chave numérica (sk_*) a partir dos valores distintos."""
    unicos = [v for v in (ordem or []) if v in set(valores)] + sorted(set(valores) - set(ordem or []))
    return pd.DataFrame({f"sk_{nome}": range(1, len(unicos) + 1), nome: unicos})


def main():
    x = pd.ExcelFile(ORIGEM)
    v = x.parse("vagas")
    comp = x.parse("competencias")
    resumo = x.parse("resumo_fontes")
    kpis = x.parse("kpis").set_index("kpi")["valor"]

    # dimensões
    v["uf"] = v["uf"].replace({"—": "Sem UF"})                      # vaga remota vem sem estado
    v["city"] = v["city"].fillna("Não informada")
    dLocal = (v[["city", "uf", "regiao"]].drop_duplicates().sort_values(["regiao", "uf", "city"])
              .rename(columns={"city": "cidade"}).reset_index(drop=True))
    dLocal.insert(0, "sk_local", range(1, len(dLocal) + 1))
    dLocal["estado"] = dLocal["uf"].map(ESTADO).fillna("Sem estado (vaga remota)")
    dLocal["pais"] = "Brasil"

    dNivel = dimensao(v["nivel"], "nivel", ORDEM_NIVEL)
    dNivel["ordem"] = dNivel["nivel"].map({n: i for i, n in enumerate(ORDEM_NIVEL, 1)})
    dNivel["vaga_de_entrada"] = dNivel["nivel"].map(lambda n: "Sim" if n in ENTRADA else "Não")

    dVinculo = dimensao(v["vinculo"], "vinculo", list(v["vinculo"].value_counts().index))
    dVinculo["informado"] = dVinculo["vinculo"].map(lambda n: "Não" if n == "Não informado" else "Sim")

    dModelo = dimensao(v["modelo_trabalho"], "modelo_trabalho", ORDEM_MODELO)

    cat = dict(zip(resumo["fonte"], resumo["catalogo_coletado"]))
    dPlataforma = pd.DataFrame([{"sk_plataforma": i, "plataforma": nome, "forma_de_acesso": acesso,
                                 "anuncios_coletados": int(cat[chave])}
                                for i, (chave, (nome, acesso)) in enumerate(PLATAFORMA.items(), 1)])

    dCompetencia = comp[["competencia", "tipo"]].copy()
    dCompetencia["tipo"] = dCompetencia["tipo"].map(lambda t: "Técnica" if t.startswith("Técnica") else "Comportamental")
    dCompetencia = dCompetencia.sort_values(["tipo", "competencia"], ascending=[False, True]).reset_index(drop=True)
    dCompetencia.insert(0, "sk_competencia", range(1, len(dCompetencia) + 1))

    # fato e ponte
    chave = lambda d, col: dict(zip(d[col], d[f"sk_{col}"]))
    sk_local = {(c, u, r): k for k, c, u, r in dLocal[["sk_local", "cidade", "uf", "regiao"]].itertuples(index=False)}
    sk_plat = dict(zip(dPlataforma["plataforma"], dPlataforma["sk_plataforma"]))
    fVagas = pd.DataFrame({
        "id_vaga": v["id"],
        "titulo": v["name"],
        "empresa": v["careerPageName"].fillna("Não informada"),
        "link": v["jobUrl"],
        "sk_plataforma": v["fonte"].map(sk_plat),
        "sk_local": [sk_local[(c, u, r)] for c, u, r in zip(v["city"], v["uf"], v["regiao"])],
        "sk_nivel": v["nivel"].map(chave(dNivel, "nivel")),
        "sk_vinculo": v["vinculo"].map(chave(dVinculo, "vinculo")),
        "sk_modelo_trabalho": v["modelo_trabalho"].map(chave(dModelo, "modelo_trabalho")),
        "menciona_graduacao": v["exige_diploma"].astype(int),
        "exige_diploma_concluido": v["exige_diploma_concluido"].astype(int),
        "aceita_cursando": v["aceita_cursando"].astype(int),
        "cita_ingles": v["exige_ingles"].astype(int),
        "pede_experiencia": v["pede_experiencia"].astype(int),
        "qtd_competencias_tecnicas": v["qtd_hard"],
        "qtd_competencias_comportamentais": v["qtd_soft"],
        "criterio_ti": v["criterio_ti"],
        "alerta": v["alerta"].fillna(""),
        "plataformas_em_que_aparece": v["fontes"],
        "data_publicacao": pd.to_datetime(v["publishedDate"], errors="coerce", utc=True).dt.tz_localize(None).dt.date,
    })
    sk_comp = chave(dCompetencia, "competencia")
    pares = [(i, c.strip()) for i, lista in zip(v["id"], v["competencias"].fillna("")) for c in lista.split(";") if c.strip()]
    fVagaCompetencia = pd.DataFrame(pares, columns=["id_vaga", "competencia"])
    desconhecidas = sorted(set(fVagaCompetencia["competencia"]) - set(sk_comp))
    assert not desconhecidas, f"competências fora do dicionário: {desconhecidas}"
    fVagaCompetencia["sk_competencia"] = fVagaCompetencia["competencia"].map(sk_comp)
    fVagaCompetencia = fVagaCompetencia[["id_vaga", "sk_competencia"]]

    # conferência com a análise
    assert fVagas["id_vaga"].is_unique and len(fVagas) == len(v)
    assert fVagas[[c for c in fVagas if c.startswith("sk_")]].notna().all().all(), "vaga sem chave de dimensão"
    assert len(fVagaCompetencia) == int(v["qtd_hard"].sum() + v["qtd_soft"].sum()), "ponte não bate com as contagens"
    nivel = fVagas["sk_nivel"].map(dict(zip(dNivel["sk_nivel"], dNivel["nivel"])))
    vinc = fVagas["sk_vinculo"].map(dict(zip(dVinculo["sk_vinculo"], dVinculo["vinculo"])))
    modelo = fVagas["sk_modelo_trabalho"].map(dict(zip(dModelo["sk_modelo_trabalho"], dModelo["modelo_trabalho"])))
    entrada = nivel.isin(ENTRADA)
    tipo = fVagaCompetencia["sk_competencia"].map(dict(zip(dCompetencia["sk_competencia"], dCompetencia["tipo"])))
    recalc = {
        "Total de vagas de TI analisadas": len(fVagas),
        "Taxa de menção a graduação (%)": 100 * fVagas["menciona_graduacao"].mean(),
        "Taxa de exigência de diploma concluído (%)": 100 * fVagas["exige_diploma_concluido"].mean(),
        "Taxa de aceite de 'cursando' (%)": 100 * fVagas["aceita_cursando"].mean(),
        "Taxa de exigência de inglês (%)": 100 * fVagas["cita_ingles"].mean(),
        "Taxa de vagas de entrada (%)": 100 * entrada.mean(),
        "Vagas de entrada que pedem experiência (%)": 100 * fVagas.loc[entrada, "pede_experiencia"].mean(),
        "Taxa de trabalho remoto (%)": 100 * (modelo == "Remoto").mean(),
        "Taxa de vagas PJ (%)": 100 * (vinc[vinc != "Não informado"] == "PJ").mean(),
        "Proporção hard skills (%)": 100 * (tipo == "Técnica").mean(),
        "Proporção soft skills (%)": 100 * (tipo == "Comportamental").mean(),
        "Média de competências técnicas por vaga": (tipo == "Técnica").sum() / len(fVagas),
    }
    print("Conferência dos indicadores (análise x modelo):")
    for k, valor in recalc.items():
        ok = abs(round(valor, 2) - float(kpis[k])) < 0.006
        print(f"   {'ok ' if ok else 'ERRO'} {k}: {float(kpis[k]):g} x {round(valor, 2):g}")
        assert ok, k
    contagem = fVagaCompetencia["sk_competencia"].map(dict(zip(dCompetencia["sk_competencia"], dCompetencia["competencia"]))).value_counts()
    assert all(contagem.get(c, 0) == n for c, n in zip(comp["competencia"], comp["vagas"])), "contagem de competências diverge"
    print(f"   ok  contagem das {len(comp)} competências igual à aba 'competencias'")

    # gravação
    tabelas = {"fVagas": fVagas, "fVagaCompetencia": fVagaCompetencia, "dCompetencia": dCompetencia, "dLocal": dLocal,
               "dNivel": dNivel, "dVinculo": dVinculo, "dModelo": dModelo, "dPlataforma": dPlataforma}
    with pd.ExcelWriter(SAIDA, engine="openpyxl") as w:
        for nome, t in tabelas.items():
            t.to_excel(w, sheet_name=nome, index=False)
    print(f"\nSalvo: {SAIDA}")
    for nome, t in tabelas.items():
        print(f"   {nome:17} {len(t):6} linhas | colunas: {', '.join(t.columns)}")


if __name__ == "__main__":
    main()

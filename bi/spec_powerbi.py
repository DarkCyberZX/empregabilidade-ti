"""
Especificação do modelo do Power BI (tabelas com a consulta Power Query, relacionamentos e medidas) para o
carrega_powerbi.ps1 aplicar via TOM no Power BI Desktop aberto. Lê as tabelas de bi/modelo_vagas_ti.xlsx (gerado por
gera_modelo.py).

Uso: python bi/spec_powerbi.py      (grava bi/modelo_powerbi.json)
"""
import json
from pathlib import Path

AQUI = Path(__file__).parent
ARQUIVO = str((AQUI / "modelo_vagas_ti.xlsx").resolve())

S, I, D = "String", "Int64", "DateTime"
TABELAS = {
    "fVagas": ("Fato: uma linha por vaga de TI (Gupy, Sólides e InfoJobs, coleta de 27 e 28/09/2026)", [
        ("id_vaga", S), ("titulo", S), ("empresa", S), ("link", S), ("sk_plataforma", I), ("sk_local", I),
        ("sk_nivel", I), ("sk_vinculo", I), ("sk_modelo_trabalho", I), ("menciona_graduacao", I),
        ("exige_diploma_concluido", I), ("aceita_cursando", I), ("cita_ingles", I), ("pede_experiencia", I),
        ("qtd_competencias_tecnicas", I), ("qtd_competencias_comportamentais", I), ("criterio_ti", S), ("alerta", S),
        ("plataformas_em_que_aparece", S), ("data_publicacao", D)]),
    "fVagaCompetencia": ("Ponte: cada competência encontrada em cada vaga", [("id_vaga", S), ("sk_competencia", I)]),
    "dCompetencia": ("As 82 competências do dicionário", [("sk_competencia", I), ("competencia", S), ("tipo", S)]),
    "dLocal": ("Cidade, UF, estado e região da vaga", [("sk_local", I), ("cidade", S), ("uf", S), ("regiao", S),
                                                      ("estado", S), ("pais", S)]),
    "dNivel": ("Nível de senioridade", [("sk_nivel", I), ("nivel", S), ("ordem", I), ("vaga_de_entrada", S)]),
    "dVinculo": ("Forma de contratação", [("sk_vinculo", I), ("vinculo", S), ("informado", S)]),
    "dModelo": ("Modelo de trabalho", [("sk_modelo_trabalho", I), ("modelo_trabalho", S)]),
    "dPlataforma": ("Plataforma de recrutamento", [("sk_plataforma", I), ("plataforma", S), ("forma_de_acesso", S),
                                                  ("anuncios_coletados", I)]),
}
TIPO_M = {S: "type text", I: "Int64.Type", D: "type date"}
# colunas ocultas (chaves), categoria de dado (mapa e link) e ordenação
OCULTAS = {"sk_plataforma", "sk_local", "sk_nivel", "sk_vinculo", "sk_modelo_trabalho", "sk_competencia", "ordem"}
CATEGORIA = {("dLocal", "cidade"): "City", ("dLocal", "estado"): "StateOrProvince", ("dLocal", "pais"): "Country",
             ("fVagas", "link"): "WebUrl"}
ORDENAR = {("dNivel", "nivel"): "ordem", ("dModelo", "modelo_trabalho"): "sk_modelo_trabalho",
           ("dVinculo", "vinculo"): "sk_vinculo", ("dCompetencia", "competencia"): "sk_competencia"}
FORMATO = {("fVagas", "data_publicacao"): "dd/mm/yyyy"}


def consulta(tabela: str, colunas: list) -> str:
    tipos = ", ".join(f'{{"{c}", {TIPO_M[t]}}}' for c, t in colunas)
    return ("let\n"
            f'    Fonte = Excel.Workbook(File.Contents("{ARQUIVO}"), null, true),\n'
            f'    Aba = Fonte{{[Item="{tabela}",Kind="Sheet"]}}[Data],\n'
            "    Cabecalhos = Table.PromoteHeaders(Aba, [PromoteAllScalars=true]),\n"
            f"    Tipos = Table.TransformColumnTypes(Cabecalhos, {{{tipos}}})\n"
            "in\n    Tipos")


RELACOES = [  # (tabela N, coluna, tabela 1, coluna, filtro nos dois sentidos)
    ("fVagas", "sk_plataforma", "dPlataforma", "sk_plataforma", False),
    ("fVagas", "sk_local", "dLocal", "sk_local", False),
    ("fVagas", "sk_nivel", "dNivel", "sk_nivel", False),
    ("fVagas", "sk_vinculo", "dVinculo", "sk_vinculo", False),
    ("fVagas", "sk_modelo_trabalho", "dModelo", "sk_modelo_trabalho", False),
    ("fVagaCompetencia", "id_vaga", "fVagas", "id_vaga", True),   # escolher uma competência filtra as vagas
    ("fVagaCompetencia", "sk_competencia", "dCompetencia", "sk_competencia", False),
]
P, N = "0.0%", "#,0"
# KEEPFILTERS soma o filtro da medida ao da segmentação, em vez de substituí-lo
MEDIDAS = [  # (nome, DAX, formato, pasta) - todas na tabela fVagas
    ("Total de vagas", "COUNTROWS ( fVagas )", N, "Vagas"),
    ("Vagas de entrada", 'CALCULATE ( [Total de vagas], KEEPFILTERS ( dNivel[vaga_de_entrada] = "Sim" ) )', N, "Vagas"),
    ("% vagas de entrada", "DIVIDE ( [Vagas de entrada], [Total de vagas] )", P, "Vagas"),
    ("% entrada que pede experiência",
     'DIVIDE ( CALCULATE ( SUM ( fVagas[pede_experiencia] ), KEEPFILTERS ( dNivel[vaga_de_entrada] = "Sim" ) ), [Vagas de entrada] )',
     P, "Vagas"),
    ("% menciona graduação", "DIVIDE ( SUM ( fVagas[menciona_graduacao] ), [Total de vagas] )", P, "Formação e idioma"),
    ("% exige diploma concluído", "DIVIDE ( SUM ( fVagas[exige_diploma_concluido] ), [Total de vagas] )", P,
     "Formação e idioma"),
    ("% aceita cursando", "DIVIDE ( SUM ( fVagas[aceita_cursando] ), [Total de vagas] )", P, "Formação e idioma"),
    ("% cita inglês", "DIVIDE ( SUM ( fVagas[cita_ingles] ), [Total de vagas] )", P, "Formação e idioma"),
    ("% remoto", 'DIVIDE ( CALCULATE ( [Total de vagas], KEEPFILTERS ( dModelo[modelo_trabalho] = "Remoto" ) ), [Total de vagas] )',
     P, "Trabalho e contratação"),
    ("% PJ (contratação informada)",
     'DIVIDE ( CALCULATE ( [Total de vagas], KEEPFILTERS ( dVinculo[vinculo] = "PJ" ) ), '
     'CALCULATE ( [Total de vagas], KEEPFILTERS ( dVinculo[informado] = "Sim" ) ) )', P, "Trabalho e contratação"),
    ("Menções de competências", "COUNTROWS ( fVagaCompetencia )", N, "Competências"),
    ("% competências técnicas",
     'DIVIDE ( CALCULATE ( [Menções de competências], KEEPFILTERS ( dCompetencia[tipo] = "Técnica" ) ), [Menções de competências] )',
     P, "Competências"),
    ("% competências comportamentais",
     'DIVIDE ( CALCULATE ( [Menções de competências], KEEPFILTERS ( dCompetencia[tipo] = "Comportamental" ) ), '
     "[Menções de competências] )", P, "Competências"),
    ("Média de competências técnicas por vaga",
     "DIVIDE ( SUM ( fVagas[qtd_competencias_tecnicas] ), [Total de vagas] )", "0.00", "Competências"),
    ("Vagas que citam a competência", "DISTINCTCOUNT ( fVagaCompetencia[id_vaga] )", N, "Competências"),
    ("% das vagas que citam a competência",
     "DIVIDE ( [Vagas que citam a competência], CALCULATE ( [Total de vagas], REMOVEFILTERS ( dCompetencia ) ) )",
     P, "Competências"),
]

spec = {
    "arquivo": ARQUIVO,
    "tabelas": [{"nome": t, "descricao": desc, "m": consulta(t, cols),
                 "colunas": [{"nome": c, "tipo": tp, "oculta": c in OCULTAS, "categoria": CATEGORIA.get((t, c)),
                              "ordenar_por": ORDENAR.get((t, c)), "formato": FORMATO.get((t, c))} for c, tp in cols]}
                for t, (desc, cols) in TABELAS.items()],
    "relacoes": [{"de_tabela": a, "de_coluna": b, "para_tabela": c, "para_coluna": d, "dois_sentidos": e}
                 for a, b, c, d, e in RELACOES],
    "medidas": [{"tabela": "fVagas", "nome": n, "dax": dax, "formato": f, "pasta": p} for n, dax, f, p in MEDIDAS],
}
(AQUI / "modelo_powerbi.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"bi/modelo_powerbi.json: {len(spec['tabelas'])} tabelas, {len(spec['relacoes'])} relacionamentos, "
      f"{len(spec['medidas'])} medidas")

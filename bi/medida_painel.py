"""
Medida DAX "HTML Painel", que gera o painel interativo exibido pelo visual HTML Content do Power BI (edição normal).

A medida entrega o estilo, os dados (dimensões e a coluna calculada fVagas[codigo_painel], uma linha por vaga) e o
código de bi/painel.js, que monta o painel e aplica os filtros. Os filtros do próprio Power BI continuam valendo.

Uso: python bi/medida_painel.py   (grava bi/medida_painel.json, carregado por carrega_medida_painel.ps1)
"""
import json
import re
from pathlib import Path

AQUI = Path(__file__).parent

MARINHO, AZUL = "#1B3A5C", "#2B5C8A"
MARINHO_RGB = ",".join(str(int(MARINHO[i:i + 2], 16)) for i in (1, 3, 5))   # matriz e mapa: marinho com transparência
MODELO = {"Presencial": MARINHO, "Híbrido": "#4F7CA8", "Remoto": "#9DB9D5"}  # "Não informado" fica cinza
MAPA_UF = [  # mapa em quadrados: (UF, linha, coluna), posições aproximadas do território
    ("RR", 1, 2), ("AP", 1, 3), ("AM", 2, 2), ("PA", 2, 3), ("MA", 2, 4), ("CE", 2, 5), ("RN", 2, 6),
    ("AC", 3, 1), ("RO", 3, 2), ("TO", 3, 3), ("PI", 3, 4), ("PE", 3, 5), ("PB", 3, 6),
    ("MT", 4, 2), ("GO", 4, 3), ("BA", 4, 4), ("SE", 4, 5), ("AL", 4, 6),
    ("MS", 5, 2), ("DF", 5, 3), ("MG", 5, 4), ("ES", 5, 5), ("PR", 6, 2), ("SP", 6, 3), ("RJ", 6, 4),
    ("SC", 7, 2), ("RS", 8, 2)]
assert len({uf for uf, _, _ in MAPA_UF}) == 27 and len({(l, c) for _, l, c in MAPA_UF}) == 27

CSS = """
*{box-sizing:border-box;margin:0}
.pn{--u:calc(100vw/1280);width:100%;display:flex;flex-direction:column;gap:U(8);padding:U(10) U(10) U(8);
background:#EEF1F5;color:#1B2A3A;font-family:'Segoe UI',wf_segoe-ui_normal,Helvetica,Arial,sans-serif;
font-variant-numeric:tabular-nums}
.ld{padding:U(16);font-size:U(12);color:#5B6878}
.hd{height:U(52);flex:none;background:MARINHO;border-radius:U(4);padding:0 U(14) 0 U(16);display:flex;align-items:center;
gap:U(14);color:#fff}
.hd-t{display:flex;flex-direction:column;gap:U(2);flex:none;width:U(250);min-width:0}
.hd-h{font-size:U(19);font-weight:600;line-height:1.15}
.hd-s{font-size:U(10);color:#BFD0E2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fl{margin-left:auto;display:flex;align-items:flex-end;gap:U(6)}
.fc{display:flex;flex-direction:column;gap:U(2);width:U(118)}
.fc span{font-size:U(8.5);color:#9FB6CE;white-space:nowrap}
.fc select{width:100%;height:U(21);font-family:inherit;font-size:U(10);color:#fff;background:rgba(255,255,255,.08);
border:1px solid rgba(255,255,255,.28);border-radius:U(3);padding:0 U(3);outline:none;cursor:pointer}
.fc.at span{color:#fff}.fc.at select{background:rgba(255,255,255,.22);border-color:#fff}
.fc select option,.fc select optgroup{color:#1B2A3A;background:#fff}
.lp{height:U(21);padding:0 U(10);font-family:inherit;font-size:U(10);color:#fff;background:transparent;
border:1px solid rgba(255,255,255,.45);border-radius:U(3);cursor:pointer}
.lp:disabled{opacity:.35;cursor:default}
.kp{height:U(78);flex:none;display:grid;grid-template-columns:repeat(6,1fr);gap:U(8)}
.kc{background:#fff;border:1px solid #DDE3EA;border-radius:U(4);padding:U(8) U(12);display:flex;
flex-direction:column;min-width:0}
.kl{font-size:U(10.5);color:#5B6878;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kc b{font-size:U(22);font-weight:600;color:MARINHO;line-height:1.2}
.kc small{font-size:U(9);color:#7A8694;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kb{margin-top:auto;height:U(4);background:#E6EBF0;border-radius:U(2);overflow:hidden}
.kb i{display:block;height:100%;background:AZUL}
.r2{height:U(300);flex:none;display:grid;grid-template-columns:1fr 1.4fr 1fr;gap:U(8)}
.r3{height:U(214);flex:none;display:grid;grid-template-columns:.95fr 1fr .95fr 1.3fr;gap:U(8)}
.tl{background:#fff;border:1px solid #DDE3EA;border-radius:U(4);padding:U(10) U(12);min-width:0;overflow:hidden}
.tt{font-size:U(12);font-weight:600;color:#1B2A3A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ts{font-size:U(9.5);color:#7A8694;margin:U(1) 0 U(8);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.br{display:grid;grid-template-columns:U(128) 1fr U(38);align-items:center;gap:U(8);height:U(21.5)}
.b2{grid-template-columns:U(118) 1fr U(38);height:U(19)}
.b3{grid-template-columns:U(104) 1fr U(38);height:U(19)}
.b4{grid-template-columns:U(86) 1fr U(38);height:U(19)}
.bl{font-size:U(10.5);color:#33414F;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bt{height:U(9)}.bt i{display:block;height:100%;background:AZUL;border-radius:0 U(2) U(2) 0}
.bv{font-size:U(10.5);text-align:right;white-space:nowrap}
.nt{font-size:U(9);color:#7A8694;margin-top:U(6);line-height:1.35}
.vz{font-size:U(10);color:#7A8694}
[data-d]{cursor:pointer}
.br[data-d]:hover .bl,.nt[data-d]:hover,td.mc:hover{color:MARINHO;text-decoration:underline}
.br.off .bt i{background:#C3D0DD}.br.off .bl,.br.off .bv{color:#9AA5B1}
.br.on .bt i{background:MARINHO}.br.on .bl,.br.on .bv{font-weight:600;color:#1B2A3A}
.nt.on{font-weight:600;color:MARINHO}
table{width:100%;border-collapse:separate;border-spacing:U(2);table-layout:fixed}
th{font-size:U(9.5);font-weight:600;color:#5B6878;text-align:center;line-height:1.2;padding:0 U(2) U(3);
vertical-align:bottom}
th:first-child{width:U(112)}
th small{display:block;font-size:U(8.5);font-weight:400;color:#8C97A4}
th.on{color:MARINHO;box-shadow:inset 0 U(-2) 0 MARINHO}
td{font-size:U(10);text-align:center;height:U(17);padding:0 U(2)}
td.mc{text-align:left;font-size:U(10.5);color:#33414F;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
td.mc.on{font-weight:600;color:MARINHO}td.mc.off{color:#9AA5B1}
td.nd{color:#8C97A4}td.mm{background:#F1F4F7;font-weight:600}td.mr{text-align:left;font-weight:600;white-space:nowrap}
.dw{display:flex;align-items:center;gap:U(14);height:U(150)}
.dn{width:U(108);height:U(108);border-radius:50%;flex:none;position:relative}
.dh{position:absolute;inset:U(20);background:#fff;border-radius:50%;display:flex;flex-direction:column;
align-items:center;justify-content:center}
.dh b{font-size:U(18);font-weight:600;color:MARINHO;line-height:1.1}.dh span{font-size:U(9);color:#7A8694}
.dl{display:flex;flex-direction:column;gap:U(7);min-width:0;flex:1}
.lg{display:grid;grid-template-columns:U(10) 1fr auto;gap:U(6);align-items:center;font-size:U(10.5);color:#33414F}
.lg i{width:U(10);height:U(10);border-radius:U(2)}.lg b{font-weight:600;color:#1B2A3A}
.lg:hover span{text-decoration:underline}.lg.off{opacity:.45}.lg.on span{font-weight:600;color:MARINHO}
.mw{display:flex;gap:U(16);align-items:flex-start}
.mp{display:grid;grid-template-columns:repeat(6,U(18));grid-template-rows:repeat(8,U(18));gap:U(1.5);flex:none}
.mp div{display:flex;align-items:center;justify-content:center;font-size:U(7.5);font-weight:600;border-radius:U(2)}
.mp div.off{opacity:.28}.mp div.on{box-shadow:0 0 0 U(1.5) #1B2A3A}.mp div:hover{box-shadow:0 0 0 U(1.5) AZUL}
.mr{flex:1;min-width:0}
.ft{display:flex;gap:U(12);font-size:U(9);color:#7A8694;padding:0 U(2)}
.ft span:first-child{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ft span:last-child{white-space:nowrap;color:#5B6878}
"""
CSS = re.sub(r"U\((-?[\d.]+)\)", lambda m: f"calc({m.group(1)}*var(--u))", CSS)
CSS = CSS.replace("MARINHO", MARINHO).replace("AZUL", AZUL).replace("\n", "")

# código do painel: tira as linhas de comentário e troca as marcas pelos valores
JS = "\n".join(l for l in (AQUI / "painel.js").read_text(encoding="utf-8").splitlines() if not l.strip().startswith("//"))
for marca, valor in {"%%MAPA_JS%%": json.dumps([list(t) for t in MAPA_UF]).replace('"', "'"),
                     "%%PRESENCIAL%%": MODELO["Presencial"], "%%HIBRIDO%%": MODELO["Híbrido"],
                     "%%REMOTO%%": MODELO["Remoto"], "%%RGB%%": MARINHO_RGB}.items():
    assert marca in JS, marca
    JS = JS.replace(marca, valor)
assert "%%" not in JS and '"' not in JS and '"' not in CSS   # vão dentro de strings DAX
assert "</script" not in JS


def txt_js(coluna: str) -> str:
    """Texto de uma coluna pronto para ir entre aspas simples no JavaScript."""
    return f"""SUBSTITUTE ( SUBSTITUTE ( {coluna}, "\\", "\\\\" ), "'", "\\'" )"""


# coluna calculada: uma linha compacta por vaga (ver o cabeçalho de painel.js)
COLUNA = r'''
VAR b36 = "0123456789abcdefghijklmnopqrstuvwxyz"
VAR uf = RELATED ( dLocal[uf] )
VAR marcas = fVagas[menciona_graduacao] + 2 * fVagas[exige_diploma_concluido] + 4 * fVagas[aceita_cursando] + 8 * fVagas[cita_ingles] + 16 * fVagas[pede_experiencia]
VAR comps =
    CONCATENATEX (
        RELATEDTABLE ( fVagaCompetencia ),
        MID ( b36, INT ( fVagaCompetencia[sk_competencia] / 36 ) + 1, 1 ) & MID ( b36, MOD ( fVagaCompetencia[sk_competencia], 36 ) + 1, 1 ),
        "", fVagaCompetencia[sk_competencia], ASC
    )
RETURN
    MID ( b36, fVagas[sk_plataforma] + 1, 1 ) & IF ( uf = "Sem UF", "--", uf ) & MID ( b36, fVagas[sk_nivel] + 1, 1 )
        & MID ( b36, fVagas[sk_modelo_trabalho] + 1, 1 ) & MID ( b36, fVagas[sk_vinculo] + 1, 1 ) & MID ( b36, marcas + 1, 1 ) & comps
'''

DAX = f'''
-- dimensões completas (para as listas de filtro) e uma linha compacta por vaga (respeita os filtros do Power BI)
VAR d_Plat = CONCATENATEX ( ALL ( dPlataforma ), "[" & dPlataforma[sk_plataforma] & ",'" & {txt_js("dPlataforma[plataforma]")} & "']", ",", dPlataforma[sk_plataforma], ASC )
VAR d_Niv = CONCATENATEX ( ALL ( dNivel ), "[" & dNivel[sk_nivel] & ",'" & {txt_js("dNivel[nivel]")} & "'," & IF ( dNivel[vaga_de_entrada] = "Sim", 1, 0 ) & "]", ",", dNivel[sk_nivel], ASC )
VAR d_Mod = CONCATENATEX ( ALL ( dModelo ), "[" & dModelo[sk_modelo_trabalho] & ",'" & {txt_js("dModelo[modelo_trabalho]")} & "']", ",", dModelo[sk_modelo_trabalho], ASC )
VAR d_Vin = CONCATENATEX ( ALL ( dVinculo ), "[" & dVinculo[sk_vinculo] & ",'" & {txt_js("dVinculo[vinculo]")} & "'," & IF ( dVinculo[informado] = "Sim", 1, 0 ) & "]", ",", dVinculo[sk_vinculo], ASC )
VAR d_Uf = CONCATENATEX ( SUMMARIZE ( ALL ( dLocal ), dLocal[uf], dLocal[regiao] ), "'" & IF ( dLocal[uf] = "Sem UF", "--", dLocal[uf] ) & "':'" & {txt_js("dLocal[regiao]")} & "'", ",", dLocal[uf], ASC )
VAR d_Comp = CONCATENATEX ( ALL ( dCompetencia ), "[" & dCompetencia[sk_competencia] & ",'" & {txt_js("dCompetencia[competencia]")} & "','" & IF ( dCompetencia[tipo] = "Técnica", "T", "C" ) & "']", ",", dCompetencia[sk_competencia], ASC )
VAR d_Vagas = CONCATENATEX ( fVagas, fVagas[codigo_painel], ";" )
RETURN
    "<style>%%CSS%%</style><div class='pn'><div class='ld'>Carregando o painel... Se esta mensagem não sumir, o visual não está executando scripts: use o HTML Content (edição normal), não o HTML Content Secure.</div></div>"
        & "<script>(function(){{var D={{p:[" & d_Plat & "],n:[" & d_Niv & "],m:[" & d_Mod & "],v:[" & d_Vin & "],u:{{" & d_Uf & "}},c:[" & d_Comp & "],x:'" & d_Vagas & "'}};"
        & "%%JS%%"
        & "}})();</script>"
'''
DAX = DAX.replace("%%CSS%%", CSS).replace("%%JS%%", JS)
assert "%%" not in DAX

spec = {
    "coluna": {"tabela": "fVagas", "nome": "codigo_painel", "dax": COLUNA.strip(),
               "descricao": "Linha compacta da vaga para o painel interativo (medida HTML Painel)"},
    "medida": {"tabela": "fVagas", "nome": "HTML Painel", "dax": DAX.strip(), "pasta": "HTML"},
}
(AQUI / "medida_painel.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"bi/medida_painel.json: coluna fVagas[codigo_painel] e medida HTML Painel ({len(DAX):,} caracteres de DAX, "
      f"{len(JS):,} de JavaScript)")

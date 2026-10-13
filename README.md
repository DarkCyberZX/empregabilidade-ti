# Empregabilidade em TI: competências exigidas nas vagas de TI no Brasil

Código e dados do Trabalho de Conclusão de Curso de **João Victhor Monteiro Barros** e **Roberto dos Santos Silva
Junior** (Bacharelado em Sistemas de Informação, Instituto Federal de Alagoas, campus Maceió, 2026), com orientação do
Prof. Edison Camilo de Moraes Junior.

O trabalho coleta os catálogos completos de vagas de três plataformas brasileiras de recrutamento (Gupy, Sólides e
InfoJobs), identifica as vagas da área de TI, extrai por mineração de texto as competências técnicas e comportamentais e
os requisitos de cada vaga e organiza os resultados em um painel no Power BI.

| | |
|---|---|
| Coleta | 27 e 28 de setembro de 2026 |
| Anúncios coletados | 280.868 |
| Vagas de TI únicas analisadas | 8.551 |
| Competências no dicionário | 82 (71 técnicas e 11 comportamentais) |

## Estrutura

```
coleta_vagas_gupy.py      coleta da Gupy e regras comuns: filtro de TI, dicionário de competências, nível, requisitos
coleta_solides.py         coleta da Sólides
coleta_outras_fontes.py   coleta da InfoJobs (e da Vagas.com e ProgramaThor, avaliadas e não usadas)
coleta_apis_menores.py    coleta da Remotar, Trampos e GitHub (avaliadas e não usadas)
analise_multifontes.py    junta as fontes, aplica o filtro de TI, remove repetições e gera a análise
analises_complementares.py  famílias de cargo, pares de competências, recorte regional e plataformas
validacao.py              amostras para leitura manual (vagas de TI e experiência no júnior) e cálculo dos resultados
auditoria_cobertura.py    listas para conferência manual do filtro de TI na Gupy
saida/                    catálogos coletados (.csv.gz) e resultados da análise
bi/                       modelo dimensional e painel do Power BI
```

## Como reproduzir os resultados

Requer Python 3.13 (versões próximas devem funcionar).

```bash
pip install -r requirements.txt
python analise_multifontes.py
```

O script lê os catálogos salvos em `saida/` (a coleta de 27 e 28/09/2026) e grava `saida/vagas_ti_multifontes.xlsx`,
com as abas `vagas` (uma linha por vaga), `competencias`, `kpis`, `nivel`, `uf`, `resumo_fontes` e
`competencias_por_fonte`, além dos gráficos `saida/multi_*.png`. Os números do trabalho saem dessa planilha.

```bash
python analises_complementares.py
```

Gera `saida/analises_complementares.xlsx`, com as famílias de cargo, os pares de competências citados na mesma vaga, o recorte por região (incluindo Nordeste e Alagoas) e a comparação entre plataformas.

### Coletar de novo (opcional)

```bash
python coleta_vagas_gupy.py
python coleta_solides.py
python coleta_outras_fontes.py infojobs
```

A coleta leva várias horas e traz as vagas abertas **no dia em que for executada**, portanto os números serão
diferentes dos do trabalho. Os coletores usam apenas rotas públicas permitidas pelo `robots.txt` de cada site, sem
login, e fazem pausa entre as requisições. Mudanças nos sites podem exigir ajustes nos coletores.

### Painel no Power BI (Windows)

```bash
python bi/gera_modelo.py      # modelo em estrela: bi/modelo_vagas_ti.xlsx (confere os indicadores com a análise)
python bi/spec_powerbi.py     # tabelas, relacionamentos e medidas: bi/modelo_powerbi.json
python bi/medida_painel.py    # medida do painel: bi/medida_painel.json
```

Com o Power BI Desktop aberto em um arquivo novo:

```powershell
powershell -File bi\carrega_powerbi.ps1         # cria as tabelas, os relacionamentos e as medidas e carrega os dados
powershell -File bi\carrega_medida_painel.ps1   # cria a medida "HTML Painel"
```

Depois, adicione à página o visual **HTML Content** (edição normal, não a Secure), disponível na loja de visuais do
Power BI, e coloque nele a medida `HTML Painel`. `bi/atualiza_dados.ps1` recarrega os dados depois de rodar a
análise de novo. Os scripts `confere_*.ps1` comparam o modelo com a análise e precisam do DAX Studio instalado.
Uma prévia do painel, que abre no navegador, está em `bi/previa/previa_painel.html`.

## Dados

- `saida/catalogo_gupy.csv.gz`, `catalogo_solides.csv.gz` e `catalogo_infojobs.csv.gz`: anúncios coletados (todas as
  áreas), no esquema comum de colunas das fontes.
- `saida/vagas_ti_multifontes.xlsx`: as 8.551 vagas de TI com nível, forma de contratação, local, modelo de trabalho,
  requisitos e competências identificadas.
- `saida/vagas_removidas_nao_ti.csv`: os 368 anúncios retirados na revisão do filtro de TI por serem de outras
  áreas, com o motivo de cada um.
- `saida/vagas_incluidas_revisao.csv`: as 168 vagas de TI que o filtro deixava de fora e passaram a ser incluídas
  na mesma revisão, com o motivo de cada uma.
- `saida/analises_complementares.xlsx`: famílias de cargo, pares de competências, recorte regional e plataformas.
- `saida/cobertura_coleta.csv`: vagas anunciadas pela API da Gupy e vagas coletadas, por fatia do catálogo.

Os anúncios foram publicados pelas empresas nas plataformas de recrutamento e são disponibilizados aqui apenas para
fins acadêmicos e de reprodutibilidade da pesquisa.
E-mails, telefones, links de WhatsApp e números com formato de CPF que apareciam nas descrições, nos títulos e nos
nomes das empresas foram substituídos por `[e-mail]`, `[telefone]`, `[whatsapp]` e `[documento]` (nos links, só o
trecho com o número); os resultados publicados já foram gerados a partir dos dados com essa substituição.

## Limitações

A extração identifica a menção a uma competência ou requisito, sem distinguir o que é obrigatório do que é desejável;
o nível de senioridade não é informado em 35,9% das vagas; e a base é um retrato das vagas abertas nas datas da coleta.
As demais limitações estão descritas no capítulo 5 do trabalho.

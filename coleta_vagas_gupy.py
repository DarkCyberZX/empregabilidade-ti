"""
Coleta do catálogo de vagas da Gupy e regras de análise comuns a todas as fontes (filtro de TI, competências,
requisitos e nível).

Uso:
    python coleta_vagas_gupy.py                 coleta o catálogo e gera a análise da Gupy
    python coleta_vagas_gupy.py --sem-coleta    reprocessa o catálogo salvo em saida/

A API pagina até o offset 9.900 por consulta, por isso o catálogo é dividido em fatias (estado, modelo de trabalho,
tipo de vaga e cidade) até que cada uma possa ser lida por completo.

Saídas em saida/: catalogo_gupy.csv.gz, cobertura_coleta.csv, vagas_ti_analise.xlsx e gráficos.
"""
import argparse
import html
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import requests
from wordcloud import WordCloud, STOPWORDS

API = "https://employability-portal.gupy.io/api/v1/jobs"
PAGE = 100
MAX_OFFSET = 9900
PAUSA = 0.35        # segundos entre requisições
SAIDA = Path(__file__).parent / "saida"

ESTADOS = ["Acre", "Alagoas", "Amapá", "Amazonas", "Bahia", "Ceará", "Distrito Federal", "Espírito Santo", "Goiás",
           "Maranhão", "Mato Grosso", "Mato Grosso do Sul", "Minas Gerais", "Pará", "Paraíba", "Paraná", "Pernambuco",
           "Piauí", "Rio de Janeiro", "Rio Grande do Norte", "Rio Grande do Sul", "Rondônia", "Roraima",
           "Santa Catarina", "São Paulo", "Sergipe", "Tocantins"]
MODELOS = ["on-site", "hybrid", "remote"]
TIPOS = ["vacancy_type_effective", "vacancy_type_talent_pool", "vacancy_type_internship", "vacancy_legal_entity",
         "vacancy_type_apprentice", "vacancy_type_associate", "vacancy_type_temporary", "vacancy_type_lecturer",
         "vacancy_type_autonomous", "vacancy_type_outsource", "vacancy_type_trainee", "vacancy_type_parter",
         "vacancy_type_summer", "vacancy_type_freelancer"]

# Primeira etapa: o título precisa casar com algum cargo ou área de TI.
_G = r"(?: ?\([ao]s?\))?"   # marcador de gênero
_CARGO = (r"(?:analista|cientista|engenheir[oa]|arquitet[oa]|especialista|coordenador[a]?|gerente|assistente|auxiliar|"
          r"estagi[aá]ri[oa]|est[aá]gio|adm[i]?nistrador[a]?|t[eé]cnic[oa]|supervisor[a]?|l[ií]der|operador[a]?|atendente|agente|"
          r"consultor[a]?|auditor[a]?|implantador[a]?|profissionais|pessoa (?:analista|t[eé]cnica|administradora|engenheira))" + _G)
_QUALIF_DADOS = (r"(?:engenharia|an[aá]lise|opera[cç][oõ]es|gest[aã]o|governan[cç]a|processamento|performance|qualidade|integra[cç][aã]o|"
                 r"modelagem|arquitetura|ci[eê]ncia|intelig[eê]ncia|plataforma|banco|base)")
FILTRO_TI = re.compile(
    # termos gerais
    r"\bti\b|\bt\.i\b|^t i$|(?<=\W)tic\b(?!\W*trens)|\btecnologia|(?:of|corporate) technology|technology (?:innovation|delivery)|\bit\b|inform[aá]tica|"
    # desenvolvimento
    r"software|desenvolvedor|developer|\bdevs?\b|programador|desenvolvimento (?:de )?(?:software|sistemas|web|mobile|aplica)|desenvolvimento\W+sistemas|\bsql\b|"
    r"full.?stack|front.?end|back.?end|\bmobile\b|\bandroid\b|\bios\b|\bweb\b|firmware|desenvolvimento de sw\b|"
    r"\bjava\b|\bpython\b|\.net\b|\bphp\b|\breact\b|\bnode\b|\bgolang\b|\bcobol\b|\babap\b|mainframe|servicenow|"
    # sistemas e ERP
    r"analista (?:de |desenvolvedor )?sistemas|sistemas de informa|analista funcional (?:de |em )?sistemas|"
    + _CARGO + r" (?:de |em )?(?:(?:implanta[cç][aã]o|sustenta[cç][aã]o|suporte|seguran[cç]a|an[aá]lise|desenvolvimento|integra[cç][aã]o) de )?sistemas?\b|"
    r"analista\W+(?:\w+\W+)?sistemas\b|sistemas? computaciona|implanta[cç][aã]o de sistemas?|implementa[cç][aã]o de sistemas?|arq\.? sistemas|field de sistemas|"
    r"sistema mes\b|sustenta[cç][aã]o\W+(?:de\W+)?(?:sistemas|infraestrutura)|analista de requisitos|"
    r"sistemas embarcados|analista funcional|\bsap\b|salesforce|\berp\b|totvs|protheus|\btasy\b|\brpa\b|automa[cç][aã]o de processos|"
    r"power platform|power automate|low.?code|automa[cç][aã]o de (?:redes|qualidade)|"
    # dados e IA
    + _CARGO + r" (?:\w+ )?(?:de |em )?(?:" + _QUALIF_DADOS + r" (?:de )?)?dados\b|modelagem.{0,4}dados|times de dados|"
    r"estagi[aá]ri[oa](?:\(a\))?\W+dados|\beng\.? de dados|engenharia de dados|\bb\.i\b|\bdbre\b|^(?!.*financeir).*\bfinops\b|tech pool|informa[cç][oõ]es gerenciais|\bmis\b|tec\.? da informa|vis[aã]o computacional|computa[cç][aã]o|"
    r"integra[cç][oõ]es e dados|neg[oó]cios e sistemas|realidade (?:aumentada|virtual)|ci[eê]ncia de dados|"
    r"(?:administrador[a]?|analista|desenvolvedor[a]?|especialista|dba)\W.{0,12}banco (?:de )?dados|"
    r"modelador de dados|informix|\bdata\b|\bbi\b|business intelligence|analytics|power ?bi|\bdba\b|\bsgbd\b|"
    r"intelig[eê]ncia artificial|\bia\b|\bai\b|machine learning|\bml\b|\bllm|\bgen ?ai\b|\bgenia\b|prompt|"
    # infraestrutura, redes, suporte e segurança
    r"devops|\bsre\b|cloud|\bnuvem\b|\baws\b|azure|" + _CARGO + r" (?:de |em )?infraestrutura|infraestrutura (?:de )?(?:ti|tecnologia|redes|cloud)|"
    + _CARGO + r" (?:de |em )?redes|redes e (?:infra|telecom|seguran)|\bnoc\b|\bsoc\b|monitoramento de redes|data ?center|"
    r"suporte (?:t[eé]cnico|de ti|em ti|de sistemas|a sistemas|n[1-3]\b|[1-3]n\b|n[íi]vel|e implanta)|suporte [1-3]n\b|" + _CARGO + r" (?:de |em )?suporte\b|"
    r"virtualiza[cç][aã]o|\bstorage\b|analista de servidores|observabilidade|engenharia de plataforma|middleware|openshift|"
    r"ansible|dynatrace|zabbix|datadog|\bitsm\b|service ?now|\bcisco\b|administra[cç][aã]o de (?:redes|servidores|banco de dados)|"
    r"administrador de banco de dados|redes de computadores|prote[cç][aã]o de redes|redes e sec\b|hardware e redes|"
    r"manuten[cç][aã]o de (?:computadores|micro|notebooks?)|t[eé]cnic[oa] (?:em|de) (?:hardware|computadores)|equipamentos de ti\b|"
    r"\bitam\b|hardware asset|network (?:&|and|e) security|network security|enterprise network|"
    r"(?:analista|consultor|engenheir[oa]|especialista|specialist|analyst|consultant)\W+(?:\w+\W+){0,2}network\b(?! performance| operations)|"
    r"\bciber|seguran[cç]a de dados|endpoint management|digital workplace|analista (?:de )?rede\b(?! (?:credenciad|oficinas|socia))|ger[eê]ncia de redes|\bsoar\b|\bcsirt\b|threat (?:hunting|intelligence)|conten[cç][aã]o de incidentes|seg(?:uran[cç]a)?\.? info\b|"
    r"application support|appsec|vmware|red hat|\blinux\b|veeam|(?:analista|especialista|administrador\w*|engenheir\w*|t[eé]cnic\w*|operador\w*)\W+(?:de\W+)?backup|backup\W+(?:de\W+)?(?:ti|dados)\b|infraestrutura de rede|adm(?:inistrador|\.)? de rede|core ip|"
    r"help.?desk|service.?desk|seguran[cç]a d[ae] informa|cyber|ciberseg|seguran[cç]a cibern|forense (?:digital|computacional)|"
    r"purple team|red team|blue team|pentest|secops|\bsiem\b|ztna|seguran[cç]a grc|resposta a incidentes|incidentes de seguran|"
    r"seguran[cç]a (?:de )?(?:sistemas|infraestrutura|aplica|redes|cloud|ofensiva|defensiva)|arquitetura de seguran|seguran[cç]a sr -f5|"
    r"transforma[cç][aã]o digital(?! -)|(?:gest[aã]o|coordenador\w*|especialista|gerente|analista|pessoa analista de projetos) "
    r"(?:\w+ )?(?:de )?(?:\(?agilidade e )?produtos? digita|\(p\.?o\)|\bp\.o\b|wordpress|engineering manager|"
    # qualidade, produto, arquitetura e UX
    r"\bqa\b|\bq\.a\b|qualidade de software|analista\W+(?:de\W+testes?|testes)\b|\btester\b|\btestador(?:\(a\)|a)?\b(?!\s*-\s*manaus)|testes? de software|quality assurance|automa[cç][aã]o de testes|"
    r"product owner|product manager|scrum|agile coach|\bux\b|\bui\b|"
    r"arquitet[oa]" + _G + r" (?:de )?(?:software|solu[cç]|sistemas|cloud|nuvem|ti\b|integra|seguran|redes|infra|dados|corporativ)|arquitetura de (?:software|solu|sistemas|dados|integra)|arquitetura digital|solutions? architect|"
    r"technical lead|tech ?lead|arquitet[oa]" + _G + r" de (?:apis?|micro)|teach lead|head of engineering|squad leader de dados|"
    r"tech lead|engenheir[oa]" + _G + r" de (?:software|computa|plataforma|confiabilidade|machine|ml|telecom)|"
    r"(?:software|data|cloud|devops|platform|backend|back-end|frontend|front-end|full.?stack|ml|machine learning|security|"
    r"site reliability|qa|test|mobile|ai|genai|rag|support|iam|infrastructure|integration|network(?: \w+)?|principal|workplace|"
    r"systems|devsecops|ip telephony) engineer",
    re.I,
)

# Cargos de outras áreas que casam com FILTRO_TI.
EXCLUI_TI = re.compile(
    r"instalador|reparador|rede externa|rede de acesso|cabos? telef|manuten[cç][aã]o de rede|consultor externo de rede|"
    r"seguran[cç]a do trabalho|eletroeletr|componentes|rede de vendas|programador de (?:servi[cç]os|produ[cç])|"
    r"gest[aã]o da qualidade|sistema de gest[aã]o|motorista|recrutador|tech recruiter|talent acquisition|"
    r"t[eé]cnic[oa]\w* (?:de )?(?:ativa[cç][aã]o|infraestrutura) e suporte telecom|suporte telecom|atendimento e suporte telecom|"
    r"\bsoc\b.{0,3}(?:io|ia)\b|s[oó]cio|pre-sales solutions engineer|(?<!process )mining|quality engineer|"
    r"redes sociais|social media|arquitet[oa](?:\(a\))? (?:de interiores|urbanista|civil)|vendedor|executivo de vendas|"
    r"\bclp\b|\bcnc\b|programador de manuten|analista comercial|suporte ao paciente|auxiliar operacional|"
    r"programa[cç][aã]o log|est[aá]gio em arquitetura|enfermagem|professor|"
    r"(?<!informa[cç][aã]o e )prote[cç][aã]o de dados|privacidade|advogad|\btribut|executivo de tecnologia|coordenador curso|tomografia|"
    r"sistemas? (?:da )?(?:qualidade|florest|de armazen|de tratamento|tratamento|de energia|audiovisual|org[aâ]nic|irriga|embalage|g[aá]s|"
    r"de monitora[cç][aã]o|vrv|daimer|comos|de esquadria)|manut\w* (?:de )?equip(?!\w* de (?:ti|inform[aá]tica)\b)|aeronav|suporte (?:acad|comercial|administ|a polos|ao cliente)|"
    r"sistemas? (?:el[eé]tric|hidr[aá]ulic|de refrigera|de inc[eê]ndio|de climatiza|mec[aâ]nic|de gest[aã]o(?! \(erp\)))|"
    r"promotor|executivo comercial|executiv[oa](?:\(a\))? de contas|representante comercial|inside sales|marketing manager|"
    r"produtor[a]? de conte|excel[eê]ncia operacional|crm growth|implantador de redes|\(comercial\)|"
    r"tecnologia do concreto|suporte\W+departamento pessoal|"
    r"analista de backoffice|voz e chat|desenvolvedor(?:\(a\))? de mercado|licita[cç]|compras|relacionamento cliente|tecnologia de alimentos|tecnologia (?:em|de) (?:alimentos|sementes|produ[cç][aã]o|aplica[cç][aã]o agr)|"
    # saúde e serviços
    r"enfermeir|fonoaudi|almoxarif|recepcionista|cozinha|desenhista|tr[aá]fego pago|secretaria acad|previdenci|"
    # planejamento de produção e manutenção
    r"programador(?:\(a\))?\s+(?:de\s+)?(?:pcp|manuten|log[ií]stic|materiais|quadro|el[eé]tric|produ[cç][aã]o|planejador|frota)|programador\s*-\s*eletricista|programador e operador|"
    # mecânica, elétrica, equipamentos e obras
    r"mec[aâ]nic|infraestrutura el[eé]tric|gerente de el[eé]trica|projetos el[eé]tricos|eletricista|fotovolt|tra[cç][aã]o el[eé]tric|"
    r"testes automotivos|equipamentos? m[eé]dicos|raios x|engenharia cl[ií]nica|suporte e equipamento|eletrot[eé]cnica|linha agr[ií]cola|"
    r"testador de ve[ií]culos|vaga n[aã]o existe|\[externo\]\[p[uú]blica|data entry|t[eé]cnic[oa] eletr[oô]nic|projetista eletr|testador produtos|\(el[eé]trica/eletr[oô]nica\)|eletr[oô]nica e equipamentos|\beta\b|\bete\b|portaria|infraestrutura e obras|predial|laborat[oó]rio da qualidade|"
    r"operador de m[aá]quina|desinfetante|^bi - (?!.*(?:analista|dados|desenvolv|engenh))|"
    r"refrigera|ar.condicionado|\bhvac\b|usinagem|sistemas? audiovisua|operador de sistema de cftv|"
    r"redes e frotas|suporte a frota|suporte (?:t[eé]cnico )?automotivo|^(?!.*suporte digital).*tecnologia automotiva|"
    r"^(?!.*(?:inform[aá]tica|bolsista)).*automa[cç][aã]o industrial|suporte industrial|tecnologia industrial|"
    # segurança eletrônica sem menção a TI
    r"^(?!.*(?:inform[aá]tica|\bti\b|\bredes\b)).*seguran[cç]a\W+(?:-\s*)?eletr[oô]nica|"
    # vendas e comercial
    r"\bsdr\b|\bbdr\b|closer comercial|\bhunters?\b|(?<!technical )account manager|executiv[oa](?:\(a\))?\s+(?:de vendas|comercial|de novos|de parcerias|de comunica|corporativo de contrata)|"
    r"new business executive|executiva de vendas|gerente comercial|consultor(?:\(a\)|a)?\s*(?:\(a\)\s*)?(?:comercial|comecial|de vendas|de servi[cç]os e vendas)|"
    r"comercial (?:jr|vendas)|time comercial|vagas comercial|desenvolvedor(?:\(a\))? de (?:neg[oó]cios|novos neg[oó]cios|vendas)|"
    r"desenvolvedor de vendas|sales developer|agente de novos neg[oó]cios|supervisor(?:\(a\))? de neg[oó]cios|analista de vendas|"
    r"suporte (?:a |de |ao )?vendas|suporte ao corban|(?:auxiliar|assistente) de vendas|vendas (?:web|beleza)|beleza na web|consultor de vendas web|cobran[cç]a link web|"
    r"telemarketing|atendente de cr[eé]dito|cobran[cç]a/reten|"
    # finanças e contabilidade
    r"analista cont[aá]bil|analista fiscal|analista de tesouraria|analista financeiro (?:s[eê]nior - contas|administrativo)|"
    r"assistente (?:administrativo )?financeiro|especialista financeiro|coordenador adm|analista (?:s[eê]nior )?de (?:folha|departamento pessoal)|l[ií]der fiscal|"
    r"processamento de dados/fiscal|faturamento erp",
    re.I,
)

# Títulos que só casam por um termo genérico e trazem um cargo de outra área são decididos pela descrição.
GENERICO_TI = re.compile(r"(?:ti|t\.i|tecnologia|technology|it|inform[aá]tica|computa[cç][aã]o|ia|ai|web|data|backup|ui|ml|"
                         r"front.?end|back.?end)", re.I)
CARGO_NAO_TI = re.compile(
    r"administrativ|(?<!pr[eé]-)(?<!pr[eé] )vendas|vendedor|\bsdr\b|comercial|de contas|clientes|customer success|compras|comprador|"
    r"treinamento|eletricista|mec[aâ]nic|automotiv|agr[ií]col|museu|materiais|relacionamento|marketing|recep[cç]|"
    r"jur[ií]dic|financeir|log[ií]stic|farm[aá]c|enfermag|enfermeir|cozinh|limpeza|patrimonial|"
    r"audiovisual|growth|conte[uú]do|engenharia civil|alugu[eé]is|fiscal|cont[aá]bil|"
    r"operador\w*(?:\(a\))? de (?:loja|caixa)|estacionamento|subgerente|estoquista|corretor|esteticista|merchandising|varejo|"
    r"electric|designer gr[aá]fico|motion|diretor de arte|editor de v[ií]deo|v[ií]deo\b|cria[cç][aã]o|\bseo\b|analista de e-?commerce|"
    r"redator|planner|\bdbm\b|sele[cç][aã]o|opera[cç][oõ]es de rh|talento de voz|instrutor|educador|docen|ensino|tutor|monitor de oficina|"
    r"coordenador\w*(?:\(a\))? de cursos?|loja de inform|auxiliar de produ|impress[aã]o 3d|rastreamento|"
    r"tecnologia de produto|est[aá]gio adm|comunica[cç][aã]o|eletr[oô]nicos\b|atendimento bil[ií]ngue|healthcare|atendimento eletr", re.I)
TECNICO_TI = re.compile(r"t[eé]cnic[oa]\w*\W+(?:\w+\W+){0,2}(?:de |em )?\(?(?:ti|t\.i)\b", re.I)
BOLSISTA = re.compile(r"bolsista", re.I)


def so_termo_generico(titulo: str) -> bool:
    achados = [m.group(0) for m in FILTRO_TI.finditer(titulo)]
    return bool(achados) and all(GENERICO_TI.fullmatch(a.strip(" .")) for a in achados)


# Segunda etapa: título ambíguo é aceito quando os requisitos citam ao menos MIN_TI_FORTE grupos de tecnologias de TI.
TITULO_AMBIGUO = re.compile(
    r"^(?!.*(?:industrial|empresarial|patrimonial|predial|el[eé]tric|trabalho|alimentar|do produto|telecom))"
    r".*(?:seguran[cç]a|automa[cç][aã]o|suporte|sistemas?\b|\binfra|implanta|(?<!pesquisa e )desenvolvimento|"
    r"sustenta[cç][aã]o|l[ií]der t[eé]cnico|banco de dados)",
    re.I,
)
TI_FORTE = {
    "sql": r"\bsql\b", "python": r"\bpython\b", "java": r"\bjava\b", "javascript": r"javascript|typescript",
    "csharp": r"c#|\.net\b", "cloud": r"\baws\b|\bazure\b|\bgcp\b|google cloud", "container": r"docker|kubernetes",
    "linux": r"\blinux\b", "windows_server": r"windows server", "ad": r"active directory|\bentra id\b",
    "firewall": r"firewall|\bvpn\b|fortinet|palo alto", "tcpip": r"tcp/ip|\bdns\b|\bdhcp\b", "api": r"\bapis?\b|rest(?:ful)?\b",
    "git": r"\bgit\b|github|gitlab", "itil": r"\bitil\b|glpi|service ?now|jira service",
    "siem": r"\bsiem\b|\bsoc\b|splunk|sentinel|pentest|iso 27001|nist", "virtualizacao": r"vmware|hyper-?v|proxmox",
    "rpa": r"\brpa\b|uipath|power automate|automation anywhere",
    "banco": r"oracle|postgres|mysql|sql server|mongodb", "etl": r"\betl\b|databricks|airflow|spark",
}
MIN_TI_FORTE = 4


def n_ti_forte(texto: str) -> int:
    return sum(1 for rx in TI_FORTE.values() if re.search(rx, texto))


# Competências técnicas
HARD = {
    "Python": r"\bpython\b", "Java": r"\bjava\b(?!\s*script)", "JavaScript": r"\bjavascript\b|\bjs\b",
    "TypeScript": r"\btypescript\b", "C#": r"c#|c sharp", ".NET": r"\.net\b|dotnet",
    "PHP": r"\bphp\b", "Go": r"\bgolang\b|\bgo lang\b", "Kotlin": r"\bkotlin\b", "Swift": r"\bswift\b",
    "C/C++": r"\bc\+\+|\bc/c\+\+", "Ruby": r"\bruby\b", "Dart/Flutter": r"\bflutter\b|\bdart\b",
    "R": r"\blinguagem r\b|\br studio\b|\brstudio\b", "COBOL": r"\bcobol\b", "ABAP": r"\babap\b",
    "SQL": r"\bsql\b", "NoSQL": r"\bnosql\b", "PostgreSQL": r"postgres", "MySQL": r"\bmysql\b",
    "SQL Server": r"sql server", "Oracle": r"\boracle\b", "MongoDB": r"mongo",
    "React": r"\breact\b|react\.?js", "React Native": r"react native", "Angular": r"\bangular\b",
    "Vue": r"\bvue\b|vue\.?js", "Node.js": r"\bnode\b|node\.?js", "Next.js": r"next\.?js",
    "Spring": r"\bspring\b", "Django": r"\bdjango\b", "Flask": r"\bflask\b", "FastAPI": r"fastapi",
    "Laravel": r"\blaravel\b", "HTML/CSS": r"\bhtml\b|\bcss\b",
    "API REST": r"\brest\b|restful|\bapis?\b", "Microsserviços": r"micro.?servi",
    "Mensageria (Kafka/RabbitMQ)": r"kafka|rabbitmq|mensageria",
    "AWS": r"\baws\b|amazon web services", "Azure": r"\bazure\b", "GCP": r"\bgcp\b|google cloud",
    "Docker": r"\bdocker\b", "Kubernetes": r"kubernetes|\bk8s\b", "Terraform": r"terraform",
    "CI/CD": r"ci/cd|ci ?& ?cd|\bci\b|jenkins|github actions|gitlab ci|azure devops|integra[cç][aã]o cont[ií]nua|entrega cont[ií]nua|deploy cont[ií]nuo",
    "Git": r"\bgit\b|github|gitlab|bitbucket", "Linux": r"\blinux\b", "Windows Server": r"windows server",
    "Redes (TCP/IP)": r"tcp/ip|\bredes\b(?! sociais| neurais| de (?:lojas|varejo|supermercados?|farm[aá]cias|drogarias|"
                      r"cosm[eé]ticos|hot[eé]is|restaurantes|franquias|ensino|escolas|sa[uú]de|hospitais|cl[ií]nicas|"
                      r"laborat[oó]rios|parceiros|relacionamento|contatos|distribui|vendas|atendimento|postos|academias|"
                      r"concession|varejistas|empresas|unidades|filiais))|firewall|\bvpn\b|roteador|\bswitch(?:es)?\b|\blan\b|\bwan\b",
    "Active Directory": r"active directory|\bad\b(?!-)",
    "ITIL": r"\bitil\b", "Power BI": r"power ?bi", "Excel": r"\bexcel\b", "Tableau": r"tableau",
    "Qlik": r"\bqlik", "ETL": r"\betl\b|\belt\b", "Spark": r"\bspark\b", "Databricks": r"databricks",
    "Airflow": r"airflow", "Pandas": r"\bpandas\b", "Machine Learning": r"machine learning|aprendizado de m[aá]quina",
    "IA / LLM": r"intelig[eê]ncia artificial|\bllms?\b|\bgenai\b|ia generativa|\bia\b",
    "Estatística": r"estat[ií]stic", "Testes automatizados": r"testes? automatizad|automa[cç][aã]o de testes|selenium|cypress|jest|junit",
    "Segurança (cyber)": r"seguran[cç]a da informa|cyber|ciberseg|pentest|\bsoc\b|\biso 27001",
    "Scrum/Ágil": r"scrum|kanban|\bagile\b|(?:metodologias?|m[eé]todos?|pr[aá]ticas?|frameworks?|cerim[oô]nias?|times?|"
                  r"squads?|gest[aã]o|projetos?) [aá]ge?is\b|(?:metodologia|pr[aá]tica|gest[aã]o|abordagem|framework) [aá]gil\b",
    "Clean Code/SOLID": r"clean code|solid\b|design patterns",
    "SAP": r"\bsap\b", "Salesforce": r"salesforce", "UX/UI": r"\bux\b|\bui\b|figma",
    "Android/iOS": r"\bandroid\b|\bios\b",
}

# Competências comportamentais
SOFT = {
    "Comunicação": r"(?:boa|excelente|[oó]tima|habilidades? de|capacidade de|facilidade de|facilidade na) comunica[cç][aã]o|"
                   r"comunica[cç][aã]o (?:verbal|escrita|oral|clara|eficaz|eficiente|assertiva|interpessoal)|comunicativ",
    "Trabalho em equipe": r"trabalho em equipe|trabalhar em equipe|esp[ií]rito de equipe|(?<!ambiente )(?<!din[aâ]mico e )colaborativ",
    "Proatividade": r"proativ", "Resolução de problemas": r"resolu[cç][aã]o de problemas|resolver problemas|solu[cç][aã]o de problemas",
    "Organização": r"\borganizad[oa]|senso de organiza|capacidade de organiza|boa organiza|organiza[cç][aã]o (?:pessoal|e planejamento|e gest)",
    "Autonomia": r"autonom[ií]a(?! para| e protagonismo)|(?:forma|maneira|perfil|profissional) aut[oô]nom[oa]|autodidat", "Liderança": r"lideran[cç]a",
    "Pensamento analítico": r"(?:pensamento|perfil|vis[aã]o|capacidade|habilidade) anal[ií]tic|racioc[ií]nio (?:l[oó]gico|anal[ií]tico)",
    "Aprendizado contínuo": r"aprendizado cont[ií]nuo|vontade de aprender|curios|autodesenvolv|aprender (?:coisas novas|continuamente|r[aá]pido)",
    "Adaptabilidade": r"adaptabilidade|capacidade de adapta|facilidade de adapta|lidar com mudan",
    "Foco no cliente": r"foco no cliente|orienta[cç][aã]o ao cliente|relacionamento com (?:o )?cliente",
}

RE_DIPLOMA = re.compile(
    r"(?:superior|gradua[cç][aã]o|bacharelado|tecn[oó]logo|forma[cç][aã]o acad[eê]mica)[^.\n]{0,40}complet|"
    r"(?:ensino|forma[cç][aã]o) superior (?:em|na [aá]rea)|gradua[cç][aã]o em|bacharelado em|forma[cç][aã]o em (?:ci[eê]ncia|engenharia|sistemas|an[aá]lise|tecnologia|ti\b)",
    re.I,
)
# Graduação em andamento
_SUPERIOR = (r"(?:superior|gradua[cç][aã]o|faculdade|bacharel\w*|tecn[oó]logo|engenharias?\b|ci[eê]ncias? da computa|"
             r"sistemas de informa|\bads\b|an[aá]lise e desenv)")
RE_CURSANDO = re.compile(
    r"cursando\s+(?:o\s+|a\s+|um\s+|uma\s+)?(?:ensino superior|n[ií]vel superior|curso superior|superior|gradua|faculdade|"
    r"bacharel|tecn[oó]logo|engenharia|ci[eê]ncias?\b|sistemas|an[aá]lise|tecnologia|\bti\b|inform[aá]tica|computa|"
    r"administra|matem|estat|economia|direito|contabil|ci[eê]ncias cont|[uú]ltimo|pen[uú]ltimo|\d|"
    r"cursos? (?:de|em|superior|na|nas|relacionad))|"
    r"cursando ou (?:ter )?(?:conclu[ií]d[oa]|complet[oa]|cursado)[^.\n]{0,30}" + _SUPERIOR + "|"
    + _SUPERIOR + r"[^.\n]{0,60}(?:em andamento|incomplet|cursando)|"
    r"(?:em andamento|cursando)[^.\n]{0,40}" + _SUPERIOR + "|"
    r"matriculad[oa]s?\s+(?:em|no|na|num|numa)\s+(?:curso|gradua|ensino superior|faculdade|institui|bacharel)|"
    r"a partir do \d+\s*[ºoaª°]?\s*(?:semestre|per[ií]odo|ano)",
    re.I,
)
RE_INGLES = re.compile(r"ingl[eê]s|english", re.I)
RE_EXPERIENCIA = re.compile(r"experi[eê]ncia (?:com|em|pr[aá]tica|comprovada|s[oó]lida|anterior)|viv[eê]ncia (?:com|em)|\d+\+? anos? de experi", re.I)

NIVEIS_ENTRADA = ["Aprendiz", "Estágio", "Trainee", "Júnior"]

VINCULO = {
    "vacancy_type_effective": "Efetivo (CLT)", "vacancy_legal_entity": "PJ", "vacancy_type_internship": "Estágio",
    "vacancy_type_talent_pool": "Banco de talentos", "vacancy_type_trainee": "Trainee", "vacancy_type_apprentice": "Aprendiz",
    "vacancy_type_temporary": "Temporário", "vacancy_type_autonomous": "Autônomo/Freelancer",
    "vacancy_type_freelancer": "Autônomo/Freelancer", "vacancy_type_associate": "Associado",
}

UF = {
    "Acre": "AC", "Alagoas": "AL", "Amapá": "AP", "Amazonas": "AM", "Bahia": "BA", "Ceará": "CE",
    "Distrito Federal": "DF", "Espírito Santo": "ES", "Goiás": "GO", "Maranhão": "MA", "Mato Grosso": "MT",
    "Mato Grosso do Sul": "MS", "Minas Gerais": "MG", "Pará": "PA", "Paraíba": "PB", "Paraná": "PR",
    "Pernambuco": "PE", "Piauí": "PI", "Rio de Janeiro": "RJ", "Rio Grande do Norte": "RN",
    "Rio Grande do Sul": "RS", "Rondônia": "RO", "Roraima": "RR", "Santa Catarina": "SC",
    "São Paulo": "SP", "Sergipe": "SE", "Tocantins": "TO",
}
REGIAO = {
    **dict.fromkeys(["AC", "AP", "AM", "PA", "RO", "RR", "TO"], "Norte"),
    **dict.fromkeys(["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"], "Nordeste"),
    **dict.fromkeys(["DF", "GO", "MT", "MS"], "Centro-Oeste"),
    **dict.fromkeys(["ES", "MG", "RJ", "SP"], "Sudeste"),
    **dict.fromkeys(["PR", "RS", "SC"], "Sul"),
}

STOP_PT = set("""
a à ao aos as às até com como da das de dela dele deles demais depois do dos e é ela ele eles em entre era essa esse
esta está estão este eu foi for há isso isto já la lá lhe mais mas me mesmo meu minha muito na nas não nem no nos nós
o os ou para pela pelas pelo pelos por qual quando que quem se seja sem ser seu seus só sua suas também te tem têm
todo todos toda todas tu um uma umas uns você vocês vai vão sobre será serão sendo sim onde nosso nossa nossos nossas
cada bem pode podem após assim ainda outro outra outros outras fazer faz feito ter ser estar etc além através dentro
vaga vagas empresa empresas time equipe área areas área atuar atuação buscamos procuramos oportunidade profissional
profissionais pessoa pessoas trabalho trabalhar responsabilidades atribuições requisitos qualificações informações
adicionais diferenciais desejáveis desejável conhecimento conhecimentos experiência experiências atividades atividade
benefícios benefício junte-se venha nosso nossa você seu sua dia dias ano anos parte forma novo nova novos novas
será cliente clientes sobre processo processos projeto projetos soluções solução desenvolvimento desenvolver
garantir apoiar apoio realizar contribuir participar busca buscando grande melhor melhores sempre todo mercado
responsabilidade qualificação requisito atribuição essenciais essencial desejáveis diferencial necessário necessária
ambiente ambientes áreas negócio negócios sistema sistemas dado tecnologia tecnologias técnica técnicas técnico técnicos análise
ferramenta ferramentas boa boas bom bons são aqui junto somos estamos acreditamos utilizando incluindo garantindo
capacidade necessidade demanda impacto resultado resultados melhoria evolução informação acompanhar identificar
criar construir construção manter uso meio alta alto avançado relacionados relacionadas relacionado correlatas
correlatos demais principais principal diversos diversas diferentes diferente outras outros novas novos
""".split())


def normaliza(txt: str) -> str:
    txt = html.unescape(txt or "")
    txt = re.sub(r"<[^>]+>", " ", txt)
    return re.sub(r"[ \t ]+", " ", unicodedata.normalize("NFKC", txt)).strip()


RE_INI_RESP = re.compile(r"responsabilidades e atribui")
RE_INI_ADIC = re.compile(r"informa[cç][oõ]es adicionais")


def secoes(desc: str) -> tuple[str, str]:
    """(texto sem benefícios, texto só de responsabilidades + requisitos). Sem cabeçalhos, devolve o texto inteiro."""
    fim = RE_INI_ADIC.search(desc)
    sem_adic = desc[:fim.start()] if fim and fim.start() > 200 else desc
    ini = RE_INI_RESP.search(sem_adic)
    return sem_adic, (sem_adic[ini.start():] if ini else sem_adic)


def vinculo(tipo) -> str:
    """Forma de contratação a partir do código da Gupy ou do texto livre das outras fontes."""
    if not isinstance(tipo, str) or not tipo.strip():
        return "Não informado"
    if tipo in VINCULO:
        return VINCULO[tipo]
    t = tipo.lower()
    # a InfoJobs informa a jornada, não o regime de contratação
    if re.fullmatch(r"\s*(?:jornada completa|tempo parcial|meio per[ií]odo)\s*", t):
        return "Não informado"
    for padrao, rotulo in [(r"est[aá]gi|internship", "Estágio"), (r"trainee", "Trainee"), (r"aprendiz", "Aprendiz"),
                           (r"\bpj\b|pessoa jur|prestador", "PJ"), (r"clt|efetiv|emprego", "Efetivo (CLT)"),
                           (r"freela|aut[oô]nom", "Autônomo/Freelancer"), (r"tempor", "Temporário"),
                           (r"banco de talentos|talent", "Banco de talentos"), (r"cooperad", "Associado")]:
        if re.search(padrao, t):
            return rotulo
    return "Outros"


# Algarismo romano do plano de cargos (I = júnior, II = pleno, III = sênior), exceto em "T.I" e entre dois cargos.
ROMANO = re.compile(r"(?<![\w.&])(i{1,3})(?![\w.&])(?!\s+(?:supervisor|t[eé]cnic|[aá]rea|analista|coordenador|gerente)\b)")
# "Senior" também é nome de ERP
SENIOR = re.compile(r"(?<!erp )(?<!mega/)s[eê]nior(?! sistemas)|\bsr\b")


def nivel(nome: str, tipo: str) -> str:
    """Nível pelo título: palavra explícita, depois cargo de especialista ou liderança, depois algarismo romano."""
    n, t = nome.lower(), (tipo if isinstance(tipo, str) else "").lower()
    if "apprentice" in t or "aprendiz" in n or "aprendiz" in t:
        return "Aprendiz"
    if "internship" in t or re.search(r"est[aá]gi|estagi[aá]ri|\bintern\b", n) or re.search(r"est[aá]gi", t):
        return "Estágio"
    if "trainee" in t or "trainee" in n:
        return "Trainee"
    if re.search(r"j[uú]nior|\bjr\b|junior", n):
        return "Júnior"
    if re.search(r"pleno|\bplena\b|\bpl\b|\bmid\b|\bmedior\b", n):
        return "Pleno"
    if SENIOR.search(n):
        return "Sênior"
    if re.search(r"especialista|specialist|staff|principal|l[ií]der|lead|coordenad|gerente|head|arquitet[oa]\b|arquitet[oa]\(", n):
        return "Especialista/Liderança"
    m = ROMANO.search(n)
    if m:
        return {"i": "Júnior", "ii": "Pleno", "iii": "Sênior"}[m.group(1)]
    return "Não informado"


class Coletor:
    """Catálogo da Gupy lido em fatias que cabem no limite de paginação da API."""

    def __init__(self):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "Mozilla/5.0 (pesquisa academica TCC)"
        self.vagas: dict[int, dict] = {}
        self.cobertura = []

    def _get(self, params: dict) -> dict:
        for tentativa in range(5):
            try:
                r = self.s.get(API, params=params, timeout=60)
                r.raise_for_status()
                time.sleep(PAUSA)
                return r.json()
            except (requests.RequestException, ValueError) as e:
                espera = 2 ** (tentativa + 1)
                print(f"   erro {params}: {e} — nova tentativa em {espera}s")
                time.sleep(espera)
        raise RuntimeError(f"falha persistente em {params}")

    def total(self, filtros: dict) -> int:
        # o 'total' só é confiável na primeira página
        return self._get({**filtros, "limit": 1, "offset": 0})["pagination"]["total"]

    def _pagina_tudo(self, filtros: dict, ordem: str, limite: int) -> set[int]:
        ids, offset = set(), 0
        while offset <= min(MAX_OFFSET, limite):
            dados = self._get({**filtros, "limit": PAGE, "offset": offset,
                               "sortBy": "publishedDate", "sortOrder": ordem}).get("data", [])
            for j in dados:
                self.vagas.setdefault(j["id"], j)
                ids.add(j["id"])
            if len(dados) < PAGE:
                break
            offset += PAGE
        return ids

    def fatia(self, filtros: dict, dims: list, rotulo: str):
        t = self.total(filtros)
        if t == 0:
            return
        if t <= MAX_OFFSET + PAGE:
            self._pagina_tudo(filtros, "asc", t)
        elif t <= 2 * (MAX_OFFSET + PAGE):
            # as mais antigas e as mais novas cobrem a fatia inteira
            self._pagina_tudo(filtros, "asc", t)
            self._pagina_tudo(filtros, "desc", t)
        elif dims:
            chave, valores = dims[0]
            if callable(valores):
                self._pagina_tudo(filtros, "asc", t)
                self._pagina_tudo(filtros, "desc", t)
                valores = valores(filtros)
            for v in valores:
                self.fatia({**filtros, chave: v}, dims[1:], f"{rotulo} > {v}")
        else:
            print(f"   AVISO: fatia {rotulo} tem {t} vagas e não há mais como dividir; coleta parcial")
            self._pagina_tudo(filtros, "asc", t)
            self._pagina_tudo(filtros, "desc", t)
        coletado = sum(1 for j in self.vagas.values() if self._na_fatia(j, filtros))
        self.cobertura.append({"fatia": rotulo, "total_api": t, "coletado": coletado})
        print(f"{rotulo:60s} api={t:6d}  coletado={coletado:6d}  (catálogo {len(self.vagas)})", flush=True)

    @staticmethod
    def _na_fatia(vaga: dict, filtros: dict) -> bool:
        return all(vaga.get(k) == v for k, v in filtros.items())

    def cidades(self, filtros: dict) -> list[str]:
        # cidades do estado vistas em qualquer fatia já lida
        uf = filtros.get("state")
        return sorted({j["city"] for j in self.vagas.values() if j.get("city") and j.get("state") == uf})


def coleta() -> tuple[pd.DataFrame, pd.DataFrame]:
    c = Coletor()
    total_geral = c.total({})
    dims = [("workplaceType", MODELOS), ("type", TIPOS), ("city", c.cidades)]
    # São Paulo por último, quando as cidades das outras fatias já são conhecidas
    for uf in [e for e in ESTADOS if e != "São Paulo"] + ["São Paulo"]:
        c.fatia({"state": uf}, dims, uf)
    # vagas sem estado
    c.fatia({"workplaceType": "remote"}, [], "Remotas (qualquer estado)")
    c.fatia({"workplaceType": "hybrid"}, [], "Híbridas (qualquer estado)")
    total_brasil = c.total({"country": "Brasil"})
    cob = pd.DataFrame(c.cobertura)
    no_brasil = sum(1 for j in c.vagas.values() if j.get("country") in ("Brasil", None))
    cob.loc[len(cob)] = {"fatia": "CATÁLOGO INTEIRO (todos os países)", "total_api": total_geral, "coletado": len(c.vagas)}
    cob.loc[len(cob)] = {"fatia": "BRASIL (escopo do TCC)", "total_api": total_brasil, "coletado": no_brasil}
    print(f"\nCatálogo: API anuncia {total_geral} vagas ({total_brasil} no Brasil); coletadas {len(c.vagas)} "
          f"({no_brasil} no Brasil = {100 * no_brasil / total_brasil:.1f}% do Brasil).")
    df = pd.DataFrame(c.vagas.values())
    df["coletado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return df, cob


def enriquece(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["name"] = df["name"].map(normaliza)
    no_brasil = df["country"].isna() | (df["country"] == "Brasil")   # sem país = remota anunciada no Brasil
    df = df[no_brasil].copy()
    excluido = df["name"].str.contains(EXCLUI_TI)
    generico = df["name"].map(so_termo_generico) & df["name"].str.contains(CARGO_NAO_TI) & ~df["name"].str.contains(TECNICO_TI) & ~df["name"].str.contains(BOLSISTA)
    df["ti_pelo_titulo"] = df["name"].str.contains(FILTRO_TI) & ~excluido & ~generico
    candidato = ~df["ti_pelo_titulo"] & ~excluido & (df["name"].str.contains(TITULO_AMBIGUO) | generico)
    df["n_ti_forte"] = 0
    df.loc[candidato, "n_ti_forte"] = [
        n_ti_forte(secoes(normaliza(d).lower())[1]) for d in df.loc[candidato, "description"].fillna("")]
    df["ti_pela_descricao"] = candidato & (df["n_ti_forte"] >= MIN_TI_FORTE)
    df = df[df["ti_pelo_titulo"] | df["ti_pela_descricao"]].copy()
    df["criterio_ti"] = df["ti_pelo_titulo"].map({True: "título", False: "descrição (título ambíguo ou genérico)"})
    df["description"] = df["description"].fillna("").map(normaliza)
    df["vinculo"] = df["type"].map(vinculo)

    desc = df["description"].str.lower()
    df["texto_vaga"] = [secoes(t)[0] for t in desc]
    df["texto_requisitos"] = [secoes(t)[1] for t in desc]
    texto = df["name"].str.lower() + " \n " + df["texto_vaga"]
    texto_req = df["name"].str.lower() + " \n " + df["texto_requisitos"]
    df["nivel"] = [nivel(n, t) for n, t in zip(df["name"], df["type"])]
    df["uf"] = df["state"].map(UF)
    df["regiao"] = df["uf"].map(REGIAO)
    sem_uf = df["uf"].isna()
    df.loc[sem_uf, "regiao"] = "Remoto / sem UF"
    df.loc[sem_uf, "uf"] = "—"
    df["modelo_trabalho"] = df["workplaceType"].map({"remote": "Remoto", "hybrid": "Híbrido", "on-site": "Presencial"}).fillna("Não informado")
    df["aceita_cursando"] = texto.str.contains(RE_CURSANDO)
    df["exige_diploma"] = texto.str.contains(RE_DIPLOMA) | df["aceita_cursando"]
    df["exige_diploma_concluido"] = df["exige_diploma"] & ~df["aceita_cursando"]
    df["exige_ingles"] = texto.str.contains(RE_INGLES)
    df["pede_experiencia"] = texto.str.contains(RE_EXPERIENCIA)

    for nome, rx in HARD.items():
        df[f"hard::{nome}"] = texto.str.contains(rx, regex=True)
    for nome, rx in SOFT.items():   # só responsabilidades e requisitos, sem a apresentação da empresa
        df[f"soft::{nome}"] = texto_req.str.contains(rx, regex=True)
    hard_cols = [c for c in df if c.startswith("hard::")]
    soft_cols = [c for c in df if c.startswith("soft::")]
    df["qtd_hard"] = df[hard_cols].sum(axis=1)
    df["qtd_soft"] = df[soft_cols].sum(axis=1)
    df["competencias"] = df[hard_cols + soft_cols].apply(
        lambda r: "; ".join(c.split("::")[1] for c, v in r.items() if v), axis=1)
    return df


def tabelas(df: pd.DataFrame):
    n = len(df)
    linhas = []
    for c in [c for c in df if c.startswith(("hard::", "soft::"))]:
        tipo, nome = c.split("::")
        qtd = int(df[c].sum())
        linhas.append({"competencia": nome, "tipo": "Técnica (hard)" if tipo == "hard" else "Comportamental (soft)",
                       "vagas": qtd, "taxa_demanda_%": round(100 * qtd / n, 2)})
    comp = pd.DataFrame(linhas).sort_values("vagas", ascending=False).reset_index(drop=True)

    entrada = df["nivel"].isin(NIVEIS_ENTRADA)
    com_vinculo = df["vinculo"] != "Não informado"
    ment_hard, ment_soft = df["qtd_hard"].sum(), df["qtd_soft"].sum()
    kpis = pd.DataFrame([
        ("Total de vagas de TI analisadas", n, ""),
        ("Taxa de menção a graduação (%)", round(100 * df["exige_diploma"].mean(), 2), "vagas que citam graduação/ensino superior ÷ total"),
        ("Taxa de exigência de diploma concluído (%)", round(100 * df["exige_diploma_concluido"].mean(), 2),
         "vagas que citam graduação e não aceitam cursando ÷ total"),
        ("Taxa de aceite de 'cursando' (%)", round(100 * df["aceita_cursando"].mean(), 2), "vagas que aceitam graduação em andamento ÷ total"),
        ("Taxa de exigência de inglês (%)", round(100 * df["exige_ingles"].mean(), 2), "vagas que citam inglês ÷ total"),
        ("Taxa de vagas de entrada (%)", round(100 * entrada.mean(), 2), "(aprendiz + estágio + trainee + júnior) ÷ total"),
        ("Vagas de entrada que pedem experiência (%)", round(100 * df.loc[entrada, "pede_experiencia"].mean(), 2) if entrada.any() else 0,
         "vagas de entrada com 'experiência com/em' ÷ vagas de entrada"),
        ("Taxa de trabalho remoto (%)", round(100 * (df["modelo_trabalho"] == "Remoto").mean(), 2), "vagas remotas ÷ total"),
        ("Taxa de vagas PJ (%)", round(100 * (df.loc[com_vinculo, "vinculo"] == "PJ").mean(), 2) if com_vinculo.any() else 0,
         "vagas com contratação PJ ÷ vagas com forma de contratação informada"),
        ("Proporção hard skills (%)", round(100 * ment_hard / (ment_hard + ment_soft), 2), "menções técnicas ÷ todas as menções"),
        ("Proporção soft skills (%)", round(100 * ment_soft / (ment_hard + ment_soft), 2), "menções comportamentais ÷ todas as menções"),
        ("Média de competências técnicas por vaga", round(df["qtd_hard"].mean(), 2), ""),
    ], columns=["kpi", "valor", "formula"])

    niv = df["nivel"].value_counts().rename_axis("nivel").reset_index(name="vagas")
    niv["%"] = (100 * niv["vagas"] / n).round(2)
    uf = df.groupby(["regiao", "uf"], dropna=False).size().reset_index(name="vagas").sort_values("vagas", ascending=False)
    uf["%"] = (100 * uf["vagas"] / n).round(2)
    return comp, kpis, niv, uf


def graficos(df: pd.DataFrame, comp: pd.DataFrame, prefixo: str = "", rotulo: str = "Gupy"):
    texto = " ".join(df["texto_requisitos"])
    texto = re.sub(r"https?://\S+|[^a-zà-ú0-9#+.\s]", " ", texto)
    WordCloud(width=1600, height=900, background_color="white", stopwords=STOPWORDS | STOP_PT,
              collocations=False, max_words=150, colormap="viridis", min_word_length=3
              ).generate(texto).to_file(SAIDA / f"{prefixo}nuvem_vagas.png")

    freq = dict(zip(comp["competencia"], comp["vagas"]))
    freq = {k: v for k, v in freq.items() if v > 0}
    WordCloud(width=1600, height=900, background_color="white", colormap="plasma",
              prefer_horizontal=0.95).generate_from_frequencies(freq).to_file(SAIDA / f"{prefixo}nuvem_competencias.png")

    top = comp[comp["tipo"].str.startswith("Técnica")].head(20).iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(top["competencia"], top["taxa_demanda_%"], color="#2f6db5")
    for y, v in enumerate(top["taxa_demanda_%"]):
        ax.text(v + 0.3, y, f"{v:.1f}%", va="center", fontsize=9)
    ax.set_xlabel("% das vagas que citam a competência")
    ax.set_title(f"Top 20 competências técnicas em vagas de TI — {rotulo} (n = {len(df):,})".replace(",", "."))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(SAIDA / f"{prefixo}top20_competencias.png", dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-coleta", action="store_true", help="reprocessa o catálogo já salvo")
    a = ap.parse_args()

    SAIDA.mkdir(exist_ok=True)
    catalogo, arq_cob = SAIDA / "catalogo_gupy.csv.gz", SAIDA / "cobertura_coleta.csv"
    if a.sem_coleta:
        df = pd.read_csv(catalogo, sep=";", encoding="utf-8", compression="gzip")
        cob = pd.read_csv(arq_cob, sep=";", encoding="utf-8-sig")
    else:
        df, cob = coleta()
        df.drop(columns=["careerPageLogo"], errors="ignore").to_csv(catalogo, sep=";", index=False, encoding="utf-8", compression="gzip")
        cob.to_csv(arq_cob, sep=";", index=False, encoding="utf-8-sig")
        print(f"Catálogo salvo: {catalogo} ({len(df)} vagas)")

    total_catalogo = len(df)
    df = enriquece(df)
    comp, kpis, niv, uf = tabelas(df)

    cols = ["id", "name", "careerPageName", "criterio_ti", "nivel", "vinculo", "city", "uf", "regiao", "modelo_trabalho",
            "publishedDate", "exige_diploma", "exige_diploma_concluido", "aceita_cursando", "exige_ingles", "pede_experiencia",
            "qtd_hard", "qtd_soft", "competencias", "jobUrl", "description"]
    with pd.ExcelWriter(SAIDA / "vagas_ti_analise.xlsx", engine="openpyxl") as w:
        df[cols].to_excel(w, sheet_name="vagas", index=False)
        comp.to_excel(w, sheet_name="competencias", index=False)
        kpis.to_excel(w, sheet_name="kpis", index=False)
        niv.to_excel(w, sheet_name="nivel", index=False)
        uf.to_excel(w, sheet_name="uf", index=False)
        cob.to_excel(w, sheet_name="cobertura_coleta", index=False)
    graficos(df, comp)

    print(f"\nVagas de TI após filtro: {len(df)} de {total_catalogo} vagas no catálogo ({100 * len(df) / total_catalogo:.1f}%)")
    print(kpis.to_string(index=False))
    print("\nTop 15 competências:")
    print(comp.head(15).to_string(index=False))
    print(f"\nArquivos em: {SAIDA}")


if __name__ == "__main__":
    main()

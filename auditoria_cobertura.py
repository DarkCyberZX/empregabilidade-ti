"""
Auditoria do filtro de TI sobre o catálogo completo da Gupy (saida/catalogo_gupy.csv.gz).

Com o catálogo inteiro baixado, a única perda possível é o FILTRO_TI rejeitar um título de TI.
Este script lista, para conferência manual:
  - rejeitados que contêm alguma palavra "suspeita" de TI (onde moram os falsos negativos);
  - uma amostra aleatória dos aceitos (para medir falsos positivos).

Uso: python auditoria_cobertura.py [tamanho_da_amostra]
Saída: saida/auditoria_rejeitados_suspeitos.csv e saida/auditoria_amostra_aceitos.csv
"""
import importlib.util
import re
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
AQUI = Path(__file__).parent
spec = importlib.util.spec_from_file_location("c", AQUI / "coleta_vagas_gupy.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

SUSPEITAS = re.compile(
    r"sistema|dado|tecnolog|desenvolv|suporte|rede|software|digital|tech|automa|program|inform|comput|"
    r"\bti\b|\bit\b|cloud|nuvem|data|seguran|infra|web|app|engineer|developer|analytics|\bbi\b|\bia\b|\bai\b|"
    r"\bnoc\b|\bsoc\b|\berp\b|\bsap\b|totvs|telecom|servidor|hardware|device|cyber|produto",
    re.I,
)

n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
df = pd.read_csv(AQUI / "saida" / "catalogo_gupy.csv.gz", sep=";", compression="gzip",
                 usecols=["id", "name", "country", "type", "city", "state"])
df = df[df["country"].isna() | (df["country"] == "Brasil")].copy()
df["name"] = df["name"].map(c.normaliza)
df["aceito"] = df["name"].str.contains(c.FILTRO_TI) & ~df["name"].str.contains(c.EXCLUI_TI)
df["barrado_por_exclusao"] = df["name"].str.contains(c.FILTRO_TI) & df["name"].str.contains(c.EXCLUI_TI)

rej = df[~df["aceito"] & df["name"].str.contains(SUSPEITAS)]
rej = rej.assign(palavra=rej["name"].str.extract(f"({SUSPEITAS.pattern})", flags=re.I)[0].str.lower())
rej.sort_values(["palavra", "name"]).to_csv(AQUI / "saida" / "auditoria_rejeitados_suspeitos.csv",
                                           sep=";", index=False, encoding="utf-8-sig")
df[df["aceito"]].sample(min(n, df["aceito"].sum()), random_state=42).to_csv(
    AQUI / "saida" / "auditoria_amostra_aceitos.csv", sep=";", index=False, encoding="utf-8-sig")

print(f"Catálogo (Brasil): {len(df)} | aceitos como TI: {df['aceito'].sum()} | "
      f"barrados pela lista de exclusão: {df['barrado_por_exclusao'].sum()} | rejeitados com palavra suspeita: {len(rej)}")
print(rej["palavra"].value_counts().head(30).to_string())

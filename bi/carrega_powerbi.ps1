# Aplica bi/modelo_powerbi.json no Power BI Desktop aberto, via TOM (bibliotecas do próprio Power BI Desktop):
# cria as tabelas com a consulta Power Query, os relacionamentos e as medidas e atualiza os dados.
# Só roda em modelo sem essas tabelas (não sobrescreve nada). Uso: powershell -File bi\carrega_powerbi.ps1
$ErrorActionPreference = "Stop"
$bin = "C:\Program Files\Microsoft Power BI Desktop\bin"
[System.AppDomain]::CurrentDomain.add_AssemblyResolve({ param($s, $e); $n = ($e.Name -split ',')[0]; $p = Join-Path $bin "$n.dll"; if (Test-Path $p) { [System.Reflection.Assembly]::LoadFrom($p) } else { $null } })
Add-Type -Path (Join-Path $bin "Microsoft.AnalysisServices.Server.Core.dll")
Add-Type -Path (Join-Path $bin "Microsoft.AnalysisServices.Server.Tabular.dll")

$base = Split-Path -Parent $MyInvocation.MyCommand.Path
$spec = Get-Content -Raw -Encoding UTF8 (Join-Path $base "modelo_powerbi.json") | ConvertFrom-Json

# servidor local do Power BI Desktop aberto (o espaço de trabalho mais recente)
$ws = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$porta = ([System.IO.File]::ReadAllText((Join-Path $ws.FullName "Data\msmdsrv.port.txt"))) -replace '[^0-9]', ''
$srv = New-Object Microsoft.AnalysisServices.Tabular.Server
$srv.Connect("localhost:$porta")
if ($srv.Databases.Count -ne 1) { throw "esperava 1 modelo aberto no Power BI, achei $($srv.Databases.Count)" }
$m = $srv.Databases[0].Model
"conectado em localhost:$porta | tabelas já existentes: $($m.Tables.Count)"
foreach ($t in $spec.tabelas) { if ($m.Tables.Contains($t.nome)) { throw "a tabela $($t.nome) já existe no modelo: nada foi alterado" } }

$TT = "Microsoft.AnalysisServices.Tabular"
foreach ($t in $spec.tabelas) {
  $tab = New-Object "$TT.Table"
  $tab.Name = $t.nome
  $tab.Description = $t.descricao
  foreach ($c in $t.colunas) {
    $dc = New-Object "$TT.DataColumn"
    $dc.Name = $c.nome; $dc.SourceColumn = $c.nome
    $dc.DataType = [Microsoft.AnalysisServices.Tabular.DataType]::($c.tipo)
    if ($c.oculta) { $dc.IsHidden = $true }
    if ($c.categoria) { $dc.DataCategory = $c.categoria }
    if ($c.formato) { $dc.FormatString = $c.formato }
    if ($c.tipo -eq "Int64") { $dc.SummarizeBy = [Microsoft.AnalysisServices.Tabular.AggregateFunction]::None }
    $tab.Columns.Add($dc)
  }
  foreach ($c in $t.colunas) { if ($c.ordenar_por) { $tab.Columns[$c.nome].SortByColumn = $tab.Columns[$c.ordenar_por] } }
  $p = New-Object "$TT.Partition"
  $p.Name = $t.nome
  $src = New-Object "$TT.MPartitionSource"
  $src.Expression = $t.m
  $p.Source = $src
  $tab.Partitions.Add($p)
  $m.Tables.Add($tab)
  "tabela: $($t.nome) ($($t.colunas.Count) colunas)"
}
foreach ($r in $spec.relacoes) {
  $rel = New-Object "$TT.SingleColumnRelationship"
  $rel.Name = "$($r.de_tabela)_$($r.de_coluna)_$($r.para_tabela)"
  $rel.FromColumn = $m.Tables[$r.de_tabela].Columns[$r.de_coluna]
  $rel.ToColumn = $m.Tables[$r.para_tabela].Columns[$r.para_coluna]
  $rel.FromCardinality = [Microsoft.AnalysisServices.Tabular.RelationshipEndCardinality]::Many
  $rel.ToCardinality = [Microsoft.AnalysisServices.Tabular.RelationshipEndCardinality]::One
  if ($r.dois_sentidos) { $rel.CrossFilteringBehavior = [Microsoft.AnalysisServices.Tabular.CrossFilteringBehavior]::BothDirections }
  else { $rel.CrossFilteringBehavior = [Microsoft.AnalysisServices.Tabular.CrossFilteringBehavior]::OneDirection }
  $m.Relationships.Add($rel)
  "relacionamento: $($r.de_tabela)[$($r.de_coluna)] -> $($r.para_tabela)[$($r.para_coluna)]" + $(if ($r.dois_sentidos) { " (dois sentidos)" } else { "" })
}
foreach ($x in $spec.medidas) {
  $me = New-Object "$TT.Measure"
  $me.Name = $x.nome; $me.Expression = $x.dax; $me.FormatString = $x.formato; $me.DisplayFolder = $x.pasta
  $m.Tables[$x.tabela].Measures.Add($me)
}
"medidas: $($spec.medidas.Count)"
$m.SaveChanges() | Out-Null
"estrutura salva; carregando os dados do Excel..."
$m.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
$m.SaveChanges() | Out-Null
"dados carregados"
$srv.Disconnect()

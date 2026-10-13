# Aplica bi/medida_painel.json no Power BI Desktop aberto, via TOM: cria ou atualiza a coluna calculada
# fVagas[codigo_painel] (recalculando o modelo) e a medida "HTML Painel". Uso: powershell -File bi\carrega_medida_painel.ps1
$ErrorActionPreference = "Stop"
$bin = "C:\Program Files\Microsoft Power BI Desktop\bin"
[System.AppDomain]::CurrentDomain.add_AssemblyResolve({ param($s, $e); $n = ($e.Name -split ',')[0]; $p = Join-Path $bin "$n.dll"; if (Test-Path $p) { [System.Reflection.Assembly]::LoadFrom($p) } else { $null } })
Add-Type -Path (Join-Path $bin "Microsoft.AnalysisServices.Server.Core.dll")
Add-Type -Path (Join-Path $bin "Microsoft.AnalysisServices.Server.Tabular.dll")
$base = Split-Path -Parent $MyInvocation.MyCommand.Path
$spec = Get-Content -Raw -Encoding UTF8 (Join-Path $base "medida_painel.json") | ConvertFrom-Json
$ws = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$porta = ([System.IO.File]::ReadAllText((Join-Path $ws.FullName "Data\msmdsrv.port.txt"))) -replace '[^0-9]', ''
$srv = New-Object Microsoft.AnalysisServices.Tabular.Server
$srv.Connect("localhost:$porta")
$m = $srv.Databases[0].Model

$c = $spec.coluna
if ($c) {
  $t = $m.Tables[$c.tabela]
  if ($t.Columns.Contains($c.nome)) {
    $col = $t.Columns[$c.nome]
    if (-not ($col -is [Microsoft.AnalysisServices.Tabular.CalculatedColumn])) { throw "$($c.nome) já existe e não é coluna calculada" }
  } else {
    $col = New-Object Microsoft.AnalysisServices.Tabular.CalculatedColumn
    $col.Name = $c.nome
    $t.Columns.Add($col)
  }
  if ($col.Expression -ne $c.dax) {
    $col.Expression = $c.dax
    $col.DataType = [Microsoft.AnalysisServices.Tabular.DataType]::String
    $col.IsHidden = $true
    $col.Description = $c.descricao
    $m.SaveChanges() | Out-Null
    $m.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Calculate)
    $m.SaveChanges() | Out-Null
    "coluna $($c.tabela)[$($c.nome)] salva e calculada"
  } else { "coluna $($c.tabela)[$($c.nome)] sem mudança" }
}

$x = $spec.medida
$t = $m.Tables[$x.tabela]
if ($t.Measures.Contains($x.nome)) { $me = $t.Measures[$x.nome] } else { $me = New-Object Microsoft.AnalysisServices.Tabular.Measure; $me.Name = $x.nome; $t.Measures.Add($me) }
$me.Expression = $x.dax; $me.DisplayFolder = $x.pasta
$m.SaveChanges() | Out-Null
"HTML Painel salva"
$srv.Disconnect()

# Atualiza, no Power BI Desktop aberto, a fórmula das medidas de bi/modelo_powerbi.json que já existem no modelo
# (não mexe em tabelas, relacionamentos nem dados). Uso: powershell -File bi\atualiza_medidas.ps1
$ErrorActionPreference = "Stop"
$bin = "C:\Program Files\Microsoft Power BI Desktop\bin"
[System.AppDomain]::CurrentDomain.add_AssemblyResolve({ param($s, $e); $n = ($e.Name -split ',')[0]; $p = Join-Path $bin "$n.dll"; if (Test-Path $p) { [System.Reflection.Assembly]::LoadFrom($p) } else { $null } })
Add-Type -Path (Join-Path $bin "Microsoft.AnalysisServices.Server.Core.dll")
Add-Type -Path (Join-Path $bin "Microsoft.AnalysisServices.Server.Tabular.dll")
$base = Split-Path -Parent $MyInvocation.MyCommand.Path
$spec = Get-Content -Raw -Encoding UTF8 (Join-Path $base "modelo_powerbi.json") | ConvertFrom-Json
$ws = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$porta = ([System.IO.File]::ReadAllText((Join-Path $ws.FullName "Data\msmdsrv.port.txt"))) -replace '[^0-9]', ''
$srv = New-Object Microsoft.AnalysisServices.Tabular.Server
$srv.Connect("localhost:$porta")
$m = $srv.Databases[0].Model
$n = 0
foreach ($x in $spec.medidas) {
  $t = $m.Tables[$x.tabela]
  if (-not $t.Measures.Contains($x.nome)) { throw "medida $($x.nome) não existe no modelo" }
  $me = $t.Measures[$x.nome]
  if ($me.Expression -ne $x.dax) { $me.Expression = $x.dax; $n++; "atualizada: $($x.nome)" }
}
if ($n -gt 0) { $m.SaveChanges() | Out-Null }
"$n medidas atualizadas"
$srv.Disconnect()

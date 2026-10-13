# Recarrega no Power BI Desktop aberto os dados de bi/modelo_vagas_ti.xlsx (gerado por gera_modelo.py), via TOM:
# atualização completa de todas as tabelas, que também recalcula as colunas calculadas (fVagas[codigo_painel]).
# Uso: powershell -File bi\atualiza_dados.ps1
$ErrorActionPreference = "Stop"
$bin = "C:\Program Files\Microsoft Power BI Desktop\bin"
[System.AppDomain]::CurrentDomain.add_AssemblyResolve({ param($s, $e); $n = ($e.Name -split ',')[0]; $p = Join-Path $bin "$n.dll"; if (Test-Path $p) { [System.Reflection.Assembly]::LoadFrom($p) } else { $null } })
Add-Type -Path (Join-Path $bin "Microsoft.AnalysisServices.Server.Core.dll")
Add-Type -Path (Join-Path $bin "Microsoft.AnalysisServices.Server.Tabular.dll")
$ws = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$porta = ([System.IO.File]::ReadAllText((Join-Path $ws.FullName "Data\msmdsrv.port.txt"))) -replace '[^0-9]', ''
$srv = New-Object Microsoft.AnalysisServices.Tabular.Server
$srv.Connect("localhost:$porta")
if ($srv.Databases.Count -ne 1) { throw "esperava 1 modelo aberto no Power BI, achei $($srv.Databases.Count)" }
$m = $srv.Databases[0].Model
"conectado em localhost:$porta | tabelas: $(($m.Tables | ForEach-Object { $_.Name }) -join ', ')"
$m.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
$m.SaveChanges() | Out-Null
"dados recarregados"
$srv.Disconnect()

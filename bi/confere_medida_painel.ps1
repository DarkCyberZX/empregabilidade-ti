$ErrorActionPreference = "Stop"
$bin = "C:\Program Files\DAX Studio\bin"
[System.AppDomain]::CurrentDomain.add_AssemblyResolve({ param($s, $e); $n = ($e.Name -split ',')[0]; $p = Join-Path $bin "$n.dll"; if (Test-Path $p) { [System.Reflection.Assembly]::LoadFrom($p) } else { $null } })
[void][Reflection.Assembly]::LoadFrom((Join-Path $bin "Microsoft.AnalysisServices.AdomdClient.dll"))
$base = Split-Path -Parent $MyInvocation.MyCommand.Path
$ws = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$porta = ([System.IO.File]::ReadAllText((Join-Path $ws.FullName "Data\msmdsrv.port.txt"))) -replace '[^0-9]', ''
$cn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$porta")
$cn.Open()
$utf8 = New-Object System.Text.UTF8Encoding $false
function Salva($nome, $dax) {
  try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $cmd = $cn.CreateCommand(); $cmd.CommandText = $dax
    $r = $cmd.ExecuteReader(); [void]$r.Read(); $v = [string]$r.GetValue(0); $r.Close()
    [System.IO.File]::WriteAllText((Join-Path $base "previa\$nome.html"), $v, $utf8)
    "ok   $nome : $($v.Length) caracteres em $($sw.ElapsedMilliseconds) ms"
  } catch { "ERRO $nome : $($_.Exception.Message)" }
}
Salva "painel" 'EVALUATE ROW("h", [HTML Painel])'
Salva "painel_junior_nordeste" 'EVALUATE CALCULATETABLE(ROW("h", [HTML Painel]), dNivel[nivel] = "Júnior", dLocal[regiao] = "Nordeste")'
Salva "painel_python" 'EVALUATE CALCULATETABLE(ROW("h", [HTML Painel]), dCompetencia[competencia] = "Python")'
Salva "painel_vazio" 'EVALUATE CALCULATETABLE(ROW("h", [HTML Painel]), dNivel[nivel] = "Trainee", dLocal[uf] = "AC")'
$cn.Close()

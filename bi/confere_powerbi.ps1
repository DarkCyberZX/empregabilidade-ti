$ErrorActionPreference = "Stop"
$bin = "C:\Program Files\DAX Studio\bin"
[System.AppDomain]::CurrentDomain.add_AssemblyResolve({ param($s, $e); $n = ($e.Name -split ',')[0]; $p = Join-Path $bin "$n.dll"; if (Test-Path $p) { [System.Reflection.Assembly]::LoadFrom($p) } else { $null } })
[void][Reflection.Assembly]::LoadFrom((Join-Path $bin "Microsoft.AnalysisServices.AdomdClient.dll"))
$ws = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$porta = ([System.IO.File]::ReadAllText((Join-Path $ws.FullName "Data\msmdsrv.port.txt"))) -replace '[^0-9]', ''
$cn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$porta")
$cn.Open()
function Q($dax) {
  $cmd = $cn.CreateCommand(); $cmd.CommandText = $dax
  $r = $cmd.ExecuteReader(); $out = @()
  while ($r.Read()) { $linha = @(); for ($i = 0; $i -lt $r.FieldCount; $i++) { $linha += "$($r.GetName($i))=$($r.GetValue($i))" }; $out += ($linha -join " | ") }
  $r.Close(); return $out
}
Q 'EVALUATE ROW("vagas", [Total de vagas], "graduacao", [% menciona graduação], "concluido", [% exige diploma concluído], "cursando", [% aceita cursando], "ingles", [% cita inglês], "entrada", [% vagas de entrada], "exp_entrada", [% entrada que pede experiência], "remoto", [% remoto], "pj", [% PJ (contratação informada)], "tecnicas", [% competências técnicas], "media_tec", [Média de competências técnicas por vaga], "mencoes", [Menções de competências])'
"--- top 5 competências"
Q 'EVALUATE TOPN(5, SUMMARIZECOLUMNS(dCompetencia[competencia], "vagas", [Vagas que citam a competência], "pct", [% das vagas que citam a competência]), [vagas], DESC) ORDER BY [vagas] DESC'
"--- Python por nível (Q10)"
Q 'EVALUATE CALCULATETABLE(SUMMARIZECOLUMNS(dNivel[nivel], "pct_python", [% das vagas que citam a competência]), dCompetencia[competencia] = "Python")'
"--- vagas por plataforma"
Q 'EVALUATE SUMMARIZECOLUMNS(dPlataforma[plataforma], "vagas", [Total de vagas])'
$cn.Close()

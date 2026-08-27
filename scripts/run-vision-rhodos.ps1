# run-vision-rhodos.ps1 — hervat de Rhodos vision-tag tot alles getagd is, onafhankelijk van de
# Claude-sessie (Scheduled Task) en met keep-awake (voorkomt Modern Standby). Idempotent via sha1-cache.
$ErrorActionPreference = 'Continue'
Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class Power { [DllImport("kernel32.dll", SetLastError=true)]
  public static extern uint SetThreadExecutionState(uint esFlags); }
'@
[void][Power]::SetThreadExecutionState([uint32]2147483649)   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED

$repo   = 'C:\Github\fvh-reisverhalen'
$photos = 'C:/claude/fvh.com/trips/20250908-griekenland/source'
$out    = 'C:/claude/fvh.com/trips/20250908-griekenland/work'
$cache  = Join-Path $out 'cache/vision'
$log    = Join-Path $out 'vision-batch.log'
$total  = 335
Set-Location $repo
$env:PYTHONUTF8 = '1'
Add-Content $log ("[{0}] === wrapper start (keep-awake) ===" -f (Get-Date -Format o))
for ($i = 0; $i -lt 40; $i++) {
  [void][Power]::SetThreadExecutionState([uint32]2147483649)
  python scripts\trip-vision-tag.py --photos $photos --trip "Griekenland" --out $out *>> $log
  $n = @(Get-ChildItem (Join-Path $cache '*.json') -ErrorAction SilentlyContinue).Count
  Add-Content $log ("[{0}] iteratie {1}: cache = {2}/{3}" -f (Get-Date -Format o), $i, $n, $total)
  if ($n -ge $total) { break }
  Start-Sleep -Seconds 15
}
[void][Power]::SetThreadExecutionState([uint32]2147483648)   # release

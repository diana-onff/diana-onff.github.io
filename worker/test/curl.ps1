# PowerShell version of curl.sh, for exercising a deployed Worker from Windows.
#
#   .\worker\test\curl.ps1 https://diana-spotline.diana-onff.workers.dev
#
# Everything here sends "dryrun": true, so Spotline validates but stores nothing.
# Run it once after the first deploy, and again after any change to
# wrangler.toml — that is the file where a wrong value stays invisible until
# somebody tries to spot from a hilltop with one bar of signal.
#
# Invoke-WebRequest throws on any non-2xx status, which is exactly the interesting
# case here, so every call goes through Send() below and the status is read back
# out of the exception. That is not elegant; it is how PowerShell works.

param(
  [Parameter(Mandatory = $true)][string]$BaseUrl
)

$ErrorActionPreference = 'Stop'
$Base = $BaseUrl.TrimEnd('/')
$Origin = 'https://diana-onff.github.io'
$script:pass = 0
$script:fail = 0

function Send {
  param([string]$Method, [string]$Url, [hashtable]$Headers, [string]$Body)
  try {
    $args = @{ Method = $Method; Uri = $Url; Headers = $Headers; UseBasicParsing = $true }
    if ($Body) { $args.Body = $Body; $args.ContentType = 'application/json' }
    $r = Invoke-WebRequest @args
    return @{ Code = [int]$r.StatusCode; Body = $r.Content }
  } catch {
    $resp = $_.Exception.Response
    if ($resp) {
      $code = [int]$resp.StatusCode
      $text = ''
      try {
        $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
        $text = $reader.ReadToEnd()
      } catch { }
      return @{ Code = $code; Body = $text }
    }
    return @{ Code = 0; Body = $_.Exception.Message }
  }
}

function Check {
  param([int]$Want, [string]$What, [string]$Method, [string]$Url, [hashtable]$Headers, [string]$Body)
  $r = Send -Method $Method -Url $Url -Headers $Headers -Body $Body
  if ($r.Code -eq $Want) {
    $script:pass++
    Write-Host ("  OK  {0} ({1})" -f $What, $r.Code) -ForegroundColor Green
  } else {
    $script:fail++
    Write-Host ("  XX  {0} - expected {1}, got {2}" -f $What, $Want, $r.Code) -ForegroundColor Red
    if ($r.Body) { Write-Host ("      {0}" -f $r.Body.Substring(0, [Math]::Min(200, $r.Body.Length))) }
  }
}

$H = @{ Origin = $Origin }

$spot = '{"activator":"ON3VZ/P","spotter":"ON3VZ","frequency_khz":14285,"mode":"SSB","reference":"ONFF-0104","dryrun":true}'

Write-Host ""
Write-Host "Worker: $Base"

Write-Host ""
Write-Host "[1] is it alive"
Check 200 "/status answers" 'GET' "$Base/status" $H $null
$s = Send -Method 'GET' -Url "$Base/status" -Headers $H
Write-Host ("      {0}" -f $s.Body)

Write-Host ""
Write-Host "[2] CORS"
Check 204 "preflight from the app's origin" 'OPTIONS' "$Base/spot" $H $null
Check 403 "preflight from somewhere else" 'OPTIONS' "$Base/spot" @{ Origin = 'https://evil.example' } $null

Write-Host ""
Write-Host "[3] what must be refused before it costs anything"
Check 400 "MHz where kHz was meant" 'POST' "$Base/spot" $H `
  '{"activator":"ON3VZ/P","spotter":"ON3VZ","frequency_khz":14.285,"mode":"SSB","reference":"ONFF-0104","dryrun":true}'
Check 400 "a reference that is not a reference" 'POST' "$Base/spot" $H `
  '{"activator":"ON3VZ/P","spotter":"ON3VZ","frequency_khz":14285,"mode":"SSB","reference":"NOPE","dryrun":true}'
Check 400 "a mode nobody transmits" 'POST' "$Base/spot" $H `
  '{"activator":"ON3VZ/P","spotter":"ON3VZ","frequency_khz":14285,"mode":"TELEPATHY","reference":"ONFF-0104","dryrun":true}'
Check 400 "not even JSON" 'POST' "$Base/spot" $H 'this is not json'
Check 404 "an endpoint that does not exist" 'POST' "$Base/whatever" $H '{}'

Write-Host ""
Write-Host "[4] a real spot, dry"
Check 200 "a valid spot is accepted by Spotline" 'POST' "$Base/spot" $H `
  '{"activator":"ON3VZ/P","spotter":"ON3VZ","frequency_khz":14285,"mode":"SSB","reference":"ONFF-0104","remarks":"dryrun test","dryrun":true}'

Write-Host ""
Write-Host "[5] a real agenda entry, dry"
$start = (Get-Date).ToUniversalTime().AddHours(2).ToString('yyyy-MM-ddTHH:mm:ssZ')
$end = (Get-Date).ToUniversalTime().AddHours(4).ToString('yyyy-MM-ddTHH:mm:ssZ')
Check 200 "a valid announcement is accepted" 'POST' "$Base/agenda" $H `
  ('{"activator_call":"ON3VZ/P","reference":"ONFF-0104","utc_start":"' + $start + '","utc_end":"' + $end + '","pin":"1234","poster":"ON3VZ","dryrun":true}')
Check 400 "an announcement two months out" 'POST' "$Base/agenda" $H `
  '{"activator_call":"ON3VZ/P","reference":"ONFF-0104","utc_start":"2027-01-01T10:00:00Z","utc_end":"2027-01-01T12:00:00Z","pin":"1234","poster":"ON3VZ","dryrun":true}'

Write-Host ""
Write-Host "[6] the rate limiter - this is the one that matters"
Write-Host "    ten spots in a row; the first few pass, the rest must come back 429"
$limited = 0
for ($i = 1; $i -le 10; $i++) {
  $r = Send -Method 'POST' -Url "$Base/spot" -Headers $H -Body $spot
  Write-Host ("    {0,2} -> {1}" -f $i, $r.Code)
  if ($r.Code -eq 429) { $limited++ }
}
if ($limited -gt 0) {
  $script:pass++
  Write-Host ("  OK  the limiter cut in ({0} of 10 refused)" -f $limited) -ForegroundColor Green
} else {
  $script:fail++
  Write-Host "  XX  nothing was refused - check LIMIT_IP_SPOTS and the KV binding" -ForegroundColor Red
}

Write-Host ""
if ($script:fail -eq 0) {
  Write-Host ("ALL OK - {0} passed" -f $script:pass) -ForegroundColor Green
  Write-Host ""
} else {
  Write-Host ("FAILED - {0} passed, {1} failed" -f $script:pass, $script:fail) -ForegroundColor Red
  Write-Host ""
  exit 1
}

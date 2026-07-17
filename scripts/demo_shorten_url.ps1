# Live product demo: shorten a real URL against the running target_app service and
# show the redirect + analytics actually work. Requires `docker compose up` (or at
# least postgres + target_app) already running.
#
# Usage: .\scripts\demo_shorten_url.ps1 [long_url]

param(
    [string]$LongUrl = "https://www.schwab.com/invest-with-us"
)

$ApiKey = if ($env:API_KEY) { $env:API_KEY } else { "change-me-in-production" }
$BaseUrl = if ($env:TARGET_APP_URL) { $env:TARGET_APP_URL } else { "http://localhost:8000" }

function Write-Section($title) {
    Write-Host ""
    Write-Host ("=" * 66)
    Write-Host " $title"
    Write-Host ("=" * 66)
}

Write-Section "URL Shortener - live demo against $BaseUrl"

Write-Host ""
Write-Host "Original URL:"
Write-Host "  $LongUrl" -ForegroundColor Yellow

try {
    $health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get -TimeoutSec 5
} catch {
    Write-Host ""
    Write-Host "ERROR: target_app is not reachable at $BaseUrl - run 'docker compose up' (or 'make up') first." -ForegroundColor Red
    exit 1
}

$body = @{ long_url = $LongUrl } | ConvertTo-Json
$headers = @{ "X-API-Key" = $ApiKey; "Content-Type" = "application/json" }

$response = Invoke-RestMethod -Uri "$BaseUrl/shorten" -Method Post -Headers $headers -Body $body

$shortUrl = "$BaseUrl/$($response.code)"

Write-Host ""
Write-Host "Shortened URL:"
Write-Host "  $shortUrl" -ForegroundColor Green

Write-Section "Following the redirect"
# Windows PowerShell 5.1's Invoke-WebRequest turns out to be unreliable here:
# -MaximumRedirection 0 throws on the 3xx, but the resulting exception's
# .Response/.Headers don't come back populated the way the .NET docs suggest
# (verified directly - not a hypothetical). curl.exe (bundled with Windows 10/11)
# sidesteps the whole thing and matches the bash version's approach exactly.
$headers = & curl.exe -s -D - -o NUL $shortUrl
$location = ($headers -split "`r?`n" | Where-Object { $_ -match '^location:' }) -replace '^location:\s*', ''
Write-Host ""
Write-Host "  Location: $location"

Write-Section "Analytics (click count after one redirect)"
$stats = Invoke-RestMethod -Uri "$shortUrl/stats" -Headers @{ "X-API-Key" = $ApiKey }
Write-Host ""
Write-Host "  code:         $($stats.code)"
Write-Host "  long_url:     $($stats.long_url)"
Write-Host "  click_count:  $($stats.click_count)" -ForegroundColor Green
Write-Host "  created_at:   $($stats.created_at)"
Write-Host ""

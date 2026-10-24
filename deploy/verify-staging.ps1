[CmdletBinding()]
param(
    [string]$ProjectId = "smj-shopify-analytics",
    [string]$Region = "us-east5",
    [string]$ServiceName = "smj-shopify-api"
)

$ErrorActionPreference = "Stop"

$gcloudCommand = (Get-Command gcloud.cmd -ErrorAction SilentlyContinue).Source
if (-not $gcloudCommand) {
    $gcloudCommand = (Get-Command gcloud -ErrorAction SilentlyContinue).Source
}
if (-not $gcloudCommand -and (Test-Path -LiteralPath "D:\SMJ-GCloud\google-cloud-sdk\bin\gcloud.cmd")) {
    $gcloudCommand = "D:\SMJ-GCloud\google-cloud-sdk\bin\gcloud.cmd"
}
if (-not $gcloudCommand) {
    throw "Google Cloud CLI (gcloud) is not installed or is not on PATH."
}

$serviceUrl = & $gcloudCommand run services describe $ServiceName `
    --project=$ProjectId `
    --region=$Region `
    --format="value(status.url)"
if ($LASTEXITCODE -ne 0 -or -not $serviceUrl) {
    throw "Unable to resolve the Cloud Run service URL."
}

$anonymousAccepted = $false
try {
    Invoke-WebRequest -Uri "$serviceUrl/health" -UseBasicParsing | Out-Null
    $anonymousAccepted = $true
} catch {
    if (-not $_.Exception.Response) {
        throw
    }
    $statusCode = [int]$_.Exception.Response.StatusCode
    if ($statusCode -notin @(401, 403)) {
        throw "Expected an unauthenticated 401/403 response, received $statusCode."
    }
    Write-Host "PASS: unauthenticated request was rejected with HTTP $statusCode."
}
if ($anonymousAccepted) {
    throw "Security check failed: the service accepted an unauthenticated request."
}

$identityToken = (& $gcloudCommand auth print-identity-token).Trim()
if ($LASTEXITCODE -ne 0 -or -not $identityToken) {
    throw "Unable to obtain a short-lived Google identity token."
}
$headers = @{ Authorization = "Bearer $identityToken" }
try {
    $health = Invoke-WebRequest -Uri "$serviceUrl/health" `
        -Headers $headers -UseBasicParsing -TimeoutSec 60
    $database = Invoke-WebRequest -Uri "$serviceUrl/health/ready" `
        -Headers $headers -UseBasicParsing -TimeoutSec 60
    if ($database.StatusCode -ne 200) { throw "Database readiness check failed." }

    $dashboard = Invoke-WebRequest -Uri "$serviceUrl/api/dashboard" `
        -Headers $headers -UseBasicParsing -TimeoutSec 60
    if ($dashboard.StatusCode -ne 200) { throw "Dashboard smoke test failed." }

    Write-Host "PASS: liveness endpoint returned HTTP 200."
    Write-Host "PASS: Neon readiness endpoint returned HTTP 200."
    Write-Host "PASS: representative analytics endpoint returned HTTP 200."
} finally {
    $identityToken = $null
    $headers = $null
}

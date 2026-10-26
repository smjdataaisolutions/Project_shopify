[CmdletBinding()]
param(
    [string]$FrontendUrl = "https://smj-shopify-frontend-876969185947.us-east5.run.app",
    [string]$BackendUrl = "https://smj-shopify-api-3douxa5qja-ul.a.run.app"
)

$ErrorActionPreference = "Stop"

try {
    Invoke-WebRequest -Uri "$BackendUrl/api/dashboard" -Method Get -UseBasicParsing | Out-Null
    throw "Backend unexpectedly accepted an anonymous analytics request."
} catch {
    $status = $_.Exception.Response.StatusCode.value__
    if ($status -notin 401, 403) { throw }
    Write-Host "PASS: Backend anonymous analytics request rejected ($status)."
}

$frontendRequest = [System.Net.HttpWebRequest]::Create($FrontendUrl)
$frontendRequest.Method = "GET"
$frontendRequest.AllowAutoRedirect = $false
$frontendResponse = $frontendRequest.GetResponse()
try {
    $frontendStatus = [int]$frontendResponse.StatusCode
}
finally {
    $frontendResponse.Close()
}
if ($frontendStatus -notin 200, 302, 303) {
    throw "Unexpected frontend status: $frontendStatus"
}
Write-Host "PASS: Public frontend entry point responded ($frontendStatus)."
Write-Host "Authenticated embedded-app testing must be completed from the approved Shopify development store."

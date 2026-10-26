[CmdletBinding(SupportsShouldProcess, ConfirmImpact = "High")]
param(
    [string]$ProjectId = "smj-shopify-analytics",
    [string]$Region = "us-east5",
    [string]$ServiceName = "smj-shopify-frontend",
    [string]$Repository = "smj-shopify-api",
    [string]$RuntimeServiceAccount = "smj-shopify-frontend-runner@smj-shopify-analytics.iam.gserviceaccount.com",
    [string]$BackendService = "smj-shopify-api",
    [string]$BackendUrl = "https://smj-shopify-api-3douxa5qja-ul.a.run.app",
    [string]$FrontendUrl = "https://smj-shopify-frontend-876969185947.us-east5.run.app",
    [string]$ShopifyApiSecret = "smj-shopify-app-api-secret",
    [string]$ShopifyApiSecretVersion = "5",
    [string]$SessionDatabaseSecret = "smj-shopify-session-database-url",
    [string]$SessionDatabaseSecretVersion = "2",
    [string]$TenantAssertionSecret = "smj-shopify-tenant-assertion-secret",
    [string]$TenantAssertionSecretVersion = "2",
    [string]$ShopifyApiKey = "38254bd587274d5002c06d0ecab16259",
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")]
    [string]$ImageTag,
    [switch]$Build,
    [switch]$GrantBackendInvoker,
    [switch]$GrantPublicAccess,
    [switch]$Execute
)

$ErrorActionPreference = "Stop"
$imageUri = "${Region}-docker.pkg.dev/${ProjectId}/${Repository}/${ServiceName}:${ImageTag}"
$secretBindings = @(
    "SHOPIFY_API_SECRET=${ShopifyApiSecret}:${ShopifyApiSecretVersion}",
    "DATABASE_URL=${SessionDatabaseSecret}:${SessionDatabaseSecretVersion}",
    "TENANT_ASSERTION_SECRET=${TenantAssertionSecret}:${TenantAssertionSecretVersion}"
) -join ","
$environmentVariables = [ordered]@{
    SHOPIFY_API_KEY          = $ShopifyApiKey
    SHOPIFY_APP_URL          = $FrontendUrl
    SCOPES                   = "read_inventory,read_locations,read_orders,write_products,write_metaobjects,write_metaobject_definitions"
    TENANT_ASSERTION_ISSUER  = "smj-shopify-frontend"
    TENANT_ASSERTION_AUDIENCE = "smj-shopify-api"
    FASTAPI_BASE_URL         = $BackendUrl
    FASTAPI_AUDIENCE         = $BackendUrl
    FASTAPI_IAM_AUTH_ENABLED = "true"
    DEPLOYMENT_ENVIRONMENT   = "staging"
}

Write-Host "Project: $ProjectId"
Write-Host "Frontend service: $ServiceName"
Write-Host "Backend service: $BackendService"
Write-Host "Image: $imageUri"
Write-Host "Runtime identity: $RuntimeServiceAccount"
Write-Host "Tenant assertion secret reference: ${TenantAssertionSecret}:${TenantAssertionSecretVersion}"
Write-Host "Scaling: 0 to 1 instance"
Write-Host "Backend public access: unchanged"
Write-Host "Frontend public grant requested: $GrantPublicAccess"

if (-not $Execute) {
    Write-Host "Preview only. No cloud commands were run."
    Write-Host "Re-run with -Execute only after deployment and IAM approval."
    exit 0
}

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

if (-not $PSCmdlet.ShouldProcess(
        "$ServiceName in $ProjectId/$Region",
        "Build and deploy the Shopify frontend"
    )) {
    exit 0
}

& $gcloudCommand projects describe $ProjectId --format="value(projectId)" | Out-Null
& $gcloudCommand artifacts repositories describe $Repository `
    --project=$ProjectId --location=$Region --format="value(name)" | Out-Null
& $gcloudCommand iam service-accounts describe $RuntimeServiceAccount `
    --project=$ProjectId --format="value(email)" | Out-Null
& $gcloudCommand secrets describe $ShopifyApiSecret `
    --project=$ProjectId --format="value(name)" | Out-Null
& $gcloudCommand secrets describe $SessionDatabaseSecret `
    --project=$ProjectId --format="value(name)" | Out-Null
& $gcloudCommand secrets describe $TenantAssertionSecret `
    --project=$ProjectId --format="value(name)" | Out-Null

if ($Build) {
    & $gcloudCommand builds submit . `
        --project=$ProjectId --region=$Region --tag=$imageUri
    if ($LASTEXITCODE -ne 0) { throw "Cloud Build failed." }
}

$environmentFile = Join-Path ([System.IO.Path]::GetTempPath()) (
    "smj-shopify-frontend-env-{0}.json" -f [guid]::NewGuid().ToString("N")
)
try {
    $environmentVariables | ConvertTo-Json | Set-Content -LiteralPath $environmentFile -Encoding utf8

    & $gcloudCommand run deploy $ServiceName `
        --project=$ProjectId `
        --region=$Region `
        --platform=managed `
        --image=$imageUri `
        --service-account=$RuntimeServiceAccount `
        --set-secrets=$secretBindings `
        --env-vars-file=$environmentFile `
        --port=8080 `
        --cpu=1 `
        --memory=512Mi `
        --concurrency=8 `
        --timeout=60s `
        --min-instances=0 `
        --max-instances=1 `
        --cpu-throttling `
        --no-cpu-boost `
        --execution-environment=gen2 `
        --ingress=all `
        --quiet
    if ($LASTEXITCODE -ne 0) { throw "Cloud Run deployment failed." }
}
finally {
    Remove-Item -LiteralPath $environmentFile -Force -ErrorAction SilentlyContinue
}

if ($GrantBackendInvoker) {
    & $gcloudCommand run services add-iam-policy-binding $BackendService `
        --project=$ProjectId `
        --region=$Region `
        --member="serviceAccount:$RuntimeServiceAccount" `
        --role="roles/run.invoker" `
        --quiet
    if ($LASTEXITCODE -ne 0) { throw "Backend invoker grant failed." }
} else {
    Write-Warning "Backend IAM was not changed."
}

if ($GrantPublicAccess) {
    & $gcloudCommand run services add-iam-policy-binding $ServiceName `
        --project=$ProjectId `
        --region=$Region `
        --member="allUsers" `
        --role="roles/run.invoker" `
        --quiet
    if ($LASTEXITCODE -ne 0) { throw "Frontend public-access grant failed." }
} else {
    Write-Warning "Frontend public IAM was not changed."
}

& $gcloudCommand run services describe $ServiceName `
    --project=$ProjectId `
    --region=$Region `
    --format="yaml(status.url,spec.template.metadata.annotations,spec.template.spec.serviceAccountName,spec.template.spec.containerConcurrency)"

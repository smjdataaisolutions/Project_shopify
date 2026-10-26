[CmdletBinding(SupportsShouldProcess, ConfirmImpact = "High")]
param(
    [string]$ProjectId = "smj-shopify-analytics",
    [string]$Region = "us-east5",
    [string]$ServiceName = "smj-shopify-api",
    [string]$Repository = "smj-shopify-api",
    [string]$RuntimeServiceAccount = "smj-shopify-api-runner@smj-shopify-analytics.iam.gserviceaccount.com",
    [string]$DatabaseSecret = "smj-shopify-neon-database-url",
    [string]$DatabaseSecretVersion = "3",
    [string]$ShopifyApiSecret = "smj-shopify-app-api-secret",
    [string]$ShopifyApiSecretVersion = "5",
    [string]$TenantAssertionSecret = "smj-shopify-tenant-assertion-secret",
    [string]$TenantAssertionSecretVersion = "2",
    [string]$ShopifyApiKey = "38254bd587274d5002c06d0ecab16259",
    [string]$Invoker = "smjdataaisolutions@gmail.com",
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")]
    [string]$ImageTag,
    [switch]$Build,
    [switch]$GrantInvoker,
    [switch]$Execute
)

$ErrorActionPreference = "Stop"
$imageUri = "${Region}-docker.pkg.dev/${ProjectId}/${Repository}/${ServiceName}:${ImageTag}"
$secretBinding = @(
    "DATABASE_URL=${DatabaseSecret}:${DatabaseSecretVersion}",
    "SHOPIFY_API_SECRET=${ShopifyApiSecret}:${ShopifyApiSecretVersion}",
    "TENANT_ASSERTION_SECRET=${TenantAssertionSecret}:${TenantAssertionSecretVersion}"
) -join ","
$environmentVariables = @(
    "APP_NAME=SMJ Shopify Analytics API - Staging",
    "DEPLOYMENT_ENVIRONMENT=staging",
    "API_DOCS_ENABLED=false",
    "API_AUTH_ENABLED=true",
    "SHOPIFY_API_KEY=$ShopifyApiKey",
    "TENANT_ASSERTION_ISSUER=smj-shopify-frontend",
    "TENANT_ASSERTION_AUDIENCE=smj-shopify-api",
    "DATABASE_POOL_SIZE=2",
    "DATABASE_MAX_OVERFLOW=2",
    "DATABASE_POOL_TIMEOUT_SECONDS=10",
    "DATABASE_POOL_RECYCLE_SECONDS=300"
) -join ","

Write-Host "Project: $ProjectId"
Write-Host "Region: $Region"
Write-Host "Service: $ServiceName"
Write-Host "Image: $imageUri"
Write-Host "Runtime identity: $RuntimeServiceAccount"
Write-Host "Secret reference: ${DatabaseSecret}:${DatabaseSecretVersion}"
Write-Host "Shopify secret reference: ${ShopifyApiSecret}:${ShopifyApiSecretVersion}"
Write-Host "Tenant assertion secret reference: ${TenantAssertionSecret}:${TenantAssertionSecretVersion}"
Write-Host "IAM policy: preserved (backend must already be private)"
Write-Host "Scaling: 0 to 1 instance"

if (-not $Execute) {
    Write-Host "Preview only. No cloud commands were run."
    Write-Host "Re-run with -Execute only after deployment approval."
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
        "Build and deploy an IAM-protected Cloud Run revision"
    )) {
    exit 0
}

# These checks do not create resources. Required APIs, repository, service account,
# secret, and secret IAM access must be prepared under a separately approved step.
& $gcloudCommand projects describe $ProjectId --format="value(projectId)" | Out-Null
& $gcloudCommand artifacts repositories describe $Repository `
    --project=$ProjectId `
    --location=$Region `
    --format="value(name)" | Out-Null
& $gcloudCommand iam service-accounts describe $RuntimeServiceAccount `
    --project=$ProjectId `
    --format="value(email)" | Out-Null
& $gcloudCommand secrets describe $DatabaseSecret `
    --project=$ProjectId `
    --format="value(name)" | Out-Null
& $gcloudCommand secrets describe $ShopifyApiSecret `
    --project=$ProjectId `
    --format="value(name)" | Out-Null
& $gcloudCommand secrets describe $TenantAssertionSecret `
    --project=$ProjectId `
    --format="value(name)" | Out-Null

if ($Build) {
    & $gcloudCommand builds submit . `
        --project=$ProjectId `
        --region=$Region `
        --tag=$imageUri
    if ($LASTEXITCODE -ne 0) { throw "Cloud Build failed." }
}

& $gcloudCommand run deploy $ServiceName `
    --project=$ProjectId `
    --region=$Region `
    --platform=managed `
    --image=$imageUri `
    --service-account=$RuntimeServiceAccount `
    --set-secrets=$secretBinding `
    --set-env-vars=$environmentVariables `
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

if ($GrantInvoker) {
    & $gcloudCommand run services add-iam-policy-binding $ServiceName `
        --project=$ProjectId `
        --region=$Region `
        --member="user:$Invoker" `
        --role="roles/run.invoker" `
        --quiet
    if ($LASTEXITCODE -ne 0) { throw "Invoker IAM grant failed." }
} else {
    Write-Warning "Invoker IAM was not changed. Use -GrantInvoker only with explicit IAM approval."
}

& $gcloudCommand run services describe $ServiceName `
    --project=$ProjectId `
    --region=$Region `
    --format="yaml(status.url,spec.template.metadata.annotations,spec.template.spec.containerConcurrency)"

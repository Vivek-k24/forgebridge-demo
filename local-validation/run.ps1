param(
    [ValidateRange(1, 200)]
    [int]$Cases = 20,

    [int]$Seed = 20260829,

    [switch]$AllBrands,

    [switch]$Keep
)

$ErrorActionPreference = 'Stop'
$compose = Join-Path $PSScriptRoot 'compose.acceptance.yaml'
$project = 'partgraph-acceptance'

$env:PARTGRAPH_ACCEPTANCE_CASES = "$Cases"
$env:PARTGRAPH_ACCEPTANCE_SEED = "$Seed"
$env:PARTGRAPH_ACCEPTANCE_ALL_BRANDS = if ($AllBrands) { 'true' } else { 'false' }

Write-Host ''
Write-Host 'PartGraph local acceptance harness' -ForegroundColor Cyan
Write-Host "  cases: $Cases"
Write-Host "  seed:  $Seed"
Write-Host "  all supported brands: $($AllBrands.IsPresent)"
Write-Host '  database: isolated disposable PostgreSQL volume' -ForegroundColor DarkGray
Write-Host ''

$exitCode = 1
try {
    Write-Host '[1/4] Resetting disposable acceptance stack...' -ForegroundColor Yellow
    docker compose -p $project -f $compose down -v --remove-orphans 2>$null | Out-Null

    Write-Host '[2/4] Building and starting PostgreSQL + API...' -ForegroundColor Yellow
    docker compose -p $project -f $compose up --build -d postgres api
    if ($LASTEXITCODE -ne 0) { throw 'Acceptance API stack failed to start.' }

    Write-Host '[3/4] Running local-only acceptance scenarios...' -ForegroundColor Yellow
    docker compose -p $project -f $compose --profile runner run --build --rm runner
    $exitCode = $LASTEXITCODE

    Write-Host '[4/4] Acceptance runner finished.' -ForegroundColor Yellow
}
finally {
    if ($Keep) {
        Write-Host ''
        Write-Host 'Keeping the acceptance stack for inspection.' -ForegroundColor Cyan
        Write-Host 'API: http://localhost:18000/docs'
        Write-Host "Stop later with: docker compose -p $project -f `"$compose`" down -v"
    }
    else {
        Write-Host 'Removing disposable containers, media, and database volume...' -ForegroundColor DarkGray
        docker compose -p $project -f $compose down -v --remove-orphans 2>$null | Out-Null
    }
}

Write-Host ''
if ($exitCode -eq 0) {
    Write-Host 'PASS: PartGraph local acceptance harness completed successfully.' -ForegroundColor Green
}
else {
    Write-Host "FAIL: PartGraph local acceptance harness exited with code $exitCode." -ForegroundColor Red
}

exit $exitCode

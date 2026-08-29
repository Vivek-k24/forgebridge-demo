param(
    [ValidateRange(20, 200)]
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
if ($AllBrands) {
    Write-Host "  case mode:     all supported/legacy makes (Cases=$Cases is the normal-run minimum)"
}
else {
    Write-Host "  repair cases:  $Cases"
}
Write-Host "  seed:          $Seed"
Write-Host "  all supported brands: $($AllBrands.IsPresent)"
Write-Host '  database: isolated disposable PostgreSQL volume' -ForegroundColor DarkGray
Write-Host ''

$exitCode = 1
try {
    Write-Host '[1/6] Resetting disposable acceptance stack...' -ForegroundColor Yellow
    docker compose -p $project -f $compose down -v --remove-orphans 2>$null | Out-Null

    Write-Host '[2/6] Building and starting PostgreSQL + VIN stub + API...' -ForegroundColor Yellow
    docker compose -p $project -f $compose up --build -d postgres vin-stub api
    if ($LASTEXITCODE -ne 0) { throw 'Acceptance API stack failed to start.' }

    Write-Host '[3/6] Seeding synthetic canonical vehicle configurations...' -ForegroundColor Yellow
    docker compose -p $project -f $compose --profile runner run --build --rm runner `
        python local-validation/seed_vehicle_pool.py
    if ($LASTEXITCODE -ne 0) {
        $exitCode = $LASTEXITCODE
        throw "Acceptance vehicle seed failed with exit code $exitCode."
    }

    Write-Host '[4/6] Running platform, auth, selector, and VIN probes...' -ForegroundColor Yellow
    docker compose -p $project -f $compose --profile runner run --rm runner `
        python local-validation/platform_acceptance.py
    if ($LASTEXITCODE -ne 0) {
        $exitCode = $LASTEXITCODE
        throw "Platform/VIN acceptance probes failed with exit code $exitCode."
    }

    Write-Host '[5/6] Running cross-manufacturer repair workflow scenarios...' -ForegroundColor Yellow
    docker compose -p $project -f $compose --profile runner run --rm runner `
        python local-validation/acceptance_runner.py
    $exitCode = $LASTEXITCODE

    Write-Host '[6/6] Acceptance runners finished.' -ForegroundColor Yellow
}
catch {
    if ($exitCode -eq 1 -and $LASTEXITCODE -ne 0) {
        $exitCode = $LASTEXITCODE
    }
    Write-Host $_.Exception.Message -ForegroundColor Red
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

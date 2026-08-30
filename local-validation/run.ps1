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

function Invoke-DockerCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [switch]$Quiet
    )

    # Windows PowerShell 5.1 converts native-process stderr into ErrorRecord objects.
    # Docker Compose legitimately writes progress messages (for example, volume/container
    # removal) to stderr even when it exits successfully. With the script-wide
    # ErrorActionPreference='Stop', those harmless messages otherwise terminate the run.
    # Treat Docker's process exit code as authoritative instead.
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        if ($Quiet) {
            & docker @Arguments 1>$null 2>$null
        }
        else {
            & docker @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
        }
        $nativeExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }

    return $nativeExitCode
}

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
    $dockerExit = Invoke-DockerCommand -Quiet -Arguments @(
        'compose', '-p', $project, '-f', $compose,
        'down', '-v', '--remove-orphans'
    )
    if ($dockerExit -ne 0) {
        throw "Could not reset the disposable acceptance stack (docker exit $dockerExit)."
    }

    Write-Host '[2/6] Building and starting PostgreSQL + VIN stub + API...' -ForegroundColor Yellow
    $dockerExit = Invoke-DockerCommand -Arguments @(
        'compose', '-p', $project, '-f', $compose,
        'up', '--build', '-d', 'postgres', 'vin-stub', 'api'
    )
    if ($dockerExit -ne 0) {
        $exitCode = $dockerExit
        throw "Acceptance API stack failed to start (docker exit $dockerExit)."
    }

    Write-Host '[3/6] Seeding synthetic canonical vehicle configurations...' -ForegroundColor Yellow
    $dockerExit = Invoke-DockerCommand -Arguments @(
        'compose', '-p', $project, '-f', $compose, '--profile', 'runner',
        'run', '--build', '--rm', 'runner',
        'python', 'local-validation/seed_vehicle_pool.py'
    )
    if ($dockerExit -ne 0) {
        $exitCode = $dockerExit
        throw "Acceptance vehicle seed failed with exit code $dockerExit."
    }

    Write-Host '[4/6] Running platform, auth, selector, and VIN probes...' -ForegroundColor Yellow
    $dockerExit = Invoke-DockerCommand -Arguments @(
        'compose', '-p', $project, '-f', $compose, '--profile', 'runner',
        'run', '--build', '--rm', 'runner',
        'python', 'local-validation/platform_acceptance.py'
    )
    if ($dockerExit -ne 0) {
        $exitCode = $dockerExit
        throw "Platform/VIN acceptance probes failed with exit code $dockerExit."
    }

    Write-Host '[5/6] Running cross-manufacturer repair workflow scenarios...' -ForegroundColor Yellow
    $dockerExit = Invoke-DockerCommand -Arguments @(
        'compose', '-p', $project, '-f', $compose, '--profile', 'runner',
        'run', '--build', '--rm', 'runner',
        'python', 'local-validation/acceptance_runner.py'
    )
    $exitCode = $dockerExit
    if ($dockerExit -ne 0) {
        throw "Cross-manufacturer repair scenarios failed with exit code $dockerExit."
    }

    Write-Host '[6/6] Acceptance runners finished.' -ForegroundColor Yellow
}
catch {
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
        $cleanupExit = Invoke-DockerCommand -Quiet -Arguments @(
            'compose', '-p', $project, '-f', $compose,
            'down', '-v', '--remove-orphans'
        )
        if ($cleanupExit -ne 0) {
            Write-Warning "Acceptance cleanup returned docker exit code $cleanupExit."
            if ($exitCode -eq 0) {
                $exitCode = $cleanupExit
            }
        }
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

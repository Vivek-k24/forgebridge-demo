param(
    [ValidateSet(
        'start',
        'stop',
        'status',
        'logs',
        'backup',
        'identity-start',
        'identity-refresh',
        'identity-status',
        'identity-export',
        'scale2',
        'reprocess'
    )]
    [string]$Action = 'start'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$IdentityContainer = 'partgraph-identity-catalog'
Set-Location $RepoRoot

function Assert-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker Desktop / docker CLI is required.'
    }
    docker compose version | Out-Null
}

function Remove-IdentityContainer {
    $Existing = docker ps -a --filter "name=^/$IdentityContainer$" --format '{{.ID}}'
    if ($Existing) {
        docker rm -f $IdentityContainer | Out-Null
    }
}

function Stop-LegacySpecCollectors {
    $SpecContainers = @(
        docker ps `
            --filter 'label=com.docker.compose.project=partgraph' `
            --filter 'label=com.docker.compose.service=collector' `
            --filter 'label=com.docker.compose.oneoff=False' `
            --format '{{.ID}}'
    )
    foreach ($ContainerId in $SpecContainers) {
        if ($ContainerId) {
            docker stop $ContainerId | Out-Null
        }
    }
}

function Start-CoreStack {
    New-Item -ItemType Directory -Force -Path 'local-data/workbench' | Out-Null
    Stop-LegacySpecCollectors
    docker compose up -d --build postgres api web
}

function Start-IdentityCollector([switch]$Refresh) {
    # Remove a stale/failed one-off collector before Compose rebuilds the active
    # stack. The identity worker intentionally runs from the same freshly built
    # API image, so it can never lag behind the checked-out Python package.
    Remove-IdentityContainer
    Start-CoreStack
    $Args = @(
        'compose', 'run', '-d', '--no-deps',
        '--name', $IdentityContainer,
        'api',
        'python', '-m', 'partgraph.knowledge.identity_catalog_worker'
    )
    if ($Refresh) {
        $Args += '--refresh'
    }
    & docker $Args | Out-Null
    Write-Host 'US identity catalog collection started.' -ForegroundColor Green
    Write-Host 'Scope: Acura, Honda, Hyundai, Lexus, Subaru, Toyota · 1996-2027 · US market'
    Write-Host 'This phase collects year + make + model + trim only. Technical specs are paused.'
    Write-Host 'Progress: .\scripts\workbench.ps1 identity-status'
    Write-Host 'Live log:  .\scripts\workbench.ps1 logs'
}

Assert-Docker

switch ($Action) {
    'start' {
        Start-CoreStack
        Write-Host ''
        Write-Host 'PartGraph local workbench is starting.' -ForegroundColor Green
        Write-Host 'Open: http://localhost:5173/#/catalog'
        Write-Host 'Specification collection is paused during the identity inventory phase.'
        Write-Host 'Start the six-make identity run with:'
        Write-Host '  .\scripts\workbench.ps1 identity-start' -ForegroundColor Cyan
    }
    'stop' {
        $Running = docker ps --filter "name=^/$IdentityContainer$" --format '{{.ID}}'
        if ($Running) {
            docker stop $IdentityContainer | Out-Null
        }
        docker compose stop
        Write-Host 'Stopped containers without deleting PostgreSQL or source-cache data.' -ForegroundColor Yellow
    }
    'status' {
        docker compose ps
        Write-Host ''
        $Identity = docker ps -a --filter "name=^/$IdentityContainer$" --format 'table {{.Status}}'
        if ($Identity) {
            Write-Host 'Identity collector:'
            Write-Host $Identity
        }
    }
    'logs' {
        $Identity = docker ps -a --filter "name=^/$IdentityContainer$" --format '{{.ID}}'
        if ($Identity) {
            docker logs -f $IdentityContainer
        }
        else {
            Write-Host 'No identity collector container exists yet.' -ForegroundColor Yellow
        }
    }
    'identity-start' {
        Start-IdentityCollector
    }
    'identity-refresh' {
        Start-IdentityCollector -Refresh
    }
    'identity-status' {
        docker compose exec -T api `
            python -m partgraph.knowledge.identity_catalog_worker --status
    }
    'identity-export' {
        docker compose exec -T api `
            python -m partgraph.knowledge.identity_catalog_worker `
            --export-json /app/workbench/identity-catalog.json
        Write-Host ''
        Write-Host 'JSON export:' -ForegroundColor Green
        Write-Host '  local-data\workbench\identity-catalog.json'
    }
    'scale2' {
        throw 'scale2 is paused. The current phase is make/model/trim inventory only.'
    }
    'reprocess' {
        throw 'Specification cache reprocessing is paused until identity inventory is complete.'
    }
    'backup' {
        $Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $Destination = Join-Path 'local-data/exports' $Stamp
        New-Item -ItemType Directory -Force -Path $Destination | Out-Null

        docker compose exec -T postgres sh -lc "pg_dump -U partgraph -d partgraph -Fc --no-owner --no-privileges -f /tmp/partgraph.dump"
        docker compose cp postgres:/tmp/partgraph.dump (Join-Path $Destination 'partgraph.dump')

        if (Test-Path 'local-data/workbench') {
            Copy-Item 'local-data/workbench' (Join-Path $Destination 'workbench') -Recurse -Force
        }

        $Commit = git rev-parse HEAD
        Set-Content -Path (Join-Path $Destination 'repository-commit.txt') -Value $Commit
        Set-Content -Path (Join-Path $Destination 'created-at.txt') -Value (Get-Date).ToString('o')

        Write-Host "Backup created at $Destination" -ForegroundColor Green
        Write-Host 'It contains a PostgreSQL custom dump, raw source cache, and repository commit reference.'
    }
}

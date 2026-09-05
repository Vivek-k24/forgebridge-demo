param(
    [ValidateSet('start', 'stop', 'status', 'logs', 'backup', 'scale2', 'reprocess')]
    [string]$Action = 'start'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Assert-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker Desktop / docker CLI is required.'
    }
    docker compose version | Out-Null
}

Assert-Docker

switch ($Action) {
    'start' {
        New-Item -ItemType Directory -Force -Path 'local-data/workbench' | Out-Null
        docker compose up -d --build
        Write-Host ''
        Write-Host 'PartGraph local workbench is starting.' -ForegroundColor Green
        Write-Host 'Open: http://localhost:5173/#/catalog'
        Write-Host 'The collector runs locally and the source cache is under local-data/workbench.'
    }
    'stop' {
        docker compose stop
        Write-Host 'Stopped containers without deleting PostgreSQL or source-cache data.' -ForegroundColor Yellow
    }
    'status' {
        docker compose ps
    }
    'logs' {
        docker compose logs -f collector
    }
    'scale2' {
        New-Item -ItemType Directory -Force -Path 'local-data/workbench' | Out-Null
        docker compose up -d --build --scale collector=2
        Write-Host 'Two local collector workers are running. Start multiple makes from the dashboard to use them.' -ForegroundColor Green
    }
    'reprocess' {
        New-Item -ItemType Directory -Force -Path 'local-data/workbench' | Out-Null
        Write-Host 'Stopping collector workers at a safe checkpoint before cache reprocessing...' -ForegroundColor Yellow
        docker compose stop collector
        try {
            docker compose run --rm --no-deps collector python -m partgraph.knowledge.workbench_worker_v2 --reprocess-cache
        }
        finally {
            docker compose start collector
        }
        Write-Host 'Cached source captures were re-extracted and reconciled without new web requests.' -ForegroundColor Green
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

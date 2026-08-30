PartGraph local acceptance harness — first run

From the repository root in PowerShell:

  git fetch origin
  git checkout partgraph-local-acceptance-harness
  git pull
  docker version
  docker compose version
  .\local-validation\run.ps1

Success ends with:

  Passed cases: 20/20
  Failed cases: 0
  RESULT: PASS — all selected cases and workflow contracts passed.
  PASS: PartGraph local acceptance harness completed successfully.

Then run:

  $LASTEXITCODE

Expected: 0

For a new reproducible random assignment:

  .\local-validation\run.ps1 -Seed 314159

For one vehicle from all 31 current supported/legacy makes:

  .\local-validation\run.ps1 -AllBrands -Seed 314159

For failure inspection:

  $env:PARTGRAPH_ACCEPTANCE_TRACEBACK = "true"
  .\local-validation\run.ps1 -Seed 314159 -Keep

Then inspect http://localhost:18000/docs and/or the acceptance PostgreSQL database.

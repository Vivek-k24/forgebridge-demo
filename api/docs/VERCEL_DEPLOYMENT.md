# Vercel deployment

The Vercel project for the PartGraph API must use these project settings:

- Root Directory: `api`
- Framework Preset: `FastAPI`
- Production Branch: `main`

The FastAPI application entrypoint is declared in `pyproject.toml` as `partgraph.main:app`.
The project-level `vercel.json` keeps the deployment in `iad1` and configures the canonical application function.

Do not deploy the repository root as a generic Python project. With the repository root selected, Vercel treats the top-level `api/` directory as its file-based Functions directory and attempts to package PartGraph modules as many independent Serverless Functions.

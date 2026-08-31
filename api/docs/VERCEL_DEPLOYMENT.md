# Vercel deployment

The Vercel project for the PartGraph production application must use these project settings:

- Root Directory: `api`
- Framework Preset: `FastAPI`
- Production Branch: `main`

The FastAPI application entrypoint is declared in `pyproject.toml` as `partgraph.main:app`.
The project-level `vercel.json` keeps the deployment in `iad1`, configures the canonical application function, and provides the same-origin frontend bridge:

- `/api/*` remains on the FastAPI runtime;
- `/` is externally rewritten to the current-main GitHub Pages Vite entry document;
- `/forgebridge-demo/*` is externally rewritten to the matching GitHub Pages static asset path.

The browser continues to see the Vercel production hostname while Vercel proxies the frontend asset requests. This keeps PartGraph's HttpOnly `SameSite=Lax` session cookie first-party for the authenticated application rather than relying on cross-site cookies between `github.io` and `vercel.app`.

Direct GitHub Pages visits remain a static preview/handoff surface and do not receive authenticated session cookies.

Do not deploy the repository root as a generic Python project. With the repository root selected, Vercel treats the top-level `api/` directory as its file-based Functions directory and attempts to package PartGraph modules as many independent Serverless Functions.

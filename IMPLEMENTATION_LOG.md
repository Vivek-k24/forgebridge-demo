# PartGraph Implementation Log

This file keeps engineering notes out of the user-facing README.

## 2026-08-23 — Public Honda manual selection

### Problem fixed

The manual vehicle selector previously showed a disabled fallback reading **“Use VIN for exact trim”** when a hard-coded trim list was unavailable. That made VIN look mandatory even though public vehicle data can support a useful manual-selection path.

### Changes

- Manual year/model/configuration selection remains the default vehicle-identification path.
- VIN decoding is explicitly a secondary, optional path.
- Added `src/lib/hondaManualConfigurationService.ts`.
- For the repair-supported 2009 Civic Sedan, trim names come from an American Honda 2009 Civic Sedan brochure.
- For other supported model years, the client can query the public FuelEconomy.gov vehicle menu service for Honda vehicle configurations.
- Existing NHTSA vPIC model discovery and VIN decoding remain in place.
- Public configuration responses are cached in `localStorage` for 30 days.
- No language-model call is used for vehicle selection.
- The UI distinguishes a public EPA/DOE vehicle configuration from a Honda marketing trim rather than pretending they are always the same thing.
- If a finer public configuration cannot be resolved, the user can still select year/model. The repair graph remains locked unless PartGraph has verified coverage for that vehicle.

### Source strategy

1. **Honda-published data** — preferred for marketing trim/configuration names and Honda-specific mechanical identity.
2. **NHTSA vPIC** — public make/model discovery and optional VIN decoding.
3. **FuelEconomy.gov / EPA / DOE** — public powertrain/configuration choices where useful for manual selection.
4. **PartGraph verified repair graph** — controls whether repair parts can actually be shown for a selected vehicle.
5. **Seller pages/APIs** — shopping only; never the source of mechanical truth.

### Current limitation

The fully verified repair graph is still concentrated on the 2009 U.S. Civic Hybrid / MX Hybrid KA CVT catalog configuration. Public vehicle browsing is broader than verified repair coverage by design.

FuelEconomy.gov is queried from the browser. If cross-origin access or the public service is unavailable, the service fails conservatively: manual year/model selection still works and PartGraph does not invent a trim/configuration.

## 2026-08-23 — Step 2 repair-selection workflow

- Added compact block → sub-block → target-part selectors.
- Published multiple source-backed system graphs.
- Nested bolts, clips, O-rings, seals and other catalog hardware under the parent part when a verified relationship exists.
- Kept orphan hardware visible as a data-quality warning instead of silently hiding it.
- Preserved deterministic repair state and OEM-first shopping behavior.

## 2026-08-23 — Mobile/user-facing pass

- Moved photo help above the assembly checklist.
- Added mobile-first camera/file capture.
- Added source-backed part thumbnails where available, with hover/tap enlarged preview.
- Added a QR code linking the desktop page to the phone experience.
- Reduced prototype/developer-facing copy in the runtime UI.

## 2026-08-22 — PartGraph V0

- Replaced the previous ChangeGraph runtime with PartGraph.
- Added the first source-backed Honda radiator-area graph.
- Added deterministic `Need / Have / Inspect / Not sure` repair state.
- Added exact OEM identities and initial purchase paths.
- Added a logical exploded-view proof of concept.
- Established the zero-runtime-LLM policy for normal repair sessions.

## Engineering rule

Mechanical truth is precomputed, source-backed, versioned, and cached. Runtime language-model usage should remain unnecessary for normal vehicle selection, assembly traversal, repair-state logic, diagrams, and exact-part seller searches. AI may assist internal ingestion or future ambiguous image recognition, but unverified model output must never become mechanical truth automatically.

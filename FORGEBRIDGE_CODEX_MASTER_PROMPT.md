# ForgeBridge: Codex Master Prompt

You are the lead product designer and frontend engineer working in VS Code. Build a complete static frontend prototype for **ForgeBridge**, an AI-native export house for small and mid-sized manufacturers.

Do not stop after making a landing page. Build the public website, manufacturer onboarding, buyer RFQ workflow, manufacturer operating dashboard, buyer portal, quote comparison, compliance workflow, shipment tracking, and payment completion story.

## Product

ForgeBridge acts as a manufacturer's outsourced international sales and export department. A factory provides its catalog, technical capabilities, certifications, capacity, MOQ, lead times, target markets, commercial limits, payment terms, and Incoterms. ForgeBridge finds qualified overseas buyers, matches RFQs, prepares landed-cost quotes, manages compliance, coordinates inspection and freight, tracks delivery, and earns a percentage of completed orders.

Primary message: **Your export department, powered by AI.**

This is not another CRM or generic marketplace. It owns the workflow from buyer demand to completed export order.

## Project directory and stack

Create the application in:

```text
./forgebridge/
```

If the workspace is empty, scaffold it with:

- React
- TypeScript
- Vite
- React Router
- Tailwind CSS
- shadcn/ui
- Lucide icons
- Recharts
- React Hook Form
- Zod
- localStorage persistence
- Seeded mock data

Use npm unless the existing repository already uses another package manager.

Commands must work:

```bash
npm install
npm run dev
npm run build
npm run lint
```

Do not add a backend, Supabase, Firebase, authentication, real APIs, real uploads, real payments, or server-side persistence. This is a frontend-only prototype. Simulate external actions and retain application state in localStorage.

## Quality bar

Every visible control must work, including navigation, CTAs, dropdowns, tabs, filters, sorting, forms, save draft, review, submit, approve, decline, duplicate, revise, generate document, upload simulation, reply, supplier selection, milestone completion, data export, and reset demo data.

Do not create dead buttons, placeholder pages, lorem ipsum, fake external links, blank routes, desktop-only screens, or actions with no feedback.

Use validation, confirmations, toasts, success states, loading skeletons where appropriate, responsive navigation, useful empty states, accessible labels, keyboard focus states, and semantic HTML.

Persist all important actions through refresh. Gracefully recover from corrupt localStorage. Include a versioned seed state and a Reset Demo Data control.

## Visual system

Create a premium, international, industrial B2B product. Avoid generic bright-blue SaaS styling.

Use:

- Warm off-white background
- Deep graphite text
- Restrained copper/amber accent
- Muted olive or slate secondary color
- Thin borders
- Subtle shadows
- Refined typography
- Generous whitespace
- Trade-route/map/grid motifs
- Clean technical charts

Suggested colors:

```text
Background       #F5F1E8
Surface          #FBF8F2
Graphite         #1D211F
Muted graphite   #5D625E
Copper           #B56A32
Dark copper      #834722
Olive            #69705B
Border           #D9D2C5
Success          #3E7255
Warning          #A56A25
Danger           #A4483E
```

The product should look credible to manufacturers, procurement teams, freight and compliance specialists, investors, and YC reviewers.

## Code organization

Use a maintainable structure similar to:

```text
forgebridge/
├── src/
│   ├── app/
│   │   ├── App.tsx
│   │   ├── router.tsx
│   │   └── providers.tsx
│   ├── components/
│   │   ├── common/
│   │   ├── layout/
│   │   ├── charts/
│   │   ├── forms/
│   │   ├── marketing/
│   │   ├── manufacturer/
│   │   └── buyer/
│   ├── data/
│   │   ├── seed.ts
│   │   ├── opportunities.ts
│   │   ├── buyers.ts
│   │   ├── quotes.ts
│   │   ├── orders.ts
│   │   └── messages.ts
│   ├── hooks/
│   ├── lib/
│   │   ├── calculations.ts
│   │   ├── formatters.ts
│   │   ├── storage.ts
│   │   ├── validation.ts
│   │   └── constants.ts
│   ├── pages/
│   │   ├── marketing/
│   │   ├── onboarding/
│   │   ├── manufacturer/
│   │   ├── buyer/
│   │   └── NotFoundPage.tsx
│   ├── state/
│   ├── styles/
│   ├── types/
│   │   └── domain.ts
│   └── main.tsx
├── public/
├── README.md
├── package.json
├── tsconfig.json
└── vite.config.ts
```

Do not put the entire application into one file. Do not use `any`.

Create strong TypeScript types for Manufacturer, FactoryCapability, Machine, Product, Certification, CommercialRules, Buyer, RFQ, Opportunity, Quote, QuoteCostBreakdown, Order, ShipmentMilestone, ComplianceDocument, MessageThread, Notification, ContactSubmission, ManufacturerOnboardingDraft, and BuyerRFQDraft.

## Seeded business story

Use this manufacturer consistently throughout the application:

```text
Company: Deccan Precision Components Pvt. Ltd.
Location: Hyderabad, Telangana, India
Founded: 2012
Employees: 86
Industry: CNC machining and precision metal components
Markets: United States, UAE, Germany
Certifications: ISO 9001:2015, ISO 14001:2015, RoHS-ready production
Processes: CNC turning, CNC milling, surface grinding, partner anodizing, CMM inspection
Materials: Aluminum 6061/7075, stainless steel 304/316, mild steel, brass
Monthly capacity: 7,200 machine hours
Available capacity: 1,650 machine hours
Minimum order value: USD 7,500
Preferred Incoterms: FOB and CIF
Minimum margin: 14%
```

Keep names, values, currencies, quantities, deadlines, statuses, and milestones internally consistent across pages.

## Public routes

Create:

```text
/
/how-it-works
/manufacturers
/buyers
/industries
/about
/contact
/start-exporting
/submit-rfq
/demo/manufacturer
/demo/buyer
```

### Home

Include:

1. Header and full navigation.
2. Hero: “Your export department, powered by AI.”
3. Start Exporting CTA.
4. Explore the Platform CTA.
5. Clearly labeled View Manufacturer Demo and View Buyer Demo links.
6. Interactive workflow: Catalog → Buyer Match → Quote → Compliance → Shipment → Payment.
7. Clearly labeled sample/demo metrics.
8. Manufacturer problems and outcomes.
9. Supported industries.
10. Buyer value proposition.
11. Outcome-based pricing explanation.
12. Strong final CTA and full footer.

### How It Works

Show separate manufacturer and buyer paths. Explain capability normalization, RFQ parsing, fit scoring, landed-cost quotes, certification checks, inspection, freight milestones, and payment release.

### Manufacturers

Show benefits, onboarding steps, sample opportunities, sample quote economics, and CTA to onboarding.

### Buyers

Show vetted supplier matching, technical specification handling, quote comparison, inspection, shipment visibility, and CTA to RFQ submission.

### Industries

Include CNC machining, industrial fasteners, electrical enclosures, pumps and valves, commercial hardware, and fabricated metal components. Clicking each card must open a useful detail page, dialog, or drawer containing common products, certifications, RFQ fields, and destination markets.

### About

Explain the mission, operating principles, why exporting is still hard, and why ForgeBridge exists. Do not invent founders, funding, investors, or customer logos.

### Contact

Validated fields: name, work email, company, country, role, and message. Store submissions locally and show a complete success state.

## Manufacturer onboarding

Route:

```text
/start-exporting
```

Build a six-step wizard with progress, step labels, back/next, validation, save and resume, edit-from-review, and submission success.

1. Company profile: legal name, trading name, country, region, city, website, founded year, employee count, contact, email, phone.
2. Capabilities: processes, materials, tolerance, machinery, inspection, monthly capacity, available capacity. Allow add/remove machines.
3. Products: add/edit/delete product records with category, description, materials, MOQ, lead time, unit price range, currency, optional HS code.
4. Quality: certifications, expiration dates, certificate numbers, inspection method, traceability, simulated uploads with file chips.
5. Commercial boundaries: target markets, currencies, minimum order, payment terms, Incoterms, minimum margin, maximum automatic discount, approval threshold.
6. Review and submit.

On submission, generate an application ID, store the profile, show success, and allow entry into the manufacturer dashboard. The dashboard must reflect submitted edits.

## Buyer RFQ workflow

Route:

```text
/submit-rfq
```

Build five steps:

1. Buyer and company details.
2. Category and technical requirement.
3. Quantity, target price, currency, destination, required date, and Incoterm.
4. Certifications, inspection, sample requirement, packaging, attachments.
5. Review and submit.

Generate an ID such as `RFQ-2026-1048`, save it locally, show success, add it to the buyer portal, and create a corresponding matched manufacturer opportunity.

## Manufacturer application shell and routes

Create:

```text
/manufacturer
/manufacturer/profile
/manufacturer/opportunities
/manufacturer/opportunities/:opportunityId
/manufacturer/quote-builder/:opportunityId
/manufacturer/quotes
/manufacturer/quotes/:quoteId
/manufacturer/orders
/manufacturer/orders/:orderId
/manufacturer/compliance
/manufacturer/buyers
/manufacturer/messages
/manufacturer/analytics
/manufacturer/settings
```

Use a responsive sidebar, mobile drawer, header, breadcrumbs, search, notifications, profile menu, and visible Demo indicator.

### Manufacturer overview

Show pipeline value, active opportunities, quotes awaiting approval, orders in transit, conversion rate, available capacity, opportunity funnel, pipeline by market, revenue by destination, capacity utilization, recent activity, next best actions, deadlines, and compliance alerts.

### Factory profile

Editable company, capabilities, machinery, products, certifications, capacity, markets, and commercial rules. Show completion score and persist edits.

### Opportunities

Seed at least 10 realistic RFQs from the US, UAE, Germany, and UK. Include buyer alias, country, product, quantity, estimated value, required delivery, match score, status, risk, and certification requirements.

Controls must work: search, country filter, product filter, match-score filter, status tabs, sorting, card/table toggle, saved-only filter.

Use realistic examples:

1. Aerospace aluminum mounting brackets, US
2. Stainless valve bodies, UAE
3. Precision sensor housings, Germany
4. Industrial fastener kits, UK
5. CNC pump impellers, UAE
6. Brass electrical terminal blocks, US
7. Food-grade stainless fittings, Germany
8. Aluminum robotic-arm joints, UK
9. Hydraulic manifold blocks, US
10. Instrumentation enclosures, UAE

### Opportunity detail

Show buyer summary, product, specifications, quantity, delivery, target price, Incoterm, certifications, match score, risk, production fit, margin potential, market context, and a meaningful AI match explanation.

Working actions: Save/Unsave, Decline with reason, Ask Question, and Build Quote.

### Quote builder

Editable fields:

- Raw material
- Machining/fabrication
- Tooling
- Inspection
- Packaging
- Inland freight
- International freight
- Insurance
- Duty estimate
- Platform commission
- Contingency
- Margin

Live calculations:

```text
manufacturingCost = material + manufacturing + tooling + inspection + packaging
exw = manufacturingCost + contingency + platformCommission + markup
fob = exw + inlandFreight
cif = fob + internationalFreight + insurance
landedCost = cif + dutyEstimate
```

Use one clearly labeled model for markup or margin and apply it consistently. Also show total quote value, per-unit price, gross margin, currency, quantity, Incoterm, payment terms, validity, and notes.

Show warnings below minimum margin and above approval threshold.

Actions: Save Draft, Preview, Submit for Internal Review, Approve, Send to Buyer. Persist every state transition.

### Quotes

Statuses: Draft, Internal Review, Sent, Negotiation, Won, Lost.

Allow open, duplicate, revise, status change, negotiation note, and mark won/lost with reason.

### Orders

Show list and detail. Milestones:

1. PO confirmed
2. Raw material secured
3. Production started
4. Production complete
5. Inspection complete
6. Packed
7. Customs documents complete
8. Pickup
9. In transit
10. Customs clearance
11. Delivered
12. Payment released

Allow completion of eligible demo milestones with confirmation and activity log. Show order value, buyer, destination, Incoterm, mode, ETA, payment, and documents.

### Compliance Center

Required documents: commercial invoice, packing list, certificate of origin, inspection report, bill of lading, insurance certificate.

Statuses: Missing, Draft, Ready, Expiring, Approved.

Actions: Generate Draft, Upload Simulation, Review, Approve, Download Simulation.

### Buyer network

Searchable anonymized buyers with country, categories, average order value, payment reliability, typical lead time, certification needs, and interactions. Include a useful detail drawer, Start Message, and View Related Opportunities.

### Messages

Threaded buyer and internal specialist messages with search, unread state, reply, compose, simulated attachments, timestamps, and related RFQ/order links.

### Analytics

Show conversion by market, quote turnaround, revenue by destination, rejection reasons, product demand, capacity utilization, average margin, RFQ-to-quote time, and PO-to-shipment time. Date controls must change the presentation.

### Settings

Tabs: Company, Team, Notifications, Commercial Rules, Currencies, Data Export, Demo Controls. Persist settings. Include Export Demo JSON, Reset Demo Data, and confirmation dialogs.

## Buyer portal

Create:

```text
/buyer
/buyer/rfqs
/buyer/rfqs/:rfqId
/buyer/compare/:rfqId
/buyer/orders
/buyer/orders/:orderId
/buyer/messages
```

Use a buyer-focused shell preserving the same brand.

### Buyer overview

Show active RFQs, quotes received, orders, compliance alerts, and delivery alerts.

### RFQs

Show seeded and newly submitted RFQs. Allow search, filtering, open detail, duplicate, cancel draft, and compare quotes.

### Quote comparison

Compare at least three suppliers across total price, unit price, lead time, certifications, payment terms, Incoterm, inspection plan, ETA, risk score, and reliability.

Include Highlight Differences, Recommended Option with explanation, Select Supplier, confirmation, success, and automatic order creation.

### Buyer orders and messages

Show supplier, production, inspection, shipment, customs, delivery, payment, and full communications.

## State and persistence

Use one application state layer with React Context + reducer or Zustand persistence.

Suggested localStorage keys:

```text
forgebridge.manufacturer
forgebridge.onboarding
forgebridge.buyerRfqs
forgebridge.opportunities
forgebridge.quotes
forgebridge.orders
forgebridge.messages
forgebridge.settings
forgebridge.contactSubmissions
```

Store a version wrapper:

```ts
{ version: 1, data: ... }
```

Create safe initialization, migration, export, and reset helpers.

## Responsive and accessibility requirements

Test at 375, 768, 1024, and 1440 pixels.

- Mobile drawer navigation
- Cards instead of unusably wide tables where practical
- Sticky wizard action bar on mobile
- Stacked quote builder on mobile
- No horizontal page overflow
- Visible focus rings
- Proper labels
- Dialog focus management
- Semantic headings
- Contrast-safe colors
- Status is not communicated by color alone

## README

Create:

```text
forgebridge/README.md
```

Document product summary, stack, setup, commands, route map, demo flows, localStorage persistence, reset behavior, known frontend-only limitations, and future backend integration points.

## Execution sequence

Work through these phases automatically without asking for approval:

1. Scaffold, dependencies, theme, routes, types, state, seed data, layouts.
2. Marketing site, contact, manufacturer onboarding, buyer RFQ.
3. Manufacturer dashboard, opportunities, details, quote builder, quotes.
4. Orders, compliance, buyer network, messages, analytics, settings.
5. Buyer portal, RFQs, comparison, supplier selection, buyer orders, messages.
6. Responsive QA, accessibility QA, route QA, data consistency, lint, build, error fixes.

## Mandatory final checks

Before stopping, verify all of the following:

- Home and all marketing routes work.
- Manufacturer onboarding completes and resumes after refresh.
- Buyer RFQ completes.
- New RFQ appears in buyer portal and manufacturer opportunities.
- Opportunity filters and actions work.
- Quote calculations update live.
- Quote save, review, approve, send, revise, duplicate, won, and lost states work.
- Order milestones persist.
- Compliance actions work.
- Messages can be composed and replied to.
- Buyer comparison works.
- Supplier selection creates an order.
- Settings persist.
- Demo reset works.
- No dead buttons.
- No blank routes.
- No browser console errors.
- No TypeScript errors.
- No horizontal overflow.
- Mobile navigation works.
- `npm run build` passes.
- `npm run lint` passes.

At completion, report:

1. What was built.
2. Route list.
3. Important file paths.
4. Commands to run.
5. Genuine limitations.
6. Actual build and lint results.

Do not claim a test passed unless you ran it.

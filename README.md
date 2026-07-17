# ForgeBridge

ForgeBridge is a static, frontend-only prototype of an AI-native export operating system for mid-market manufacturers. It connects manufacturer onboarding, matched RFQs, landed-cost quotes, compliance, orders, messages, and a buyer sourcing portal in one persisted demo.

## Stack and setup

React, TypeScript, Vite, React Router, Tailwind CSS, Lucide, Recharts, React Hook Form and Zod are installed. The interactive prototype uses a typed React Context/reducer state layer and seeded data.

```bash
npm install
npm run dev
npm run build
npm run lint
```

## Routes

Public: `/`, `/how-it-works`, `/manufacturers`, `/buyers`, `/industries`, `/about`, `/contact`, `/start-exporting`, `/submit-rfq`, `/demo/manufacturer`, `/demo/buyer`.

Manufacturer: `/manufacturer`, `/manufacturer/profile`, `/manufacturer/opportunities`, opportunity details, quote builder, quotes and details, orders and details, compliance, buyers, messages, analytics, and settings.

Buyer: `/buyer`, `/buyer/rfqs`, RFQ details and comparison, `/buyer/orders`, order details, and messages.

## Demo flows

- Complete or save/resume the six-step manufacturer onboarding.
- Submit a five-step buyer RFQ; it is added to buyer RFQs and creates a matched manufacturer opportunity.
- Filter and act on opportunities, build a live landed-cost quote, and transition its status.
- Advance eligible order milestones and progress compliance documents.
- Compare three suppliers and select one to automatically create an order.
- Reply to shared messages, edit the factory profile, change settings, export JSON, or reset seeded data.

State is stored as a versioned wrapper under `forgebridge.state`. Invalid or outdated data safely falls back to version 1 seed data. Reset Demo Data restores the complete seed story.

## Limitations and future integration

This prototype intentionally has no authentication, backend, real file transfer, APIs, payments, document generation, email, freight carrier connection, or multi-user concurrency. Production work would replace localStorage with authenticated services, durable relational storage, object storage, job queues, audit logs, payment rails, customs/document APIs, carrier webhooks, and role-based access control.

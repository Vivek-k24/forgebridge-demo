# PartGraph Roadmap

## Current focus

### Vehicle Coverage Workbench

Status: In progress

The initial dataset contains 363 vehicle configuration candidates from the selected Asian brands workbook.

The dataset is a starting research population, not a completed canonical catalog.

Workflow:

```
Candidate rows
    ↓
Source collection
    ↓
Evidence capture
    ↓
Verification
    ↓
Canonical promotion
```

Collection and verification are separate measurements.

---

# Local Research Environment

The collection workflow is designed to run locally.

Goals:

- avoid coupling research execution to production hosting;
- allow pause/resume operation;
- retain source evidence;
- maintain reproducible research state.

Future production deployment can publish reviewed data separately.

---

# Planned: Admin Console

Status: Draft / Not implemented

The PartGraph Admin Console will be a separate operational application.

It will not be visible to normal users.

## Planned modules

### Overview

- total users
- active users
- registration trends
- retention metrics
- system health summary

### User Management

- account lookup
- account status
- user activity
- repair history summary
- support actions

### Product Analytics

- vehicles added
- repairs started
- repairs completed
- feature usage
- search patterns

### Catalog Operations

- make/model coverage
- collection jobs
- verification progress
- source evidence
- failed collection attempts
- worker status

### AI Operations

- AI requests
- token usage
- model usage
- estimated cost
- user acceptance metrics

### Application Monitoring

- API errors
- frontend errors
- failed jobs
- database health
- server metrics

### Reports

- bug reports
- feature requests
- data corrections
- safety reports

### Security

- login failures
- suspicious activity
- audit history
- administrator actions

### Future Mobile Analytics

Prepared UI areas for:

- Android downloads
- iOS downloads
- active app versions
- crash reports

---

# Future Expansion

- Mobile applications
- Expanded vehicle coverage
- Production data operations
- Advanced analytics
- Additional repair domains

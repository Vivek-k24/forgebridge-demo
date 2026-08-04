export type Connector = {
  name: string;
  role: string;
  status: 'Connected' | 'Indexed' | 'Optional';
  detail: string;
};

export type DiffLine = {
  kind: 'context' | 'add' | 'remove';
  text: string;
};

export type ChangedFile = {
  path: string;
  language: string;
  additions: number;
  deletions: number;
  reason: string;
  diff: DiffLine[];
};

export type AnalysisStep = {
  title: string;
  detail: string;
  mode: 'deterministic' | 'retrieval' | 'ai';
  input: string;
  output: string;
};

export type ImpactItem = {
  label: string;
  value: string;
  source: string;
  confidence: 'High' | 'Medium';
};

export const samplePush = {
  repository: 'acme-operations/hr-platform',
  branch: 'feature/PAY-248-manager-approval',
  commit: '9c3a8e7',
  author: 'Maya Chen',
  ticket: 'PAY-248',
  title: 'Allow managers to approve weekly timesheets',
  description:
    'Managers can approve submitted timesheets from the team view. Approved hours should continue to flow into the existing payroll export without changing its contract.',
  pushedAt: 'Aug 3, 2026 · 7:41 PM',
  filesChanged: 5,
  additions: 96,
  deletions: 31,
};

export const changedFiles: ChangedFile[] = [
  {
    path: 'src/Api/TimesheetApprovalController.cs',
    language: 'C#',
    additions: 34,
    deletions: 8,
    reason: 'Adds the manager approval endpoint and permission check.',
    diff: [
      { kind: 'context', text: '@@ public async Task<IActionResult> Approve(Guid id)' },
      { kind: 'add', text: '+ await authorization.RequireRole(User, Roles.Manager);' },
      { kind: 'add', text: '+ var result = await approvalService.ApproveAsync(id, User.Id());' },
      { kind: 'add', text: '+ return Ok(new ApprovalResponse(result.Status, result.ApprovedAt));' },
      { kind: 'remove', text: '- return NoContent();' },
    ],
  },
  {
    path: 'src/Payroll/PayrollExportService.cs',
    language: 'C#',
    additions: 11,
    deletions: 4,
    reason: 'Unexpectedly changes the payroll export field used by an external consumer.',
    diff: [
      { kind: 'context', text: '@@ private PayrollRow Map(Employee employee, Timesheet sheet)' },
      { kind: 'remove', text: '- EmploymentStatus = employee.Status,' },
      { kind: 'add', text: '+ EmploymentStatus = employee.EmploymentStatus,' },
      { kind: 'add', text: '+ ApprovalState = sheet.ApprovalState.ToString(),' },
      { kind: 'context', text: '  Hours = sheet.ApprovedHours' },
    ],
  },
  {
    path: 'db/migrations/20260803_add_timesheet_approval.sql',
    language: 'SQL',
    additions: 22,
    deletions: 0,
    reason: 'Adds approval state and approver metadata.',
    diff: [
      { kind: 'add', text: '+ ALTER TABLE timesheets ADD approval_state varchar(24) NOT NULL DEFAULT \'Submitted\';' },
      { kind: 'add', text: '+ ALTER TABLE timesheets ADD approved_by uuid NULL;' },
      { kind: 'add', text: '+ CREATE INDEX ix_timesheets_approval_state ON timesheets(approval_state);' },
    ],
  },
  {
    path: 'contracts/payroll-export.openapi.yaml',
    language: 'OpenAPI',
    additions: 9,
    deletions: 7,
    reason: 'Renames a response field and adds approvalState.',
    diff: [
      { kind: 'context', text: '@@ components.schemas.PayrollRow.properties' },
      { kind: 'remove', text: '- employeeStatus:' },
      { kind: 'add', text: '+ employmentStatus:' },
      { kind: 'add', text: '+ approvalState:' },
      { kind: 'context', text: '    type: string' },
    ],
  },
  {
    path: 'tests/TimesheetApprovalTests.cs',
    language: 'C# test',
    additions: 20,
    deletions: 12,
    reason: 'Covers manager approval but not payroll export compatibility.',
    diff: [
      { kind: 'add', text: '+ [Fact] public async Task Manager_can_approve_submitted_timesheet()' },
      { kind: 'add', text: '+ [Fact] public async Task Non_manager_cannot_approve_timesheet()' },
      { kind: 'context', text: '  // No payroll export contract test added' },
    ],
  },
];

export const connectors: Connector[] = [
  {
    name: 'GitHub',
    role: 'Push webhook, pull-request diff, CODEOWNERS',
    status: 'Connected',
    detail: 'Reads only the changed commit and repository graph identifiers.',
  },
  {
    name: 'Linear / Jira',
    role: 'Ticket intent and acceptance criteria',
    status: 'Connected',
    detail: 'Retrieves PAY-248 because the branch and pull request reference it.',
  },
  {
    name: 'OpenAPI',
    role: 'Public API contract comparison',
    status: 'Indexed',
    detail: 'Detects the employeeStatus → employmentStatus contract change.',
  },
  {
    name: 'CI + coverage',
    role: 'Test results and changed-line coverage',
    status: 'Connected',
    detail: 'Finds that approval tests pass but payroll contract coverage is missing.',
  },
  {
    name: 'Sentry / incidents',
    role: 'Historical production failure retrieval',
    status: 'Indexed',
    detail: 'Retrieves INC-184 because it involved PayrollExportService.',
  },
  {
    name: 'Datadog / observability',
    role: 'Runtime ownership and service map',
    status: 'Optional',
    detail: 'Not needed for this static prototype; useful after deployment.',
  },
];

export const analysisSteps: AnalysisStep[] = [
  {
    title: 'Receive the delta',
    detail: 'The GitHub webhook supplies one commit, not the whole repository.',
    mode: 'deterministic',
    input: '5 changed files · 127 changed lines',
    output: 'Changed paths, symbols and contract files',
  },
  {
    title: 'Parse changed symbols',
    detail: 'Language parsers identify methods, routes, schemas and database objects.',
    mode: 'deterministic',
    input: 'C# AST · SQL migration · OpenAPI diff',
    output: '8 changed symbols · 2 endpoints · 1 table',
  },
  {
    title: 'Query the persistent graph',
    detail: 'The product follows existing symbol-to-workflow links instead of asking a model to rediscover the repository.',
    mode: 'retrieval',
    input: 'Changed symbols',
    output: 'Timesheet approval · payroll export · 2 UI routes',
  },
  {
    title: 'Retrieve only relevant context',
    detail: 'Ticket, tests, API consumers, CODEOWNERS and the nearest similar incident are selected.',
    mode: 'retrieval',
    input: 'Graph neighborhood',
    output: 'PAY-248 · 7 tests · 2 owners · INC-184',
  },
  {
    title: 'Explain business impact',
    detail: 'A small language-model call converts selected technical evidence into a plain-language review.',
    mode: 'ai',
    input: '9.4k selected tokens in this sample',
    output: 'Impact summary · missing tests · review questions',
  },
  {
    title: 'Apply release gates',
    detail: 'Normal code checks CI, contract compatibility, coverage and required reviewers.',
    mode: 'deterministic',
    input: 'Policy + evidence',
    output: 'Not ready to merge · 3 blockers',
  },
];

export const impactSummary: ImpactItem[] = [
  {
    label: 'Primary workflow',
    value: 'Manager timesheet approval',
    source: 'PAY-248 + TimesheetApprovalController.Approve',
    confidence: 'High',
  },
  {
    label: 'Secondary workflow',
    value: 'Payroll export generation',
    source: 'PayrollExportService.Map + prior graph edge',
    confidence: 'High',
  },
  {
    label: 'User interfaces',
    value: '/manager/timesheets · /payroll/export',
    source: 'Route index + frontend API consumers',
    confidence: 'High',
  },
  {
    label: 'API contracts',
    value: 'PATCH /timesheets/{id}/approve · GET /payroll/export',
    source: 'Controller route + OpenAPI schema diff',
    confidence: 'High',
  },
  {
    label: 'Data objects',
    value: 'timesheets.approval_state · employee status mapping',
    source: 'SQL migration + export mapper',
    confidence: 'High',
  },
  {
    label: 'Affected roles',
    value: 'Manager · payroll administrator · HR administrator',
    source: 'Authorization rules + workflow graph',
    confidence: 'Medium',
  },
];

export const blockers = [
  {
    title: 'Backward compatibility test missing',
    detail: 'The payroll export contract renames employeeStatus, but no consumer compatibility test was added.',
    owner: 'Backend engineer',
    evidence: 'OpenAPI diff + test inventory',
  },
  {
    title: 'Ticket and implementation disagree',
    detail: 'PAY-248 says the payroll export contract must remain unchanged. The push changes two exported fields.',
    owner: 'Product owner',
    evidence: 'Acceptance criterion 4 + PayrollExportService.cs',
  },
  {
    title: 'Payroll owner review required',
    detail: 'CODEOWNERS covers the API folder, but the payroll contract owner is not requested on the pull request.',
    owner: 'Release manager',
    evidence: 'CODEOWNERS + affected workflow graph',
  },
];

export const suggestedTests = [
  'Manager approves a submitted timesheet and the status is visible in the team UI.',
  'A non-manager cannot approve a timesheet.',
  'Approved hours appear in the payroll export.',
  'The payroll export remains compatible with the existing employeeStatus consumer.',
  'Rejected or reopened timesheets do not enter payroll.',
  'The database migration can be rolled back without losing existing approvals.',
];

export const contextBudget = {
  fullRepositoryTokens: 184000,
  incrementalTokens: 9400,
  fullRepositoryFiles: 1264,
  selectedFiles: 18,
  changedFiles: 5,
  graphNodesVisited: 42,
  note: 'Illustrative values for this static sample. Real usage depends on repository size, language and context policy.',
};

export const excludedContext = [
  'Unchanged source files outside the impact graph',
  'Production databases and customer data',
  'Secrets, credentials and environment files',
  'Unrelated tickets and incident records',
  'Binary assets and generated files',
  'Private repositories outside the installation scope',
];

export const graphEdges = [
  ['TimesheetApprovalController.Approve', 'Manager approval workflow'],
  ['Manager approval workflow', '/manager/timesheets'],
  ['Manager approval workflow', 'PayrollExportService.Map'],
  ['PayrollExportService.Map', 'GET /api/payroll/export'],
  ['GET /api/payroll/export', '/payroll/export'],
  ['PayrollExportService.Map', 'INC-184'],
] as const;

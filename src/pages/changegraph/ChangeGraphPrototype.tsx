import {useEffect,useMemo,useState} from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Braces,
  CheckCircle2,
  Clock3,
  Database,
  FileCode2,
  Gauge,
  GitCommit,
  GitPullRequest,
  Github,
  Lock,
  Monitor,
  Network,
  Play,
  RotateCcw,
  Server,
  ShieldCheck,
  TestTube2,
  TicketCheck,
  Users,
} from 'lucide-react';
import {
  analysisSteps,
  blockers,
  changedFiles,
  connectors,
  contextBudget,
  excludedContext,
  graphEdges,
  impactSummary,
  samplePush,
  suggestedTests,
  type ChangedFile,
} from '../../data/changeGraphDemo';

type DetailTab = 'impact' | 'tests' | 'tokens' | 'graph';
type PreviewScreen = 'manager' | 'payroll';

const modeLabel = {
  deterministic: 'Code',
  retrieval: 'Graph',
  ai: 'AI',
} as const;

function FileDiff({file}:{file:ChangedFile}){
  return <div className="cg-diff" aria-label={`Diff for ${file.path}`}>
    <div className="cg-diff-head"><span>{file.path}</span><b>+{file.additions} −{file.deletions}</b></div>
    <p>{file.reason}</p>
    <pre>{file.diff.map((line,index)=><code key={`${line.text}-${index}`} className={line.kind}>{line.text}{'\n'}</code>)}</pre>
  </div>;
}

function ManagerPreview(){return <div className="cg-ui-window">
  <div className="cg-ui-browser"><span/><span/><span/><b>/manager/timesheets</b></div>
  <div className="cg-ui-body">
    <div className="cg-ui-title"><div><small>TEAM WORKFLOW</small><h3>Weekly timesheets</h3></div><span className="cg-badge neutral">3 awaiting approval</span></div>
    <div className="cg-timesheet-row"><span className="cg-avatar">AR</span><div><b>Ana Rivera</b><small>40.0 hours · Week 31</small></div><span className="cg-badge warning">Submitted</span><button>Approve</button></div>
    <div className="cg-timesheet-row muted"><span className="cg-avatar">JL</span><div><b>Jon Lee</b><small>38.5 hours · Week 31</small></div><span className="cg-badge success">Approved</span><button disabled>Approved</button></div>
    <div className="cg-impact-callout"><AlertTriangle/><p><b>New behavior:</b> approving here now writes data consumed by the payroll export.</p></div>
  </div>
</div>}

function PayrollPreview(){return <div className="cg-ui-window">
  <div className="cg-ui-browser"><span/><span/><span/><b>/payroll/export</b></div>
  <div className="cg-ui-body">
    <div className="cg-ui-title"><div><small>EXTERNAL CONTRACT</small><h3>Payroll export</h3></div><span className="cg-badge danger">Compatibility risk</span></div>
    <div className="cg-schema">
      <div><span>employeeId</span><b>unchanged</b></div>
      <div className="removed"><span>employeeStatus</span><b>removed</b></div>
      <div className="added"><span>employmentStatus</span><b>added</b></div>
      <div className="added"><span>approvalState</span><b>added</b></div>
    </div>
    <div className="cg-impact-callout danger"><AlertTriangle/><p><b>Hidden impact:</b> the ticket says this contract must not change, but the push renames a field.</p></div>
  </div>
</div>}

export function ChangeGraphPrototype(){
  const[selectedFilePath,setSelectedFilePath]=useState(changedFiles[0].path);
  const[analysisStage,setAnalysisStage]=useState(0);
  const[running,setRunning]=useState(false);
  const[detailTab,setDetailTab]=useState<DetailTab>('impact');
  const[preview,setPreview]=useState<PreviewScreen>('manager');
  const[reviewDecision,setReviewDecision]=useState<'open'|'acknowledged'>('open');

  const selectedFile=useMemo(()=>changedFiles.find(file=>file.path===selectedFilePath)??changedFiles[0],[selectedFilePath]);
  const complete=analysisStage>=analysisSteps.length;
  const progress=Math.round((analysisStage/analysisSteps.length)*100);
  const savedPercent=Math.round((1-contextBudget.incrementalTokens/contextBudget.fullRepositoryTokens)*100);

  useEffect(()=>{
    if(!running)return;
    if(analysisStage>=analysisSteps.length){setRunning(false);return;}
    const timer=window.setTimeout(()=>setAnalysisStage(stage=>stage+1),620);
    return()=>window.clearTimeout(timer);
  },[running,analysisStage]);

  function runAnalysis(){setAnalysisStage(0);setReviewDecision('open');setDetailTab('impact');setRunning(true)}
  function reset(){setRunning(false);setAnalysisStage(0);setReviewDecision('open');setDetailTab('impact');setPreview('manager')}

  return <main className="cg-app">
    <header className="cg-topbar">
      <div className="cg-brand"><Network/><span>CHANGE<strong>GRAPH</strong></span><small>working name</small></div>
      <div className="cg-top-status"><span><i/> Static product prototype</span><b>GitHub Pages</b></div>
    </header>

    <section className="cg-intro">
      <div>
        <span className="cg-eyebrow">SYSTEM A → INTELLIGENCE LAYER → SYSTEM B</span>
        <h1>Understand a code push<br/><em>without rereading the repository.</em></h1>
        <p>A normal AI reviewer can spend the same tokens a developer would spend asking Copilot or Claude to inspect the repo again. This prototype tests a different architecture: maintain a persistent code-to-business graph, process only the new delta, and send a small evidence package to the model.</p>
      </div>
      <div className="cg-thesis-card">
        <span>THE PRODUCT THESIS</span>
        <h2>The savings are not “AI instead of AI.”</h2>
        <p>The savings come from <b>not rediscovering unchanged context</b> after every push.</p>
        <div><span>Full repo recheck</span><b>{contextBudget.fullRepositoryTokens.toLocaleString()} tokens</b></div>
        <div className="good"><span>Incremental sample</span><b>{contextBudget.incrementalTokens.toLocaleString()} tokens</b></div>
        <small>Illustrative static sample—not a measured customer result.</small>
      </div>
    </section>

    <section className="cg-three-system">
      <article className="cg-system cg-system-a">
        <div className="cg-system-label"><span>SYSTEM A</span><b><GitCommit/> Sample code push</b></div>
        <div className="cg-pr-meta">
          <div><GitPullRequest/><span><b>{samplePush.ticket}</b><small>{samplePush.title}</small></span></div>
          <p>{samplePush.description}</p>
          <dl>
            <div><dt>Repository</dt><dd>{samplePush.repository}</dd></div>
            <div><dt>Branch</dt><dd>{samplePush.branch}</dd></div>
            <div><dt>Commit</dt><dd>{samplePush.commit}</dd></div>
            <div><dt>Changed</dt><dd>{samplePush.filesChanged} files · +{samplePush.additions} −{samplePush.deletions}</dd></div>
          </dl>
        </div>
        <div className="cg-file-list" aria-label="Changed files">
          {changedFiles.map(file=><button key={file.path} className={selectedFilePath===file.path?'active':''} onClick={()=>setSelectedFilePath(file.path)}><FileCode2/><span>{file.path}<small>{file.language} · +{file.additions} −{file.deletions}</small></span></button>)}
        </div>
        <FileDiff file={selectedFile}/>
      </article>

      <article className="cg-system cg-system-core">
        <div className="cg-system-label"><span>OUR PRODUCT</span><b><Network/> Incremental impact engine</b></div>
        <div className="cg-core-header">
          <div><span>Persistent project graph</span><h2>ChangeGraph</h2><p>Changed symbols are linked to workflows, APIs, data, tests, incidents and owners.</p></div>
          <div className="cg-score"><strong>{complete?'HIGH':'—'}</strong><span>release risk</span></div>
        </div>
        <div className="cg-run-controls">
          <button className="cg-primary" onClick={runAnalysis} disabled={running}><Play/>{running?'Analyzing push…':complete?'Run again':'Run impact analysis'}</button>
          <button className="cg-secondary" onClick={reset}><RotateCcw/>Reset</button>
        </div>
        <div className="cg-progress"><i style={{width:`${progress}%`}}/><span>{progress}%</span></div>
        <div className="cg-pipeline">
          {analysisSteps.map((step,index)=>{
            const state=index<analysisStage?'done':index===analysisStage&&running?'active':'waiting';
            return <div key={step.title} className={`cg-pipeline-step ${state}`}>
              <b>{state==='done'?<CheckCircle2/>:index+1}</b>
              <div><div><h3>{step.title}</h3><span className={step.mode}>{modeLabel[step.mode]}</span></div><p>{step.detail}</p><small><strong>Input:</strong> {step.input}</small><small><strong>Output:</strong> {step.output}</small></div>
            </div>;
          })}
        </div>
        <div className="cg-model-boundary">
          <ShieldCheck/><div><b>Only step 5 needs a language model.</b><p>Parsing, graph traversal, contract comparison and release gates use deterministic code.</p></div>
        </div>
      </article>

      <article className={`cg-system cg-system-b ${complete?'ready':''}`}>
        <div className="cg-system-label"><span>SYSTEM B</span><b><Monitor/> Endpoint and user impact</b></div>
        {!complete?<div className="cg-waiting-output"><Server/><h2>Waiting for the push analysis</h2><p>The output is not a generic pull-request summary. It shows where the code becomes visible to users and which release decision is blocked.</p><ArrowRight/></div>:<>
          <div className="cg-decision">
            <span>MERGE DECISION</span><h2><AlertTriangle/> Not ready to merge</h2><p>Three evidence-backed blockers must be resolved.</p>
          </div>
          <div className="cg-preview-tabs"><button className={preview==='manager'?'active':''} onClick={()=>setPreview('manager')}>Manager UI</button><button className={preview==='payroll'?'active':''} onClick={()=>setPreview('payroll')}>Payroll endpoint</button></div>
          {preview==='manager'?<ManagerPreview/>:<PayrollPreview/>}
          <div className="cg-endpoints">
            <h3>Affected endpoints</h3>
            <div><span className="method patch">PATCH</span><code>/api/timesheets/{'{id}'}/approve</code><b>intended</b></div>
            <div><span className="method get">GET</span><code>/api/payroll/export</code><b className="risk">unexpected</b></div>
          </div>
          <div className="cg-owners"><Users/><div><span>Required reviewers</span><b>Payroll owner · Backend owner · Product owner</b></div></div>
        </>}
      </article>
    </section>

    <section className="cg-connectors">
      <div className="cg-section-head"><span>CONNECTED CONTEXT</span><h2>APIs to the tools that already know part of the answer</h2><p>These systems supply targeted evidence. They are not copied into one giant prompt.</p></div>
      <div className="cg-connector-grid">{connectors.map((connector,index)=>{
        const icons=[<Github/>,<TicketCheck/>,<Braces/>,<TestTube2/>,<Activity/>,<Gauge/>];
        return <article key={connector.name}><div>{icons[index]}<span className={`cg-connector-status ${connector.status.toLowerCase()}`}>{connector.status}</span></div><h3>{connector.name}</h3><b>{connector.role}</b><p>{connector.detail}</p></article>;
      })}</div>
    </section>

    <section className="cg-review-workbench">
      <div className="cg-tabs" role="tablist" aria-label="Analysis details">
        <button className={detailTab==='impact'?'active':''} onClick={()=>setDetailTab('impact')}>Impact map</button>
        <button className={detailTab==='tests'?'active':''} onClick={()=>setDetailTab('tests')}>Regression plan</button>
        <button className={detailTab==='tokens'?'active':''} onClick={()=>setDetailTab('tokens')}>Context and tokens</button>
        <button className={detailTab==='graph'?'active':''} onClick={()=>setDetailTab('graph')}>Project graph</button>
      </div>

      {detailTab==='impact'&&<div className="cg-tab-panel">
        <div className="cg-section-head"><span>EVIDENCE-BACKED REVIEW</span><h2>What the push can change in the business system</h2></div>
        <div className="cg-impact-grid">{impactSummary.map(item=><article key={item.label}><span>{item.label}</span><h3>{item.value}</h3><p>{item.source}</p><b>{item.confidence} confidence</b></article>)}</div>
        <div className="cg-blocker-list"><h3>Merge blockers</h3>{blockers.map((blocker,index)=><article key={blocker.title}><b>{index+1}</b><div><h4>{blocker.title}</h4><p>{blocker.detail}</p><small>Evidence: {blocker.evidence}</small></div><span>{blocker.owner}</span></article>)}</div>
      </div>}

      {detailTab==='tests'&&<div className="cg-tab-panel">
        <div className="cg-section-head"><span>REGRESSION PLAN</span><h2>Test the user behavior and the hidden contract</h2><p>The system does not write or run every test. It identifies which existing and missing scenarios are justified by the impact graph.</p></div>
        <div className="cg-test-plan">{suggestedTests.map((test,index)=><article key={test}><b>{index+1}</b><p>{test}</p><span>{index<2?'Existing':'Recommended'}</span></article>)}</div>
      </div>}

      {detailTab==='tokens'&&<div className="cg-tab-panel">
        <div className="cg-section-head"><span>THE ECONOMIC TEST</span><h2>Does the product actually avoid repeated context discovery?</h2><p>Without a persistent graph and aggressive context selection, this becomes another review summary tool and your criticism is correct.</p></div>
        <div className="cg-token-compare">
          <article><span>Naive agent recheck</span><strong>{contextBudget.fullRepositoryTokens.toLocaleString()}</strong><small>illustrative input tokens</small><div><b>{contextBudget.fullRepositoryFiles.toLocaleString()}</b> repository files reconsidered</div></article>
          <ArrowRight/>
          <article className="efficient"><span>Incremental graph query</span><strong>{contextBudget.incrementalTokens.toLocaleString()}</strong><small>illustrative input tokens</small><div><b>{contextBudget.selectedFiles}</b> selected files · {contextBudget.graphNodesVisited} graph nodes</div></article>
          <article className="saving"><span>Illustrative reduction</span><strong>{savedPercent}%</strong><small>less model context</small><div>The exact saving must be measured on real repositories.</div></article>
        </div>
        <div className="cg-exclusions"><Lock/><div><h3>Context excluded from the model call</h3><div>{excludedContext.map(item=><span key={item}>{item}</span>)}</div></div></div>
        <p className="cg-footnote">{contextBudget.note}</p>
      </div>}

      {detailTab==='graph'&&<div className="cg-tab-panel">
        <div className="cg-section-head"><span>PERSISTENT PROJECT MEMORY</span><h2>The graph stores relationships once and updates the delta</h2><p>This is the part a one-off Copilot or Claude prompt normally has to rediscover.</p></div>
        <div className="cg-graph">
          {graphEdges.map(([from,to],index)=><div key={`${from}-${to}`} className={`edge edge-${index}`}><span>{from}</span><ArrowRight/><b>{to}</b></div>)}
        </div>
        <div className="cg-graph-legend"><span><i className="code"/>Code symbol</span><span><i className="workflow"/>Workflow or UI</span><span><i className="evidence"/>Incident or evidence</span></div>
      </div>}
    </section>

    <section className="cg-human-gate">
      <div><span>HUMAN CORRECTION LOOP</span><h2>The graph becomes useful only when reviewers correct it.</h2><p>A reviewer can confirm that the payroll export is genuinely affected, reject a false connection, or assign the correct owner. That correction becomes project memory for the next push.</p></div>
      <div className="cg-review-card">
        <span>PROPOSED LEARNING</span><h3>Manager approval → payroll export</h3><p>Because approved hours are consumed by <code>PayrollExportService.Map</code>.</p>
        {reviewDecision==='open'?<div><button className="cg-primary" onClick={()=>setReviewDecision('acknowledged')}><CheckCircle2/>Confirm relationship</button><button className="cg-secondary" onClick={()=>setReviewDecision('acknowledged')}>Mark false impact</button></div>:<p className="cg-recorded"><CheckCircle2/> Sample correction recorded in project memory.</p>}
      </div>
    </section>

    <footer className="cg-footer"><div className="cg-brand"><Network/><span>CHANGE<strong>GRAPH</strong></span></div><p>Static prototype · simulated integrations and analysis · no live model or repository indexing is connected.</p><span><Clock3/> Built to test one claim: understand the delta, not the whole repo.</span></footer>
  </main>;
}

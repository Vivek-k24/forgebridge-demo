import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {AlertTriangle,ArrowLeft,ArrowRight,BrainCircuit,CheckCircle2,Eye,FileSearch,Lock,RotateCcw,Scale,ShieldCheck,Truck,UserCheck,WalletCards} from 'lucide-react';
import {Button,Card} from '../../components/common/UI';
import {transactionHeader,v4Stages,type Owner,type Visibility} from '../../data/v4Transaction';

type View='evidence'|'rules'|'guardrails';
const storageKey='forgebridge.v4.demo';
const ownerIcon=(owner:Owner)=>owner==='AI PREPARES'?<BrainCircuit/>:owner==='HUMAN APPROVES'?<UserCheck/>:<Truck/>;
const visibilityClass=(value:Visibility)=>value==='Shared parties'?'shared':'restricted';

export function V4Demo(){
  const initial=()=>{try{return Math.min(Number(localStorage.getItem(storageKey))||0,v4Stages.length-1)}catch{return 0}};
  const[step,setStep]=useState(initial);
  const[view,setView]=useState<View>('evidence');
  const[approved,setApproved]=useState<Record<number,boolean>>({});
  const current=v4Stages[step];
  const progress=Math.round(((step+1)/v4Stages.length)*100);
  const approvals=Object.keys(approved).length;
  useEffect(()=>{try{localStorage.setItem(storageKey,String(step))}catch{/* storage unavailable */}},[step]);
  function reset(){setStep(0);setView('evidence');setApproved({});try{localStorage.removeItem(storageKey)}catch{/* storage unavailable */}}
  return <div className="v4demo">
    <div className="demobanner">V4 DEMO · SAMPLE DATA · NOT LEGAL OR CUSTOMS ADVICE · NO ACCOUNT REQUIRED</div>
    <header className="v4demohead"><Link className="brand" to="/">FORGE<span>BRIDGE</span></Link><div><Button className="ghost" onClick={reset}><RotateCcw/> Reset</Button><Link className="btn ghost" to="/">Exit demo</Link></div></header>
    <div className="v4demolayout">
      <aside className="v4sidebar"><span>TRANSACTION FB-26041</span><h2>Industrial pump assemblies</h2><p>India → United States</p><div className="v4progress"><i style={{width:`${progress}%`}}/></div><small>{progress}% through the transaction</small><nav>{v4Stages.map((stage,index)=><button key={stage.name} className={index===step?'active':index<step?'done':''} onClick={()=>{setStep(index);setView('evidence')}}><b>{index<step?'✓':index+1}</b><span>{stage.name}<small>{stage.status}</small></span></button>)}</nav></aside>
      <main>
        <section className="v4demopage">
          <div className="v4demoeyebrow"><span>STEP {step+1} OF {v4Stages.length}</span><span className={`owner ${current.owner.toLowerCase().replaceAll(' ','-')}`}>{ownerIcon(current.owner)} {current.owner}</span></div>
          <h1>{current.name}</h1><p className="lead">{current.summary}</p>
          <div className="v4transactionbar">{transactionHeader.slice(0,4).map(([label,value])=><div key={label}><span>{label}</span><b>{value}</b></div>)}</div>
          <div className="v4status"><div><span>Current status</span><b>{current.status}</b></div><div><span>Current blocker</span><b>{current.blocker}</b></div><div><span>Next action</span><b>{current.nextAction}</b></div></div>

          <div className="v4viewtabs" role="tablist" aria-label="Stage information views">
            <button className={view==='evidence'?'active':''} onClick={()=>setView('evidence')}><Eye/> Evidence summary</button>
            <button className={view==='rules'?'active':''} onClick={()=>setView('rules')}><Scale/> Rules and standards</button>
            <button className={view==='guardrails'?'active':''} onClick={()=>setView('guardrails')}><ShieldCheck/> AI scan guardrails</button>
          </div>

          {view==='evidence'&&<section className="v4panel" aria-label="Evidence summary">
            <div className="v4panelhead"><div><span>VISIBLE WITHOUT OPENING DOCUMENTS</span><h2>Evidence summary</h2></div><p>Every displayed fact keeps its source, verification state and viewing permissions. The full document is optional.</p></div>
            <div className="v4evidencegrid">{current.evidence.map(item=><Card key={item.label} className="v4evidencecard"><span className="fieldlabel">{item.label}</span><h3>{item.value}</h3><dl><div><dt>Source</dt><dd>{item.source}</dd></div><div><dt>Verification</dt><dd>{item.verification}</dd></div></dl><div className="v4visibility">{item.visibility.map(v=><span key={v} className={visibilityClass(v)}>{v==='Shared parties'?<Eye/>:<Lock/>}{v}</span>)}</div></Card>)}</div>
            <Card className="v4visibilitynote"><Eye/><div><h3>Shared does not mean public</h3><p>“Shared parties” means the approved buyer, seller and ForgeBridge users attached to this transaction. Cost, margin, bank, identity and risk information stays role-restricted.</p></div></Card>
          </section>}

          {view==='rules'&&<section className="v4panel" aria-label="Applicable rules">
            <div className="v4panelhead"><div><span>NO INVENTED UNIVERSAL PROCEDURE</span><h2>Rules attached to this stage</h2></div><p>The workflow records the rule source and review status. A reference model is not displayed as a law, and a candidate classification is not displayed as a customs decision.</p></div>
            <div className="v4rulesgrid">{current.rules.map(rule=><Card key={`${rule.layer}-${rule.name}`} className="v4rulecard"><div><span>{rule.layer}</span><b className={rule.status.toLowerCase().replaceAll(' ','-')}>{rule.status}</b></div><h3>{rule.name}</h3><p>{rule.note}</p><small>Authority or owner: {rule.authority}</small></Card>)}</div>
            <Card className="v4warning"><AlertTriangle/><div><h3>Authorized review remains mandatory</h3><p>ForgeBridge may retrieve and summarize official requirements. Customs brokers, engineers, quality managers, lawyers, banks and regulators retain their actual authority.</p></div></Card>
          </section>}

          {view==='guardrails'&&<section className="v4panel" aria-label="AI scan guardrails">
            <div className="v4panelhead"><div><span>SCAN MANIFEST</span><h2>What the AI may read—and what it must ignore</h2></div><p>The scan scope is defined before model execution. A document cannot expand the AI’s permissions or instruct it to bypass controls.</p></div>
            <Card className="v4purpose"><FileSearch/><div><span>Purpose</span><h3>{current.scan.purpose}</h3></div></Card>
            <div className="v4guardgrid"><Card><h3>Allowed documents</h3>{current.scan.allowedDocuments.map(x=><p key={x}><CheckCircle2/> {x}</p>)}</Card><Card><h3>Excluded documents</h3>{current.scan.excludedDocuments.map(x=><p key={x}><Lock/> {x}</p>)}</Card><Card><h3>Allowed fields</h3>{current.scan.allowedFields.map(x=><p key={x}><CheckCircle2/> {x}</p>)}</Card><Card className="blocked"><h3>AI cannot</h3>{current.scan.blockedActions.map(x=><p key={x}><AlertTriangle/> {x}</p>)}</Card></div>
            <div className="v4controlstrip"><span>Required controls</span>{['Tenant isolation','Document allowlist','Field allowlist','Source provenance','Version tracking','Conflict escalation','Named approver','Audit log'].map(x=><b key={x}>{x}</b>)}</div>
          </section>}

          <section className="v4lanes"><Card><BrainCircuit/><span>AI PREPARES</span>{current.ai.map(x=><p key={x}>{x}</p>)}</Card><Card><UserCheck/><span>HUMANS APPROVE</span>{current.human.length?current.human.map(x=><p key={x}>{x}</p>):<p>No new human approval at this stage.</p>}</Card><Card><Truck/><span>PARTNERS EXECUTE</span>{current.partner.length?current.partner.map(x=><p key={x}>{x}</p>):<p>No external partner action at this stage.</p>}</Card></section>

          {current.owner==='HUMAN APPROVES'&&!approved[step]&&<Card className="v4approval"><ShieldCheck/><div><h3>Named approval required</h3><p>The system can prepare the decision, but it cannot cross this commitment gate automatically.</p></div><Button onClick={()=>setApproved(previous=>({...previous,[step]:true}))}>Record sample approval</Button></Card>}
          {approved[step]&&<p className="approved"><CheckCircle2/> Sample approval recorded with stage, role and timestamp.</p>}
          {step===v4Stages.length-1&&<Card className="v4complete"><WalletCards/><h2>Transaction successful</h2><p>The buyer received 400 assemblies. The seller confirmed payment. Rules, evidence, permissions, approvals and partner milestones remain attached to FB-26041.</p><div><span>Approvals recorded</span><b>{approvals}</b><span>Summarized evidence fields</span><b>{v4Stages.reduce((total,s)=>total+s.evidence.length,0)}</b><span>Open blockers</span><b>0</b></div></Card>}
        </section>
        <div className="v4demoactions">{step>0&&<Button className="ghost" onClick={()=>{setStep(step-1);setView('evidence')}}><ArrowLeft/> Back</Button>}<span/><Button className="ghost" onClick={()=>{setStep(6);setView('evidence')}}>Open release evidence</Button>{step<v4Stages.length-1?<Button onClick={()=>{setStep(step+1);setView('evidence')}}>Next <ArrowRight/></Button>:<Button onClick={reset}>Restart transaction</Button>}</div>
      </main>
    </div>
  </div>
}

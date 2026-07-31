import {useState} from 'react';
import {NavLink,Outlet,Link} from 'react-router-dom';
import {Menu} from 'lucide-react';
import {Button} from '../common/UI';

export function AppShell(){return <Outlet/>}

export function PublicLayout(){const[open,setOpen]=useState(false);const links=[['Problem','/problem'],['Product','/product'],['Rules map','/rules'],['AI guardrails','/ai'],['Participants','/network'],['Contact','/contact']];return <><header className="publichead v3publichead"><Link className="brand" to="/">FORGE<span>BRIDGE</span></Link><Button className="menubtn" onClick={()=>setOpen(!open)} aria-label="Open navigation"><Menu/></Button><nav className={open?'open':''}>{links.map(x=><NavLink key={x[1]} to={x[1]} onClick={()=>setOpen(false)}>{x[0]}</NavLink>)}<Link className="btn" to="/demo" onClick={()=>setOpen(false)}>Visual V4 demo</Link></nav></header><Outlet/><footer className="v3footer"><div><div className="brand">FORGE<span>BRIDGE</span></div><p>One standards-aware, evidence-backed transaction from request through payment.</p></div><div><Link to="/problem">Problem</Link><Link to="/product">Product</Link><Link to="/rules">Rules map</Link><Link to="/ai">AI guardrails</Link><Link to="/demo">Demo</Link></div><small>© 2026 ForgeBridge · Product-validation prototype · Sample data only · Not legal, customs or compliance advice</small></footer></>}

import type {ButtonHTMLAttributes,InputHTMLAttributes,ReactNode,SelectHTMLAttributes} from 'react';
export function Button({className='',...p}:ButtonHTMLAttributes<HTMLButtonElement>){return <button className={`btn ${className}`} {...p}/>}
export function Input({className='',...p}:InputHTMLAttributes<HTMLInputElement>){return <input className={`input ${className}`} {...p}/>}
export function Select({className='',...p}:SelectHTMLAttributes<HTMLSelectElement>){return <select className={`input ${className}`} {...p}/>}
export function Card({children,className=''}:{children:ReactNode;className?:string}){return <section className={`card ${className}`}>{children}</section>}
export function Badge({children,tone=''}:{children:ReactNode;tone?:string}){return <span className={`badge ${tone}`}>{children}</span>}
export function Modal({title,children,onClose}:{title:string;children:ReactNode;onClose:()=>void}){return <div className="modalback" role="dialog" aria-modal="true" aria-label={title} onMouseDown={e=>e.target===e.currentTarget&&onClose()}><div className="modal"><div className="row between"><h2>{title}</h2><Button onClick={onClose} aria-label="Close dialog">×</Button></div>{children}</div></div>}
export const Field=({label,children}:{label:string;children:ReactNode})=><label className="field"><span>{label}</span>{children}</label>;

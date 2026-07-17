import type {QuoteCostBreakdown} from '../types/domain';
export const quoteTotals=(c:QuoteCostBreakdown)=>{const manufacturingCost=c.material+c.manufacturing+c.tooling+c.inspection+c.packaging;const markup=manufacturingCost*(c.margin/100);const exw=manufacturingCost+c.contingency+c.platformCommission+markup;const fob=exw+c.inlandFreight;const cif=fob+c.internationalFreight+c.insurance;return{manufacturingCost,exw,fob,cif,landed:cif+c.duty,markup};};
export const money=(n:number,c='USD')=>new Intl.NumberFormat('en-US',{style:'currency',currency:c,maximumFractionDigits:0}).format(n);

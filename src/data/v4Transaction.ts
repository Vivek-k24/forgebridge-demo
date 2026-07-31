export type Owner='AI PREPARES'|'HUMAN APPROVES'|'PARTNER EXECUTES';
export type Visibility='Shared parties'|'Buyer only'|'Seller only'|'ForgeBridge operations'|'Inspector'|'Freight partner'|'Customs broker'|'Bank or payment provider';

export type EvidenceField={
  label:string;
  value:string;
  source:string;
  verification:string;
  visibility:Visibility[];
};

export type RuleReference={
  layer:'International model'|'Contract rule'|'Country system'|'Product rule'|'AI governance';
  name:string;
  authority:string;
  status:'Applies'|'Candidate'|'Review required'|'Not used in sample';
  note:string;
};

export type ScanManifest={
  purpose:string;
  allowedDocuments:string[];
  excludedDocuments:string[];
  allowedFields:string[];
  blockedActions:string[];
};

export type V4Stage={
  name:string;
  summary:string;
  owner:Owner;
  status:string;
  ai:string[];
  human:string[];
  partner:string[];
  evidence:EvidenceField[];
  rules:RuleReference[];
  scan:ScanManifest;
  blocker:string;
  nextAction:string;
};

export const transactionHeader=[
  ['Transaction','FB-26041'],
  ['Goods','400 industrial pump assemblies'],
  ['Seller','Meridian Industrial Systems · India'],
  ['Buyer','North American Process Equipment · United States'],
  ['Route','Hyderabad → Port of Houston'],
  ['Value','USD 248,000 · sample data']
] as const;

const shared:Visibility[]=['Shared parties'];
const sellerOps:Visibility[]=['Seller only','ForgeBridge operations'];
const customs:Visibility[]=['Customs broker','ForgeBridge operations'];

export const v4Stages:V4Stage[]=[
  {
    name:'Buyer request',
    summary:'A US maintenance distributor asks for 400 industrial pump assemblies delivered to Houston in 75 days.',
    owner:'AI PREPARES',status:'Needs clarification',
    ai:['Reads the buyer email and approved attachments','Creates a structured requirement record','Detects missing delivery-point, warranty and inspection details'],
    human:['Buyer confirms intended use and final delivery point'],partner:[],
    evidence:[
      {label:'Product',value:'Industrial pump assembly · Model family IPA-400',source:'Buyer email · paragraph 1',verification:'AI extracted · buyer review required',visibility:shared},
      {label:'Quantity',value:'400 units',source:'Quantity Schedule.xlsx · row 8',verification:'Cross-document match',visibility:shared},
      {label:'Requested delivery',value:'Within 75 days',source:'Buyer email · paragraph 2',verification:'Meaning unclear: shipped or delivered',visibility:shared},
      {label:'Destination',value:'Houston, Texas',source:'Delivery Note.pdf · field 4',verification:'Final facility not stated',visibility:shared},
      {label:'Required pressure rating',value:'16 bar',source:'Specification Sheet.pdf · section 2.3',verification:'AI extracted · engineer review required',visibility:shared},
      {label:'Buyer contact',value:'Procurement manager · verified sample identity',source:'Buyer master record',verification:'ForgeBridge review complete',visibility:['ForgeBridge operations','Seller only']}
    ],
    rules:[
      {layer:'International model',name:'UN/CEFACT Buy-Ship-Pay Reference Data Model',authority:'UN/CEFACT',status:'Applies',note:'Provides common concepts for buyer, seller, product, order, delivery and settlement data.'},
      {layer:'Contract rule',name:'Buyer specification package',authority:'Buyer and seller',status:'Review required',note:'The specification becomes binding only after both parties approve the final controlled version.'},
      {layer:'Product rule',name:'Destination product requirements',authority:'Relevant US regulator or standards body',status:'Review required',note:'The demo does not assume a mandatory product standard before classification and intended use are confirmed.'}
    ],
    scan:{purpose:'Create the initial requirement record.',allowedDocuments:['Buyer email','Specification Sheet.pdf','Quantity Schedule.xlsx','Delivery Note.pdf'],excludedDocuments:['Seller cost sheets','Employee identity records','Bank instructions','Unrelated customer files'],allowedFields:['Product','Quantity','Technical requirements','Destination','Requested date','Buyer contact'],blockedActions:['Approve technical feasibility','Commit price','Promise delivery','Declare regulatory compliance']},
    blocker:'Delivery meaning and product-use details are incomplete.',nextAction:'Buyer answers the four clarification questions.'
  },
  {
    name:'Source and capability',summary:'Two manufacturers and one distributor are compared against the controlled requirement.',
    owner:'AI PREPARES',status:'Source selected',
    ai:['Retrieves approved catalog, capacity and certificate records','Compares material, pressure, quality, capacity and lead time','Explains each fit, gap and source'],
    human:['Procurement manager selects the source','Seller engineer confirms provisional capability'],partner:[],
    evidence:[
      {label:'Selected source',value:'Meridian Industrial Systems',source:'Supplier comparison · version 2',verification:'Procurement approved',visibility:shared},
      {label:'Technical fit',value:'Pressure and material requirements provisionally supported',source:'Factory Capability Record · items 18–26',verification:'Engineer confirmation pending',visibility:shared},
      {label:'Available capacity',value:'520 units in requested window',source:'Capacity Plan · week 31',verification:'Production manager verified',visibility:sellerOps},
      {label:'Quality system',value:'ISO 9001 certificate current in sample record',source:'Certificate Register · CERT-114',verification:'Expiry checked',visibility:shared},
      {label:'Rejected source A',value:'Insufficient pressure test capability',source:'Supplier Comparison · reason code T-07',verification:'AI prepared · procurement accepted',visibility:['Buyer only','ForgeBridge operations']},
      {label:'Rejected source B',value:'Lead time exceeds 95 days',source:'Supplier response · quotation 44',verification:'Supplier supplied',visibility:['Buyer only','ForgeBridge operations']}
    ],
    rules:[
      {layer:'International model',name:'UN/CEFACT supply-chain semantics',authority:'UN/CEFACT',status:'Applies',note:'Normalizes party, product, certificate and delivery information across source records.'},
      {layer:'Product rule',name:'Buyer technical specification',authority:'Buyer and seller',status:'Applies',note:'Capabilities are compared with the buyer-approved specification; AI does not certify manufacturability.'},
      {layer:'AI governance',name:'Source provenance requirement',authority:'ForgeBridge control policy',status:'Applies',note:'A capability cannot be marked confirmed without a named source and verification state.'}
    ],
    scan:{purpose:'Compare approved source records with the buyer requirement.',allowedDocuments:['Approved supplier catalog','Factory capability record','Certificate register','Capacity plan','Historical delivery records'],excludedDocuments:['Unapproved marketing claims','Other suppliers confidential pricing','Personnel records','General internet results'],allowedFields:['Processes','Materials','Capacity','Certificates','Inspection capability','Lead time history'],blockedActions:['Certify manufacturability','Select supplier automatically','Share confidential source data','Override expired certificates']},
    blocker:'Final technical feasibility still needs the seller engineer.',nextAction:'Engineer confirms capability and clarifications are sent.'
  },
  {
    name:'Clarifications',summary:'The parties remove ambiguity before anyone commits price, production or delivery.',
    owner:'HUMAN APPROVES',status:'Requirement complete',
    ai:['Drafts questions from missing and conflicting fields','Updates the controlled requirement when answers arrive','Shows every change between versions'],
    human:['Buyer approves specification answers','Seller engineer approves technical feasibility'],partner:[],
    evidence:[
      {label:'Final delivery point',value:'Buyer facility, Houston metro area',source:'Clarification reply · answer 1',verification:'Buyer approved',visibility:shared},
      {label:'Delivery definition',value:'Delivered within 75 calendar days',source:'Clarification reply · answer 2',verification:'Buyer and seller accepted',visibility:shared},
      {label:'Inspection',value:'Independent final inspection required',source:'Clarification reply · answer 3',verification:'Buyer approved',visibility:shared},
      {label:'Warranty',value:'18 months from delivery',source:'Clarification reply · answer 4',verification:'Commercial approval required',visibility:shared},
      {label:'Specification version',value:'PUMP-SPEC-22 · Revision C',source:'Controlled requirement record',verification:'Supersedes revisions A and B',visibility:shared},
      {label:'Engineering decision',value:'Feasible with approved test fixture',source:'Engineer decision ENG-26041',verification:'Signed by sample engineer',visibility:sellerOps}
    ],
    rules:[
      {layer:'Contract rule',name:'Controlled specification and change log',authority:'Buyer and seller',status:'Applies',note:'Only the mutually approved revision is used for quotation and fulfillment.'},
      {layer:'AI governance',name:'Conflict escalation',authority:'ForgeBridge control policy',status:'Applies',note:'AI must display conflicts and cannot silently choose one value.'}
    ],
    scan:{purpose:'Update the requirement from the approved clarification thread.',allowedDocuments:['Clarification email thread','Specification revision C','Engineer decision record'],excludedDocuments:['Draft replies not sent','Internal legal advice','Unrelated transaction messages'],allowedFields:['Approved answers','Changed requirements','Decision owner','Version','Timestamp'],blockedActions:['Resolve disagreements silently','Change the buyer specification','Approve warranty terms','Send unapproved messages']},
    blocker:'Warranty and commercial consequences need pricing review.',nextAction:'Build the commercial offer using the approved requirement.'
  },
  {
    name:'Commercial offer',summary:'Product, inspection, freight, duty, insurance, payment and margin assumptions become one decision pack.',
    owner:'AI PREPARES',status:'Awaiting approvals',
    ai:['Retrieves approved cost inputs','Assembles the landed-cost decision pack','Flags margin, currency and delivery risks','Drafts the quotation and buyer message'],
    human:['Seller approves cost, margin, capacity, delivery and payment terms'],
    partner:['Freight partner supplies rate','Insurance partner supplies coverage estimate'],
    evidence:[
      {label:'Quoted value',value:'USD 248,000',source:'Quote Calculator · version 3',verification:'Finance approval pending',visibility:shared},
      {label:'Unit price',value:'USD 620 per assembly',source:'Quote Calculator · derived value',verification:'Deterministic calculation',visibility:shared},
      {label:'Incoterm',value:'CIF Port of Houston · Incoterms 2020',source:'Draft Quote · term 7',verification:'Named port present · buyer approval pending',visibility:shared},
      {label:'Freight assumption',value:'Ocean freight · USD 18,400',source:'Forwarder rate FR-8891',verification:'Valid through 15 August',visibility:['Seller only','ForgeBridge operations','Freight partner']},
      {label:'Factory margin',value:'16.2%',source:'Internal Cost Worksheet · margin model',verification:'Finance review required',visibility:sellerOps},
      {label:'Payment proposal',value:'30% deposit · 70% before shipment release',source:'Draft Quote · term 9',verification:'Owner approval required',visibility:shared}
    ],
    rules:[
      {layer:'Contract rule',name:'Incoterms 2020 · CIF named port',authority:'International Chamber of Commerce',status:'Candidate',note:'The selected rule and named port must be written into the contract; it does not replace the full sales agreement.'},
      {layer:'International model',name:'UN/CEFACT Buy-Ship-Pay data concepts',authority:'UN/CEFACT',status:'Applies',note:'Connects trade agreement, delivery and settlement data.'},
      {layer:'Country system',name:'India and US duty/classification review',authority:'Customs authorities and authorized brokers',status:'Review required',note:'Displayed duty and classification values remain candidates until authorized review.'}
    ],
    scan:{purpose:'Prepare the commercial decision pack.',allowedDocuments:['Approved requirement','Approved seller cost inputs','Current freight rate','Insurance estimate','Approved commercial rules'],excludedDocuments:['Other customer prices','Unapproved supplier quotes','Employee payroll','Bank credentials'],allowedFields:['Costs','Margin thresholds','Freight','Insurance','Currency','Payment terms','Quote validity'],blockedActions:['Set final price','Lower margin below threshold','Commit delivery','Choose customs classification','Send the quotation']},
    blocker:'Finance and owner approvals are incomplete.',nextAction:'Named approvers review the price, terms and delivery commitment.'
  },
  {
    name:'Agreement',summary:'The accepted offer becomes the controlled transaction baseline for every participant.',
    owner:'HUMAN APPROVES',status:'Order accepted',
    ai:['Compares the purchase order with the approved quote','Flags changed quantity, warranty and delivery language','Creates the obligation and due-date checklist'],
    human:['Buyer and seller approve scope, price, terms and responsibilities'],partner:['Bank confirms deposit receipt'],
    evidence:[
      {label:'Purchase order',value:'PO-NA-7784 · 400 units',source:'Purchase Order · header and line 1',verification:'Matches approved quote',visibility:shared},
      {label:'Contract baseline',value:'Sales Contract SC-26041 · version 2',source:'Signed contract',verification:'Buyer and seller signatures present',visibility:shared},
      {label:'Deposit received',value:'USD 74,400',source:'Bank confirmation BC-26041',verification:'Finance confirmed',visibility:['Seller only','ForgeBridge operations','Bank or payment provider']},
      {label:'Final Incoterm',value:'CIF Port of Houston · Incoterms 2020',source:'Sales Contract · clause 8',verification:'Both parties approved',visibility:shared},
      {label:'Required delivery',value:'18 October 2026',source:'Sales Contract · schedule A',verification:'Controlled date',visibility:shared},
      {label:'Open obligation',value:'Buyer to nominate receiving facility contact',source:'Obligation checklist · item B-04',verification:'Due in 5 days',visibility:shared}
    ],
    rules:[
      {layer:'Contract rule',name:'Sales contract and incorporated Incoterms rule',authority:'Buyer and seller / ICC rule incorporated by contract',status:'Applies',note:'The contract controls the parties obligations; the Incoterms rule allocates defined delivery tasks, costs and risks.'},
      {layer:'AI governance',name:'Version and signature check',authority:'ForgeBridge control policy',status:'Applies',note:'AI can compare versions and locate signatures but cannot determine legal enforceability.'}
    ],
    scan:{purpose:'Compare the purchase order and contract with the approved offer.',allowedDocuments:['Approved quotation','Purchase order','Sales contract','Deposit confirmation'],excludedDocuments:['Privileged legal notes','Bank login information','Other contracts'],allowedFields:['Quantity','Price','Dates','Incoterm','Payment terms','Warranty','Signatures','Obligations'],blockedActions:['Provide legal opinion','Accept changed terms','Sign the contract','Release funds']},
    blocker:'No commercial blocker; fulfillment can begin.',nextAction:'Production and quality teams execute the controlled baseline.'
  },
  {
    name:'Fulfillment',summary:'Production and quality evidence are tracked against the approved agreement.',
    owner:'HUMAN APPROVES',status:'Inspection passed',
    ai:['Collects milestone updates','Checks missing or late evidence','Summarizes exceptions for buyer and seller'],
    human:['Manufacturer confirms production milestones','Quality manager approves inspection plan and results'],partner:['Independent inspector performs final inspection'],
    evidence:[
      {label:'Production status',value:'400 units complete',source:'Production Log · milestone 6',verification:'Production manager confirmed',visibility:shared},
      {label:'Material certificate',value:'Certificate MTC-4402 present',source:'Quality Record · attachment 2',verification:'Quality manager verified',visibility:shared},
      {label:'Inspection basis',value:'Contract-approved final inspection plan',source:'Sales Contract schedule Q / Inspection Plan IP-22',verification:'Buyer and quality manager approved',visibility:shared},
      {label:'Sample examined',value:'50 units',source:'Inspection Report IR-26041 · section 3',verification:'Independent inspector recorded',visibility:shared},
      {label:'Inspection result',value:'Passed with 2 accepted minor observations',source:'Inspection Report IR-26041 · conclusion',verification:'Quality manager accepted',visibility:shared},
      {label:'Internal rework cost',value:'USD 1,280',source:'Internal Nonconformance NC-44',verification:'Finance recorded',visibility:sellerOps}
    ],
    rules:[
      {layer:'Product rule',name:'Contract-approved inspection plan',authority:'Buyer, seller and qualified inspector',status:'Applies',note:'The demo does not impose a universal sampling standard; the approved contract determines the inspection basis.'},
      {layer:'AI governance',name:'No autonomous quality acceptance',authority:'ForgeBridge control policy',status:'Applies',note:'AI summarizes evidence; the authorized quality manager accepts or rejects the result.'}
    ],
    scan:{purpose:'Create the fulfillment and inspection summary.',allowedDocuments:['Production log','Material certificate','Inspection plan','Inspection report','Approved nonconformance record'],excludedDocuments:['Employee performance files','Unrelated quality cases','Proprietary process parameters not approved for sharing'],allowedFields:['Milestones','Quantity complete','Certificate status','Sample size','Defects','Inspection result','Approved exceptions'],blockedActions:['Perform inspection','Change sampling basis','Accept defects','Approve shipment release']},
    blocker:'Document and payment release conditions still need confirmation.',nextAction:'Prepare the shipment-release evidence pack.'
  },
  {
    name:'Documents and release',summary:'The goods cannot move until documents, inspection, customs data and payment conditions are reconciled.',
    owner:'HUMAN APPROVES',status:'Released',
    ai:['Checks document completeness and cross-document consistency','Shows every blocked release condition','Prepares the customs, freight and payment handoff pack'],
    human:['Authorized seller manager approves shipment release'],
    partner:['Customs broker validates filing data','Payment provider confirms the balance condition'],
    evidence:[
      {label:'Commercial invoice',value:'CI-26041 · USD 248,000 · 400 units',source:'Commercial Invoice v3 · fields 1, 8 and 12',verification:'Seller approved',visibility:shared},
      {label:'Packing list',value:'20 pallets · gross 8,420 kg',source:'Packing List v2 · totals',verification:'Warehouse verified',visibility:shared},
      {label:'Country of origin',value:'India',source:'Certificate of Origin COO-26041',verification:'Present · broker review pending',visibility:shared},
      {label:'HS classification',value:'Candidate recorded · final broker confirmation required',source:'Classification Worksheet CW-44',verification:'Not a final customs determination',visibility:customs},
      {label:'Inspection release',value:'Passed · authorized quality acceptance recorded',source:'Inspection Report IR-26041 and approval QA-11',verification:'Complete',visibility:shared},
      {label:'Payment release condition',value:'Remaining 70% confirmed before shipment release',source:'Sales Contract clause 9 / payment confirmation',verification:'Finance and provider confirmed',visibility:['Seller only','ForgeBridge operations','Bank or payment provider']}
    ],
    rules:[
      {layer:'International model',name:'WCO Data Model',authority:'World Customs Organization',status:'Applies',note:'Provides harmonized customs and cross-border regulatory data concepts for declarations, goods, parties and supporting documents.'},
      {layer:'Country system',name:'ICEGATE / I4C trade data review',authority:'Indian Customs',status:'Applies',note:'Supports tariff, policy, duty and Partner Government Agency review for the export-side data package.'},
      {layer:'Country system',name:'ACE import data package',authority:'US Customs and Border Protection',status:'Review required',note:'The importer or authorized broker remains responsible for the US filing and admissibility data.'},
      {layer:'Contract rule',name:'Shipment release conditions',authority:'Buyer and seller',status:'Applies',note:'Inspection, payment and approved document conditions must all be satisfied before release.'}
    ],
    scan:{purpose:'Prepare the shipment-release summary and partner handoff.',allowedDocuments:['Commercial invoice','Packing list','Certificate of origin','Inspection report','Insurance certificate','Payment confirmation','Classification worksheet'],excludedDocuments:['Factory cost sheet','Employee identity records','Bank account credentials','Internal legal advice','Other customer transactions'],allowedFields:['Quantity','Value','Packages','Weight','Origin','Classification candidate','Inspection result','Document numbers','Release conditions'],blockedActions:['Make final HS determination','File customs declaration','Approve regulatory compliance','Release shipment','Release funds']},
    blocker:'All sample release conditions are complete after named approvals.',nextAction:'Freight and customs partners execute movement and clearance.'
  },
  {
    name:'Transport and customs',summary:'Specialists move and clear the goods while ForgeBridge keeps milestones and exceptions connected.',
    owner:'PARTNER EXECUTES',status:'Delivered',
    ai:['Ingests approved partner milestones','Compares actual dates with the contract','Alerts parties when customs or delivery risk changes'],
    human:['Buyer and seller respond to exceptions'],
    partner:['Forwarder transports cargo','Customs brokers complete export and import clearance','Carrier confirms final delivery'],
    evidence:[
      {label:'Bill of lading',value:'BOL-88210 · 20 pallets',source:'Carrier record · issued document',verification:'Carrier issued',visibility:shared},
      {label:'Export clearance',value:'Cleared',source:'India customs status · broker update',verification:'Broker confirmed',visibility:shared},
      {label:'Import status',value:'Released for delivery',source:'US broker / ACE status update',verification:'Broker confirmed',visibility:shared},
      {label:'Actual port arrival',value:'14 October 2026',source:'Carrier milestone',verification:'Carrier supplied',visibility:shared},
      {label:'Final delivery',value:'17 October 2026 · buyer facility',source:'Proof of Delivery POD-26041',verification:'Buyer receiver signed',visibility:shared},
      {label:'Internal fraud indicator',value:'No alert',source:'ForgeBridge risk monitor',verification:'Internal operational signal',visibility:['ForgeBridge operations']}
    ],
    rules:[
      {layer:'International model',name:'WTO Trade Facilitation Agreement principles',authority:'World Trade Organization',status:'Applies',note:'Supports concepts such as pre-arrival processing and electronic customs procedures; national law and systems control the actual filing.'},
      {layer:'Country system',name:'India export and US import customs procedures',authority:'Indian Customs / US CBP',status:'Applies',note:'Authorized brokers and responsible traders perform filings and respond to government requirements.'},
      {layer:'Contract rule',name:'CIF delivery and carriage obligations',authority:'Sales contract incorporating Incoterms 2020',status:'Applies',note:'The contract and named port determine the parties agreed responsibilities.'}
    ],
    scan:{purpose:'Monitor approved transport and customs status.',allowedDocuments:['Carrier milestones','Bill of lading metadata','Broker status updates','Proof of delivery'],excludedDocuments:['Customs broker credentials','Government portal passwords','Unrelated cargo records','Law-enforcement restricted data'],allowedFields:['Document number','Packages','Dates','Status','Location','Exception code','Proof of delivery'],blockedActions:['Move cargo','File declarations','Clear goods','Override government hold','Reveal restricted cargo intelligence']},
    blocker:'No open blocker after delivery.',nextAction:'Reconcile acceptance, payment and transaction closeout.'
  },
  {
    name:'Settlement and close',summary:'Delivery, acceptance, fees and seller payment are reconciled into the final transaction record.',
    owner:'HUMAN APPROVES',status:'Transaction successful',
    ai:['Checks payment conditions against approved evidence','Creates the closeout statement','Records reusable outcomes and exceptions'],
    human:['Buyer confirms acceptance','Seller confirms funds received','Finance closes the transaction'],partner:['Bank or payment provider moves funds'],
    evidence:[
      {label:'Delivery accepted',value:'400 units accepted',source:'Buyer Acceptance AC-26041',verification:'Buyer approved',visibility:shared},
      {label:'Final buyer payment',value:'USD 173,600',source:'Payment Confirmation PC-26041',verification:'Finance confirmed',visibility:['Seller only','ForgeBridge operations','Bank or payment provider']},
      {label:'Total transaction value',value:'USD 248,000',source:'Contract and final statement',verification:'Reconciled',visibility:shared},
      {label:'Seller receipt',value:'Funds received · sample record',source:'Seller finance confirmation',verification:'Seller confirmed',visibility:['Seller only','ForgeBridge operations']},
      {label:'Claims',value:'None open',source:'Closeout checklist',verification:'Buyer and seller confirmed',visibility:shared},
      {label:'Learning record',value:'Delivery completed one day early; two minor inspection observations accepted',source:'Transaction outcome summary',verification:'ForgeBridge operations reviewed',visibility:['ForgeBridge operations','Seller only']}
    ],
    rules:[
      {layer:'Contract rule',name:'Payment and acceptance conditions',authority:'Buyer and seller',status:'Applies',note:'Funds are reconciled only against the conditions written into the approved contract.'},
      {layer:'International model',name:'UN/CEFACT trade settlement concepts',authority:'UN/CEFACT',status:'Applies',note:'Connects invoice, payment terms, payment reference and transaction closeout data.'},
      {layer:'AI governance',name:'Human-controlled financial release',authority:'ForgeBridge control policy',status:'Applies',note:'AI may reconcile evidence but cannot move or release funds.'}
    ],
    scan:{purpose:'Prepare the final settlement and closeout summary.',allowedDocuments:['Proof of delivery','Buyer acceptance','Payment confirmation','Final transaction statement','Approved claims record'],excludedDocuments:['Bank login credentials','Unrelated account statements','Internal legal advice','Other customer payment records'],allowedFields:['Accepted quantity','Payment amount','Payment reference','Fees','Claims status','Closeout date'],blockedActions:['Move funds','Release escrow','Approve write-off','Declare legal completion without authorized confirmation']},
    blocker:'No open blocker.',nextAction:'Archive the controlled record and use approved learning for future transactions.'
  }
];

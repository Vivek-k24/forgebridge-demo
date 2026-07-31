import {Navigate,Route,Routes} from 'react-router-dom';
import {PublicLayout} from '../components/layout/Shells';
import {AI,Contact,Home,Network,Problem,Product} from '../pages/v3/V3Marketing';
import {UnifiedDemo} from '../pages/v3/V3Demo';

const NotFound=()=> <main className="v3page"><span className="v3eyebrow">404 · ROUTE NOT FOUND</span><h1>This transaction route does not exist.</h1><p className="lead">Return to the public website or open the guided transaction.</p><a className="btn" href="#/">Return home</a></main>;

export default function App(){return <Routes>
  <Route element={<PublicLayout/>}>
    <Route path="/" element={<Home/>}/>
    <Route path="/problem" element={<Problem/>}/>
    <Route path="/product" element={<Product/>}/>
    <Route path="/ai" element={<AI/>}/>
    <Route path="/network" element={<Network/>}/>
    <Route path="/contact" element={<Contact/>}/>
  </Route>
  <Route path="/demo" element={<UnifiedDemo/>}/>
  <Route path="/how-it-works" element={<Navigate to="/product" replace/>}/>
  <Route path="/manufacturers" element={<Navigate to="/product" replace/>}/>
  <Route path="/buyers" element={<Navigate to="/network" replace/>}/>
  <Route path="/what-we-manage" element={<Navigate to="/product" replace/>}/>
  <Route path="/industries" element={<Navigate to="/network" replace/>}/>
  <Route path="/about" element={<Navigate to="/problem" replace/>}/>
  <Route path="/demo/factory" element={<Navigate to="/demo" replace/>}/>
  <Route path="/demo/buyer" element={<Navigate to="/demo" replace/>}/>
  <Route path="/demo/manufacturer" element={<Navigate to="/demo" replace/>}/>
  <Route path="/start-exporting" element={<Navigate to="/demo" replace/>}/>
  <Route path="/submit-rfq" element={<Navigate to="/demo" replace/>}/>
  <Route path="/manufacturer/*" element={<Navigate to="/demo" replace/>}/>
  <Route path="/buyer/*" element={<Navigate to="/demo" replace/>}/>
  <Route path="*" element={<NotFound/>}/>
</Routes>}

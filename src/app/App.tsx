import {Navigate,Route,Routes} from 'react-router-dom';
import {PublicLayout} from '../components/layout/Shells';
import {AI,Contact,Home,Participants,Problem,Product,Rules} from '../pages/v4/V4Marketing';
import {V4Demo} from '../pages/v4/V4Demo';

const NotFound=()=> <main className="v4page"><span className="v4eyebrow">404 · ROUTE NOT FOUND</span><h1>This transaction route does not exist.</h1><p className="lead">Return to the public website or open the guided transaction.</p><a className="btn" href="#/">Return home</a></main>;

export default function App(){return <Routes>
  <Route element={<PublicLayout/>}>
    <Route path="/" element={<Home/>}/>
    <Route path="/problem" element={<Problem/>}/>
    <Route path="/product" element={<Product/>}/>
    <Route path="/rules" element={<Rules/>}/>
    <Route path="/ai" element={<AI/>}/>
    <Route path="/network" element={<Participants/>}/>
    <Route path="/contact" element={<Contact/>}/>
  </Route>
  <Route path="/demo" element={<V4Demo/>}/>
  <Route path="/how-it-works" element={<Navigate to="/product" replace/>}/>
  <Route path="/manufacturers" element={<Navigate to="/product" replace/>}/>
  <Route path="/buyers" element={<Navigate to="/network" replace/>}/>
  <Route path="/what-we-manage" element={<Navigate to="/product" replace/>}/>
  <Route path="/industries" element={<Navigate to="/network" replace/>}/>
  <Route path="/about" element={<Navigate to="/problem" replace/>}/>
  <Route path="/standards" element={<Navigate to="/rules" replace/>}/>
  <Route path="/demo/factory" element={<Navigate to="/demo" replace/>}/>
  <Route path="/demo/buyer" element={<Navigate to="/demo" replace/>}/>
  <Route path="/demo/manufacturer" element={<Navigate to="/demo" replace/>}/>
  <Route path="/start-exporting" element={<Navigate to="/demo" replace/>}/>
  <Route path="/submit-rfq" element={<Navigate to="/demo" replace/>}/>
  <Route path="/manufacturer/*" element={<Navigate to="/demo" replace/>}/>
  <Route path="/buyer/*" element={<Navigate to="/demo" replace/>}/>
  <Route path="*" element={<NotFound/>}/>
</Routes>}

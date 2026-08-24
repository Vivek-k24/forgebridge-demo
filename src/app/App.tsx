import {Route,Routes} from 'react-router-dom';
import {PartGraphSixthGen} from '../pages/partgraph/PartGraphSixthGen';
import {PartGraphStep2} from '../pages/partgraph/PartGraphStep2';

export default function App(){
  return (
    <Routes>
      <Route path="/8th-gen" element={<PartGraphStep2/>}/>
      <Route path="*" element={<PartGraphSixthGen/>}/>
    </Routes>
  );
}

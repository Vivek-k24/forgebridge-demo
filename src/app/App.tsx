import {Route,Routes} from 'react-router-dom';
import {PartGraphPrototype} from '../pages/partgraph/PartGraphPrototype';

export default function App(){
  return <Routes><Route path="*" element={<PartGraphPrototype/>}/></Routes>;
}

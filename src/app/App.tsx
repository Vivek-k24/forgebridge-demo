import {Route,Routes} from 'react-router-dom';
import {PartGraphStep2} from '../pages/partgraph/PartGraphStep2';

export default function App(){
  return <Routes><Route path="*" element={<PartGraphStep2/>}/></Routes>;
}

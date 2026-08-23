import {Route,Routes} from 'react-router-dom';
import {PartGraphUser} from '../pages/partgraph/PartGraphUser';

export default function App(){
  return <Routes><Route path="*" element={<PartGraphUser/>}/></Routes>;
}

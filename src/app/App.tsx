import {Route,Routes} from 'react-router-dom';
import {ChangeGraphPrototype} from '../pages/changegraph/ChangeGraphPrototype';

export default function App(){
  return <Routes><Route path="*" element={<ChangeGraphPrototype/>}/></Routes>;
}

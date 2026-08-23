import React from 'react';
import ReactDOM from 'react-dom/client';
import {HashRouter} from 'react-router-dom';
import App from './app/App';
import './styles/partgraph.css';
import './styles/partgraph-vehicle.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HashRouter><App/></HashRouter>
  </React.StrictMode>
);

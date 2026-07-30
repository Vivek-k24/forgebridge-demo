import React from 'react';
import ReactDOM from 'react-dom/client';
import {HashRouter} from 'react-router-dom';
import App from './app/App';
import {AppProvider} from './state/AppState';
import './styles/index.css';
import './styles/v3.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HashRouter>
      <AppProvider><App/></AppProvider>
    </HashRouter>
  </React.StrictMode>
);

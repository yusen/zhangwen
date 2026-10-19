import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './style.css';
import './workbench.css';
import './final-design.css';
import { migrateBrowserNames } from './legacyBrowserNames';
migrateBrowserNames();
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);

import React from 'react';
import { createRoot } from 'react-dom/client';
import Root from './App';
import './styles.css';
import './pages.css';
import './theme.css';
import './landing-motion.css';
createRoot(document.getElementById('root')).render(<React.StrictMode><Root/></React.StrictMode>);

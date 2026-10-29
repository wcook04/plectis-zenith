import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles/tokens.css';
import './styles/site.css';
import './styles/graph.css';
// Shared with Will Cook's other websites; loaded last so its component rules
// win ties with the site's element defaults (a, a:hover, figcaption).
import './styles/family.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

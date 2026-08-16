import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { PreviewApp } from './app/PreviewApp';
import './design/global.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <PreviewApp />
  </StrictMode>,
);

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, useParams } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import SharedReportPage from './SharedReportPage.jsx'

function SharedReportRoute() {
  const { token } = useParams();
  return <SharedReportPage token={token} />;
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/shared/:token" element={<SharedReportRoute />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)

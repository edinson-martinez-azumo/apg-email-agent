import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { InboxPage } from './routes/inbox'
import { DraftPage } from './routes/draft'
import { DashboardPage } from './routes/dashboard'
import { DemoPage } from './routes/demo'

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/inbox" replace />} />
        <Route path="/inbox" element={<InboxPage />} />
        <Route path="/draft/:id" element={<DraftPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/demo" element={<DemoPage />} />
      </Routes>
    </BrowserRouter>
  )
}

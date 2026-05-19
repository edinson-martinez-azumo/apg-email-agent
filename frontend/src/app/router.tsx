import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { AppLayout } from '@/components/AppLayout'
import { InboxPage } from './routes/inbox'
import { DraftPage } from './routes/draft'
import { DashboardPage } from './routes/dashboard'
import { DemoPage } from './routes/demo'
import { SettingsPage } from './routes/settings'

function Layout() {
  return (
    <AppLayout>
      <Outlet />
    </AppLayout>
  )
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/inbox" replace />} />
        <Route path="/" element={<Layout />}>
          <Route path="inbox" element={<InboxPage />} />
          <Route path="draft/:id" element={<DraftPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="demo" element={<DemoPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

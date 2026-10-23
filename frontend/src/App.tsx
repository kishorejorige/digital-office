import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import OverviewPage from './features/overview/OverviewPage'
import ResearchPage from './features/research/ResearchPage'
import LeadsPage from './features/leads/LeadsPage'
import ProposalsPage from './features/proposals/ProposalsPage'
import SettingsPage from './features/settings/SettingsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/research" element={<ResearchPage />} />
        <Route path="/leads" element={<LeadsPage />} />
        <Route path="/proposals" element={<ProposalsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}

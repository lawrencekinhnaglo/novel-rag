import { Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ChatPage } from './pages/ChatPage'
import { ChaptersPage } from './pages/ChaptersPage'
import { KnowledgePage } from './pages/KnowledgePage'
import { GraphPage } from './pages/GraphPage'
import { SettingsPage } from './pages/SettingsPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<ChatPage />} />
        <Route path="chapters" element={<ChaptersPage />} />
        <Route path="knowledge" element={<KnowledgePage />} />
        <Route path="graph" element={<GraphPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}

export default App


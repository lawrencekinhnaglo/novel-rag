import { Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ChatPage } from './pages/ChatPage'
import { ChaptersPage } from './pages/ChaptersPage'
import { KnowledgePage } from './pages/KnowledgePage'
import { GraphPage } from './pages/GraphPage'
import { UploadPage } from './pages/UploadPage'
import { SettingsPage } from './pages/SettingsPage'
import { StoryPage } from './pages/StoryPage'
import { StoryWorkspacePage } from './pages/StoryWorkspacePage'
import { VerificationPage } from './pages/VerificationPage'
import { PlotLabPage } from './pages/PlotLabPage'
import { TimelinePage } from './pages/TimelinePage'
import { ResearchPage } from './pages/ResearchPage'
import { BranchesPage } from './pages/BranchesPage'
import { ExportPage } from './pages/ExportPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<ChatPage />} />
        <Route path="workspace" element={<StoryWorkspacePage />} />
        <Route path="story" element={<StoryPage />} />
        <Route path="verification" element={<VerificationPage />} />
        <Route path="chapters" element={<ChaptersPage />} />
        <Route path="knowledge" element={<KnowledgePage />} />
        <Route path="graph" element={<GraphPage />} />
        <Route path="upload" element={<UploadPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="plot-lab" element={<PlotLabPage />} />
        <Route path="timeline" element={<TimelinePage />} />
        <Route path="research" element={<ResearchPage />} />
        <Route path="branches" element={<BranchesPage />} />
        <Route path="export" element={<ExportPage />} />
      </Route>
    </Routes>
  )
}

export default App


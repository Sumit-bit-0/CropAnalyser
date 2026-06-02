import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { WorkspaceProvider } from './workspace/WorkspaceContext'
import Workspace from './workspace/Workspace'

// Old routes deep-link into the workspace with the right intent + sub-tab.
const DEEP_LINKS = {
  '/advisor': ['grow', 'advisor'], '/recommend': ['grow', 'soil'],
  '/mandi': ['sell', 'mandi'], '/profit': ['sell', 'profit'],
  '/map': ['explore', 'map'], '/crops': ['explore', 'crops'],
  '/revenue': ['explore', 'revenue'], '/trends': ['explore', 'trends'],
  '/forecast': ['explore', 'forecast'],
}

export default function App() {
  return (
    <BrowserRouter>
      <WorkspaceProvider>
        <Routes>
          <Route path="/" element={<Workspace />} />
          {Object.entries(DEEP_LINKS).map(([path, [i, t]]) => (
            <Route key={path} path={path} element={<Workspace initialIntent={i} initialTool={t} />} />
          ))}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </WorkspaceProvider>
    </BrowserRouter>
  )
}

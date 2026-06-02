import { createContext, useContext, useState } from 'react'

const WorkspaceContext = createContext(null)

const DEFAULT = {
  state: 'Punjab', district: 'Ludhiana', area: '', pincode: '',
  lat: null, lon: null, season: 'Any', crop: '', mode: 'simple', soil: null,
}

export function WorkspaceProvider({ children }) {
  const [ctx, setCtx] = useState(DEFAULT)
  const value = {
    ...ctx,
    setLocation: (partial) => setCtx((c) => ({ ...c, ...partial })),
    setSeason: (season) => setCtx((c) => ({ ...c, season })),
    setCrop: (crop) => setCtx((c) => ({ ...c, crop })),
    // leaving Smart clears soil so the Advisor reverts to Simple cleanly
    setMode: (mode) => setCtx((c) => ({ ...c, mode, soil: mode === 'simple' ? null : c.soil })),
    setSoil: (soil) => setCtx((c) => ({ ...c, soil })),
  }
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function useWorkspace() {
  const v = useContext(WorkspaceContext)
  if (!v) throw new Error('useWorkspace must be used within WorkspaceProvider')
  return v
}

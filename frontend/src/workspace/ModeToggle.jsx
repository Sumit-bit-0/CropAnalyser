import { useWorkspace } from './WorkspaceContext'

export default function ModeToggle() {
  const { mode, setMode } = useWorkspace()
  const smart = mode === 'smart'
  return (
    <label className="flex items-center gap-2 text-sm select-none">
      <span className={smart ? 'opacity-70' : 'font-semibold'}>Simple</span>
      <button type="button" role="switch" aria-checked={smart} aria-label="Toggle Smart mode"
        onClick={() => setMode(smart ? 'simple' : 'smart')}
        className={`relative w-10 h-5 rounded-full transition ${smart ? 'bg-green-300' : 'bg-green-900'}`}>
        <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full transition-all ${smart ? 'left-5' : 'left-0.5'}`} />
      </button>
      <span className={smart ? 'font-semibold' : 'opacity-70'}>Smart</span>
    </label>
  )
}

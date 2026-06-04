import { useWorkspace } from './WorkspaceContext'

export default function ModeToggle() {
  const { mode, setMode } = useWorkspace()
  const smart = mode === 'smart'
  return (
    <label className="flex items-center gap-2 text-sm select-none">
      <span className={smart ? 'text-muted-foreground' : 'font-semibold text-foreground'}>Simple</span>
      <button type="button" role="switch" aria-checked={smart} aria-label="Toggle Smart mode"
        onClick={() => setMode(smart ? 'simple' : 'smart')}
        className={`relative w-10 h-5 rounded-full transition-colors ${smart ? 'bg-primary' : 'bg-input'}`}>
        <span className={`absolute top-0.5 w-4 h-4 bg-card rounded-full shadow-sm transition-all ${smart ? 'left-5' : 'left-0.5'}`} />
      </button>
      <span className={smart ? 'font-semibold text-foreground' : 'text-muted-foreground'}>Smart</span>
    </label>
  )
}

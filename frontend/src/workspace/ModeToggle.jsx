import { motion, useReducedMotion } from 'framer-motion'
import { Sparkles, SlidersHorizontal } from 'lucide-react'
import { useWorkspace } from './WorkspaceContext'

const MODES = [
  { id: 'simple', label: 'Simple', Icon: SlidersHorizontal },
  { id: 'smart', label: 'Smart', Icon: Sparkles },
]

export default function ModeToggle() {
  const { mode, setMode } = useWorkspace()
  const reduce = useReducedMotion()

  return (
    <div role="radiogroup" aria-label="Analysis mode"
      className="relative inline-flex items-center rounded-full border border-border bg-card p-0.5 text-sm">
      {MODES.map(({ id, label, Icon }) => {
        const active = mode === id
        return (
          <button key={id} type="button" role="radio" aria-checked={active}
            aria-label={`${label} mode`} onClick={() => setMode(id)}
            className="relative z-10 flex items-center gap-1.5 rounded-full px-3 py-1.5 font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            {active && (
              <motion.span layoutId="mode-pill"
                className="absolute inset-0 -z-10 rounded-full bg-primary shadow-sm"
                transition={reduce ? { duration: 0 } : { type: 'spring', stiffness: 420, damping: 34 }} />
            )}
            <Icon className={`h-3.5 w-3.5 ${active ? 'text-primary-foreground' : 'text-muted-foreground'}`} />
            <span className={active ? 'text-primary-foreground' : 'text-muted-foreground'}>{label}</span>
          </button>
        )
      })}
    </div>
  )
}

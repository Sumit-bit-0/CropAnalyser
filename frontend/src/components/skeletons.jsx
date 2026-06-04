// Loading skeletons matching the editorial table/card surfaces.

export function TableSkeleton({ rows = 4, cols = 4 }) {
  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      <div className="bg-secondary border-b border-border px-4 py-3 flex items-center gap-4">
        <div className="w-6 h-4 bg-border rounded animate-pulse" />
        <div className="flex-1 h-4 bg-border rounded animate-pulse" />
        {Array.from({ length: cols }).map((_, i) => (
          <div key={i} className="w-24 h-4 bg-border rounded animate-pulse" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="px-4 py-4 flex items-center gap-4 border-b border-border last:border-b-0">
          <div className="w-6 h-4 bg-muted rounded animate-pulse" />
          <div className="flex-1">
            <div className="h-4 bg-muted rounded animate-pulse w-3/4" />
          </div>
          {Array.from({ length: cols }).map((_, j) => (
            <div key={j} className="w-24 h-4 bg-muted rounded animate-pulse" />
          ))}
        </div>
      ))}
    </div>
  )
}

export function CardSkeleton() {
  return (
    <div className="bg-card rounded-lg border border-border p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="h-10 w-10 bg-muted rounded-lg animate-pulse" />
        <div className="h-5 bg-muted rounded animate-pulse w-32" />
      </div>
      <div className="space-y-2">
        <div className="h-4 bg-muted rounded animate-pulse w-full" />
        <div className="h-4 bg-muted rounded animate-pulse w-5/6" />
        <div className="h-4 bg-muted rounded animate-pulse w-4/6" />
      </div>
    </div>
  )
}

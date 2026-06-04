export default function PageHeader({ title, subtitle }) {
  return (
    <div className="mb-6">
      <h1 className="font-display text-2xl font-semibold text-foreground tracking-[-0.02em]">{title}</h1>
      {subtitle && <p className="mt-2 text-muted-foreground leading-relaxed">{subtitle}</p>}
    </div>
  )
}

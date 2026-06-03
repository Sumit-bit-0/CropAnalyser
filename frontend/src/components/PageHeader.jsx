export default function PageHeader({ title, subtitle }) {
  return (
    <div className="mb-4">
      <h1 className="text-2xl font-bold text-foreground mb-1">{title}</h1>
      {subtitle && <p className="text-muted-foreground">{subtitle}</p>}
    </div>
  )
}

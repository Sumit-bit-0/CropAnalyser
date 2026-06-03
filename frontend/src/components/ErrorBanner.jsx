export default function ErrorBanner({ message }) {
  return (
    <div className="bg-destructive/10 text-destructive border border-destructive/30 p-4 rounded-md m-4">
      {message}
    </div>
  )
}

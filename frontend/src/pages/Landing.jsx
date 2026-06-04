import { Link } from "react-router-dom"
import { Sprout, Store, BarChart3, ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"

export default function Landing() {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border">
        <div className="mx-auto max-w-[1100px] px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sprout className="h-6 w-6 text-primary" />
            <span className="font-display font-semibold text-lg text-foreground">
              Crop Analyser
            </span>
          </div>
          <nav className="hidden md:flex items-center gap-8">
            <a href="#features" className="text-muted-foreground hover:text-foreground transition-colors text-sm">
              Features
            </a>
            <a href="#about" className="text-muted-foreground hover:text-foreground transition-colors text-sm">
              About
            </a>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <main>
        <section className="py-20 md:py-32">
          <div className="mx-auto max-w-[1100px] px-6">
            <div className="max-w-2xl">
              <h1 className="font-display text-4xl md:text-5xl lg:text-[3.5rem] font-semibold text-foreground leading-[1.1] tracking-[-0.02em] text-balance">
                Know what to grow. Know where to sell.
              </h1>
              <p className="mt-6 text-lg text-muted-foreground leading-relaxed max-w-xl">
                A decision tool for Indian farmers. Compare crops by expected yield and price,
                find the best mandi for your harvest, and make choices grounded in real data.
              </p>
              <div className="mt-10">
                <Button asChild size="lg" className="px-8 h-12 text-base">
                  <Link to="/workspace">
                    Open the analyser
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
              </div>
            </div>
          </div>
        </section>

        {/* Features */}
        <section id="features" className="py-20 bg-secondary">
          <div className="mx-auto max-w-[1100px] px-6">
            <h2 className="font-display text-2xl md:text-3xl font-semibold text-foreground tracking-[-0.02em] text-balance">
              Three ways to use the analyser
            </h2>
            <div className="mt-12 grid gap-8 md:grid-cols-3">
              {[
                {
                  to: '/advisor', icon: Sprout, iconBg: 'bg-primary text-primary-foreground', title: 'Grow',
                  body: 'Discover which crops suit your region this season. See expected yields, price forecasts, and whether a crop has traditional roots in your area.',
                },
                {
                  to: '/mandi', icon: Store, iconBg: 'bg-accent text-accent-foreground', title: 'Sell',
                  body: 'Compare mandis by distance and net price after transport. Find where your harvest fetches the best return, or confirm that local is the smart choice.',
                },
                {
                  to: '/map', icon: BarChart3, iconBg: 'bg-muted text-foreground', title: 'Explore',
                  body: 'Dive into historical price trends, seasonal patterns, and regional data. Build your own understanding of the agricultural landscape.',
                },
              ].map(({ to, icon: Icon, iconBg, title, body }) => (
                <Link key={to} to={to}
                  className="group flex flex-col rounded-lg -m-3 p-3 transition-colors hover:bg-card hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  <div className="flex items-center gap-3 mb-4">
                    <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${iconBg}`}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <h3 className="font-display text-xl font-semibold text-foreground transition-colors group-hover:text-primary">{title}</h3>
                    <ArrowRight className="h-4 w-4 text-primary ml-auto opacity-0 -translate-x-1 transition-all group-hover:opacity-100 group-hover:translate-x-0" />
                  </div>
                  <p className="text-muted-foreground leading-relaxed">{body}</p>
                </Link>
              ))}
            </div>
          </div>
        </section>

        {/* About */}
        <section id="about" className="py-20">
          <div className="mx-auto max-w-[1100px] px-6">
            <div className="max-w-2xl">
              <h2 className="font-display text-2xl md:text-3xl font-semibold text-foreground tracking-[-0.02em] text-balance">
                Built for honest decisions
              </h2>
              <p className="mt-6 text-muted-foreground leading-relaxed">
                Crop Analyser aggregates data from government mandis, weather services, and
                agricultural research to give you a clear picture, not a rosy one. When we're
                uncertain, we tell you. When data is thin, we show it. Your farm deserves
                straight talk.
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-border py-8">
        <div className="mx-auto max-w-[1100px] px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Sprout className="h-5 w-5 text-primary" />
              <span className="font-display font-semibold text-foreground">Crop Analyser</span>
            </div>
            <p className="text-sm text-muted-foreground">Data for the Indian farmer</p>
          </div>
        </div>
      </footer>
    </div>
  )
}

import { ReactNode } from "react"

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-border bg-surface shadow-[0_30px_60px_-40px_rgba(167,139,250,0.5)] transition-colors ${className}`}>
      {children}
    </div>
  )
}

export function CardHeader({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`px-5 py-4 border-b border-borderSubtle ${className}`}>{children}</div>
}

export function CardContent({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`px-5 py-4 ${className}`}>{children}</div>
}

export function CardTitle({ children }: { children: ReactNode }) {
  return <h2 className="text-base font-semibold tracking-tight">{children}</h2>
}

export function CardDescription({ children }: { children: ReactNode }) {
  return <p className="text-sm text-textSecondary mt-1">{children}</p>
}


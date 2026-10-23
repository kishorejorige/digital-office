import { NavLink, Outlet } from "react-router-dom"
import { LayoutDashboard, Search, Users, FileText, Settings, Activity } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { fetchHealth } from "../lib/api"

const navItems = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/research", label: "Research & Tasks", icon: Search },
  { to: "/leads", label: "Leads", icon: Users },
  { to: "/proposals", label: "Proposals & Approvals", icon: FileText },
  { to: "/settings", label: "Settings", icon: Settings },
]

export default function Layout() {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    retry: 1,
    refetchInterval: 30000,
  })

  return (
    <div className="min-h-screen bg-background text-textPrimary flex">
      <aside className="hidden md:flex w-64 flex-col border-r border-border bg-surface">
        <div className="h-16 flex items-center px-6 border-b border-borderSubtle">
          <span className="text-lg font-semibold tracking-tight">Digital Office</span>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                  isActive
                    ? "bg-accentMuted text-textPrimary"
                    : "text-textSecondary hover:text-textPrimary hover:bg-surface2/80"
                }`
              }
            >
              <item.icon className="h-4 w-4" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 flex items-center justify-between px-4 md:px-6 border-b border-border bg-surface/90 backdrop-blur">
          <div className="flex items-center gap-2">
            <span className="md:hidden text-lg font-semibold">Digital Office</span>
            <span className="hidden md:inline text-sm text-textSecondary">Premium Dashboard</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <Activity className="h-4 w-4 text-textSecondary" />
            {isLoading && <span className="text-textSecondary">Checking...</span>}
            {!isLoading && isError && <span className="text-danger">Disconnected</span>}
            {!isLoading && !isError && data && (
              <span className="text-success">Connected · {data.version || "v0.6.0"}</span>
            )}
          </div>
        </header>
        <main className="flex-1 p-4 md:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}


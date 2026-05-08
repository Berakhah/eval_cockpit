import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <header className="h-12 border-b border-border bg-surface-1 flex items-center px-4 gap-4 shrink-0">
        <Link to="/" className="flex items-center gap-2 text-sm font-semibold tracking-tight">
          <Logo />
          <span>PolyEval</span>
          <span className="text-muted-foreground font-normal text-xs">cockpit</span>
        </Link>
        <nav className="flex items-center gap-1 text-xs font-mono">
          <NavLink to="/">submit</NavLink>
          <NavLink to="/dashboard">dashboard</NavLink>
          <NavLink to="/settings">settings</NavLink>
        </nav>
        <div className="ml-auto flex items-center gap-1 text-xs text-muted-foreground font-mono">
          <span className="px-2 py-0.5 rounded bg-surface-2 border border-border">v1.0</span>
        </div>
      </header>
      <main className="flex-1 min-h-0 flex flex-col">{children}</main>
    </div>
  );
}

function NavLink({ to, children }: { to: "/" | "/dashboard" | "/settings"; children: ReactNode }) {
  return (
    <Link
      to={to}
      activeOptions={{ exact: true }}
      className="px-2 py-1 rounded text-muted-foreground hover:text-foreground hover:bg-surface-2 transition-colors data-[status=active]:text-foreground data-[status=active]:bg-surface-2"
    >
      {children}
    </Link>
  );
}

function Logo() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="2" y="2" width="5" height="5" rx="1" fill="currentColor" opacity="0.9" />
      <rect x="9" y="2" width="5" height="5" rx="1" fill="currentColor" opacity="0.55" />
      <rect x="2" y="9" width="5" height="5" rx="1" fill="currentColor" opacity="0.55" />
      <rect x="9" y="9" width="5" height="5" rx="1" fill="currentColor" opacity="0.9" />
    </svg>
  );
}
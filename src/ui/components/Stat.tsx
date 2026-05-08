import { cn } from "@/lib/cn";
import type { ReactNode } from "react";

export function Card({
  children,
  className,
  title,
  hint,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  hint?: ReactNode;
}) {
  return (
    <section
      className={cn(
        "bg-card border border-border rounded-md flex flex-col min-h-0",
        className,
      )}
    >
      {(title || hint) && (
        <header className="flex items-center justify-between px-3 h-8 border-b border-border shrink-0">
          <h3 className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">
            {title}
          </h3>
          <div className="text-[11px] text-muted-foreground font-mono">{hint}</div>
        </header>
      )}
      <div className="flex-1 min-h-0">{children}</div>
    </section>
  );
}

export function Stat({
  label,
  value,
  caption,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  caption?: ReactNode;
  tone?: "default" | "success" | "warn" | "danger" | "info";
}) {
  const toneClass =
    tone === "success"
      ? "text-success"
      : tone === "warn"
        ? "text-warn"
        : tone === "danger"
          ? "text-danger"
          : tone === "info"
            ? "text-info"
            : "text-foreground";
  return (
    <div className="flex flex-col gap-1 px-4 py-3">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">
        {label}
      </div>
      <div className={cn("text-3xl font-mono font-semibold tabular-nums leading-none", toneClass)}>
        {value}
      </div>
      {caption && <div className="text-[11px] text-muted-foreground font-mono">{caption}</div>}
    </div>
  );
}

export function Pill({
  children,
  tone = "default",
}: {
  children: ReactNode;
  tone?: "default" | "success" | "warn" | "danger" | "info";
}) {
  const map: Record<string, string> = {
    default: "bg-surface-2 text-muted-foreground border-border",
    success: "bg-success/10 text-success border-success/30",
    warn: "bg-warn/10 text-warn border-warn/30",
    danger: "bg-danger/10 text-danger border-danger/30",
    info: "bg-info/10 text-info border-info/30",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-1.5 h-5 rounded text-[10px] uppercase tracking-wider font-medium border font-mono",
        map[tone],
      )}
    >
      {children}
    </span>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex items-center justify-center min-w-5 h-5 px-1 rounded border border-border bg-surface-2 text-[10px] font-mono text-muted-foreground">
      {children}
    </kbd>
  );
}
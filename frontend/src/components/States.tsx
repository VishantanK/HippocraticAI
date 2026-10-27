import { AlertTriangle, Loader2 } from "lucide-react";
import type { ReactNode } from "react";

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-muted" role="status">
      <Loader2 className="animate-spin" size={18} aria-hidden /> {label}…
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start gap-3 rounded border border-reject/30 bg-reject-tint px-4 py-3 text-sm text-ink">
      <AlertTriangle size={18} className="mt-0.5 shrink-0 text-reject" aria-hidden />
      <div className="flex-1">
        <p className="font-semibold">Couldn't load this.</p>
        <p className="text-ink-2">{message}. Check that the server is running on port 8001.</p>
      </div>
      {onRetry && <button className="btn-quiet" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded border border-dashed border-line px-6 py-10 text-center">
      <p className="font-semibold text-ink">{title}</p>
      {children && <div className="mt-1 text-sm text-muted">{children}</div>}
    </div>
  );
}

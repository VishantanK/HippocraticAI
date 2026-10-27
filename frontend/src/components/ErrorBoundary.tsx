import { AlertTriangle } from "lucide-react";
import { Component, type ReactNode } from "react";

/** Keeps a render bug in one page from blanking the whole app. Reset by remounting (key). */
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error("[portal] page crashed", error);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div role="alert" className="flex max-w-xl items-start gap-3 rounded-lg border border-reject/30 bg-reject-tint px-4 py-4 text-sm">
        <AlertTriangle size={18} className="mt-0.5 shrink-0 text-reject" aria-hidden />
        <div className="flex-1">
          <p className="font-semibold">This page hit a problem.</p>
          <p className="mt-1 text-ink-2">Nothing was lost: decisions are stored on the server. Reload to try again, or use the menu to go elsewhere.</p>
          <button className="btn-quiet mt-3" onClick={() => window.location.reload()}>Reload</button>
        </div>
      </div>
    );
  }
}

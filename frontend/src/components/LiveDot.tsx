import { useLiveStatus } from "../lib/live";

export function LiveDot() {
  const up = useLiveStatus();
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted" title={up ? "Updates arrive live" : "Reconnecting to live updates"}>
      <span className={`h-2 w-2 rounded-full ${up ? "bg-approve" : "bg-muted"}`} aria-hidden />
      {up ? "Live" : "Reconnecting"}
    </span>
  );
}

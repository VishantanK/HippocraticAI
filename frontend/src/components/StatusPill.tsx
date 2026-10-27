import { AlertTriangle, CheckCircle2, HelpCircle, Loader2, XCircle } from "lucide-react";
import { statusLabel } from "../lib/format";
import type { Status } from "../lib/types";

const STYLE: Record<string, { cls: string; Icon: typeof CheckCircle2 }> = {
  approve: { cls: "bg-approve-tint text-approve", Icon: CheckCircle2 },
  reject: { cls: "bg-reject-tint text-reject", Icon: XCircle },
  flag: { cls: "bg-flag-tint text-flag", Icon: HelpCircle },
  checking: { cls: "bg-sunk text-muted", Icon: Loader2 },
  error: { cls: "bg-reject-tint text-reject", Icon: AlertTriangle },
};

/** Compact status for tables: icon + label, never colour alone. */
export function StatusPill({ status }: { status: Status }) {
  const s = status ?? "checking";
  const { cls, Icon } = STYLE[s] ?? STYLE.checking;
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ${cls}`}>
      <Icon size={13} aria-hidden className={s === "checking" ? "animate-spin" : ""} />
      {statusLabel(s)}
    </span>
  );
}

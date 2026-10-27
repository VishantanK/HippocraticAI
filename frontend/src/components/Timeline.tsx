import { day } from "../lib/format";
import { RULE_LABEL } from "../lib/format";
import type { ExpenseDetail } from "../lib/types";
import { StatusPill } from "./StatusPill";

/** Each revision, with the question asked and the answer that led to the next one. */
export function Timeline({ expense, showDelivery = false }: { expense: ExpenseDetail; showDelivery?: boolean }) {
  const items = [...expense.decisions].reverse();
  return (
    <ol className="relative ml-2 border-l border-line">
      {items.map((d) => {
        const fu = expense.followups.find((f) => f.decision_revision === d.revision);
        return (
          <li key={d.revision} className="relative pb-5 pl-5 last:pb-0">
            <span className="absolute -left-[5px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-panel bg-line" aria-hidden />
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill status={d.decision} />
              <span className="text-sm font-semibold">Revision {d.revision}</span>
              <span className="text-xs text-muted">
                {d.decided_by === "human" ? "Finance" : "Automatic"}, {day(d.decided_at)}{" "}
                {new Date(d.decided_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
              </span>
              {showDelivery && (
                <span className={`text-xs ${d.post_status === "sent" ? "text-muted" : "font-semibold text-reject"}`}>
                  {d.post_status === "sent" ? "Delivered" : `Delivery ${d.post_status} (${d.post_attempts} attempts)`}
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-ink-2">{d.payload.reasons.map((r) => RULE_LABEL[r.rule] ?? r.rule).join(", ")}</p>
            {fu && (
              <div className="mt-2 rounded bg-sunk px-3 py-2 text-sm">
                <p><span className="font-semibold">Question:</span> {fu.question}</p>
                {fu.answer ? (
                  <p className="mt-1"><span className="font-semibold">Answer:</span> {fu.answer}</p>
                ) : (
                  <p className="mt-1 text-muted">{fu.status === "open" ? "Waiting for a reply" : "Superseded by an edit"}</p>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}

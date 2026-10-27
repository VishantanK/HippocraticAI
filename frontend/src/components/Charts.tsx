import { useState } from "react";
import { DECISIONS, money, STATUS_LABEL } from "../lib/format";
import type { Decision } from "../lib/types";

// Decision colours are status colours (validated light + dark); always paired with a label.
const FILL: Record<Decision, string> = { approve: "bg-approve", flag: "bg-flag", reject: "bg-reject" };

export function Legend() {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
      {DECISIONS.map((d) => (
        <li key={d} className="flex items-center gap-1.5"><span className={`h-2.5 w-2.5 rounded-sm ${FILL[d]}`} aria-hidden />{STATUS_LABEL[d]}</li>
      ))}
    </ul>
  );
}

type Tip = { x: number; text: string } | null;

/** Part-to-whole of decisions: one thin stacked bar, direct labels underneath. */
export function DecisionMix({ counts }: { counts: Record<string, number> }) {
  const total = DECISIONS.reduce((s, d) => s + (counts[d] ?? 0), 0);
  const [tip, setTip] = useState<Tip>(null);
  if (!total) return <p className="text-sm text-muted">No decisions yet.</p>;
  const pct = (n: number) => Math.round((n / total) * 100);
  return (
    <figure>
      <div className="relative" onMouseLeave={() => setTip(null)}>
        <div className="flex h-3 gap-[2px]" role="img" aria-label={DECISIONS.map((d) => `${STATUS_LABEL[d]} ${counts[d] ?? 0}`).join(", ")}>
          {DECISIONS.filter((d) => counts[d]).map((d, i, arr) => (
            <div
              key={d}
              className={`${FILL[d]} h-full ${i === 0 ? "rounded-l" : ""} ${i === arr.length - 1 ? "rounded-r" : ""}`}
              style={{ width: `${(counts[d] / total) * 100}%` }}
              onMouseMove={(e) => {
                const box = e.currentTarget.parentElement!.getBoundingClientRect();
                setTip({ x: e.clientX - box.left, text: `${STATUS_LABEL[d]}: ${counts[d]} (${pct(counts[d])}%)` });
              }}
            />
          ))}
        </div>
        {tip && <div className="pointer-events-none absolute -top-9 z-10 -translate-x-1/2 whitespace-nowrap rounded bg-ink px-2 py-1 text-xs text-paper" style={{ left: tip.x }}>{tip.text}</div>}
      </div>
      <figcaption className="mt-3 grid grid-cols-3 gap-2">
        {DECISIONS.map((d) => (
          <div key={d}>
            <p className="text-xl font-semibold tabular-nums">{pct(counts[d] ?? 0)}%</p>
            <p className="flex items-center gap-1.5 text-xs text-ink-2"><span className={`h-2 w-2 rounded-sm ${FILL[d]}`} aria-hidden />{STATUS_LABEL[d]} ({counts[d] ?? 0})</p>
          </div>
        ))}
      </figcaption>
    </figure>
  );
}

/** USD by category, stacked by decision. Sorted by total; total labelled at the bar end. */
export function SpendByCategory({ rows }: { rows: { category: string; approve: number; reject: number; flag: number }[] }) {
  const [tip, setTip] = useState<{ row: number; x: number; text: string } | null>(null);
  if (!rows.length) return <p className="text-sm text-muted">No USD amounts yet.</p>;
  const totals = rows.map((r) => r.approve + r.flag + r.reject);
  const max = Math.max(...totals);
  return (
    <div>
      <ul className="space-y-2.5" onMouseLeave={() => setTip(null)}>
        {rows.map((r, i) => (
          <li key={r.category} className="grid grid-cols-[7.5rem_1fr_5.5rem] items-center gap-3 text-sm">
            <span className="truncate text-ink-2">{r.category === "GroundTransport" ? "Ground transport" : r.category}</span>
            <div className="relative h-2.5">
              <div className="flex h-full gap-[2px]" style={{ width: `${(totals[i] / max) * 100}%` }}>
                {DECISIONS.filter((d) => r[d] > 0).map((d, j, arr) => (
                  <div
                    key={d}
                    className={`${FILL[d]} h-full ${j === 0 ? "rounded-l" : ""} ${j === arr.length - 1 ? "rounded-r" : ""}`}
                    style={{ width: `${(r[d] / totals[i]) * 100}%` }}
                    onMouseMove={(e) => {
                      const box = e.currentTarget.parentElement!.parentElement!.getBoundingClientRect();
                      setTip({ row: i, x: e.clientX - box.left, text: `${STATUS_LABEL[d]}: ${money(r[d])}` });
                    }}
                  />
                ))}
              </div>
              {tip?.row === i && <div className="pointer-events-none absolute -top-8 z-10 -translate-x-1/2 whitespace-nowrap rounded bg-ink px-2 py-1 text-xs text-paper" style={{ left: tip.x }}>{tip.text}</div>}
            </div>
            <span className="text-right tabular-nums">{money(totals[i])}</span>
          </li>
        ))}
      </ul>
      <div className="mt-4"><Legend /></div>
    </div>
  );
}

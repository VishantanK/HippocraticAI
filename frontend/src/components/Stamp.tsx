import type { Status } from "../lib/types";

const TEXT: Record<string, string> = { approve: "Approved", reject: "Rejected", flag: "Needs info", checking: "Checking", error: "Check failed" };
const COLOR: Record<string, string> = { approve: "text-approve", reject: "text-reject", flag: "text-flag", checking: "text-muted", error: "text-reject" };

/** The decision as a rubber stamp. `land` animates it in (once, when a new decision arrives). */
export function Stamp({ status, size = "lg", land = false }: { status: Status; size?: "md" | "lg"; land?: boolean }) {
  const s = status ?? "checking";
  const sizing = size === "lg" ? "text-3xl" : "text-lg";
  return (
    <span
      role="status"
      aria-label={`Decision: ${TEXT[s] ?? s}`}
      className={`stamp ${sizing} ${COLOR[s] ?? "text-muted"} ${s === "checking" ? "animate-pulse border-dashed" : ""} ${land ? "stamp-land" : ""}`}
      style={s === "checking" ? { borderStyle: "dashed", borderWidth: 2 } : undefined}
    >
      {TEXT[s] ?? s}
    </span>
  );
}

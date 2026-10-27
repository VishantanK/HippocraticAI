import { UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useIdentity } from "../lib/identity";

/** No auth in this demo: the employee says who they are (stored in this browser). */
export function IdentityPicker({ compact = false }: { compact?: boolean }) {
  const [me, setMe] = useIdentity();
  const [names, setNames] = useState<string[]>([]);
  const [draft, setDraft] = useState(me);
  useEffect(() => { api.employees().then(setNames).catch(() => setNames([])); }, []);
  useEffect(() => setDraft(me), [me]);

  return (
    <form
      className={`flex items-center gap-2 ${compact ? "" : "flex-wrap"}`}
      onSubmit={(e) => { e.preventDefault(); if (draft.trim()) setMe(draft.trim()); }}
    >
      <UserRound size={16} className="text-muted" aria-hidden />
      <label htmlFor="me" className="sr-only">Your name</label>
      <input
        id="me"
        list="known-employees"
        className={`field ${compact ? "w-44 py-1 text-sm" : "w-64"}`}
        placeholder="Your full name"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => draft.trim() && draft.trim() !== me && setMe(draft.trim())}
      />
      <datalist id="known-employees">{names.map((n) => <option key={n} value={n} />)}</datalist>
      {!compact && <button className="btn-primary" type="submit">Continue</button>}
    </form>
  );
}

import { useEffect, useState } from "react";

// No auth in this demo (see ASSUMPTIONS.md A4): the employee says who they are.
const KEY = "expense-portal.me";
const subs = new Set<(v: string) => void>();

function read() {
  try { return localStorage.getItem(KEY) ?? ""; } catch { return ""; }
}

export function setIdentity(name: string) {
  try { localStorage.setItem(KEY, name); } catch { /* storage blocked: identity lasts this tab only */ }
  subs.forEach((fn) => fn(name));
}

export function useIdentity(): [string, (n: string) => void] {
  const [me, setMe] = useState(read);
  useEffect(() => {
    subs.add(setMe);
    return () => { subs.delete(setMe); };
  }, []);
  return [me, setIdentity];
}

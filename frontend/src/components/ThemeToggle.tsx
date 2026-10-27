import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

const KEY = "expense-portal.theme";

function initial(): "light" | "dark" {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch { /* ignore */ }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState(initial);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem(KEY, theme); } catch { /* ignore */ }
  }, [theme]);
  const next = theme === "dark" ? "light" : "dark";
  return (
    <button className="rounded p-1.5 text-muted hover:bg-sunk hover:text-ink" onClick={() => setTheme(next)} aria-label={`Switch to ${next} mode`}>
      {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}

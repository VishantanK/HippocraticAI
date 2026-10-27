import { Inbox, LayoutDashboard, Rows3, Send } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "../lib/api";
import { useData } from "../lib/useData";
import { LiveDot } from "./LiveDot";
import { ThemeToggle } from "./ThemeToggle";

const link = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-2.5 rounded px-3 py-2 text-sm font-medium ${isActive ? "bg-sunk text-ink" : "text-ink-2 hover:bg-sunk/60 hover:text-ink"}`;

export function FinanceLayout() {
  const { data: stats } = useData(api.stats, [], (e) => e.type === "decision" || e.type === "delivery");
  const needsDecision = stats ? stats.by_status.flag ?? 0 : null;
  const undelivered = stats ? stats.post.dead + stats.post.failed : null;
  return (
    <div className="min-h-screen md:grid md:grid-cols-[220px_1fr]">
      <aside className="border-b border-line bg-panel md:sticky md:top-0 md:h-screen md:border-b-0 md:border-r">
        <div className="flex items-center justify-between px-4 py-4">
          <span className="font-semibold tracking-tight">Expense review</span>
          <ThemeToggle />
        </div>
        <nav className="flex gap-1 px-2 pb-3 md:flex-col">
          <NavLink to="/finance" end className={link}><LayoutDashboard size={16} aria-hidden />Overview</NavLink>
          <NavLink to="/finance/queue" className={link}>
            <Inbox size={16} aria-hidden />Review queue
            {needsDecision ? <span className="ml-auto rounded-full bg-flag px-2 text-xs font-semibold text-white">{needsDecision}</span> : null}
          </NavLink>
          <NavLink to="/finance/expenses" className={link}><Rows3 size={16} aria-hidden />All expenses</NavLink>
          <NavLink to="/finance/delivery" className={link}>
            <Send size={16} aria-hidden />Delivery
            {undelivered ? <span className="ml-auto rounded-full bg-reject px-2 text-xs font-semibold text-white">{undelivered}</span> : null}
          </NavLink>
        </nav>
        <div className="hidden px-5 md:absolute md:bottom-4 md:block"><LiveDot /></div>
      </aside>
      <main className="min-w-0 px-4 py-6 md:px-8">
        <Outlet />
      </main>
    </div>
  );
}

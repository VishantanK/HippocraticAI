import { NavLink, Outlet } from "react-router-dom";
import { IdentityPicker } from "./IdentityPicker";
import { LiveDot } from "./LiveDot";
import { ThemeToggle } from "./ThemeToggle";

const link = ({ isActive }: { isActive: boolean }) =>
  `rounded px-3 py-1.5 text-sm font-medium ${isActive ? "bg-sunk text-ink" : "text-ink-2 hover:text-ink"}`;

export function EmployeeLayout() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-panel">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <NavLink to="/employee" className="font-semibold tracking-tight">Expenses</NavLink>
          <nav className="flex gap-1">
            <NavLink to="/employee" end className={link}>My expenses</NavLink>
            <NavLink to="/employee/new" className={link}>New expense</NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <LiveDot />
            <IdentityPicker compact />
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}

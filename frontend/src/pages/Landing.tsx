import { Link } from "react-router-dom";
import { Stamp } from "../components/Stamp";

export default function Landing() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-6 py-16">
      <div className="mb-10 flex items-center gap-4">
        <Stamp status="approve" />
      </div>
      <h1 className="max-w-xl text-4xl font-semibold leading-tight tracking-tight">
        Expenses are checked against policy the moment they're submitted.
      </h1>
      <p className="mt-4 max-w-xl text-lg text-ink-2">
        Routine claims are decided automatically. Anything unclear comes back with one specific question, and Finance only sees what needs a person.
      </p>
      <div className="mt-10 grid gap-4 sm:grid-cols-2">
        <Link to="/employee" className="group rounded-lg border border-line bg-panel p-5 hover:border-ink-2">
          <p className="font-semibold">I'm submitting expenses</p>
          <p className="mt-1 text-sm text-muted">Add receipts, see decisions, answer questions.</p>
        </Link>
        <Link to="/finance" className="group rounded-lg border border-line bg-panel p-5 hover:border-ink-2">
          <p className="font-semibold">I review expenses for Finance</p>
          <p className="mt-1 text-sm text-muted">Work the review queue and track every decision.</p>
        </Link>
      </div>
    </main>
  );
}

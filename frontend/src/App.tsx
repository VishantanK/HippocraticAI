import { Navigate, Route, Routes } from "react-router-dom";
import { EmployeeLayout } from "./components/EmployeeLayout";
import { FinanceLayout } from "./components/FinanceLayout";
import Landing from "./pages/Landing";
import EmployeeHome from "./pages/employee/EmployeeHome";
import EmployeeExpense from "./pages/employee/EmployeeExpense";
import NewExpense from "./pages/employee/NewExpense";
import AllExpenses from "./pages/finance/AllExpenses";
import Delivery from "./pages/finance/Delivery";
import FinanceExpense from "./pages/finance/FinanceExpense";
import Overview from "./pages/finance/Overview";
import Queue from "./pages/finance/Queue";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/employee" element={<EmployeeLayout />}>
        <Route index element={<EmployeeHome />} />
        <Route path="new" element={<NewExpense />} />
        <Route path="expenses/:id" element={<EmployeeExpense />} />
      </Route>
      <Route path="/finance" element={<FinanceLayout />}>
        <Route index element={<Overview />} />
        <Route path="queue" element={<Queue />} />
        <Route path="expenses" element={<AllExpenses />} />
        <Route path="expenses/:id" element={<FinanceExpense />} />
        <Route path="delivery" element={<Delivery />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

import { BrowserRouter, Route, Routes } from "react-router";
import { ClaimPage } from "./ClaimPage";
import { InstructionsPage } from "./InstructionsPage";
import { Layout } from "./Layout";
import { QueuePage } from "./QueuePage";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<QueuePage />} />
        <Route path="claims/:claimId" element={<ClaimPage />} />
        <Route path="instructions" element={<InstructionsPage />} />
        <Route path="*" element={<p>There is no page here.</p>} />
      </Route>
    </Routes>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}

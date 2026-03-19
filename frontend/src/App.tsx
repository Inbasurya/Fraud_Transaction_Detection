import React from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { FraudProvider } from "./context/FraudContext";
import DashboardLayout from "./components/DashboardLayout";
import Dashboard from "./pages/Dashboard.tsx";
import Alerts from "./pages/Alerts.tsx";
import Customers from "./pages/Customers";
import CustomerManagement from "./pages/CustomerManagement";
import FraudGraph from "./pages/FraudGraph.tsx";
import Models from "./pages/Models.tsx";
import Settings from "./pages/Settings.tsx";
import { Login } from "./pages/Login.tsx";
import { ErrorBoundary } from "./components/ErrorBoundary";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('token');
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <FraudProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={
            <ProtectedRoute>
              <DashboardLayout />
            </ProtectedRoute>
          }>
            <Route path="/" element={<ErrorBoundary pageName="Dashboard"><Dashboard /></ErrorBoundary>} />
            <Route path="/alerts" element={<ErrorBoundary pageName="Alerts"><Alerts /></ErrorBoundary>} />
            <Route path="/customers" element={<ErrorBoundary pageName="Customers"><Customers /></ErrorBoundary>} />
            <Route path="/customer-intel" element={<CustomerManagement />} />
            <Route path="/graph" element={<ErrorBoundary pageName="Fraud Network"><FraudGraph /></ErrorBoundary>} />
            <Route path="/models" element={<ErrorBoundary pageName="Models"><Models /></ErrorBoundary>} />
            <Route path="/settings" element={<ErrorBoundary pageName="Settings"><Settings /></ErrorBoundary>} />
          </Route>
        </Routes>
      </FraudProvider>
    </BrowserRouter>
  );
}

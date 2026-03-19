import axios from "axios";
import type {
  Transaction,
  Alert,
  DashboardStats,
  CustomerProfile,
  NetworkData,
} from "../types";

// Dynamic host: works on localhost AND network IPs like 10.185.29.154
const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
export const API_BASE = isLocalhost
  ? (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  : `http://${window.location.hostname}:8000`

export const WS_BASE = isLocalhost
  ? 'ws://localhost:8000'
  : `ws://${window.location.hostname}:8000`

const API = axios.create({
  baseURL: API_BASE,
});

API.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

API.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('role');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ── Transactions ───────────────────────────────────────────
export async function fetchTransactions(params?: {
  page?: number;
  size?: number;
  risk_level?: string;
  customer_id?: string;
}): Promise<{ transactions: Transaction[]; total: number }> {
  const { data } = await API.get("/api/transactions", { params });
  return data;
}

export async function fetchTransaction(id: string): Promise<Transaction> {
  const { data } = await API.get(`/api/transactions/${id}`);
  return data;
}

// ── Alerts ─────────────────────────────────────────────────
export async function fetchAlerts(params?: {
  page?: number;
  size?: number;
  status?: string;
  severity?: string;
}): Promise<{ alerts: Alert[]; total: number }> {
  const { data } = await API.get("/api/alerts", { params });
  return data;
}

export async function updateAlert(
  id: string,
  payload: Partial<Alert>
): Promise<Alert> {
  const { data } = await API.patch(`/api/alerts/${id}`, payload);
  return data;
}

export async function fetchAlertStats(): Promise<{
  by_status: Record<string, number>;
  by_severity: Record<string, number>;
}> {
  const { data } = await API.get("/api/alerts/stats");
  return data;
}

// ── Dashboard ──────────────────────────────────────────────
export async function fetchDashboardStats(): Promise<DashboardStats> {
  const { data } = await API.get("/api/dashboard/stats");
  return data;
}

// ── Customers ──────────────────────────────────────────────
export async function fetchCustomer(id: string): Promise<CustomerProfile> {
  const { data } = await API.get(`/api/customers/${id}`);
  return data;
}

export async function fetchCustomers(params?: {
  page?: number;
  size?: number;
  risk_tier?: string;
}): Promise<{
  customers: { id: string; name: string; segment: string; risk_tier: string; home_city: string }[];
  total: number;
}> {
  const { data } = await API.get("/api/customers", { params });
  return data;
}

// ── Graph ──────────────────────────────────────────────────
export async function fetchNetworkGraph(): Promise<NetworkData> {
  const { data } = await API.get("/api/graph/network");
  return data;
}

// ── Health ─────────────────────────────────────────────────
export async function fetchHealth(): Promise<{ status: string; version: string }> {
  const { data } = await API.get("/health");
  return data;
}

// ── Models ───────────────────────────────────────────────────
export async function fetchModelInfo(): Promise<any> {
    const { data } = await API.get("/api/model-info");
    return data;
}

export async function fetchModelDrift(): Promise<any> {
    const { data } = await API.get("/api/model/drift");
    return data;
}

export async function fetchCustomerDNA(id: string): Promise<any> {
    const { data } = await API.get(`/api/customers/${id}/dna`);
    return data;
}

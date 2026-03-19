import { useState, useEffect, useCallback } from "react";
import { fetchAlerts, updateAlert as apiUpdateAlert } from "../services/api";
import type { Alert } from "../types";

export function useAlerts(params?: {
  page?: number;
  size?: number;
  status?: string;
  severity?: string;
}) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAlerts(params);
      setAlerts(data.alerts);
      setTotal(data.total);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [params?.page, params?.size, params?.status, params?.severity]);

  useEffect(() => {
    load();
  }, [load]);

  const updateAlert = useCallback(
    async (id: string, payload: Partial<Alert>) => {
      const updated = await apiUpdateAlert(id, payload);
      setAlerts((prev) => prev.map((a) => (a.id === id ? updated : a)));
      return updated;
    },
    []
  );

  return { alerts, total, loading, reload: load, updateAlert };
}

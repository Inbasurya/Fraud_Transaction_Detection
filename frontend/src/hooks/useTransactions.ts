import { useState, useEffect, useCallback } from "react";
import { fetchTransactions } from "../services/api";
import type { Transaction } from "../types";

export function useTransactions(params?: {
  page?: number;
  size?: number;
  risk_level?: string;
  customer_id?: string;
}) {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchTransactions(params);
      setTransactions(data.transactions);
      setTotal(data.total);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [params?.page, params?.size, params?.risk_level, params?.customer_id]);

  useEffect(() => {
    load();
  }, [load]);

  return { transactions, total, loading, reload: load };
}

export interface Transaction {
  id: string;
  customer_id: string;
  amount: number;
  merchant_id: string;
  merchant_category: string;
  lat: number;
  lng: number;
  device_fingerprint: string;
  ip_address: string;
  risk_score: number;
  risk_level: "low" | "medium" | "high" | "critical";
  is_fraud: boolean;
  fraud_type: string | null;
  score_breakdown: Record<string, number>;
  triggered_rules: RuleResult[];
  shap_values: Record<string, number>;
  ml_score: number;
  behavioral_score: number;
  behavioral_flags: string[];
  graph_score: number;
  graph_patterns: string[];
  processing_latency_ms: number;
  scored_at: string;
  created_at: string;
}

export interface RuleResult {
  rule_id: string;
  name: string;
  triggered: boolean;
  score: number;
}

export interface Alert {
  id: string;
  transaction_id: string;
  customer_id: string;
  severity: "low" | "medium" | "high" | "critical";
  risk_score: number;
  status: "new" | "investigating" | "resolved" | "false_positive";
  assigned_to: string | null;
  notes: string | null;
  triggered_rules: RuleResult[];
  created_at: string;
  updated_at: string | null;
}

export interface DashboardStats {
  total_transactions: number;
  transactions_24h: number;
  fraud_detected: number;
  fraud_rate: number;
  avg_risk_score: number;
  total_amount_processed: number;
  active_alerts: number;
  avg_processing_latency_ms: number;
  model_accuracy: number;
}

export interface CustomerProfile {
  customer_id: string;
  name: string;
  segment: string;
  risk_tier: string;
  total_transactions: number;
  avg_risk_score: number;
  total_amount: number;
  home_city: string;
  registered_devices: string[];
  recent_transactions: {
    id: string;
    amount: number;
    risk_score: number;
    merchant_category: string;
    created_at: string;
  }[];
}

export interface GraphNode {
  id: string;
  type: "customer" | "merchant" | "device" | "ip";
  fraud_score: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
}

export interface NetworkData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

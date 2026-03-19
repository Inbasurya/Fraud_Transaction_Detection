import React, { useEffect, useState } from 'react';
import API from '../services/api';

const Alerts = () => {
  const [alerts, setAlerts] = useState([]);

  const authConfig = () => {
    const token = localStorage.getItem('token');
    return token ? { headers: { Authorization: `Bearer ${token}` } } : {};
  };

  useEffect(() => {
    const load = async () => {
      try {
        const response = await API.get('/alerts', authConfig());
        const highRisk = response.data.filter(alert => (alert.risk_score ?? 0) >= 70);
        setAlerts(highRisk);
      } catch (error) {
        // Fallback path for non-admin users using transaction risk scores.
        const txResponse = await API.get('/transaction', authConfig());
        const highRiskTx = txResponse.data
          .filter(tx => (tx.risk_score ?? 0) >= 70)
          .map(tx => ({
            id: tx.id,
            transaction_id: tx.transaction_id,
            risk_score: tx.risk_score,
            alert_type: 'HIGH_RISK',
            status: 'OPEN',
            message: 'High-risk transaction',
            created_at: tx.created_at || tx.timestamp,
          }));
        setAlerts(highRiskTx);
      }
    };
    load();
  }, []);

  return (
    <div className="alerts">
      <h2>Alerts</h2>
      <table>
        <thead>
          <tr>
            <th>Transaction ID</th>
            <th>Risk Score</th>
            <th>Type</th>
            <th>Status</th>
            <th>Message</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {alerts.map(a => (
            <tr key={a.id} className="high-risk">
              <td>{a.transaction_id}</td>
              <td>{a.risk_score}</td>
              <td>{a.alert_type}</td>
              <td>{a.status}</td>
              <td>{a.message}</td>
              <td>{new Date(a.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default Alerts;

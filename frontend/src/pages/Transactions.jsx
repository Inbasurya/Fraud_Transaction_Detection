import React, { useEffect, useState } from 'react';
import API from '../services/api';

const Transactions = () => {
  const [txs, setTxs] = useState([]);

  const authConfig = () => {
    const token = localStorage.getItem('token');
    return token ? { headers: { Authorization: `Bearer ${token}` } } : {};
  };

  useEffect(() => {
    const load = async () => {
      const response = await API.get('/transaction', authConfig());
      setTxs(response.data);
    };
    load();
  }, []);

  return (
    <div className="transactions">
      <h2>Transactions</h2>
      <table>
        <thead>
          <tr>
            <th>Transaction ID</th>
            <th>Amount</th>
            <th>Risk Score</th>
            <th>Prediction</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {txs.map(tx => (
            <tr key={tx.transaction_id}>
              <td>{tx.transaction_id}</td>
              <td>{tx.amount}</td>
              <td>{tx.risk_score ?? 0}</td>
              <td>{tx.risk_category ?? 'Unknown'}</td>
              <td>{new Date(tx.timestamp).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default Transactions;

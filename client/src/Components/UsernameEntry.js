import React, { useState } from 'react';
import SERVER_URL from '../config.js';

const UsernameEntry = ({ onLinked }) => {
  const [leetcodeUsername, setLeetcodeUsername] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const response = await fetch(`${SERVER_URL}/api/leaderboard/register/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Token ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({ username: leetcodeUsername }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `Error: ${response.status}`);
      onLinked();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <h2>Enter your LeetCode username</h2>
      <form onSubmit={handleSubmit}>
        <label>
          Username:
          <input type="text" value={leetcodeUsername} onChange={(e) => setLeetcodeUsername(e.target.value)} required />
        </label>
        <button type="submit" disabled={submitting}>Submit</button>
      </form>
      {error && <p className="error">{error}</p>}
    </div>
  );
};

export default UsernameEntry;

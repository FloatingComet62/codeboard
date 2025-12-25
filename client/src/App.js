import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './Components/Navbar';
import Profile from './Components/Profile';
import Leaderboard from './Components/Leaderboard';
import Login from './Components/Login';
import UsernameEntry from './Components/UsernameEntry';
import SERVER_URL from './config.js';
import './App.css';

function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);

  // Validate a stored token and fetch the current user
  const fetchUser = useCallback(async () => {
    const token = localStorage.getItem('token');
    if (!token) {
      setChecking(false);
      return;
    }
    try {
      const response = await fetch(`${SERVER_URL}/api/auth/me/`, {
        headers: { 'Authorization': `Token ${token}` },
      });
      if (response.status === 401) {
        localStorage.removeItem('token');
        setUser(null);
      } else if (response.ok) {
        setUser(await response.json());
      }
    } catch (err) {
      console.error('Error fetching user:', err);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  if (checking) return <div className="loading">Loading...</div>;

  return (
    <Router>
      <div className="app-container">
        {!user ? (
          <Routes>
            <Route path="/login" element={<Login onLogin={setUser} />} />
            <Route path="*" element={<Navigate to="/login" />} />
          </Routes>
        ) : !user.has_leetcode ? (
          <Routes>
            <Route path="/username" element={<UsernameEntry onLinked={fetchUser} />} />
            <Route path="*" element={<Navigate to="/username" />} />
          </Routes>
        ) : (
          <>
            <Navbar />
            <div className="content">
              <Routes>
                <Route path="/" element={<Profile />} />
                <Route path="/profile" element={<Profile />} />
                <Route path="/daily" element={<Leaderboard type="daily" />} />
                <Route path="/weekly" element={<Leaderboard type="weekly" />} />
                <Route path="/monthly" element={<Leaderboard type="monthly" />} />
                <Route path="*" element={<Navigate to="/profile" />} />
              </Routes>
            </div>
          </>
        )}
      </div>
    </Router>
  );
}

export default App;

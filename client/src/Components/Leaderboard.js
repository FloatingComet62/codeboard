import React, { useEffect, useState } from 'react';
import axios from 'axios';

import SERVER_URL from "../config.js";
const BASE_URL = SERVER_URL+'/api/leaderboard';

const TITLES = { daily: 'Daily', weekly: 'Weekly', monthly: 'Monthly' };

const Leaderboard = ({ type }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    axios.get(`${BASE_URL}/${type}/`)
      .then(response => {
        // Convert {rank: entry} object to an array sorted by rank
        const dataArray = Object.keys(response.data)
          .sort((a, b) => Number(a) - Number(b))
          .map(key => ({ rank: Number(key), ...response.data[key] }));
        setData(dataArray);
      })
      .catch(error => setError(error))
      .finally(() => setLoading(false));
  }, [type]);

  if (loading) return <p className="loading">Loading...</p>;
  if (error) return <p className="error">Error loading data: {error.message}</p>;

  return (
    <div className="leaderboard-container">
      <h1 className="leaderboard-title">{TITLES[type]} Leaderboard</h1>
      <table className="leaderboard-table">
        <thead>
          <tr>
            <th>Rank</th>
            <th></th>
            <th>Username</th>
            <th>Questions Solved</th>
          </tr>
        </thead>
        <tbody>
          {data.map(item => (
            <tr key={item.rank} className="leaderboard-row">
              <td>{item.rank}</td>
              <td>{item.photo_url && <img src={item.photo_url} alt={item.username} />}</td>
              <td>{item.username}</td>
              <td>{item.ques_solv}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default Leaderboard;

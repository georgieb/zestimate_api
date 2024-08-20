import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [zpid, setZpid] = useState('');
  const [properties, setProperties] = useState([]);
  const [error, setError] = useState('');

  const handleSearch = async () => {
    setError('');
    setProperties([]);

    try {
      const response = await axios.get(`http://localhost:5001/api/caprates`, {
        params: { zpid }
      });

      if (response.data) {
        setProperties(response.data);
      } else {
        setError('No properties found.');
      }
    } catch (err) {
      console.error(err);
      setError('Error fetching data. Please try again.');
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Cap Rate Finder</h1>
        <input
          type="text"
          placeholder="Enter ZPID"
          value={zpid}
          onChange={(e) => setZpid(e.target.value)}
        />
        <button onClick={handleSearch}>Search</button>
        {error && <p>{error}</p>}
        {properties.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Address</th>
                <th>Zestimate</th>
                <th>Rental Zestimate</th>
                <th>Cap Rate</th>
              </tr>
            </thead>
            <tbody>
              {properties.map((property, index) => (
                <tr key={index}>
                  <td>{property.address}</td>
                  <td>{property.zestimate}</td>
                  <td>{property.rentalZestimate}</td>
                  <td>{property.capRate}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </header>
    </div>
  );
}

export default App;

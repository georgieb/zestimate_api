import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './ZPIDDashboard.css'; // Import the CSS file

function ZPIDDashboard() {
    const [zpidInput, setZpidInput] = useState('');
    const [properties, setProperties] = useState([]);
    const [error, setError] = useState('');
    const [savedSearches, setSavedSearches] = useState([]);
    const [selectedSearch, setSelectedSearch] = useState('');

    useEffect(() => {
        // Load saved searches from localStorage when component mounts
        const searches = JSON.parse(localStorage.getItem('savedSearches')) || [];
        setSavedSearches(searches);
    }, []);

    const handleSubmit = async (e) => {
        e.preventDefault();
        const zpidArray = zpidInput.split(',').map(zpid => zpid.trim());
        try {
            const response = await axios.post('http://localhost:5001/get-properties', { zpids: zpidArray });
            setProperties(response.data);
            setError('');
            saveSearch(zpidArray);
        } catch (error) {
            setError('Failed to fetch properties. Please try again.');
            console.error('Error fetching properties:', error);
        }
    };

    const saveSearch = (zpidArray) => {
        const searchName = prompt('Enter a name for this search:');
        if (searchName) {
            const newSearch = { name: searchName, zpids: zpidArray };
            let searches = JSON.parse(localStorage.getItem('savedSearches')) || [];
            searches = [newSearch, ...searches].slice(0, 10); // Keep only the last 10 searches
            localStorage.setItem('savedSearches', JSON.stringify(searches));
            setSavedSearches(searches);
        }
    };

    const handleSearchSelection = (e) => {
        const searchName = e.target.value;
        setSelectedSearch(searchName);
        const search = savedSearches.find(search => search.name === searchName);
        if (search) {
            setZpidInput(search.zpids.join(', '));
        }
    };

    const openNearbyProperties = (zpid) => {
        window.open(`/nearby-properties?zpid=${zpid}`, '_blank');
    };

    return (
        <div className="container">
            <div className="form-container">
                <h1>ZPID Dashboard</h1>
                <form onSubmit={handleSubmit}>
                    <label>
                        Enter ZPIDs (comma-separated):
                        <input 
                            type="text" 
                            value={zpidInput} 
                            onChange={(e) => setZpidInput(e.target.value)} 
                            placeholder="e.g., 44158191, 43994986" 
                        />
                    </label>
                    <button type="submit">Submit</button>
                    <label>
                        Saved Searches:
                        <select value={selectedSearch} onChange={handleSearchSelection}>
                            <option value="">Select a saved search</option>
                            {savedSearches.map((search, index) => (
                                <option key={index} value={search.name}>{search.name}</option>
                            ))}
                        </select>
                    </label>
                </form>
                {error && <p className="error-message">{error}</p>}
            </div>
            <div className="dashboard-table">
                <table>
                    <thead>
                        <tr>
                            <th>Address</th>
                            <th>Rental Zestimate</th>
                            <th>Zestimate</th>
                            <th>Cap Rate</th> 
                            <th>Zillow URL</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {properties.map((property, index) => (
                            <tr key={index}>
                                <td>{property.address}</td>
                                <td>{property.rentalZestimate.toLocaleString()}</td>
                                <td>{property.zestimate.toLocaleString()}</td>
                                <td>{property.capRate}</td> 
                                <td><a href={property.zillowUrl} target="_blank" rel="noopener noreferrer">View on Zillow</a></td>
                                <td>
                                    <button onClick={() => openNearbyProperties(property.zpid)}>
                                        Find Nearby Properties
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

export default ZPIDDashboard;

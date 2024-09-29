import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import './ZPIDDashboard.css';

function ZPIDDashboard() {
    const [zpidInput, setZpidInput] = useState('');
    const [properties, setProperties] = useState([]);
    const [error, setError] = useState('');
    const [savedSearches, setSavedSearches] = useState([]);
    const [selectedSearch, setSelectedSearch] = useState('');
    const navigate = useNavigate();

    useEffect(() => {
        const searches = JSON.parse(localStorage.getItem('savedSearches')) || [];
        setSavedSearches(searches);
    }, []);

    const handleSubmit = async (e) => {
        e.preventDefault();
        const zpidArray = zpidInput.split(',').map(zpid => zpid.trim());
        try {
            const response = await axios.post(`${process.env.REACT_APP_API_BASE_URL}/get-properties`, { zpids: zpidArray });
            setProperties(response.data);
            setError('');
            if (!selectedSearch) {
                saveSearch(zpidArray);
            }
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
            searches = [newSearch, ...searches].slice(0, 10);
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
        navigate(`/nearby-properties?zpid=${zpid}`);
    };

    const openParcelData = (zpid) => {
        navigate(`/parcel-data?zpid=${zpid}`);
    };

    const openMapView = () => {
        const zpidArray = zpidInput.split(',').map(zpid => zpid.trim());
        navigate(`/properties?zpids=${zpidArray.join(',')}`);
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
                    <button type="button" onClick={openMapView}>View on Map</button>
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
                            <th>Actions</th>
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
                                    <button onClick={() => openParcelData(property.zpid)}>
                                        View Parcel Data
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
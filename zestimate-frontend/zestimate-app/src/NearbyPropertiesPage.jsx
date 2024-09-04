import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';
import './NearbyPropertiesPage.css'; // Import the CSS file

function NearbyPropertiesPage() {
    const [searchParams] = useSearchParams();
    const zpid = searchParams.get('zpid');
    const [properties, setProperties] = useState([]);
    const [sourceProperty, setSourceProperty] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchSourceProperty = async () => {
            try {
                const response = await axios.post('http://localhost:5001/get-properties', { zpids: [zpid] });
                if (response.data.length > 0) {
                    setSourceProperty(response.data[0]);
                } else {
                    console.warn('No source property data found.');
                }
            } catch (error) {
                console.error('Error fetching source property:', error.message);
            }
        };

        const fetchNearbyProperties = async () => {
            try {
                const response = await axios.get(`http://localhost:5001/get-nearby-properties?zpid=${zpid}`);
                if (Array.isArray(response.data)) {
                    setProperties(response.data);
                } else {
                    console.warn('Nearby properties data is not an array.');
                }
            } catch (error) {
                console.error('Error fetching nearby properties:', error.message);
            }
        };

        if (zpid) {
            fetchSourceProperty();
            fetchNearbyProperties();
            setLoading(false);
        } else {
            console.error('No ZPID found in the URL.');
            setLoading(false);
        }
    }, [zpid]);

    return (
        <div className="container">
            <div className="properties-table">
                <h1>Nearby Properties</h1>
                {loading ? <p>Loading...</p> : (
                    <table>
                        <thead>
                            <tr>
                                <th>Address</th>
                                <th>Rental Zestimate</th>
                                <th>Zestimate</th>
                                <th>Cap Rate</th>
                                <th>Zillow URL</th>
                            </tr>
                        </thead>
                        <tbody>
                            {properties
                                .filter(property => property.address !== sourceProperty?.address) // Exclude the source property from the list
                                .map((property, index) => (
                                    <tr key={index}>
                                        <td>{property.address}</td>
                                        <td>{property.rentalZestimate.toLocaleString()}</td>
                                        <td>{property.zestimate.toLocaleString()}</td>
                                        <td>{property.capRate}</td>
                                        <td><a href={property.zillowUrl} target="_blank" rel="noopener noreferrer">View on Zillow</a></td>
                                    </tr>
                                ))
                            }
                        </tbody>
                    </table>
                )}
            </div>
            <div className="source-property">
                {sourceProperty ? (
                    <div>
                        <h2>Source Property</h2>
                        <p><strong>Address:</strong> {sourceProperty.address}</p>
                        <p><strong>Rental Zestimate:</strong> {sourceProperty.rentalZestimate.toLocaleString()}</p>
                        <p><strong>Zestimate:</strong> {sourceProperty.zestimate.toLocaleString()}</p>
                        <p><strong>Cap Rate:</strong> {(sourceProperty.rentalZestimate * 12 * 0.60 / sourceProperty.zestimate * 100).toFixed(2)}%</p>
                        <p><strong>Zillow URL:</strong> <a href={sourceProperty.zillowUrl} target="_blank" rel="noopener noreferrer">View on Zillow</a></p>
                    </div>
                ) : (
                    <p>Loading source property...</p>
                )}
            </div>
        </div>
    );
}

export default NearbyPropertiesPage;

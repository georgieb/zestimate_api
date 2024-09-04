import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';
import './ParcelDataPage.css';

function ParcelDataPage() {
    const [searchParams] = useSearchParams();
    const zpid = searchParams.get('zpid');
    const [parcelData, setParcelData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        const fetchParcelData = async () => {
            try {
                const response = await axios.post('http://localhost:5001/get-parcel-data', { zpids: [zpid] });
                if (response.data.length > 0) {
                    setParcelData(response.data[0]);
                } else {
                    setError('No parcel data found for this ZPID.');
                }
            } catch (error) {
                setError('Failed to fetch parcel data. Please try again.');
                console.error('Error fetching parcel data:', error);
            } finally {
                setLoading(false);
            }
        };

        if (zpid) {
            fetchParcelData();
        } else {
            setError('No ZPID provided.');
            setLoading(false);
        }
    }, [zpid]);

    if (loading) {
        return <div>Loading...</div>;
    }

    if (error) {
        return <div className="error-message">{error}</div>;
    }

    const formatValue = (value) => {
        if (Array.isArray(value)) return value.join(', ');
        if (typeof value === 'object' && value !== null) return JSON.stringify(value);
        return value || 'N/A';
    };

    const renderTable = (data, prefix = '') => {
        return Object.entries(data).map(([key, value]) => {
            const fullKey = prefix ? `${prefix}.${key}` : key;
            if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                return renderTable(value, fullKey);
            } else {
                return (
                    <tr key={fullKey}>
                        <th>{fullKey.charAt(0).toUpperCase() + fullKey.slice(1).replace(/([A-Z])/g, ' $1').trim()}</th>
                        <td>{formatValue(value)}</td>
                    </tr>
                );
            }
        });
    };

    return (
        <div className="parcel-data-container">
            <h1>Parcel Data</h1>
            {parcelData && (
                <table>
                    <tbody>
                        {renderTable(parcelData)}
                    </tbody>
                </table>
            )}
        </div>
    );
}

export default ParcelDataPage;
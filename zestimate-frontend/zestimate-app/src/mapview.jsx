import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import axios from 'axios';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default marker icon
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

function MapView() {
    const [properties, setProperties] = useState([]);
    const [error, setError] = useState('');
    const location = useLocation();

    useEffect(() => {
        const fetchProperties = async () => {
            const searchParams = new URLSearchParams(location.search);
            const zpids = searchParams.get('zpids').split(',');
            
            try {
                const response = await axios.post('http://localhost:5001/get-properties', { zpids });
                setProperties(response.data);
            } catch (error) {
                setError('Failed to fetch properties. Please try again.');
                console.error('Error fetching properties:', error);
            }
        };

        fetchProperties();
    }, [location]);

    if (error) {
        return <div className="error-message">{error}</div>;
    }

    // Calculate the center of the map
    const center = properties.length > 0
        ? [
            properties.reduce((sum, prop) => sum + prop.Latitude, 0) / properties.length,
            properties.reduce((sum, prop) => sum + prop.Longitude, 0) / properties.length
          ]
        : [25.761681, -80.191788]; // Default to Miami coordinates

    return (
        <div className="map-container">
            <h1>Property Map</h1>
            <MapContainer center={center} zoom={11} style={{ height: '1000px', width: '1860px' }}>
                <TileLayer
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                />
                {properties.map((property, index) => (
                    <Marker key={index} position={[property.Latitude, property.Longitude]}>
                        <Popup>
                            {property.address}<br />
                            Zestimate: ${property.zestimate?.toLocaleString()}<br />
                            Rental Zestimate: ${property.rentalZestimate?.toLocaleString()}<br />
                            Cap Rate: ${property.capRate}<br />
                            Zillow Link: <a href={property.zillowUrl} target="_blank" rel="noopener noreferrer">View on Zillow</a>
                        </Popup>
                    </Marker>
                ))}
            </MapContainer>
        </div>
    );
}

export default MapView;
// static/js/main.js
document.addEventListener('DOMContentLoaded', function() {
    // Helper Functions
    const safeNumber = (value, defaultValue = 0) => {
        if (value === null || value === undefined || isNaN(value)) {
            return defaultValue;
        }
        return Number(value);
    };

    const formatNumber = (number) => {
        return new Intl.NumberFormat('en-US').format(safeNumber(number));
    };

    const formatCurrency = (number) => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(safeNumber(number));
    };

    // Initialize Mapbox
    mapboxgl.accessToken = 'pk.eyJ1IjoiZ2JvcnJlcm8iLCJhIjoiY20zYzh1aXl4MXlpazJxcHNyeXBycnpxaCJ9.Scyic85rzjP_OLOeM4_F5w';
    const map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/streets-v11',
        center: [-98.5795, 39.8283],
        zoom: 3
    });

    let currentPortfolio = null;

    // Function to show loading state
    const setLoading = (isLoading) => {
        const analyzeBtn = document.getElementById('analyzeBtn');
        if (analyzeBtn) {
            analyzeBtn.disabled = isLoading;
            analyzeBtn.innerHTML = isLoading ? 
                '<span class="animate-pulse">Analyzing...</span>' : 
                'Analyze Portfolio';
        }
    };

    // Function to update the portfolio summary
    const updateSummary = (summary) => {
        document.getElementById('totalValue').textContent = formatCurrency(summary.total_value);
        document.getElementById('totalRental').textContent = formatCurrency(summary.total_rental);
        document.getElementById('avgCapRate').textContent = `${summary.avg_cap_rate.toFixed(2)}%`;
        document.getElementById('propertyCount').textContent = summary.property_count;
    };

    // Function to update the property list
    const updatePropertyList = (properties) => {
        const propertyList = document.getElementById('propertyList');
        propertyList.innerHTML = '';

        properties.forEach(property => {
            const sqft = safeNumber(property.livingArea);
            const zestimate = safeNumber(property.zestimate);
            const pricePerSqft = sqft > 0 ? zestimate / sqft : 0;
            
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50 cursor-pointer';
            row.innerHTML = `
                <td class="px-6 py-4">
                    <div class="flex flex-col">
                        <span class="font-medium">${property.address || 'N/A'}</span>
                        <span class="text-sm text-gray-500">${property.propertyType || 'N/A'}</span>
                    </div>
                </td>
                <td class="px-6 py-4 text-right">${formatCurrency(zestimate)}</td>
                <td class="px-6 py-4 text-right">${formatCurrency(safeNumber(property.rentalZestimate))}</td>
                <td class="px-6 py-4 text-right">${safeNumber(property.capRate).toFixed(2)}%</td>
                <td class="px-6 py-4 text-right">${safeNumber(property.bedrooms)}/${safeNumber(property.bathrooms)}</td>
                <td class="px-6 py-4 text-right">${formatNumber(sqft)} sqft</td>
                <td class="px-6 py-4 text-right">${formatCurrency(pricePerSqft)}/sqft</td>
                <td class="px-6 py-4 text-right">${property.yearBuilt || 'N/A'}</td>
            `;
            
            row.addEventListener('click', () => showPropertyDetails(property));
            propertyList.appendChild(row);
        });
    };

    // Function to update the map
    const updateMap = (properties) => {
        // Clear existing markers
        const markers = document.getElementsByClassName('mapboxgl-marker');
        while(markers[0]) {
            markers[0].parentNode.removeChild(markers[0]);
        }

        // Add new markers
        const bounds = new mapboxgl.LngLatBounds();
        let hasValidCoordinates = false;

        properties.forEach(property => {
            const lat = safeNumber(property.latitude || property.Latitude);
            const lng = safeNumber(property.longitude || property.Longitude);
            
            if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
                hasValidCoordinates = true;
                
                new mapboxgl.Marker()
                    .setLngLat([lng, lat])
                    .setPopup(new mapboxgl.Popup().setHTML(`
                        <div class="p-2">
                            <h3 class="font-bold text-sm mb-1">${property.address || 'N/A'}</h3>
                            <p class="text-sm">Zestimate: ${formatCurrency(property.zestimate)}</p>
                            <p class="text-sm">Cap Rate: ${safeNumber(property.capRate).toFixed(2)}%</p>
                            <p class="text-sm">${property.bedrooms || 0} beds, ${property.bathrooms || 0} baths</p>
                            <p class="text-sm">${formatNumber(property.livingArea || 0)} sqft</p>
                        </div>
                    `))
                    .addTo(map);

                bounds.extend([lng, lat]);
            }
        });

        if (hasValidCoordinates) {
            map.fitBounds(bounds, {
                padding: 50,
                maxZoom: 15
            });
        }
    };

    // Function to show property details
    const showPropertyDetails = (property) => {
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center p-4 z-50';
        modal.innerHTML = `
            <div class="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
                <div class="p-6">
                    <div class="flex justify-between items-start mb-4">
                        <h2 class="text-xl font-bold">${property.address || 'N/A'}</h2>
                        <button class="text-gray-400 hover:text-gray-600" onclick="this.closest('.fixed').remove()">×</button>
                    </div>
                    
                    <div class="grid grid-cols-2 gap-4 mb-6">
                        <div>
                            <h3 class="font-medium text-gray-700">Property Details</h3>
                            <dl class="mt-2 space-y-1">
                                <div class="flex justify-between">
                                    <dt class="text-gray-500">Type:</dt>
                                    <dd>${property.propertyType || 'N/A'}</dd>
                                </div>
                                <div class="flex justify-between">
                                    <dt class="text-gray-500">Year Built:</dt>
                                    <dd>${property.yearBuilt || 'N/A'}</dd>
                                </div>
                                <div class="flex justify-between">
                                    <dt class="text-gray-500">Bedrooms:</dt>
                                    <dd>${safeNumber(property.bedrooms)}</dd>
                                </div>
                                <div class="flex justify-between">
                                    <dt class="text-gray-500">Bathrooms:</dt>
                                    <dd>${safeNumber(property.bathrooms)}</dd>
                                </div>
                                <div class="flex justify-between">
                                    <dt class="text-gray-500">Living Area:</dt>
                                    <dd>${formatNumber(property.livingArea)} sqft</dd>
                                </div>
                                <div class="flex justify-between">
                                    <dt class="text-gray-500">Lot Size:</dt>
                                    <dd>${formatNumber(property.lotSize)} sqft</dd>
                                </div>
                            </dl>
                        </div>
                        
                        <div>
                            <h3 class="font-medium text-gray-700">Financial Details</h3>
                            <dl class="mt-2 space-y-1">
                                <div class="flex justify-between">
                                    <dt class="text-gray-500">Zestimate:</dt>
                                    <dd>${formatCurrency(property.zestimate)}</dd>
                                </div>
                                <div class="flex justify-between">
                                    <dt class="text-gray-500">Monthly Rent:</dt>
                                    <dd>${formatCurrency(property.rentalZestimate)}</dd>
                                </div>
                                <div class="flex justify-between">
                                    <dt class="text-gray-500">Cap Rate:</dt>
                                    <dd>${safeNumber(property.capRate).toFixed(2)}%</dd>
                                </div>
                                <div class="flex justify-between">
                                    <dt class="text-gray-500">Price/Sqft:</dt>
                                    <dd>${formatCurrency(safeNumber(property.zestimate) / safeNumber(property.livingArea, 1))}/sqft</dd>
                                </div>
                                <div class="flex justify-between">
                                    <dt class="text-gray-500">Last Sale Price:</dt>
                                    <dd>${formatCurrency(property.lastSalePrice)}</dd>
                                </div>
                                <div class="flex justify-between">
                                    <dt class="text-gray-500">Last Sale Date:</dt>
                                    <dd>${property.lastSaleDate || 'N/A'}</dd>
                                </div>
                            </dl>
                        </div>
                    </div>

                    <button onclick="getNearbyProperties('${property.zpid}')"
                            class="mt-4 bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">
                        Show Nearby Properties
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    };

    // Function to get nearby properties
    const getNearbyProperties = async (zpid) => {
        try {
            setLoading(true);
            const response = await fetch(`/api/nearby-properties/${zpid}`);
            if (!response.ok) throw new Error('Failed to fetch nearby properties');
            
            const properties = await response.json();
            updatePropertyList(properties);
            updateMap(properties);
        } catch (error) {
            alert('Error fetching nearby properties: ' + error.message);
        } finally {
            setLoading(false);
        }
    };

    // Function to load portfolio from URL
    async function loadPortfolio(portfolioName) {
        try {
            setLoading(true);
            const response = await fetch(`/api/load-portfolio/${encodeURIComponent(portfolioName)}`);
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to load portfolio');
            }
            
            const portfolioData = await response.json();
            
            // Update the UI
            document.getElementById('portfolioName').value = portfolioData.name;
            document.getElementById('zpidInput').value = portfolioData.properties.map(p => p.zpid).join(',');
            
            updateSummary(portfolioData.summary);
            updatePropertyList(portfolioData.properties);
            updateMap(portfolioData.properties);
            
        } catch (error) {
            alert('Error loading portfolio: ' + error.message);
        } finally {
            setLoading(false);
        }
    }
    // Function to analyze portfolio
    // Update the analyzePortfolio function in main.js
const analyzePortfolio = async () => {
    const zpidInput = document.getElementById('zpidInput').value;
    const zpids = zpidInput.split(',').map(zpid => zpid.trim());

    try {
        setLoading(true);
        const response = await fetch('/api/properties', { // Note the URL change
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ zpids })
        });

        if (!response.ok) throw new Error('Failed to fetch property data');

        const data = await response.json();
        currentPortfolio = {
            name: document.getElementById('portfolioName').value,
            zpids,
            data
        };

        updateSummary(data.summary);
        updatePropertyList(data.properties);
        updateMap(data.properties);
    } catch (error) {
        alert('Error analyzing portfolio: ' + error.message);
    } finally {
        setLoading(false);
    }
};

    // Event Listeners
    document.getElementById('analyzeBtn')?.addEventListener('click', analyzePortfolio);

    document.getElementById('savePortfolioBtn')?.addEventListener('click', async () => {
        if (!currentPortfolio) {
            alert('Please analyze a portfolio first');
            return;
        }

        try {
            const response = await fetch('/api/save-portfolio', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(currentPortfolio)
            });

            if (!response.ok) throw new Error('Failed to save portfolio');

            alert('Portfolio saved successfully!');
        } catch (error) {
            alert('Error saving portfolio: ' + error.message);
        }
    });

    // Make getNearbyProperties globally available
    window.getNearbyProperties = getNearbyProperties;

    // Load portfolio from URL if present
    loadPortfolio();
});
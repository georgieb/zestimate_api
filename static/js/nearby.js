// Reuse your existing helper functions (formatNumber, formatCurrency, etc.)
// But create specific functions for the nearby properties page

const updatePropertyList = (properties) => {
    const propertyList = document.getElementById('nearbyPropertiesList');
    propertyList.innerHTML = '';

    properties.forEach(property => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-50';
        row.innerHTML = `
            <td class="px-6 py-4">
                <div class="flex flex-col">
                    <span class="font-medium">${property.address || 'N/A'}</span>
                    <span class="text-sm text-gray-500">${property.propertyType || 'N/A'}</span>
                </div>
            </td>
            <td class="px-6 py-4 text-right">${formatCurrency(property.zestimate)}</td>
            <td class="px-6 py-4 text-right">${formatCurrency(property.rentalZestimate)}</td>
            <td class="px-6 py-4 text-right">${property.capRate.toFixed(2)}%</td>
            <td class="px-6 py-4 text-right">${property.bedrooms}/${property.bathrooms}</td>
            <td class="px-6 py-4 text-right">${formatNumber(property.livingArea)} sqft</td>
            <td class="px-6 py-4 text-right">${formatCurrency(property.pricePerSqft)}/sqft</td>
            <td class="px-6 py-4 text-right">${property.yearBuilt || 'N/A'}</td>
        `;
        propertyList.appendChild(row);
    });
};  
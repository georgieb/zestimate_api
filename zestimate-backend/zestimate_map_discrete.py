import folium

# Postal codes and their coordinates
postal_codes_coordinates = {
    "33054": [(25.9023, -80.2789), (25.8808, -80.2868), (25.8788, -80.2565), (25.8935, -80.2507)],
    "33055": [(25.9191, -80.3415), (25.8997, -80.3376), (25.9046, -80.3181), (25.9207, -80.3218)],
    "33056": [(25.9623, -80.2898), (25.9267, -80.2993), (25.9282, -80.2627), (25.9594, -80.2524)],
    "33127": [(25.8109, -80.2371), (25.8151, -80.2215), (25.8144, -80.2145), (25.8110, -80.2089)],
    "33142": [(25.8181, -80.2422), (25.8074, -80.2435), (25.8067, -80.2364), (25.8167, -80.2331)],
    "33147": [(25.8463, -80.2493), (25.8353, -80.2478), (25.8388, -80.2359), (25.8488, -80.2389)],
    "33150": [(25.8669, -80.2299), (25.8555, -80.2279), (25.8571, -80.2146), (25.8671, -80.2176)],
    "33162": [(25.9563, -80.1861), (25.9403, -80.1941), (25.9421, -80.1757), (25.9578, -80.1676)],
    "33167": [(25.8979, -80.2273), (25.8816, -80.2294), (25.8830, -80.1989), (25.8988, -80.1972)],
    "33168": [(25.9177, -80.2472), (25.9064, -80.2452), (25.9081, -80.2257), (25.9198, -80.2277)],
    "33169": [(25.9617, -80.2109), (25.9304, -80.2199), (25.9319, -80.1920), (25.9614, -80.1841)],
    "33181": [(25.9240, -80.1671), (25.9005, -80.1746), (25.9020, -80.1436), (25.9230, -80.1436)]
}

# Extract latitude and longitude values from the coordinates
all_latitudes = [coord[0] for coords in postal_codes_coordinates.values() for coord in coords]
all_longitudes = [coord[1] for coords in postal_codes_coordinates.values() for coord in coords]

# Find the minimum and maximum latitude and longitude values
min_latitude = min(all_latitudes)
max_latitude = max(all_latitudes)
min_longitude = min(all_longitudes)
max_longitude = max(all_longitudes)

# Calculate center of the circular boundary
center_lat = (min_latitude + max_latitude) / 2
center_lon = (min_longitude + max_longitude) / 2

# Calculate radius of the circular boundary
radius = max(max_latitude - min_latitude, max_longitude - min_longitude) / 2

# Create a map centered at the center of the circular boundary
m = folium.Map(location=[center_lat, center_lon], zoom_start=11)

# Add a circle to represent the circular boundary
folium.Circle(
    location=[center_lat, center_lon],
    radius=radius * 100000,  # Convert radius to meters
    color='#0371C0',
    fill=True,
    fill_color='#0371C0',
    fill_opacity=0.2
).add_to(m)

# Save the map to an HTML file
m.save("postal_code_boundary_circle.html")

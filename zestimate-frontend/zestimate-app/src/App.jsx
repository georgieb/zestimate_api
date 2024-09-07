import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import ZPIDDashboard from './ZPIDDashboard';
import NearbyPropertiesPage from './NearbyPropertiesPage';
import ParcelDataPage from './ParcelDataPage';
import MapView from './mapview';
import 'leaflet/dist/leaflet.css';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<ZPIDDashboard />} />
        <Route path="/nearby-properties" element={<NearbyPropertiesPage />} />
        <Route path="/parcel-data" element={<ParcelDataPage />} />
        <Route path="/properties" element={<MapView />} />
      </Routes>
    </Router>
  );
}

export default App;
import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import ZPIDDashboard from "./ZPIDDashboard";
import NearbyPropertiesPage from "./NearbyPropertiesPage";

function App() {
    return (
        <Router>
            <Routes>
                <Route path="/" element={<ZPIDDashboard />} />
                <Route path="/nearby-properties" element={<NearbyPropertiesPage />} />
            </Routes>
        </Router>
    );
}

export default App;

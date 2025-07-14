import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import NavBar from './components/NavBar';
import PrivateRoute from './components/PrivateRoute';
import Home from './pages/Home';
import About from './pages/About';
import Benchmark from './pages/Benchmark';
import Metrics from './pages/Metrics';
import Login from './pages/Login';
import CompareMetrics from './pages/CompareMetrics';


function App() {
  return (
    <Router>
      <NavBar />

      <Routes>
        { /* public route */ }
        <Route path="/login" element={<Login />} />

        { /* everything else requires auth */ }
        <Route element={<PrivateRoute />}>
          <Route path="/" element={<Home />} />
          <Route path="/about" element={<About />} />
          <Route path="/benchmark" element={<Benchmark />} />
          <Route path="/metrics" element={<Metrics />} />
          <Route path="/metrics/compare" element={<CompareMetrics />} />
          { /* catch-all: redirect unknown URLs back to home */ }
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;

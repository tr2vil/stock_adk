import React from 'react';
import Navbar from './components/Navbar';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';

import Dashboard from './pages/Dashboard';
import StockAnalysis from './pages/StockAnalysis';
import Portfolio from './pages/Portfolio';
import Strategy from './pages/Strategy';
import Settings from './pages/Settings';

function App() {
    return (
        <Router>
            <div className="app-container min-vh-100 bg-light">
                <Navbar />
                <main>
                    <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/stock-analysis" element={<StockAnalysis />} />
                        <Route path="/portfolio" element={<Portfolio />} />
                        <Route path="/strategy" element={<Strategy />} />
                        <Route path="/settings" element={<Settings />} />
                    </Routes>
                </main>
            </div>
        </Router>
    );
}

export default App;

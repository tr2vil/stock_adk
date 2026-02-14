import React from 'react';
import Navbar from './components/Navbar';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { MessageSquare } from 'lucide-react';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';

import Dashboard from './pages/Dashboard';
import AIAssistant from './pages/AIAssistant';
import StockAnalysis from './pages/StockAnalysis';
import Settings from './pages/Settings';

function App() {
    return (
        <Router>
            <div className="app-container min-vh-100 bg-light">
                <Navbar />
                <main>
                    <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/ai-assistant" element={<AIAssistant />} />
                        <Route path="/stock-analysis" element={<StockAnalysis />} />
                        <Route path="/portfolio" element={<div className="container mt-4"><h2>포트폴리오</h2><p>준비중입니다.</p></div>} />
                        <Route path="/settings" element={<Settings />} />
                    </Routes>
                </main>
            </div>
        </Router>
    );
}

export default App;

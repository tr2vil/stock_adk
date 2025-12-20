import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, MessageSquare, Briefcase, BarChart3, Settings } from 'lucide-react';
import styles from './Navbar.module.css';

const Navbar = () => {
    return (
        <nav className="navbar navbar-expand-lg navbar-dark bg-dark sticky-top shadow-sm">
            <div className="container-fluid">
                <NavLink className={`navbar-brand d-flex align-items-center ${styles.navbarBrand}`} to="/">
                    <BarChart3 className="me-2 text-primary" size={24} />
                    <span className="fw-bold">StockADK</span>
                </NavLink>

                <button className="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                    <span className="navbar-toggler-icon"></span>
                </button>

                <div className="collapse navbar-collapse" id="navbarNav">
                    <ul className="navbar-nav me-auto mb-2 mb-lg-0">
                        <li className="nav-item">
                            <NavLink
                                className={({ isActive }) => `nav-link d-flex align-items-center ${styles.navLink} ${isActive ? styles.activeLink : ''}`}
                                to="/"
                            >
                                <LayoutDashboard size={18} className="me-1" /> 대시보드
                            </NavLink>
                        </li>
                        <li className="nav-item">
                            <NavLink
                                className={({ isActive }) => `nav-link d-flex align-items-center ${styles.navLink} ${isActive ? styles.activeLink : ''}`}
                                to="/ai-assistant"
                            >
                                <MessageSquare size={18} className="me-1" /> AI 비서 (A2UI)
                            </NavLink>
                        </li>
                        <li className="nav-item">
                            <NavLink
                                className={({ isActive }) => `nav-link d-flex align-items-center ${styles.navLink} ${isActive ? styles.activeLink : ''}`}
                                to="/portfolio"
                            >
                                <Briefcase size={18} className="me-1" /> 포트폴리오
                            </NavLink>
                        </li>
                    </ul>

                    <div className="d-flex align-items-center text-light">
                        <div className="me-3 small d-none d-md-block">
                            <span className="badge bg-success me-1">Backend Online</span>
                            <span className="badge bg-primary">Gemini 2.5 Flash</span>
                        </div>
                        <button className="btn btn-outline-light btn-sm">
                            <Settings size={18} />
                        </button>
                    </div>
                </div>
            </div>
        </nav>
    );
};

export default Navbar;

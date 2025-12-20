import React from 'react';
import styles from './Dashboard.module.css';

const Dashboard = () => {
    // In a real scenario, this would be the URL of a specific Grafana dashboard
    // For now, we point to the main Grafana instance
    const grafanaUrl = "http://localhost:3001";

    return (
        <div className={styles.dashboardWrapper}>
            <iframe
                src={grafanaUrl}
                className={styles.grafanaIframe}
                title="Grafana Dashboard"
                frameBorder="0"
            />
        </div>
    );
};

export default Dashboard;

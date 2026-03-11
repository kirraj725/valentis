import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Login from './pages/Login';
import TOTPVerify from './pages/TOTPVerify';
import Dashboard from './pages/Dashboard';
import FraudAlerts from './pages/FraudAlerts';
import FraudFlagged from './pages/FraudFlagged';
import FraudHighConfidence from './pages/FraudHighConfidence';
import AnomalyMonitor from './pages/AnomalyMonitor';
import DepartmentDetail from './pages/DepartmentDetail';
import AccountDrillDown from './pages/AccountDrillDown';
import PaymentPlans from './pages/PaymentPlans';
import AuditLog from './pages/AuditLog';
import Upload from './pages/Upload';
import CSVViewer from './pages/CSVViewer';
import PaymentHistory from './pages/PaymentHistory';
import AuditAlertDetail from './pages/AuditAlertDetail';
import ClaimsOverview from './pages/ClaimsOverview';
import FlaggedClaims from './pages/FlaggedClaims';
import AIInsights from './pages/AIInsights';

function AppContent() {
    const { authStep } = useAuth();
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);

    // Step 1: Show Login page
    if (authStep === 'login') return <Login />;

    // Step 2: Show TOTP verification page
    if (authStep === 'totp') return <TOTPVerify />;

    // Step 3: Authenticated — show full app
    return (
        <div className={`app-layout ${!isSidebarOpen ? 'app-layout--collapsed' : ''}`}>
            <Sidebar isOpen={isSidebarOpen} toggle={() => setIsSidebarOpen(prev => !prev)} />
            <div className="main-content">
                <Header />
                <div className="page-container">
                    <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/fraud" element={<FraudAlerts />} />
                        <Route path="/fraud/flagged" element={<FraudFlagged />} />
                        <Route path="/fraud/high-confidence" element={<FraudHighConfidence />} />
                        <Route path="/anomalies" element={<AnomalyMonitor />} />
                        <Route path="/anomalies/department" element={<DepartmentDetail />} />
                        <Route path="/accounts/:id" element={<AccountDrillDown />} />
                        <Route path="/plans" element={<PaymentPlans />} />
                        <Route path="/audit" element={<AuditLog />} />
                        <Route path="/claims" element={<ClaimsOverview />} />
                        <Route path="/claims/flagged" element={<FlaggedClaims />} />
                        <Route path="/claims/insights" element={<AIInsights />} />
                        <Route path="/upload" element={<Upload />} />
                        <Route path="/upload/view/:filename" element={<CSVViewer />} />
                        <Route path="/plans/history/:accountId" element={<PaymentHistory />} />
                        <Route path="/audit/user/:userId" element={<AuditAlertDetail />} />
                    </Routes>
                </div>
            </div>
        </div>
    );
}

function App() {
    return (
        <Router>
            <AuthProvider>
                <AppContent />
            </AuthProvider>
        </Router>
    );
}

export default App;

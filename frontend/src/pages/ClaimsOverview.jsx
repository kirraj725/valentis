import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import StatCard from '../components/StatCard';
import { getAnomalyStats, runAnalysis } from '../services/api';

export default function ClaimsOverview() {
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [analyzing, setAnalyzing] = useState(false);
    const [result, setResult] = useState(null);
    const navigate = useNavigate();

    const loadStats = () => {
        setLoading(true);
        getAnomalyStats()
            .then((r) => setStats(r.data))
            .catch(() => setStats(null))
            .finally(() => setLoading(false));
    };

    useEffect(() => { loadStats(); }, []);

    const handleRunAnalysis = () => {
        setAnalyzing(true);
        setResult(null);
        runAnalysis()
            .then((r) => {
                setResult(r.data);
                loadStats();
            })
            .catch((e) => setResult({ status: 'error', message: e.response?.data?.detail || 'Analysis failed' }))
            .finally(() => setAnalyzing(false));
    };

    if (loading) {
        return <div className="loading"><div className="loading__spinner"></div>Loading claims data...</div>;
    }

    return (
        <div className="page page--claims-overview">
            <div className="page__header">
                <h1>Claims Intelligence</h1>
                <p>ML-powered anomaly detection on your billing data</p>
            </div>

            <div className="stats-grid">
                <StatCard
                    icon="📋"
                    title="Total Claims"
                    value={stats?.total_claims?.toLocaleString() || '0'}
                    status="info"
                />
                <StatCard
                    icon="🚨"
                    title="Flagged Anomalies"
                    value={stats?.total_flagged?.toLocaleString() || '0'}
                    status="danger"
                />
                <StatCard
                    icon="📊"
                    title="Flagged Rate"
                    value={`${stats?.flagged_percentage || 0}%`}
                    status="warning"
                />
                <StatCard
                    icon="✅"
                    title="Pending Review"
                    value={stats?.pending_review?.toLocaleString() || '0'}
                    status="success"
                />
            </div>

            {stats?.date_range?.start && (
                <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
                    <div className="card__header">
                        <h3>Data Coverage</h3>
                        <span className="badge">{stats.date_range.start} → {stats.date_range.end}</span>
                    </div>
                </div>
            )}

            <div className="claims-actions">
                <button
                    className="btn btn--primary btn--lg"
                    onClick={handleRunAnalysis}
                    disabled={analyzing}
                    id="run-analysis-btn"
                >
                    {analyzing ? (
                        <><div className="loading__spinner" style={{ width: 16, height: 16, borderWidth: 2 }}></div> Running Isolation Forest...</>
                    ) : '🔬 Run Anomaly Detection'}
                </button>

                <button
                    className="btn btn--secondary"
                    onClick={() => navigate('/claims/flagged')}
                    id="view-flagged-btn"
                >
                    View Flagged Claims →
                </button>

                <button
                    className="btn btn--secondary"
                    onClick={() => navigate('/claims/insights')}
                    id="view-insights-btn"
                >
                    AI Insights →
                </button>
            </div>

            {result && (
                <div className={`card analysis-result ${result.status === 'error' ? 'analysis-result--error' : ''}`}>
                    <div className="card__header">
                        <h3>{result.status === 'error' ? '❌ Error' : '✅ Analysis Complete'}</h3>
                    </div>
                    <div style={{ padding: 'var(--space-5) var(--space-6)' }}>
                        {result.status === 'error' ? (
                            <p style={{ color: 'var(--color-danger)' }}>{result.message}</p>
                        ) : (
                            <div className="analysis-result__grid">
                                <div><strong>{result.total_scored?.toLocaleString()}</strong> claims scored</div>
                                <div><strong>{result.new_flags?.toLocaleString()}</strong> new anomalies flagged</div>
                                <div><strong>{result.flagged_percentage}%</strong> flagged rate</div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

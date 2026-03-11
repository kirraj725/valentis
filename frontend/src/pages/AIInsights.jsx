import React, { useEffect, useState } from 'react';
import { generateInsights, getInsights } from '../services/api';

export default function AIInsights() {
    const [summaries, setSummaries] = useState([]);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [genTime, setGenTime] = useState(null);

    useEffect(() => {
        getInsights()
            .then((r) => setSummaries(r.data.summaries || []))
            .finally(() => setLoading(false));
    }, []);

    const handleRegenerate = () => {
        setGenerating(true);
        generateInsights()
            .then((r) => {
                setSummaries(r.data.summaries || []);
                setGenTime(r.data.generation_time_seconds);
            })
            .catch((e) => console.error('Insight generation failed', e))
            .finally(() => setGenerating(false));
    };

    if (loading) {
        return <div className="loading"><div className="loading__spinner"></div>Loading insights...</div>;
    }

    return (
        <div className="page page--ai-insights">
            <div className="page__header">
                <h1>AI Revenue Insights</h1>
                <p>LLM-generated provider analysis and revenue integrity summaries</p>
            </div>

            <div className="insight-disclaimer">
                <span className="insight-disclaimer__icon">ℹ️</span>
                <span>These insights are <strong>AI-generated for human review</strong> — they are advisory only, not automated decisions.</span>
            </div>

            <div className="insight-actions">
                <button
                    className="btn btn--primary"
                    onClick={handleRegenerate}
                    disabled={generating}
                    id="regenerate-insights-btn"
                >
                    {generating ? (
                        <><div className="loading__spinner" style={{ width: 16, height: 16, borderWidth: 2 }}></div> Generating...</>
                    ) : '🔄 Regenerate Insights'}
                </button>
                {genTime && (
                    <span style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
                        Generated in {genTime}s
                    </span>
                )}
            </div>

            {summaries.length === 0 ? (
                <div className="card" style={{ padding: '2rem', textAlign: 'center' }}>
                    <p style={{ color: 'var(--color-text-secondary)' }}>
                        No insights generated yet. Click "Regenerate Insights" to analyze flagged anomalies.
                    </p>
                </div>
            ) : (
                <div className="insight-grid">
                    {summaries.map((s, i) => (
                        <div key={i} className="insight-card">
                            <div className="insight-card__header">
                                <div className="insight-card__provider">
                                    <span className="insight-card__provider-icon">🏥</span>
                                    <strong>{s.provider_id}</strong>
                                </div>
                                <div className="insight-card__meta">
                                    <span className="badge">{s.claim_count} claims</span>
                                    <span className={`score-badge ${s.avg_anomaly_score < -0.2 ? 'score-badge--critical' : s.avg_anomaly_score < -0.1 ? 'score-badge--warning' : 'score-badge--low'}`}>
                                        Score: {s.avg_anomaly_score.toFixed(3)}
                                    </span>
                                </div>
                            </div>
                            <div className="insight-card__body">
                                <p>{s.summary}</p>
                            </div>
                            <div className="insight-card__footer">
                                <span className="insight-card__source">
                                    {s.source === 'anthropic' ? '🤖 Claude' : '📊 Rule-based'}
                                </span>
                                <span className="insight-card__time">
                                    {new Date(s.generated_at).toLocaleString()}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

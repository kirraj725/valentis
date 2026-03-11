import React, { useEffect, useState } from 'react';
import { getMLAnomalies, patchAnomalyReviewed } from '../services/api';

export default function FlaggedClaims() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [filter, setFilter] = useState(null); // null = all, true = reviewed, false = pending
    const perPage = 25;

    const loadData = (p = page, reviewed = filter) => {
        setLoading(true);
        getMLAnomalies(p, perPage, reviewed)
            .then((r) => setData(r.data))
            .finally(() => setLoading(false));
    };

    useEffect(() => { loadData(); }, []);

    const handlePageChange = (newPage) => {
        setPage(newPage);
        loadData(newPage, filter);
    };

    const handleFilterChange = (newFilter) => {
        setFilter(newFilter);
        setPage(1);
        loadData(1, newFilter);
    };

    const handleMarkReviewed = async (id) => {
        try {
            await patchAnomalyReviewed(id);
            loadData(page, filter);
        } catch (e) {
            console.error('Failed to update review status', e);
        }
    };

    const severityFromScore = (score) => {
        if (score < -0.2) return { label: 'Critical', color: 'var(--color-danger)', bg: 'rgba(248, 113, 113, 0.15)' };
        if (score < -0.1) return { label: 'Warning', color: 'var(--color-warning)', bg: 'rgba(251, 191, 36, 0.15)' };
        return { label: 'Low', color: 'var(--color-success)', bg: 'rgba(52, 211, 153, 0.15)' };
    };

    if (loading && !data) {
        return <div className="loading"><div className="loading__spinner"></div>Loading flagged claims...</div>;
    }

    const pagination = data?.pagination || {};
    const flags = data?.flags || [];

    return (
        <div className="page page--flagged-claims">
            <div className="page__header">
                <h1>Flagged Claims</h1>
                <p>Anomalies detected by Isolation Forest — review and resolve</p>
            </div>

            <div className="flagged-filters">
                <button
                    className={`btn btn--sm ${filter === null ? 'btn--primary' : 'btn--ghost'}`}
                    onClick={() => handleFilterChange(null)}
                >All ({pagination.total || 0})</button>
                <button
                    className={`btn btn--sm ${filter === false ? 'btn--primary' : 'btn--ghost'}`}
                    onClick={() => handleFilterChange(false)}
                >Pending Review</button>
                <button
                    className={`btn btn--sm ${filter === true ? 'btn--primary' : 'btn--ghost'}`}
                    onClick={() => handleFilterChange(true)}
                >Reviewed</button>
            </div>

            <div className="card">
                <div className="data-table-wrapper">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Claim ID</th>
                                <th>Anomaly Score</th>
                                <th>Severity</th>
                                <th>Flag Reason</th>
                                <th>Status</th>
                                <th>Flagged At</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {flags.map((f) => {
                                const sev = severityFromScore(f.anomaly_score);
                                return (
                                    <tr key={f.id}>
                                        <td><code>{f.claim_id}</code></td>
                                        <td>
                                            <span style={{
                                                padding: '2px 10px', borderRadius: '12px',
                                                fontWeight: 700, fontSize: '0.85rem',
                                                background: sev.bg, color: sev.color,
                                            }}>
                                                {f.anomaly_score.toFixed(3)}
                                            </span>
                                        </td>
                                        <td>
                                            <span style={{
                                                padding: '2px 10px', borderRadius: '12px',
                                                fontSize: '0.8rem', fontWeight: 600,
                                                background: sev.bg, color: sev.color,
                                            }}>
                                                {sev.label}
                                            </span>
                                        </td>
                                        <td style={{ whiteSpace: 'normal', maxWidth: 300 }}>{f.flag_reason}</td>
                                        <td>
                                            <span className={`review-badge ${f.reviewed ? 'review-badge--reviewed' : 'review-badge--pending'}`}>
                                                {f.reviewed ? '✅ Reviewed' : '⏳ Pending'}
                                            </span>
                                        </td>
                                        <td style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)' }}>
                                            {f.flagged_at ? new Date(f.flagged_at).toLocaleDateString() : '—'}
                                        </td>
                                        <td>
                                            <button
                                                className={`btn btn--sm ${f.reviewed ? 'btn--ghost' : 'btn--accent'}`}
                                                onClick={() => handleMarkReviewed(f.id)}
                                                id={`review-btn-${f.id}`}
                                            >
                                                {f.reviewed ? 'Undo' : 'Mark Reviewed'}
                                            </button>
                                        </td>
                                    </tr>
                                );
                            })}
                            {flags.length === 0 && (
                                <tr><td colSpan={7} style={{ textAlign: 'center', padding: '2rem', color: 'var(--color-text-secondary)' }}>
                                    No flagged claims found. Run analysis first.
                                </td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {pagination.total_pages > 1 && (
                <div className="pagination">
                    <button
                        className="btn btn--sm btn--ghost"
                        disabled={page <= 1}
                        onClick={() => handlePageChange(page - 1)}
                    >← Previous</button>
                    <span className="pagination__info">
                        Page {pagination.page} of {pagination.total_pages} ({pagination.total} total)
                    </span>
                    <button
                        className="btn btn--sm btn--ghost"
                        disabled={page >= pagination.total_pages}
                        onClick={() => handlePageChange(page + 1)}
                    >Next →</button>
                </div>
            )}
        </div>
    );
}

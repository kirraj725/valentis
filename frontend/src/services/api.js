/**
 * API client for ClearCollect AI backend.
 */
import axios from 'axios';

const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || '/api',
    headers: { 'Content-Type': 'application/json' },
});

export const uploadData = (fileOrFormData, isMulti = false) => {
    if (isMulti) {
        // Already a FormData with multiple files
        return api.post('/upload/multi', fileOrFormData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
    }
    const formData = new FormData();
    formData.append('file', fileOrFormData);
    return api.post('/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    });
};

export const getRiskScores = () => api.get('/risk/scores');
export const getAccountRisk = (id) => api.get(`/risk/scores/${id}`);
export const getFraudAlerts = () => api.get('/fraud/alerts');
export const getAnomalies = () => api.get('/anomaly/alerts');
export const getHeatmap = () => api.get('/anomaly/heatmap');
export const getForecast = () => api.get('/forecast');
export const getAllPlans = () => api.get('/plans');
export const getPaymentPlan = (id) => api.get(`/plans/${id}`);
export const getAuditLogs = () => api.get('/audit/logs');
export const getAccessAlerts = () => api.get('/audit/access');
export const getExportLogs = () => api.get('/audit/exports');

// ML Analysis & Anomaly Detection
export const runAnalysis = () => api.post('/analyze');
export const getMLAnomalies = (page = 1, perPage = 25, reviewed = null) => {
    const params = { page, per_page: perPage };
    if (reviewed !== null) params.reviewed = reviewed;
    return api.get('/anomalies', { params });
};
export const patchAnomalyReviewed = (id) => api.patch(`/anomalies/${id}`);
export const getAnomalyStats = () => api.get('/anomalies/stats');

// AI Insights
export const generateInsights = () => api.post('/insights/generate');
export const getInsights = () => api.get('/insights');

export default api;

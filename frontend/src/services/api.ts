/**
 * API service for TerraWatch frontend.
 * Handles all REST API communication with the backend.
 */

const API_BASE = '/api/v1';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body || res.statusText);
  }
  return res.json();
}

export const api = {
  // Soil Analysis
  analyzeSoil(lat: number, lon: number, depth?: number) {
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon) });
    if (depth) params.set('depth_cm', String(depth));
    return request<any>(`/soil/analyze?${params}`);
  },

  getSoilHistory(lat: number, lon: number, radius?: number) {
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon) });
    if (radius) params.set('radius_km', String(radius));
    return request<any>(`/soil/history?${params}`);
  },

  // Risk Assessment
  assessRisk(lat: number, lon: number) {
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon) });
    return request<any>(`/risk/all?${params}`);
  },

  getEarthquakes(days?: number, minMagnitude?: number) {
    const params = new URLSearchParams();
    if (days) params.set('days', String(days));
    if (minMagnitude) params.set('min_magnitude', String(minMagnitude));
    return request<any>(`/risk/earthquake/recent?${params}`);
  },

  getSpecificRisk(type: string, lat: number, lon: number) {
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon) });
    return request<any>(`/risk/${type}?${params}`);
  },

  // Recommendations
  getAgricultureRecs(lat: number, lon: number) {
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon) });
    return request<any>(`/recommendations/agriculture?${params}`);
  },

  getDisasterPrep(lat: number, lon: number) {
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon) });
    return request<any>(`/recommendations/disaster?${params}`);
  },

  getRestorationRecs(lat: number, lon: number) {
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon) });
    return request<any>(`/recommendations/environmental?${params}`);
  },

  // Alerts
  getActiveAlerts() {
    return request<any>('/alerts/active');
  },

  getAlertHistory(limit?: number) {
    const params = new URLSearchParams();
    if (limit) params.set('limit', String(limit));
    return request<any>(`/alerts/history?${params}`);
  },

  // Export
  exportCsv(lat: number, lon: number, radius?: number) {
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon) });
    if (radius) params.set('radius_km', String(radius));
    return `${API_BASE}/export/soil/csv?${params}`;
  },

  exportGeojson(lat: number, lon: number, radius?: number) {
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon) });
    if (radius) params.set('radius_km', String(radius));
    return `${API_BASE}/export/soil/geojson?${params}`;
  },

  exportRiskGeojson(lat: number, lon: number, radius?: number) {
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon) });
    if (radius) params.set('radius_km', String(radius));
    return `${API_BASE}/export/risk/geojson?${params}`;
  },

  // Export report
  exportReport(lat: number, lon: number) {
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon) });
    return `${API_BASE}/export/report?${params}`;
  },

  // Health
  health() {
    return request<any>('/health');
  },
};

export default api;

/**
 * API client for TerraWatch.
 *
 * All requests are relative to the page origin and go through `/api/v1`,
 * so the same build works behind the Vite dev proxy, nginx, or the
 * single-container FastAPI deployment.
 */

const API_BASE = '/api/v1';
const DEFAULT_TIMEOUT_MS = 45_000;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value));
    }
  }
  return search.toString();
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

  const headers = new Headers(options.headers);
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
      signal: controller.signal,
    });

    if (!res.ok) {
      let detail: unknown = res.statusText;
      let message = `Request failed (${res.status})`;
      const text = await res.text();
      if (text) {
        try {
          const parsed = JSON.parse(text);
          detail = parsed;
          if (typeof parsed?.detail === 'string') {
            message = parsed.detail;
          } else if (Array.isArray(parsed?.detail)) {
            message = parsed.detail
              .map((item: { msg?: string; loc?: unknown[] }) => item.msg ?? String(item))
              .join('; ');
          } else {
            message = text.slice(0, 300);
          }
        } catch {
          message = text.slice(0, 300);
        }
      }
      throw new ApiError(res.status, message, detail);
    }

    if (res.status === 204) {
      return undefined as T;
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError(408, 'The request timed out. Please try again.');
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  // Soil Analysis
  analyzeSoil(lat: number, lon: number, landCover?: string) {
    const query = buildQuery({ lat, lon, land_cover: landCover });
    return request<any>(`/soil/analyze?${query}`);
  },

  getSoilMoisture(lat: number, lon: number) {
    const query = buildQuery({ lat, lon });
    return request<any>(`/soil/moisture?${query}`);
  },

  // Risk Assessment
  assessRisk(lat: number, lon: number) {
    const query = buildQuery({ lat, lon });
    return request<any>(`/risk/all?${query}`);
  },

  getEarthquakes(days?: number, minMagnitude?: number) {
    const query = buildQuery({ days, min_magnitude: minMagnitude });
    return request<any>(`/risk/earthquake/recent?${query}`);
  },

  getSpecificRisk(type: 'landslide' | 'flood', lat: number, lon: number) {
    const query = buildQuery({ lat, lon });
    return request<any>(`/risk/${type}?${query}`);
  },

  // Recommendations
  getAgricultureRecs(lat: number, lon: number) {
    const query = buildQuery({ lat, lon });
    return request<any>(`/recommendations/agriculture?${query}`);
  },

  getDisasterPrep(lat: number, lon: number) {
    const query = buildQuery({ lat, lon });
    return request<any>(`/recommendations/disaster?${query}`);
  },

  getRestorationRecs(lat: number, lon: number) {
    const query = buildQuery({ lat, lon });
    return request<any>(`/recommendations/environmental?${query}`);
  },

  // Alerts
  getActiveAlerts() {
    return request<any>('/alerts/active');
  },

  getAlertHistory(limit?: number) {
    const query = buildQuery({ limit });
    return request<any>(`/alerts/history?${query}`);
  },

  dismissAlert(id: string) {
    return request<any>(`/alerts/${encodeURIComponent(id)}`, { method: 'DELETE' });
  },

  // Export (download URLs, opened directly by the browser)
  exportCsv(lat: number, lon: number, radius?: number) {
    return `${API_BASE}/export/soil/csv?${buildQuery({ lat, lon, radius_km: radius })}`;
  },

  exportGeojson(lat: number, lon: number, radius?: number) {
    return `${API_BASE}/export/soil/geojson?${buildQuery({ lat, lon, radius_km: radius })}`;
  },

  exportRiskGeojson(lat: number, lon: number, radius?: number) {
    return `${API_BASE}/export/risk/geojson?${buildQuery({ lat, lon, radius_km: radius })}`;
  },

  exportReport(lat: number, lon: number) {
    return `${API_BASE}/export/report?${buildQuery({ lat, lon })}`;
  },

  // Health / diagnostics
  health() {
    return request<any>('/health');
  },

  dataQuality(lat: number, lon: number) {
    return request<any>(`/data-quality?${buildQuery({ lat, lon })}`);
  },
};

export default api;

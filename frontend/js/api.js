/* api.js — Fetch wrapper for backend API */

// Auto-detect API base:
//   - Port 3000 → local dev, backend is on localhost:8000
//   - Port 8000 or any other (ngrok/Cloud Run) → same-origin, use relative URLs
export const API_BASE = window.location.port === '3000'
  ? 'http://localhost:8000'
  : '';

export async function uploadAsset(file, sourceUrl = '', platform = 'Unknown', algorithm = 'average') {
  const form = new FormData();
  form.append('file', file);
  form.append('source_url', sourceUrl);
  form.append('platform', platform);
  form.append('algorithm', algorithm);
  const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Upload failed (${res.status})`);
  }
  return res.json();
}

export async function scanUrl(imageUrl, sourceUrl = '', platform = 'Unknown', algorithm = 'average') {
  const form = new FormData();
  form.append('image_url', imageUrl);
  form.append('source_url', sourceUrl);
  form.append('platform', platform);
  form.append('algorithm', algorithm);
  const res = await fetch(`${API_BASE}/scan-url`, { method: 'POST', body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `URL scan failed (${res.status})`);
  }
  return res.json();
}

export async function getViolations() {
  const res = await fetch(`${API_BASE}/violations`);
  if (!res.ok) throw new Error('Failed to fetch violations');
  return res.json();
}

export async function getAllScans(limit = 500) {
  const res = await fetch(`${API_BASE}/scans?limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch scans');
  return res.json();
}

export async function getDashboardStats() {
  const res = await fetch(`${API_BASE}/dashboard/stats`);
  if (!res.ok) throw new Error('Failed to fetch dashboard stats');
  return res.json();
}

export async function getScan(assetId) {
  const res = await fetch(`${API_BASE}/scan/${assetId}`);
  if (!res.ok) throw new Error('Scan not found');
  return res.json();
}

export async function generateLegal({ ownerName, infringingUrl, assetId }) {
  const form = new FormData();
  form.append('owner_name', ownerName);
  form.append('infringing_url', infringingUrl);
  if (assetId) form.append('asset_id', assetId);
  const res = await fetch(`${API_BASE}/generate-legal`, { method: 'POST', body: form });
  if (!res.ok) throw new Error('Failed to generate legal notice');
  return res.json();
}

export async function getAssets() {
  const res = await fetch(`${API_BASE}/assets`);
  if (!res.ok) throw new Error('Failed to fetch assets');
  return res.json();
}

/* ── Helpers ────────────────────────────────────────── */
export function statusClass(status) {
  switch (status) {
    case 'Copied':     return 'copied';
    case 'Suspicious': return 'suspicious';
    default:           return 'original';
  }
}

export function statusIcon(status) {
  switch (status) {
    case 'Copied':     return '🚨';
    case 'Suspicious': return '⚠️';
    default:           return '✅';
  }
}

export function riskLabel(score) {
  if (score >= 75) return 'High';
  if (score >= 45) return 'Medium';
  return 'Low';
}

export function riskColor(score) {
  if (score >= 75) return '#EF4444';
  if (score >= 45) return '#F59E0B';
  return '#10B981';
}

export function formatDate(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

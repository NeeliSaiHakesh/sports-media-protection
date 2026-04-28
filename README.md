# Media Guard — Digital Asset Protection for Sports Media

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Cloud Run](https://img.shields.io/badge/Google%20Cloud-Run-4285F4?logo=google-cloud)](https://cloud.google.com/run)

> AI-powered sports media copyright protection — detect unauthorized usage, assess risk, and generate DMCA notices in seconds.

---

## Overview

Media Guard is a full-stack SaaS platform that:
- **Fingerprints** uploaded images using perceptual hashing (average, difference, or color hash)
- **Detects** unauthorized copies by comparing against a reference database
- **Classifies** content as Original / Suspicious / Copied with confidence scoring
- **Generates** professional DMCA takedown notices automatically
- **Monitors** via a live dashboard with 7-day trend charts and platform breakdowns
- **Reverse Image Search** — upload images directly to Google Lens, TinEye, and Bing

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JS (ES Modules) |
| Backend | FastAPI (Python 3.9+) |
| Database | SQLite (via aiosqlite) |
| AI Engine | CLIP ViT-B/32 + DINOv2-small + imagehash (ensemble: 50% CLIP + 30% DINO + 20% hash) |
| Charts | Chart.js 4.x |
| Deployment | Google Cloud Run (Docker) |

---

## Google Services

### ✅ Active Services

| Service | Purpose | Status |
|---|---|---|
| **Google Cloud Run** | Serverless container hosting — deploys the full app (nginx + FastAPI) in a single container | ✅ **Active** |
| **Google Lens** | Reverse image search — users can upload scanned images to Google Lens to find copies online | ✅ **Active** (opens lens.google.com) |

### ⏸️ Disabled Services (Available but not configured)

| Service | Purpose | Status | How to Enable |
|---|---|---|---|
| **Google Cloud Vision API** — Web Detection | Finds where images appear across the internet (pages with matching images, visually similar images, best-guess labels) | ⏸️ **Disabled** | Set `GOOGLE_APPLICATION_CREDENTIALS` env variable ([Setup Guide](https://cloud.google.com/vision/docs/setup)) |
| **Google Cloud Vision API** — Label Detection | Auto-detects content labels/tags for uploaded images | ⏸️ **Disabled** | Same as above |
| **Google Cloud Vision API** — Safe Search | Flags adult, violent, or inappropriate content | ⏸️ **Disabled** | Same as above |

> **Note:** All 3 Vision API features have fully implemented backend endpoints (`/vision/web-detect`, `/vision/labels`, `/vision/safe-search`). They are disabled because `GOOGLE_APPLICATION_CREDENTIALS` is not set. Once you configure a GCP service account, these endpoints automatically activate — no code changes needed.

### To Enable Google Cloud Vision API:

```bash
# 1. Create a GCP project and enable the Vision API
# 2. Create a service account with Vision API User role
# 3. Download the JSON key file
# 4. Set the environment variable:

export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"

# 5. Verify:
curl http://localhost:8000/vision/status
# → {"available": true, "features": ["web_detection", "label_detection", "safe_search"]}
```

---

## Quick Start

### Prerequisites
- Python 3.9+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/NeeliSaiHakesh/media-guard-ai.git
cd media-guard-ai

# Install backend dependencies
pip install -r backend/requirements.txt

# Start everything
./start.sh
```

**Frontend:** http://localhost:3000  
**API Docs:** http://localhost:8000/docs

---

## Cloud Run Deployment

```bash
# Deploy to Google Cloud Run (one command)
gcloud run deploy media-guard \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --memory 2Gi

# With Vision API enabled:
gcloud run deploy media-guard \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --set-env-vars "GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json"
```

---

## Project Structure

```
media-guard-ai/
├── backend/
│   ├── main.py           # FastAPI application & all routes
│   ├── fingerprint.py    # Perceptual hashing engine
│   ├── watermark.py      # Watermarking + EXIF extractor
│   ├── scanner.py        # Scan pipeline (compare + classify)
│   ├── legal.py          # DMCA notice generator
│   ├── database.py       # SQLite schema + seed data
│   ├── ai_engine.py      # CLIP + DINOv2 ensemble AI
│   ├── vision_api.py     # Google Cloud Vision API (disabled)
│   └── requirements.txt
├── frontend/
│   ├── index.html        # Landing page
│   ├── dashboard.html    # Analytics dashboard
│   ├── upload.html       # Upload / URL scanner
│   ├── results.html      # Scan results + comparison
│   ├── violations.html   # Violation management
│   ├── legal.html        # DMCA notice generator
│   ├── library.html      # Asset library
│   ├── history.html      # Scan history log
│   ├── watermark.html    # Watermark tool
│   ├── css/
│   │   ├── common.css    # Design system (dark + light theme)
│   │   └── animations.css
│   └── js/
│       ├── api.js        # API wrapper (auto-detect dev/prod)
│       ├── toast.js      # Toast notification system
│       └── theme.js      # Chrome-style theme management
├── Dockerfile            # Cloud Run unified container
├── .dockerignore
├── docker-compose.yml    # Local dev multi-container
├── start.sh              # One-command startup script
└── README.md
```

---

## API Reference

### Scan Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/upload` | Upload & scan an image file |
| `POST` | `/scan-url` | Fetch a public image URL & scan it |
| `DELETE` | `/assets/{id}` | Delete an asset and its scan data |
| `GET` | `/asset-image/{id}` | Serve the raw image file |

### Analytics

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/dashboard/stats` | KPI metrics (totals, risk rates) |
| `GET` | `/scan-trend` | Daily scan counts (last 30 days) |
| `GET` | `/dashboard/platform-breakdown` | Violation counts by platform |

### Legal

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/generate-legal` | Generate single DMCA notice |
| `POST` | `/bulk-legal` | Generate all pending DMCA notices |
| `GET` | `/export/violations.csv` | Download violations as CSV |
| `GET` | `/export/scans.csv` | Download full scan history as CSV |

### Watermark

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/watermark` | Embed visible/tiled watermark into image |

### Google Vision API (⏸️ Disabled)

| Method | Endpoint | Description | Status |
|---|---|---|---|
| `GET` | `/vision/status` | Check if Vision API is configured | ⏸️ Disabled |
| `GET` | `/vision/web-detect/{id}` | Find image copies across the web | ⏸️ Disabled |
| `GET` | `/vision/labels/{id}` | Auto-detect image labels | ⏸️ Disabled |
| `GET` | `/vision/safe-search/{id}` | Safe search content moderation | ⏸️ Disabled |

### Interactive Docs

```
http://localhost:8000/docs
```

---

## Classification Logic

| Similarity | Verdict | Risk Level |
|---|---|---|
| 0 – 60% | ✅ Original | Low |
| 60 – 85% | ⚠️ Suspicious | Medium |
| 85 – 100% | 🚨 Copied / Violation | High |

> Risk score is platform-weighted: YouTube ×1.5, Instagram ×1.2, Twitter/Facebook ×1.1

---

## Fingerprint Algorithms

| Algorithm | Best for |
|---|---|
| Average Hash | General-purpose, most reliable |
| Difference Hash | Edge-based similarity, good for edited images |
| Color Hash | Color-dominant content (jerseys, fields) |

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

| Variable | Purpose | Required |
|---|---|---|
| `PORT` | Backend port (default: 8000) | No |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account JSON key — enables Vision API | No (disabled without it) |

---

## License

MIT — see [LICENSE](LICENSE).

---

*Built with FastAPI, CLIP, DINOv2, Google Cloud Run, Pillow, and Chart.js*

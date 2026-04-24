# GuardSport AI — Digital Asset Protection for Sports Media

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> AI-powered sports media copyright protection — detect unauthorized usage, assess risk, and generate DMCA notices in seconds.

---

## Overview

GuardSport AI is a full-stack SaaS platform that:
- **Fingerprints** uploaded images using perceptual hashing (average, difference, or color hash)
- **Detects** unauthorized copies by comparing against a reference database
- **Classifies** content as Original / Suspicious / Copied with confidence scoring
- **Generates** professional DMCA takedown notices automatically
- **Monitors** via a live dashboard with 7-day trend charts and platform breakdowns

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JS (ES Modules) |
| Backend | FastAPI (Python 3.9+) |
| Database | SQLite (via aiosqlite) |
| AI Engine | CLIP ViT-B/32 + DINOv2-small + imagehash (ensemble: 50% CLIP + 30% DINO + 20% hash) |
| Charts | Chart.js 4.x |
| Serving | Python HTTP server (dev) |

---

## Quick Start

### Prerequisites
- Python 3.9+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/guardsport-ai.git
cd guardsport-ai/sports-media-protection

# Install backend dependencies
pip install -r backend/requirements.txt

# Start everything
./start.sh
```

**Frontend:** http://localhost:3000  
**API Docs:** http://localhost:8000/docs

---

## Project Structure

```
sports-media-protection/
├── backend/
│   ├── main.py           # FastAPI application & all routes
│   ├── fingerprint.py    # Perceptual hashing engine
│   ├── watermark.py      # Watermarking + EXIF extractor
│   ├── scanner.py        # Scan pipeline (compare + classify)
│   ├── legal.py          # DMCA notice generator
│   ├── database.py       # SQLite schema + seed data
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
│       ├── api.js        # API wrapper
│       ├── toast.js      # Toast notification system
│       └── theme.js      # Chrome-style theme management
├── start.sh              # One-command startup script
├── docker-compose.yml
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

## Docker Deployment

```bash
docker-compose up
```

This starts:
- Backend API on port **8000**
- Frontend files served on port **3000**

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

---

## License

MIT — see [LICENSE](LICENSE).

---

*Built with FastAPI, Pillow, and Chart.js*

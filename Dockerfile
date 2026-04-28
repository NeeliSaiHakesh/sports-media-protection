FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Backend setup ─────────────────────────────────────────────────────────────
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
RUN mkdir -p /app/backend/data /app/backend/uploads /app/backend/reference_assets

# ── Frontend setup ────────────────────────────────────────────────────────────
COPY frontend/ /usr/share/nginx/html/

# ── Nginx config — proxy /api to backend, serve frontend on / ─────────────────
RUN cat > /etc/nginx/sites-available/default <<'NGINX'
server {
    listen 8080;
    server_name _;

    # Serve frontend static files
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy all API calls to the FastAPI backend
    location ~ ^/(upload|upload-url|scan-url|scan|scans|assets|asset-image|violations|dashboard|generate-legal|bulk-legal|export|match|watermark|health|ai|vision) {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        client_max_body_size 50M;
    }
}
NGINX

# ── Startup script ────────────────────────────────────────────────────────────
RUN cat > /app/start.sh <<'SCRIPT'
#!/bin/bash
set -e

echo "🛡️  Media Guard — Starting on Cloud Run"

# Start FastAPI backend (in background)
cd /app/backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --log-level info &

# Wait for backend to be ready
echo "⏳ Waiting for backend..."
for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then
        echo "✅ Backend ready"
        break
    fi
    sleep 1
done

# Start nginx (foreground — PID 1)
echo "🌐 Starting nginx on port $PORT"
sed -i "s/listen 8080/listen ${PORT:-8080}/" /etc/nginx/sites-available/default
nginx -g "daemon off;"
SCRIPT
RUN chmod +x /app/start.sh

# HuggingFace Spaces requires port 7860
ENV PORT=7860
EXPOSE 7860

CMD ["/app/start.sh"]

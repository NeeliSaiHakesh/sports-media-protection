#!/bin/bash
# start.sh — Launch GuardSport AI (Frontend + Backend)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$SCRIPT_DIR/backend"
FRONTEND="$SCRIPT_DIR/frontend"

echo ""
echo "🛡️  GuardSport AI — Digital Asset Protection for Sports Media"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Kill existing processes
pkill -f "uvicorn main:app" 2>/dev/null || true
pkill -f "python -m http.server 3000" 2>/dev/null || true
sleep 1

# Start Backend
echo "▶ Starting API server on http://localhost:8000 ..."
cd "$BACKEND"
nohup python -m uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/guardsport-api.log 2>&1 &
API_PID=$!

# Wait for backend
echo "  Waiting for backend to start..."
for i in {1..15}; do
  if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "  ✅ Backend ready (PID: $API_PID)"
    break
  fi
  sleep 1
done

# Start Frontend
echo ""
echo "▶ Starting frontend server on http://localhost:3000 ..."
cd "$FRONTEND"
nohup python -m http.server 3000 > /tmp/guardsport-frontend.log 2>&1 &
FE_PID=$!
sleep 1
echo "  ✅ Frontend ready (PID: $FE_PID)"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 GuardSport AI is RUNNING!"
echo ""
echo "  🌐 Frontend:   http://localhost:3000"
echo "  ⚙️  API Docs:   http://localhost:8000/docs"
echo "  📊 Dashboard:  http://localhost:3000/dashboard.html"
echo "  📁 Upload:     http://localhost:3000/upload.html"
echo "  🚨 Violations: http://localhost:3000/violations.html"
echo "  ⚖️  Legal:      http://localhost:3000/legal.html"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Press Ctrl+C to stop both servers"
echo ""

# Open browser
sleep 1
open http://localhost:3000 2>/dev/null || xdg-open http://localhost:3000 2>/dev/null || true

# Keep running until Ctrl+C
trap "echo ''; echo 'Shutting down...'; kill $API_PID $FE_PID 2>/dev/null; exit 0" INT TERM
wait

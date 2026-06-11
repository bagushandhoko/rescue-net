#!/bin/sh
set -eu

API_DIR="${RN_API_DIR:-/volume1/docker/rescue-net-api}"
IMAGE="${RN_API_IMAGE:-rescue-net-api:0.1}"
CONTAINER="${RN_API_CONTAINER:-rescue-net-api}"
PORT="${RN_API_PORT:-8092}"
ENV_FILE="${RN_API_ENV_FILE:-/volume1/docker/rescue-net-api/.env}"
UPLOADS="${RN_UPLOADS_DIR:-/volume1/docker/osiun-api/data/uploads}"

if [ ! -f "$API_DIR/main.py" ]; then
  echo "ERROR: main.py not found in $API_DIR"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: env file not found: $ENV_FILE"
  exit 1
fi

echo "=== Rescue-Net API Rebuild ==="
echo "API_DIR=$API_DIR"
echo "IMAGE=$IMAGE"
echo "CONTAINER=$CONTAINER"
echo "PORT=$PORT"

echo "1. Python compile"
cd "$API_DIR"
python3 -m py_compile main.py app_shared.py routes/*.py

echo "2. Docker build"
sudo docker build --no-cache -t "$IMAGE" .

echo "3. Replace container"
sudo docker rm -f "$CONTAINER" 2>/dev/null || true
sudo docker run -d   --name "$CONTAINER"   --restart unless-stopped   -p "$PORT:$PORT"   --env-file "$ENV_FILE"   -v "$UPLOADS:/data/uploads"   "$IMAGE"

echo "4. Health check"
sleep 3
curl -fsS "http://127.0.0.1:$PORT/health"
echo ""
echo "OK: Rescue-Net API rebuilt."

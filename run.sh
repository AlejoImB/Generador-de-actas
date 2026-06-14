#!/usr/bin/env bash
# Desarrollo local:  bash run.sh
# Producción:        docker compose up --build -d
set -e
cd "$(dirname "$0")/backend"

echo "==> Instalando dependencias…"
pip install -q -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> .env creado — edítalo y agrega tu ANTHROPIC_API_KEY"
fi

if [ ! -f acta_ia.db ]; then
  echo "==> Sembrando datos demo…"
  python -m app.seed
fi

# Frontend en segundo plano
( cd ../frontend && python -m http.server 5500 >/dev/null 2>&1 & )

echo ""
echo "  Frontend:  http://localhost:5500"
echo "  API:       http://localhost:8000/docs"
echo ""
echo "==> Levantando servidor (Ctrl+C para detener)…"
exec uvicorn app.main:app --reload --port 8000

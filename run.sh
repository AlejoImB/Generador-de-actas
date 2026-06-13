#!/usr/bin/env bash
# Arranque de ActaIA en un solo comando:  bash run.sh
set -e
cd "$(dirname "$0")/backend"

echo "==> Instalando dependencias…"
pip install -q -r requirements.txt

if [ ! -f .env ]; then cp .env.example .env; echo "==> .env creado (AI_PROVIDER=mock)"; fi
if [ ! -f acta_ia.db ]; then echo "==> Sembrando datos demo…"; python -m app.seed; fi

# Servir el frontend estático en :5500 en segundo plano
( cd ../frontend && python -m http.server 5500 >/dev/null 2>&1 & )

echo ""
echo "  API:       http://localhost:8000   (docs: /docs)"
echo "  Frontend:  http://localhost:5500"
echo "  Login:     ana.torres@empresa.com / Demo1234"
echo ""
echo "==> Levantando API (Ctrl+C para detener)…"
exec uvicorn app.main:app --reload --port 8000

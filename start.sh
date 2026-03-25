#!/bin/bash
# Render startup script
echo "Starting SalesPilot..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

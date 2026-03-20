#!/bin/bash
# Render startup script: init schema, load data, start server

echo "Starting SalesPilot..."

# Render provides postgresql:// but psycopg2 needs postgresql+psycopg2://
if [[ "$DATABASE_URL" == postgresql://* ]] && [[ "$DATABASE_URL" != *psycopg2* ]]; then
  export DATABASE_URL="${DATABASE_URL/postgresql:\/\//postgresql+psycopg2:\/\/}"
  echo "Adjusted DATABASE_URL driver to psycopg2"
fi

# Start uvicorn (schema init + model warmup happen in lifespan)
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

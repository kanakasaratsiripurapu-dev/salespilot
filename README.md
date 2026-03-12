# SalesPilot

Field sales route optimization backend powered by XGBoost + OR-Tools.

## Quick Start

### 1. Start services

```bash
docker compose up --build
```

This starts PostgreSQL and the FastAPI API. The database schema is auto-created on first run.

### 2. Load data

```bash
docker compose exec api python -m app.data.data_loader /data/raw
```

Or locally (with DB running):

```bash
python -m app.data.data_loader data/raw
```

### 3. Train the model

```bash
docker compose exec api python -m app.ml.train_model --csv /data/raw
```

Or locally:

```bash
python -m app.ml.train_model --csv data/raw
```

To train from data already loaded in the database:

```bash
python -m app.ml.train_model
```

### 4. Run tests

```bash
pytest tests/ -v
```

### 5. API usage

**Health check:**

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok"}
```

**Score accounts:**

```bash
curl -X POST http://localhost:8000/v1/score-accounts \
  -H "Content-Type: application/json" \
  -d '{"account_ids": [101, 205, 330]}'
```

```json
{
  "scores": [
    {"account_id": 101, "priority_score": 0.82}
  ],
  "model_version": "xgb_v1"
}
```

**Optimize route:**

```bash
curl -X POST http://localhost:8000/v1/optimize-route \
  -H "Content-Type: application/json" \
  -d '{"start_account_id": 1, "account_ids": [101, 205, 330], "top_n": 3, "distance_mode": "haversine"}'
```

```json
{
  "selected_accounts": [
    {"account_id": 101, "priority_score": 0.82}
  ],
  "route": [
    {"stop_index": 0, "account_id": 1, "label": "START"},
    {"stop_index": 1, "account_id": 101, "label": "ACCOUNT"},
    {"stop_index": 2, "account_id": 205, "label": "ACCOUNT"},
    {"stop_index": 3, "account_id": 330, "label": "ACCOUNT"},
    {"stop_index": 4, "account_id": 1, "label": "END"}
  ],
  "total_distance_km": 412.6,
  "distance_mode": "haversine"
}
```

## Project Structure

```
salespilot/
  app/
    api/          routes.py, schemas.py
    core/         config.py
    data/         data_loader.py, synthetic_geo.py
    db/           schema.sql, session.py
    ml/           train_model.py, predictor.py, artifacts/
    optimization/ distance_provider.py, haversine.py, ortools_tsp.py
  tests/          test_scoring.py, test_optimize_route.py
  docker-compose.yml
  Dockerfile
  requirements.txt
```

## Environment Variables

See `.env.example` for all configuration options.

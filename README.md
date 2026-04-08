# SalesPilot: Intelligent Backend System for Sales Route and Deal Prioritisation

**Course:** CMPE 258 — Deep Learning (Spring 2026), San Jose State University  
**Team Member:** Kanaka Sarat Siripurapu (SJSU ID: 019132776)  
**Email:** kanakasarat.siripurapu@sjsu.edu  
**Live Demo:** [https://salespilot-44lq.onrender.com](https://salespilot-44lq.onrender.com)

---

## Project Overview

SalesPilot is a backend-driven system that helps field sales representatives plan client visits more effectively. It combines **Deep learning-based deal prioritisation** with **route optimisation** to create efficient round-trip travel plans.

The system predicts which client accounts are most likely to close deals, ranks them by priority score, and generates an optimised visit route — minimising travel distance while maximising business value.

## Problem Statement

Field sales reps manage multiple client accounts across different cities. With limited time and travel budgets, they cannot visit every account. Standard navigation tools find the shortest path, but don't help determine **which accounts are most valuable to visit**.

SalesPilot solves this by:
1. **Predicting** high-value accounts using Deep learning
2. **Prioritising** them by deal closure probability
3. **Generating** an efficient round-trip visit route

## Dataset

- **Source:** [CRM Sales Opportunities Dataset — Maven Analytics](https://mavenanalytics.io/data-playground)
- **Files:** `accounts.csv`, `products.csv`, `sales_teams.csv`, `sales_pipeline.csv`
- **Records:** 85 accounts, 8,800 opportunities, 35 sales agents, 7 products
- **Features used for ML:** industry, company_size, region, deal_value, sales_stage, days_since_last_contact
- **Target:** `deal_closed` (binary: 0 = open, 1 = won)
- **Geo-coordinates:** Synthetically generated from region data using 8 anchor cities with deterministic noise

## Approach

### Deep Learning Pipeline
- **Model:** XGBoost binary classifier wrapped in a scikit-learn Pipeline
- **Preprocessing:** OneHotEncoder for categoricals, log1p transform for deal_value, passthrough for numerics
- **Training split:** 70/15/15 stratified (train/validation/test)
- **Class balancing:** Automatic `scale_pos_weight` for imbalanced classes
- **Output:** Probability score (0–1) per account indicating deal closure likelihood
- **Metrics:** AUC and Accuracy evaluated on train, validation, and test sets

### Route Optimisation
- **Algorithm:** Travelling Salesman Problem (TSP) solver
- **Primary solver:** OR-Tools with GUIDED_LOCAL_SEARCH metaheuristic
- **Fallback:** Nearest-neighbour heuristic (when OR-Tools is unavailable)
- **Distance:** Haversine formula for geographic coordinates
- **Output:** Ordered round-trip route (START → accounts → END) with total distance in km

### System Architecture
```
┌─────────────┐     ┌───────────────┐     ┌──────────────┐
│  Frontend    │────▶│  FastAPI REST  │────▶│  PostgreSQL  │
│  (Leaflet)   │◀────│  API Server   │◀────│  Database    │
└─────────────┘     └───────┬───────┘     └──────────────┘
                            │
                    ┌───────┴───────┐
                    │               │
              ┌─────▼─────┐  ┌─────▼──────┐
              │  XGBoost   │  │  TSP Solver │
              │  Predictor │  │  (OR-Tools) │
              └───────────┘  └────────────┘
```

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11, FastAPI |
| Database | PostgreSQL 16 |
| ML Model | XGBoost + scikit-learn Pipeline |
| Route Optimisation | OR-Tools / Nearest-Neighbour TSP |
| Frontend | Leaflet.js, Vanilla JS (no build tools) |
| Deployment | Render (free tier), Docker |
| Data Pipeline | Pandas, SQLAlchemy bulk upsert |

## Progress So Far

### Completed
- [x] Data preprocessing and PostgreSQL database setup with bulk upsert pipeline
- [x] Synthetic geo-coordinate generation from region data (8 anchor cities)
- [x] XGBoost model training with sklearn Pipeline (OHE + log1p + classifier)
- [x] Model evaluation (AUC, Accuracy on train/val/test splits)
- [x] TSP route optimisation with OR-Tools + nearest-neighbour fallback
- [x] Haversine distance calculation for geographic routing
- [x] FastAPI REST API with endpoints: health, meta, score-accounts, optimize-route, load-data, accounts CRUD
- [x] Pydantic v2 request/response schemas
- [x] Interactive frontend with Leaflet.js map, account management, route visualisation
- [x] Docker + Docker Compose configuration
- [x] Public deployment on Render
- [x] Demo notebook with charts, interactive maps, and API verification
- [x] Unit tests for scoring and route optimisation

### API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/meta` | Service info and model version |
| POST | `/v1/score-accounts` | Score accounts by deal closure probability |
| POST | `/v1/optimize-route` | Get optimised round-trip route for top accounts |
| POST | `/v1/load-data` | Load CSV seed data into database |
| GET | `/v1/accounts` | List all accounts |
| GET | `/v1/accounts/{id}` | Get single account |
| POST | `/v1/accounts` | Create new account |
| DELETE | `/v1/accounts/{id}` | Delete account |

## Next Steps

- [ ] Experiment with deep learning models (neural network classifier) for deal prediction
- [ ] Add hyperparameter tuning with cross-validation
- [ ] Implement real-time model retraining pipeline
- [ ] Add Google Maps API integration for real travel distances
- [ ] Build more advanced analytics dashboard

## Project Structure

```
salespilot/
├── app/
│   ├── api/             # FastAPI routes and Pydantic schemas
│   │   ├── routes.py
│   │   └── schemas.py
│   ├── core/            # Configuration (env vars, settings)
│   │   └── config.py
│   ├── data/            # Data pipeline and geo-coordinate generation
│   │   ├── data_loader.py
│   │   └── synthetic_geo.py
│   ├── db/              # Database schema and session management
│   │   ├── schema.sql
│   │   └── session.py
│   ├── ml/              # ML training, prediction, and saved artifacts
│   │   ├── train_model.py
│   │   ├── predictor.py
│   │   └── artifacts/
│   │       ├── model.joblib
│   │       └── metrics.json
│   ├── optimization/    # TSP solver and distance calculations
│   │   ├── ortools_tsp.py
│   │   ├── haversine.py
│   │   └── distance_provider.py
│   └── main.py          # FastAPI app entrypoint with lifespan handler
├── data/raw/            # Source CSV datasets
├── static/              # Frontend (Leaflet.js map interface)
│   ├── index.html
│   ├── css/style.css
│   └── js/
├── tests/               # Unit tests
├── notebooks/           # Jupyter notebooks
├── Dockerfile
├── docker-compose.yml
├── render.yaml          # Render deployment blueprint
├── requirements.txt
└── start.sh
```

## How to Run

### Option 1: Docker (recommended)
```bash
docker compose up --build
```

### Option 2: Local setup
```bash
pip install -r requirements.txt
# Set DATABASE_URL in .env (see .env.example)
python -m app.ml.train_model --csv data/raw
uvicorn app.main:app --reload
```

### Load seed data
```bash
curl -X POST http://localhost:8000/v1/load-data
```

### Run tests
```bash
pytest tests/ -v
```

## References

- [CRM Sales Opportunities Dataset — Maven Analytics](https://mavenanalytics.io/data-playground)
- [XGBoost Documentation](https://xgboost.readthedocs.io/)
- [Google OR-Tools Documentation](https://developers.google.com/optimization)
- [scikit-learn Documentation](https://scikit-learn.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Leaflet.js Documentation](https://leafletjs.com/)

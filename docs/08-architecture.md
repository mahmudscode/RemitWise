# 08 — Architecture

Reference flow from the guideline: **INPUT → INTELLIGENCE → ACTION**
Synthetic data → feature/context layer → ML/AI engine → explanation/recommendation → user action → measurable outcome → feedback loop.

## Layers
| Layer | Responsibility | Candidate tech (any reasonable stack allowed) |
|---|---|---|
| Data | Synthetic generation, storage, feature prep | Python, Pandas, PostgreSQL or SQLite |
| ML | Forecaster, shortfall risk model | scikit-learn, LightGBM |
| Rules/Optimizer | Allocation, thresholds, consent rules | Plain Python module, kept separate from ML |
| GenAI | Grounded explanations | LLM API with structured input + number check |
| API | Expose capabilities as services | FastAPI |
| Frontend | Family app, sender app, demo control panel | React / Next.js |
| Monitoring | Prediction logs, metrics, calibration views | Simple logs + metrics page |
 
## Components
1. **Data Simulator** — generates households and events; writes to store.
2. **Feature Builder** — turns history into model inputs; separate from inference.
3. **Forecast Service** — returns arrival/amount distributions.
4. **Allocation Engine** — rules + optimizer; consumes forecast; returns plans and reasons.
5. **Risk Monitor** — Monte-Carlo/classifier; returns shortfall probability and drivers.
6. **Consent Service** — single source of truth for who can see what; enforced at API level, not only UI.
7. **Explanation Service** — builds structured facts, calls LLM, validates numbers, falls back to templates.
8. **Simulation Runner** — replays a year with/without policy for metrics.
9. **Frontends** — family, sender, admin/demo panel.
10. **Audit Log** — records predictions, plans, decisions (accepted/edited/rejected), consent changes.

## Design rules (from guideline)
- Data prep separate from inference.
- Business rules separate from ML.
- Outputs traceable (each carries inputs version, model version, reasons).
- API designed to later connect to a real backend (stable contracts; synthetic source is swappable via an adapter).
- No sensitive decision logic inside the LLM prompt.

## Security considerations
- Role-based access: family vs sender vs admin.
- Consent enforced server-side; sender endpoints return only permitted fields.
- LLM: input sanitization, no secrets/PII in prompts, output validation, prompt-injection tests (e.g., goal name containing instructions).
- No real credentials or data in repo; environment-based config.
- Rate limiting and basic abuse checks on demo endpoints.

## Reliability for demo
- Pre-generated dataset and pre-trained models committed as artifacts.
- Cached explanation fallback if LLM unavailable.
- Scripted scenario toggles for deterministic demo.

## Integration path
Adapter layer replaces the simulator with upay event feeds later; contracts unchanged (doc 09, doc 16).

# 18 — Tech Stack (Proposed)

Status: **updated with team choices (PostgreSQL, Groq); rest still proposal.** The guideline allows any reasonable stack; this follows its reference architecture. Confirm or change, then treat as fixed. Related decisions: doc 17 (questions 13–15).

**Recommendation:** all-Python backend + React frontend. One language for data, ML and API is the fastest path in a hackathon time box.

## Stack by layer
| Layer | Proposed tech | Why | Alternative |
|---|---|---|---|
| Data simulation | Python, Pandas, NumPy (seeded) | Reproducible synthetic households and planted patterns | — |
| Storage | PostgreSQL (team choice) | Production-like, matches the guideline's suggested data layer, supports concurrent family/sender sessions and audit/consent tables | SQLite for a zero-setup fallback |
| Forecasting | LightGBM quantile models + conformal calibration (scikit-learn) | Outputs P10/P50/P90 ranges; fast; explainable | Probabilistic time-series model (Prophet-style) |
| Allocator | Plain Python module (rules + simple optimizer, e.g. SciPy) | Business rules kept separate from ML (guideline requirement) | — |
| Shortfall warning | Monte-Carlo projection (NumPy); optional gradient-boosting classifier | Gives probability and run-out date range | — |
| Explainability | Feature importance / SHAP, rule traces | Show reasons behind predictions | — |
| GenAI | Groq API (team choice) with structured JSON input, post-generation number check, template fallback | Fast inference for live demo; LLM explains only computed numbers; no decision logic in prompts | Local open model if external APIs are not allowed |
| Backend API | FastAPI (Python) | Same language as ML; auto-generated API docs; async | Node.js |
| Consent & audit | Part of the API layer, enforced server-side | Sender data must never leak via UI-only checks | — |
| Frontend | React or Next.js, mobile-style web app, Tailwind | Two windows: family and sender; demo control panel | — |
| Charts | A lightweight chart library (e.g. Recharts) | Forecast ranges, balance timeline, progress bars | — |
| Monitoring | Prediction/decision logs + simple metrics page | Evaluation and traceability | — |
| Testing | pytest; a small set of prompt-injection and consent-leak tests | Responsible AI evidence | — |
| Dev tooling | Git, a virtual environment, a single run script, environment-based config (Groq API key and database URL in env vars only) | Reproducibility, no secrets in repo | Docker Compose to start PostgreSQL + API together (recommended) |

## Packaging for demo reliability
- Pre-generated dataset and pre-trained model artifacts committed or stored locally.
- Groq is an external service: cache generated summaries and keep template fallbacks so the demo works if the network or API fails or is rate-limited.
- PostgreSQL must be running locally for the demo; use one start script (or Docker Compose) and a seeded database dump to restore state quickly.
- One command/button to reset the demo and replay scenarios.

## Constraints from the guideline
- Separate data preparation from model inference.
- Keep business rules distinct from ML predictions.
- Traceable, explainable outputs.
- APIs ready for a future real backend (simulator sits behind an adapter).
- Do not put sensitive decision logic entirely in an LLM prompt.

## Security notes for these choices
- Groq API key and database credentials only in environment variables; never committed.
- Send Groq only structured computed facts: no real PII (none exists), no other households' data.
- Sanitize free text (e.g., goal names) before it reaches the prompt; validate numbers in the output.

## Decided
- Storage: PostgreSQL.
- GenAI provider: Groq.

## Decisions still to confirm
1. Forecaster: LightGBM quantile + conformal (recommended) vs time-series model.
2. Groq model choice, and confirmation from organizers that external APIs are permitted (see doc 17).
3. Bangla output quality on the chosen Groq model; English fallback if weak.
4. Frontend: React vs Next.js; English only or Bangla too.
5. Run PostgreSQL via Docker Compose or local install?

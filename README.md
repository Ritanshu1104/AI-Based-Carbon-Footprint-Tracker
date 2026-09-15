# Carbon Evidence Lab

Carbon Evidence Lab is a local research prototype for estimating a person's daily carbon footprint from natural-language activity logs. It records the evidence behind each estimate, reports a range alongside the point estimate, and asks one high-value clarification at a time when an input is missing or ambiguous.

## What changed from the original demo

- Natural-language extraction covers every activity label in the repository's 1,000-row phrase dataset.
- Quantity values retain their original text as evidence and miles are normalized to kilometres.
- Generic cars and flights produce uncertainty ranges instead of silently hiding an average.
- A clarification engine ranks missing facts by expected range reduction, decision sensitivity, and effort.
- Appliance duration is never treated as electrical energy. The tracker requests kWh.
- Every factor exposes its version, candidate values, geography, boundary, GWP basis, and data-quality status.
- Each result includes an audit graph connecting user evidence, factor records, and calculated totals.
- Recommendations state whether their direction remains stable across the available factor range.
- Users can label quantities as estimates, measurements, bills/meters, or routing-service evidence.
- Completed results can be explicitly saved to a local SQLite journal with a rolling baseline.
- The interface includes category contribution bars and downloadable audit JSON.
- Consent-gated Google Routes and OSRM providers can acquire road distance.
- Local Tesseract OCR can extract candidate kWh and meter-reading differences from bill images.
- A multinomial classifier handles unmatched phrasing and encrypted correction memory learns authenticated corrections.
- Possible duplicate activities trigger a separate/remove decision before calculation.
- Local accounts use PBKDF2 password hashing, hashed session tokens, and Fernet-encrypted journal payloads.
- Monthly goals, daily trends, ARIMA forecasts, and an explicit rolling fallback are available per user.
- A reproducible experiment runner compares keyword and hybrid extraction methods.
- The Flask server hosts both the API and frontend, so the application starts with one command.

## Research status and factor limitation

The included `Realistic_Emission_Factors_300.csv` does not identify an authoritative publisher, geography, lifecycle boundary, validity date, or global-warming-potential basis. Those transport and food values remain **illustrative and unverified**. Indian electricity uses the Central Electricity Authority Version 22.0 weighted-average grid factor for FY 2025–26: `0.675 tCO2/MWh`, equivalent to `0.675 kgCO2/kWh`. The vegetarian-meal factor remains a project placeholder.

This implementation is suitable for workflow research, experiments, and software evaluation. Replace the factor catalogue with cited, jurisdiction-appropriate sources before making scientific, environmental, or public accuracy claims.

## Architecture

```text
User text
  → deterministic extraction + trained fallback + correction memory
  → ActivityExtractor: event + quantity + evidence + duplicate signals
  → ClarificationEngine: question ranked by range reduction, decision sensitivity, and effort
  → consented route evidence or local bill OCR when selected
  → FactorStore: versioned candidate factors + provenance
  → CarbonCalculator: point estimate + interval + recommendations
  → Audit graph: events → factors → result
  → encrypted per-user journal → goals, trends, ARIMA/fallback forecast
```

| File | Responsibility |
| --- | --- |
| `backend/nlp_extractor.py` | Extract structured activity events while preserving source text |
| `backend/clarification.py` | Select and apply one clarification at a time |
| `backend/factor_store.py` | Load factors and expose provenance and quality metadata |
| `backend/carbon_calculator.py` | Calculate estimates, intervals, recommendations, and audit graph |
| `backend/journal.py` | Persist explicitly saved records in a local SQLite journal |
| `backend/security.py` | Password hashing, token authentication, and journal encryption |
| `backend/routing.py` | Consent-gated Google Routes and OSRM integration |
| `backend/ocr_evidence.py` | Local Tesseract OCR and bill-quantity validation |
| `backend/learning.py` | Trained fallback classifier and encrypted correction memory |
| `backend/forecasting.py` | ARIMA forecast with rolling fallback |
| `backend/app.py` | Serve the local application and JSON API |
| `frontend/` | Accessible single-page research interface |
| `tests/test_tracker.py` | NLP, calculation, provenance, API, and clarification regressions |
| `experiments/evaluate_methods.py` | Keyword-versus-hybrid evaluation harness |

## Run locally

Python 3.10 or newer is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python backend\app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). The server keeps clarification sessions in memory for one hour; restarting it clears all sessions.

For Google route evidence, configure a Routes API key before starting:

```powershell
$env:GOOGLE_MAPS_API_KEY = "your-key"
python backend\app.py
```

Without a Google key, coordinate-based OSRM routing remains available. Every route request requires an explicit consent checkbox because locations are transmitted to the selected provider. Configure a self-hosted OSRM instance for dependable or production use:

```powershell
$env:OSRM_BASE_URL = "https://your-osrm-host"
```

Bill-image OCR requires a local Tesseract 5 executable in `PATH`. Python OCR packages are installed through `requirements.txt`; the native Tesseract engine is installed separately for the operating system.

Run the regression suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## API

### `POST /api/analyze`

```json
{
  "text": "I drove my car 25 km and used 4 kWh of electricity."
}
```

The response contains the current estimate, supported range, extracted events, factor candidates, audit graph, and either `status: "complete"` or `status: "needs_clarification"` with one question.

### `POST /api/clarify`

```json
{
  "session_id": "returned-by-analyze",
  "question_id": "returned-by-analyze",
  "answer": "Electric Car"
}
```

### `GET /api/factors`

Returns the full factor catalogue and its quality warning.

### `GET /api/health`

Returns service health, factor version, and session-storage mode.

### Authentication

`POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, and `GET /api/auth/me` provide local multi-user access. Private endpoints use `Authorization: Bearer <token>`.

### `GET /api/journal` and `POST /api/journal`

List encrypted per-user records or explicitly save a completed session. `DELETE /api/journal/<entry_id>` removes one record.

### Evidence and learning

- `POST /api/evidence/route` obtains a consented route distance and attaches its provenance.
- `POST /api/evidence/bill` performs local image OCR and returns ranked kWh candidates for review.
- `POST /api/corrections` applies and privately remembers an authenticated extraction correction.

### Dashboard and goals

- `GET /api/dashboard?month=YYYY-MM` returns daily totals, categories, goal progress, and forecast.
- `PUT /api/goals/YYYY-MM` creates or updates a private monthly target.
- `GET /api/capabilities` reports whether Google Routes, OSRM, Tesseract OCR, and ARIMA are available.

## Supported activities

Transport includes cars by powertrain, bus, train, metro, taxi, motorcycle, scooter, auto rickshaw, bicycle, walking, and domestic/international flights. Food includes vegetarian, chicken, beef, fish, lamb, and pork meals. Electricity accepts kWh directly; appliance-hour descriptions trigger a request for actual or estimated kWh.

## Patent and publication work

The potentially differentiating research direction is the combined workflow: evidence-preserving natural-language events, source-aware factor candidates, uncertainty propagation, and sequential questions chosen by their expected reduction of decision uncertainty. That combination still requires a professional prior-art search, claim drafting, experiments, and legal review. A working prototype does not establish novelty, inventive step, patentability, or freedom to operate.

Keep technical novelty documents and unpublished experimental details private until the project guide or patent professional approves disclosure. Public commits, demonstrations, conference submissions, and repository pushes can affect filing strategy in some jurisdictions.

## Suggested evaluation

1. **Extraction:** entity, activity, quantity, and unit accuracy on held-out natural-language logs.
2. **Calibration:** how often reported CO2e intervals contain a trusted reference calculation.
3. **Question utility:** uncertainty reduction per user question against fixed-form and ask-everything baselines.
4. **Decision stability:** whether recommendations remain unchanged after missing facts are resolved.
5. **Usability:** completion rate, time, question count, and perceived trust.

Run the current engineering comparison:

```powershell
.\.venv\Scripts\python.exe experiments\evaluate_methods.py
```

The bundled data is templated, so its scores are regression evidence rather than publication evidence. Collect an independent held-out corpus before a conference submission.

## Privacy and deployment notes

- The current application has local accounts and no remote account service.
- Unsaved activity text is stored only in process memory for clarification and expires after one hour.
- Clicking **Save to local journal** encrypts activity text and the audit result before writing to `data/carbon_journal.db`.
- Passwords use PBKDF2-HMAC-SHA256; bearer tokens are stored as hashes; the encryption key is local and excluded from Git.
- Losing `data/.carbon.key` makes existing encrypted journal and correction records unreadable. Back it up securely for any real use.
- Production deployment still needs HTTPS, rate limiting, secure key management, recovery controls, database migration tooling, and a privacy review.

## Authoritative references integrated

- Central Electricity Authority, *CO2 Baseline Database for the Indian Power Sector*, Version 22.0, August 2026: <https://cea.nic.in/wp-content/uploads/baseline/2026/09/User_Guide__Version_22.0.pdf>
- OSRM HTTP API route service: <https://project-osrm.org/docs/v5.24.0/api/#route-service>
- Tesseract 5 documentation: <https://tesseract-ocr.github.io/tessdoc/>
- statsmodels ARIMA documentation: <https://www.statsmodels.org/stable/generated/statsmodels.tsa.arima.model.ARIMA.html>

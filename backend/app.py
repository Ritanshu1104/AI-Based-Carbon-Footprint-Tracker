"""Flask API and local web host for the research prototype."""

import os
import time
import uuid

from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

from carbon_calculator import CarbonCalculator
from clarification import ClarificationEngine
from factor_store import FactorStore
from forecasting import FootprintForecaster
from journal import JournalRepository
from nlp_extractor import ActivityExtractor
from ocr_evidence import BillOcrService
from routing import RouteEvidenceService
from security import AuthRepository, DataCipher


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 9 * 1024 * 1024
CORS(app, resources={r"/api/*": {"origins": [
    r"http://localhost:*", r"http://127.0.0.1:*", "null"
]}})

data_cipher = DataCipher()
auth = AuthRepository()
factor_store = FactorStore()
extractor = ActivityExtractor()
calculator = CarbonCalculator(factor_store)
clarifier = ClarificationEngine(factor_store)
journal = JournalRepository(cipher=data_cipher)
forecaster = FootprintForecaster()
routes = RouteEvidenceService()
bill_ocr = BillOcrService()
sessions = {}
SESSION_TTL_SECONDS = 60 * 60


def _token():
    header = request.headers.get("Authorization", "")
    return header[7:].strip() if header.lower().startswith("bearer ") else None


def _user():
    return auth.resolve_token(_token())


def _authentication_error():
    return jsonify({"error": "Sign in is required for private journal data"}), 401


def _remove_expired_sessions():
    cutoff = time.time() - SESSION_TTL_SECONDS
    for session_id in [key for key, value in sessions.items() if value["updated_at"] < cutoff]:
        sessions.pop(session_id, None)


def _response(session_id, activities):
    result = calculator.calculate_footprint(activities)
    question = clarifier.next_question(activities)
    status = "needs_clarification" if question else "complete"
    if not activities:
        status = "no_activities"
    return {
        **result,
        "status": status,
        "session_id": session_id,
        "question": question,
        "extracted_activities": activities,
        "unrecognized_entries": sessions.get(session_id, {}).get("unrecognized_entries", []),
        "privacy": "Session data is held in server memory and expires after one hour.",
    }


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/health")
def health():
    return jsonify({
        "status": "ok", "factor_version": factor_store.DATASET_VERSION,
        "session_storage": "in-memory", "journal_encryption": "Fernet authenticated encryption",
    })


@app.get("/api/capabilities")
def capabilities():
    return jsonify({
        "routing": routes.capability, "bill_ocr": bill_ocr.capability,
        "forecasting": forecaster.capability,
        "hybrid_nlp": {"classifier": "multinomial-naive-bayes-v1",
                       "correction_memory": "encrypted-local"},
        "electricity_factor": factor_store.records["Electricity"],
        "google_map": {"browser_map_available": bool(os.environ.get("GOOGLE_MAPS_BROWSER_KEY"))},
    })


@app.get("/api/maps/config")
def maps_config():
    """Expose only the referrer-restricted browser key used by Maps JavaScript."""
    key = os.environ.get("GOOGLE_MAPS_BROWSER_KEY")
    if not key:
        return jsonify({"available": False})
    return jsonify({"available": True, "browser_key": key})


@app.post("/api/places/autocomplete")
def place_autocomplete():
    data = request.get_json(silent=True) or {}
    if data.get("consent_external_processing") is not True:
        return jsonify({"error": "Location consent is required before requesting place suggestions"}), 400
    try:
        suggestions = routes.autocomplete(data.get("query"), data.get("session_token"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({"suggestions": suggestions, "provider": "Google Maps"})


@app.post("/api/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    try:
        user = auth.register(data.get("username"), data.get("password"))
        login_result = auth.login(data.get("username"), data.get("password"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({**login_result, "user": user}), 201


@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(auth.login(data.get("username"), data.get("password")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 401


@app.post("/api/auth/logout")
def logout():
    token = _token()
    if token:
        auth.logout(token)
    return "", 204


@app.get("/api/auth/me")
def current_user():
    user = _user()
    return jsonify({"user": user}) if user else _authentication_error()


@app.get("/api/factors")
def factors():
    return jsonify(factor_store.catalogue())


@app.get("/api/journal")
def journal_entries():
    user = _user()
    if not user:
        return _authentication_error()
    try:
        limit = int(request.args.get("limit", "30"))
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400
    entries = journal.list(user["user_id"], limit, request.args.get("month"))
    return jsonify({"entries": entries, "count": len(entries)})


@app.post("/api/journal")
def save_journal_entry():
    user = _user()
    if not user:
        return _authentication_error()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400
    session = sessions.get(data.get("session_id"))
    if session is None:
        return jsonify({"error": "Session not found or expired"}), 404
    if session.get("user_id") not in {None, user["user_id"]}:
        return jsonify({"error": "Session belongs to a different local account"}), 403
    payload = _response(data["session_id"], session["activities"])
    if payload["status"] != "complete":
        return jsonify({"error": "Resolve the pending clarification before saving"}), 409
    try:
        entry = journal.save(user["user_id"], session["original_text"], payload,
                             data.get("entry_date"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(entry), 201


@app.delete("/api/journal/<entry_id>")
def delete_journal_entry(entry_id):
    user = _user()
    if not user:
        return _authentication_error()
    if not journal.delete(user["user_id"], entry_id):
        return jsonify({"error": "Journal entry not found"}), 404
    return "", 204


@app.get("/api/dashboard")
def dashboard():
    user = _user()
    if not user:
        return _authentication_error()
    month = request.args.get("month") or time.strftime("%Y-%m")
    try:
        result = journal.dashboard(user["user_id"], month)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    result["forecast"] = forecaster.forecast(result.pop("series"), steps=7)
    return jsonify(result)


@app.put("/api/goals/<month>")
def update_goal(month):
    user = _user()
    if not user:
        return _authentication_error()
    data = request.get_json(silent=True) or {}
    try:
        goal = journal.set_goal(user["user_id"], month, data.get("target_kg"))
    except (TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(goal)


def _session_event(session_id, event_id):
    session = sessions.get(session_id)
    if session is None:
        raise ValueError("Session not found or expired")
    event = next((item for item in session["activities"] if item["event_id"] == event_id), None)
    if event is None:
        raise ValueError("Activity event not found")
    return session, event


def _assert_session_access(session):
    """Allow anonymous sessions, but keep account-owned sessions private."""
    owner_id = session.get("user_id")
    if owner_id is None:
        return
    user = _user()
    if not user or user["user_id"] != owner_id:
        raise PermissionError("Session belongs to a different local account")


@app.post("/api/evidence/route")
def route_evidence():
    data = request.get_json(silent=True) or {}
    try:
        session, event = _session_event(data.get("session_id"), data.get("event_id"))
        _assert_session_access(session)
        route = routes.route(data)
    except PermissionError as error:
        return jsonify({"error": str(error)}), 403
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    event["quantity"] = route["distance_km"]
    event["unit"] = "km"
    event["quantity_source"] = "route-service"
    event["confidence"] = "externally-verified"
    event.setdefault("evidence", []).append({
        "kind": "route-distance", "value": route["distance_km"], "unit": "km",
        "verification": "external-service", "provider": route["provider"],
        "reference": route["source_url"], "duration": route.get("duration"),
    })
    session["updated_at"] = time.time()
    return jsonify({**_response(data["session_id"], session["activities"]),
                    "route_evidence": route})


@app.post("/api/evidence/bill")
def bill_evidence():
    upload = request.files.get("bill")
    if upload is None:
        return jsonify({"error": "Attach a bill image in the bill field"}), 400
    try:
        session, _event = _session_event(request.form.get("session_id"),
                                         request.form.get("event_id"))
        _assert_session_access(session)
        result = bill_ocr.extract(upload.read(BillOcrService.MAX_BYTES + 1), upload.filename)
    except PermissionError as error:
        return jsonify({"error": str(error)}), 403
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(result)


@app.post("/api/corrections")
def correct_activity():
    user = _user()
    if not user:
        return _authentication_error()
    data = request.get_json(silent=True) or {}
    try:
        session, event = _session_event(data.get("session_id"), data.get("event_id"))
        _assert_session_access(session)
        label = str(data.get("label", "")).strip()
        if factor_store.resolve(label) is None:
            raise ValueError("Corrected activity does not have an emission factor")
        quantity = data.get("quantity", event.get("quantity"))
        quantity = float(quantity) if quantity is not None else None
        unit = data.get("unit", event.get("unit"))
        extractor.correction_store.save(user["user_id"], event.get("source_text", ""),
                                        label, quantity, unit)
        event.update({"label": label, "quantity": quantity, "unit": unit,
                      "confidence": "user-corrected", "quantity_source": "user-corrected"})
        event.setdefault("evidence", []).append({
            "kind": "user-correction", "value": label, "verification": "authenticated-user"
        })
        session["updated_at"] = time.time()
    except PermissionError as error:
        return jsonify({"error": str(error)}), 403
    except (TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(_response(data["session_id"], session["activities"]))


@app.post("/api/analyze")
def analyze():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400
    entries = data.get("entries")
    if entries is None:
        text = data.get("text", "")
        entries = [text] if isinstance(text, str) else []
    if (not isinstance(entries, list) or len(entries) > 30 or
            any(not isinstance(entry, str) for entry in entries)):
        return jsonify({"error": "Send up to 30 activity entries as text"}), 400
    entries = [entry.strip() for entry in entries if entry.strip()]
    if not entries:
        return jsonify({"error": "Describe at least one daily activity"}), 400
    if any(len(entry) > 1000 for entry in entries) or sum(map(len, entries)) > 5000:
        return jsonify({"error": "Use at most 1,000 characters per activity and 5,000 in total"}), 400

    _remove_expired_sessions()
    session_id = str(uuid.uuid4())
    user = _user()
    activities, unrecognized = [], []
    for index, entry in enumerate(entries):
        extracted = extractor.extract_activities(entry, user["user_id"] if user else None)
        if extracted:
            activities.extend(extracted)
        else:
            unrecognized.append({
                "entry_id": f"entry-{index + 1}", "source_text": entry,
                "reason": "activity-or-factor-not-supported",
            })
    text = "\n".join(entries)
    sessions[session_id] = {
        "activities": activities, "original_text": text, "updated_at": time.time(),
        "unrecognized_entries": unrecognized,
        "user_id": user["user_id"] if user else None,
    }
    return jsonify(_response(session_id, activities))


@app.post("/api/clarify")
def clarify():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400
    session_id, answer = data.get("session_id"), data.get("answer")
    session = sessions.get(session_id)
    if session is None:
        return jsonify({"error": "Session not found or expired; analyze the activity log again"}), 404
    try:
        _assert_session_access(session)
    except PermissionError as error:
        return jsonify({"error": str(error)}), 403
    question = clarifier.next_question(session["activities"])
    if question is None:
        return jsonify({"error": "This session has no pending question"}), 409
    if data.get("question_id") and data["question_id"] != question["question_id"]:
        return jsonify({"error": "The submitted question is no longer current"}), 409
    try:
        clarifier.apply_answer(session["activities"], question, answer)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    session["updated_at"] = time.time()
    return jsonify(_response(session_id, session["activities"]))


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "Request is too large"}), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")),
            debug=os.environ.get("FLASK_DEBUG") == "1")

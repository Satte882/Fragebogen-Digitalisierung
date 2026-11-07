"""FastAPI pilot server. Run a single process: workspaces are intentionally in memory."""
from __future__ import annotations

import base64
from contextlib import asynccontextmanager
from io import BytesIO
import json
import hmac
import re
import time
from uuid import uuid4
import warnings

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

from .config import Settings
from .contracts import Confirmation, Recognition, suggestion
from .demo import make_demo_items
from .export import batch_csv
from .providers import MockProvider, OpenRouterProvider, ProviderError
from .security import Session, WorkspaceStore, verify_password


class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=256)


class RenamePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ModelPayload(BaseModel):
    provider: str
    model: str = Field(default="", max_length=150)


def normalize_image(data: bytes, limit_mb: int) -> bytes:
    if not data or len(data) > limit_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Bilddatei leer oder größer als {limit_mb} MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as original:
                if original.format not in ("JPEG", "PNG"):
                    raise HTTPException(status_code=400, detail="Nur JPEG und PNG erlaubt.")
                if original.width * original.height > 20_000_000:
                    raise HTTPException(status_code=413, detail="Bildauflösung überschreitet 20 Megapixel.")
                oriented = ImageOps.exif_transpose(original)
                oriented.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
                rgb = oriented.convert("RGB")
                output = BytesIO()
                rgb.save(output, format="JPEG", quality=86, optimize=True)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise HTTPException(status_code=400, detail="Bilddatei nicht lesbar oder zu groß aufgelöst.") from exc


def clean_name(name: str, fallback: str = "Neuer Vorgang") -> str:
    value = re.sub(r"[\x00-\x1f\x7f]", " ", name).strip()
    return value[:120] or fallback


def new_item(filename: str, normalized_image: bytes, sequence: int, *, source: str = "upload") -> dict:
    return {
        "id": str(uuid4()), "filename": clean_name(filename, "bild.jpg"), "sequence": sequence,
        "image": normalized_image, "status": "pending", "raw": None, "raw_text": None,
        "final": None, "draft": None, "review_started": False, "review_mode": None, "error": None, "source": source,
    }


def new_batch(name: str, items: list[dict], *, synthetic: bool = False) -> dict:
    return {
        "id": str(uuid4()), "name": clean_name(name), "items": {x["id"]: x for x in items},
        "synthetic": synthetic, "created_at": time.time(),
    }


def item_summary(item: dict) -> dict:
    return {k: item[k] for k in ("id", "filename", "sequence", "status", "review_mode", "review_started", "error", "source")}


def batch_summary(batch: dict) -> dict:
    statuses = [x["status"] for x in batch["items"].values()]
    return {
        "id": batch["id"], "name": batch["name"], "synthetic": batch["synthetic"],
        "count": len(statuses), "confirmed": statuses.count("confirmed"),
        "ready": statuses.count("ready"), "review_required": statuses.count("review_required"),
        "items": [item_summary(x) for x in batch["items"].values()],
    }


def get_batch(session: Session, batch_id: str) -> dict:
    batch = session.batches.get(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden.")
    return batch


def get_item(batch: dict, item_id: str) -> dict:
    item = batch["items"].get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Bild nicht gefunden.")
    return item


def build_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    # Validate before serving any requests; module import remains safe for CI/test collection.
    store = WorkspaceStore(settings.session_ttl_minutes)
    model_config = {"provider": settings.model_provider, "model": settings.openrouter_model}
    usage = {"total_live_calls": 0}
    max_live_calls_per_session = 25
    max_live_calls_global = 80

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        settings.validate()
        yield
        store.sessions.clear()

    app = FastAPI(title="Form Digitizer", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)

    def session_for(request: Request) -> Session:
        session = store.get(request.cookies.get("fd_session"))
        if session is None:
            raise HTTPException(401, "Nicht angemeldet oder Sitzung abgelaufen. Bitte neu anmelden.")
        if request.method in ("POST", "PATCH", "PUT", "DELETE"):
            csrf = request.headers.get("x-csrf-token", "")
            if not csrf or not hmac.compare_digest(csrf, session.csrf):
                raise HTTPException(403, "Ungültiger Formularschutz (CSRF).")
        return session

    def admin_only(session: Session = Depends(session_for)) -> Session:
        if session.role != "admin":
            raise HTTPException(403, "Nur für Administratoren.")
        return session

    @app.middleware("http")
    async def secure_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'self'"
        )
        return response

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/api/login")
    async def login(payload: LoginPayload, response: Response, request: Request):
        # Delay-based online rate limiting for the single-instance demonstration.
        ip = request.client.host if request.client else "unknown"
        if store.is_rate_limited(ip):
            raise HTTPException(429, "Zu viele Anmeldeversuche. Bitte später erneut versuchen.")
        username = payload.username.casefold().strip()
        # Always perform a key derivation to avoid a trivial timing discrepancy.
        configured_hash = settings.admin_password_hash if username == "admin" else settings.test_password_hash
        authenticated = verify_password(payload.password, configured_hash)
        if username not in ("admin", "test") or not authenticated:
            store.record_login_attempt(ip)
            raise HTTPException(401, "Benutzername oder Passwort falsch.")
        session = store.start(username)
        response.set_cookie(
            "fd_session", session.token,
            httponly=True, secure=settings.app_env == "production", samesite="lax",
            max_age=settings.session_ttl_minutes * 60, path="/",
        )
        return {"role": session.role, "csrf": session.csrf, "ttl_minutes": settings.session_ttl_minutes}

    @app.get("/api/me")
    async def me(session: Session = Depends(session_for)):
        return {"role": session.role, "csrf": session.csrf, "ttl_minutes": settings.session_ttl_minutes,
                "provider": model_config["provider"],
                "model": model_config["model"] if model_config["provider"] == "openrouter" else "Demo ohne KI"}

    @app.post("/api/logout")
    async def logout(request: Request, response: Response, session: Session = Depends(session_for)):
        store.end(session.token)
        response.delete_cookie("fd_session", path="/")
        return {"ok": True}

    @app.get("/api/admin/config")
    async def admin_config(session: Session = Depends(admin_only)):
        return {"provider": model_config["provider"], "model": model_config["model"],
                "openrouter_key_configured": bool(settings.openrouter_api_key),
                "provider_note": "Modelleinstellung gilt nur bis zum Serverneustart.",
                "total_live_calls": usage["total_live_calls"], "global_live_call_limit": max_live_calls_global}

    @app.post("/api/admin/config")
    async def update_model(payload: ModelPayload, session: Session = Depends(admin_only)):
        if payload.provider not in ("mock", "openrouter"):
            raise HTTPException(422, "Nur mock und openrouter unterstützt.")
        if payload.provider == "openrouter" and (not settings.openrouter_api_key or not payload.model.strip()):
            raise HTTPException(422, "Für OpenRouter müssen API-Schlüssel und Modell-ID konfiguriert sein.")
        # Admin-controlled model id; server still validates and never accepts arbitrary endpoint URLs.
        model_config.update(provider=payload.provider, model=payload.model.strip())
        return {"provider": model_config["provider"], "model": model_config["model"]}

    @app.get("/api/batches")
    async def batches(session: Session = Depends(session_for)):
        return [batch_summary(x) for x in session.batches.values()]

    @app.post("/api/batches")
    async def create_batch(name: str = Form(...), images: list[UploadFile] = File(...),
                           session: Session = Depends(session_for)):
        if not images or len(images) > settings.max_images_per_session:
            raise HTTPException(400, "Ungültige Anzahl von Bildern.")
        existing_count = sum(len(batch["items"]) for batch in session.batches.values())
        if existing_count + len(images) > settings.max_images_per_session:
            raise HTTPException(429, f"Maximal {settings.max_images_per_session} Bilder pro Anmeldung.")
        items: list[dict] = []
        for index, upload in enumerate(images, 1):
            filename = upload.filename or f"bild_{index}.jpg"
            # Browser relative paths are never trusted as storage paths.
            filename = filename.replace("\\", "/").split("/")[-1]
            if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                raise HTTPException(400, f"Nicht unterstützter Dateityp: {filename[:80]}")
            content = await upload.read(settings.max_upload_mb * 1024 * 1024 + 1)
            normalized = normalize_image(content, settings.max_upload_mb)
            items.append(new_item(filename, normalized, index))
        batch = new_batch(name, items)
        session.batches[batch["id"]] = batch
        return batch_summary(batch)

    @app.post("/api/demo")
    async def add_demo(session: Session = Depends(session_for)):
        fixtures = make_demo_items()
        existing_count = sum(len(batch["items"]) for batch in session.batches.values())
        if existing_count + len(fixtures) > settings.max_images_per_session:
            raise HTTPException(429, "Bildlimit erreicht.")
        items = []
        for seq, (filename, photo, parsed) in enumerate(fixtures, 1):
            item = new_item(filename, photo, seq, source="synthetic_demo")
            item["raw"] = parsed.model_dump()
            item["raw_text"] = json.dumps(item["raw"], ensure_ascii=False)
            item["status"] = parsed.recommended_status
            items.append(item)
        batch = new_batch("Synthetische Demo – keine KI-Verarbeitung", items, synthetic=True)
        session.batches[batch["id"]] = batch
        return batch_summary(batch)

    @app.get("/api/batches/{batch_id}")
    async def batch_detail(batch_id: str, session: Session = Depends(session_for)):
        return batch_summary(get_batch(session, batch_id))

    @app.patch("/api/batches/{batch_id}")
    async def rename_batch(batch_id: str, payload: RenamePayload, session: Session = Depends(session_for)):
        batch = get_batch(session, batch_id)
        batch["name"] = clean_name(payload.name)
        return batch_summary(batch)

    @app.get("/api/batches/{batch_id}/items/{item_id}")
    async def item_detail(batch_id: str, item_id: str, session: Session = Depends(session_for)):
        item = get_item(get_batch(session, batch_id), item_id)
        return {
            **item_summary(item),
            "image_url": "data:image/jpeg;base64," + base64.b64encode(item["image"]).decode("ascii"),
            "raw": item["raw"], "raw_text": item["raw_text"], "final": item["final"], "draft": item["draft"],
        }

    @app.post("/api/batches/{batch_id}/items/{item_id}/recognize")
    async def recognize_item(batch_id: str, item_id: str, session: Session = Depends(session_for)):
        batch = get_batch(session, batch_id)
        item = get_item(batch, item_id)
        if item["status"] == "confirmed":
            raise HTTPException(409, "Ein bestätigter Datensatz kann nicht erneut automatisch verarbeitet werden.")
        if item["source"] == "synthetic_demo":
            raise HTTPException(409, "Synthetische Fixdaten sind keine echte Bilderkennung.")
        if model_config["provider"] == "openrouter":
            if getattr(session, "live_calls", 0) >= max_live_calls_per_session or usage["total_live_calls"] >= max_live_calls_global:
                raise HTTPException(429, "Sicherheitslimit für kostenpflichtige Modellaufrufe erreicht.")
            session.live_calls = getattr(session, "live_calls", 0) + 1
            usage["total_live_calls"] += 1
        provider = (OpenRouterProvider(settings.openrouter_api_key, model_config["model"])
                    if model_config["provider"] == "openrouter" else MockProvider())
        try:
            parsed, raw_text = await provider.recognize(item["image"])
        except ProviderError as exc:
            item["status"] = "error"
            item["error"] = str(exc)
            raise HTTPException(502, str(exc)) from exc
        item["raw"] = parsed.model_dump()
        item["raw_text"] = raw_text[:30000]
        item["final"] = None
        item["draft"] = None
        item["review_started"] = False
        item["error"] = None
        item["status"] = parsed.recommended_status
        return item_summary(item)


    @app.post("/api/batches/{batch_id}/items/{item_id}/review")
    async def start_review(batch_id: str, item_id: str, session: Session = Depends(session_for)):
        item = get_item(get_batch(session, batch_id), item_id)
        if item["status"] not in ("ready", "review_required") or item["raw"] is None:
            raise HTTPException(409, "Das Bild hat noch keinen bearbeitbaren Modellvorschlag.")
        item["review_started"] = True
        return item_summary(item)

    @app.post("/api/batches/{batch_id}/items/{item_id}/reopen")
    async def reopen_item(batch_id: str, item_id: str, session: Session = Depends(session_for)):
        item = get_item(get_batch(session, batch_id), item_id)
        if item["status"] != "confirmed":
            raise HTTPException(409, "Nur bestätigte Datensätze können wieder geöffnet werden.")
        item["draft"] = item["final"]
        item["final"] = None
        item["status"] = "review_required"
        item["review_started"] = True
        item["review_mode"] = None
        return item_summary(item)

    @app.post("/api/batches/{batch_id}/items/{item_id}/confirm")
    async def confirm_item(batch_id: str, item_id: str, payload: Confirmation,
                           session: Session = Depends(session_for)):
        item = get_item(get_batch(session, batch_id), item_id)
        if item["status"] not in ("ready", "review_required") or item["raw"] is None:
            raise HTTPException(409, "Zuerst Bild erkennen oder offenes Ergebnis prüfen.")
        if item["status"] == "review_required" and not item["review_started"]:
            raise HTTPException(409, "Zuerst „Manuell prüfen“ auswählen.")
        original = Recognition.model_validate(item["raw"])
        if any(getattr(payload, f"q{i}").value is not None
               and getattr(payload, f"q{i}").value != getattr(original, f"q{i}").value
               and not payload.evidence_confirmed for i in range(1, 6)):
            raise HTTPException(422, "Für jede neu eingetragene oder geänderte Bewertung ist ein sichtbarer Beleg zu bestätigen.")
        # A final choice may correct an AI error if the operator confirms a visible mark.
        clean_final = payload.model_dump(exclude={"evidence_confirmed"})
        if clean_final["text"]["text_status"] == "unreadable" and clean_final["text"]["german_translation"].strip():
            raise HTTPException(422, "Nicht lesbarer Freitext darf nicht durch erfundenen Text ersetzt werden.")
        baseline = suggestion(original)
        # Normalized to the same final-schema text field names.
        item["review_mode"] = "unchanged" if clean_final == baseline else "corrected"
        item["final"] = clean_final
        item["draft"] = None
        item["review_started"] = False
        item["status"] = "confirmed"
        return item_summary(item)

    @app.post("/api/batches/{batch_id}/confirm-ready")
    async def confirm_all_ready(batch_id: str, session: Session = Depends(session_for)):
        batch = get_batch(session, batch_id)
        accepted = 0
        for item in batch["items"].values():
            if item["status"] != "ready" or not item["raw"]:
                continue
            baseline = suggestion(Recognition.model_validate(item["raw"]))
            # A 'ready' case cannot contain review_required text by construction.
            Confirmation.model_validate(baseline)
            item["final"] = baseline
            item["review_mode"] = "unchanged"
            item["status"] = "confirmed"
            accepted += 1
        return {"accepted": accepted, "batch": batch_summary(batch)}

    @app.get("/api/batches/{batch_id}/export.csv")
    async def export_csv(batch_id: str, session: Session = Depends(session_for)):
        batch = get_batch(session, batch_id)
        if not any(item["status"] == "confirmed" for item in batch["items"].values()):
            raise HTTPException(409, "Noch keine bestätigten Ergebnisse zum Export vorhanden.")
        content = batch_csv(batch)
        headers = {"Content-Disposition": f'attachment; filename="form-digitizer-{batch_id[:8]}.csv"',
                   "X-Exported-Count": str(sum(x["status"] == "confirmed" for x in batch["items"].values())),
                   "X-Unconfirmed-Count": str(sum(x["status"] != "confirmed" for x in batch["items"].values()))}
        return Response(content, media_type="text/csv; charset=utf-8", headers=headers)

    from pathlib import Path
    public = Path(__file__).parent / "static"
    @app.get("/")
    async def index():
        return FileResponse(public / "index.html", media_type="text/html")

    app.mount("/static", StaticFiles(directory=public), name="static")
    # Test harness uses app.state to inspect session isolation without public endpoint.
    app.state.workspaces = store
    app.state.model_config = model_config
    return app


# Keep import-time bootstrapping explicit. The service fails closed without secrets.
app = build_app()

"""FastAPI pilot server. Run a single process: workspaces are intentionally in memory."""
from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from io import BytesIO
import json
import hmac
import re
import time
from uuid import uuid4
import warnings

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException
from starlette.types import ASGIApp, Receive, Scope, Send
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

from .config import Settings
from .contracts import Confirmation, Recognition, suggestion
from .demo import BLANK_FORM, EXAMPLE_FORMS, HANDWRITING_FORMS, make_demo_items
from .export import batch_csv
from .providers import MockProvider, OpenRouterProvider, PROMPT_VERSION, ProviderError
from .security import Session, WorkspaceStore, verify_password


class SmallBodyLimit:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        method = scope.get("method")
        if scope["type"] != "http" or method not in ("POST", "PATCH", "PUT", "DELETE") or (
            method == "POST" and scope["path"] == "/api/batches"
        ):
            await self.app(scope, receive, send)
            return

        chunks = bytearray()
        async for chunk in Request(scope, receive).stream():
            if len(chunks) + len(chunk) > 64 * 1024:
                reply = JSONResponse({"detail": "Anfrage zu groß."}, status_code=413)
                await reply(scope, receive, send)
                return
            chunks.extend(chunk)

        async def replay():
            nonlocal chunks
            if chunks is None:
                return await receive()
            message = {"type": "http.request", "body": bytes(chunks), "more_body": False}
            chunks = None
            return message

        await self.app(scope, replay, send)


class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=256)


class RenamePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ModelPayload(BaseModel):
    provider: str
    model: str = Field(default="", max_length=150)


def normalize_image(data: bytes, limit_mb: int, max_edge: int = 2200, quality: int = 90) -> bytes:
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
                oriented.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
                if "A" in oriented.getbands() or "transparency" in oriented.info:
                    rgba = oriented.convert("RGBA")
                    rgb = Image.new("RGB", rgba.size, "white")
                    rgb.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    rgb = oriented.convert("RGB")
                rgb.info.clear()
                output = BytesIO()
                rgb.save(output, format="JPEG", quality=quality, optimize=True)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise HTTPException(status_code=400, detail="Bilddatei nicht lesbar oder zu groß aufgelöst.") from exc


def clean_name(name: str, fallback: str = "Neuer Vorgang") -> str:
    value = re.sub(r"[\x00-\x1f\x7f]", " ", name).strip()
    return value[:120] or fallback


def make_thumbnail(image: bytes | None) -> bytes | None:
    if image is None:
        return None
    with Image.open(BytesIO(image)) as photo:
        photo.thumbnail((160, 160))
        preview = BytesIO()
        photo.save(preview, format="JPEG", quality=75)
    return preview.getvalue()


def new_item(filename: str, normalized_image: bytes | None, sequence: int, *, source: str = "upload") -> dict:
    return {
        "id": str(uuid4()), "filename": clean_name(filename, "bild.jpg"), "sequence": sequence,
        "image": normalized_image, "thumbnail": make_thumbnail(normalized_image), "status": "pending", "raw": None, "raw_text": None,
        "final": None, "draft": None, "review_started": False, "review_mode": None, "error": None, "source": source,
        "classification": None, "confirmation_source": None, "sample_selected": False,
        "sample_reviewed": False, "sample_corrected": False, "error_code": None, "runs": [], "corrections": [],
    }


def new_batch(name: str, items: list[dict], *, synthetic: bool = False) -> dict:
    return {
        "id": str(uuid4()), "name": clean_name(name), "items": {x["id"]: x for x in items},
        "synthetic": synthetic, "created_at": time.time(), "run": None,
    }


def review_findings(item: dict) -> list[dict]:
    raw = item["raw"]
    if not raw:
        return []
    if item["source"] == "mock_upload":
        return [{"field": "image", "kind": "mock", "reason": "Demo-Modus. Dieses Bild wurde nicht automatisch erkannt."}]
    if item["source"] == "synthetic_demo" and raw["text"]["text_status"] == "review_required":
        return [{"field": "text", "kind": "demo", "reason": "Die fünf Antworten und der Freitext sind korrekt vorgegeben. Der künstliche Prüfhinweis demonstriert die manuelle Prüfung."}]
    findings = list(raw.get("findings", []))
    fields = {finding["field"] for finding in findings}
    for i in range(1, 6):
        field = f"q{i}"
        status = raw[field]["status"]
        if field not in fields and status in ("multiple", "unreadable"):
            reason = "Mehrere Markierungen sichtbar." if status == "multiple" else "Markierung nicht eindeutig lesbar oder zuordenbar."
            findings.append({"field": field, "kind": status, "reason": reason})
    text_status = raw["text"]["text_status"]
    if "text" not in fields and text_status in ("review_required", "unreadable"):
        reason = "Transkription und Übersetzung am Original prüfen." if text_status == "review_required" else "Freitext nicht sicher lesbar."
        findings.append({"field": "text", "kind": text_status, "reason": reason})
    if item["source"] != "synthetic_demo":
        findings.extend({"field": "image", "kind": "other", "reason": warning} for warning in raw["warnings"])
    return findings


def item_summary(item: dict) -> dict:
    return {k: item[k] for k in ("id", "filename", "sequence", "status", "review_mode", "review_started", "error", "source",
                                   "classification", "confirmation_source", "sample_selected", "sample_reviewed",
                                   "sample_corrected", "error_code")} | {
        "has_thumbnail": item["thumbnail"] is not None,
        "findings": review_findings(item),
        "can_recognize": item["source"] != "synthetic_demo" and item["image"] is not None
        and item["status"] in ("pending", "error"),
    }


def batch_summary(batch: dict) -> dict:
    statuses = [x["status"] for x in batch["items"].values()]
    run = batch["run"]
    if run:
        run_statuses = [batch["items"][key]["status"] for key in run["item_ids"]]
        run = {**run, "total": len(run_statuses),
               "done": sum(status not in ("queued", "processing") for status in run_statuses),
               "successful": sum(status in ("ready", "review_required", "confirmed") for status in run_statuses),
               "review_required": run_statuses.count("review_required"), "failed": run_statuses.count("error")}
    return {
        "id": batch["id"], "name": batch["name"], "synthetic": batch["synthetic"],
        "count": len(statuses), "confirmed": statuses.count("confirmed"),
        "ready": statuses.count("ready"), "review_required": statuses.count("review_required"),
        "run": run,
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
    usage = dict(sent=0, succeeded=0, failed=0, repeated=0)
    slots = asyncio.Semaphore(settings.batch_parallelism)
    upload_slot = asyncio.Lock()

    def ensure_image_capacity(session: Session, items: list[dict]) -> None:
        existing = [item for batch in session.batches.values() for item in batch['items'].values()]
        if len(existing) + len(items) > settings.max_images_per_session:
            raise HTTPException(429, 'Bildlimit erreicht.')
        size = sum(len(item['image'] or b'') + len(item['thumbnail'] or b'') for item in existing + items)
        if size > settings.max_workspace_mb * 1024 * 1024:
            raise HTTPException(413, 'Bildspeicher der Sitzung ist voll. Bitte kleinere Fotos verwenden.')
    tasks: set[asyncio.Task] = set()

    def budget(session: Session) -> dict:
        return {
            **session.live_calls,
            "remaining": min(settings.live_calls_per_session - session.live_calls["sent"],
                             settings.live_calls_global - usage["sent"]),
        }

    async def process_item(session: Session, item: dict, provider, model: str) -> None:
        live = not isinstance(provider, MockProvider)
        started = time.monotonic()
        timestamp = datetime.now(timezone.utc).isoformat()
        attempts = 0
        item.update(status="processing", error=None, error_code=None)
        try:
            while True:
                async with slots:
                    if store.get(session.token) is None:
                        raise ProviderError("Sitzung beendet.", code="session_ended")
                    if live and budget(session)["remaining"] <= 0:
                        raise ProviderError("Technisches Modellaufrufbudget erschöpft.", code="budget")
                    repeated = attempts > 0 or any(run["calls"] for run in item["runs"])
                    attempts += 1
                    if live:
                        for counter in (session.live_calls, usage):
                            counter["sent"] += 1
                            counter["repeated"] += int(repeated)
                    try:
                        parsed, raw_text = await provider.recognize(item["image"])
                    except ProviderError as exc:
                        error = exc
                        if live:
                            for counter in (session.live_calls, usage):
                                counter["failed"] += 1
                    except (Exception, asyncio.CancelledError):
                        if live:
                            for counter in (session.live_calls, usage):
                                counter["failed"] += 1
                        raise
                    else:
                        if live:
                            for counter in (session.live_calls, usage):
                                counter["succeeded"] += 1
                        break
                if (error.code not in ("rate_limit", "timeout", "provider_unavailable")
                        or attempts > settings.provider_retries or error.retry_after > 30):
                    raise error
                await asyncio.sleep(max(error.retry_after, 0.5 * 2 ** (attempts - 1)))
            source = item["source"] if item["source"] == "handwriting_example" else ("upload" if live else "mock_upload")
            item.update(source=source, raw=parsed.model_dump(),
                        raw_text=raw_text, status=parsed.recommended_status,
                        classification=parsed.recommended_status)
        except ProviderError as exc:
            item.update(status="error", error=str(exc), error_code=exc.code)
        finally:
            if item["status"] == "processing":
                item.update(status="error", error="Verarbeitung unterbrochen.", error_code="interrupted")
            item["runs"].append({
                "model": model, "prompt_version": PROMPT_VERSION, "timestamp": timestamp,
                "duration_seconds": round(time.monotonic() - started, 3),
                "status": item["status"], "error_code": item["error_code"], "calls": attempts if live else 0,
            })

    def configured_provider(expected_provider: str | None = None, *, requires_live: bool = False):
        if expected_provider is not None and model_config['provider'] != expected_provider:
            raise HTTPException(409, 'Der Modellmodus wurde geändert. Bitte starte die Verarbeitung erneut.')
        if model_config["provider"] == "openrouter":
            return OpenRouterProvider(settings.openrouter_api_key, model_config["model"]), model_config["model"]
        if requires_live:
            raise HTTPException(409, "Handschrift-Beispiele benötigen aktive KI-Erkennung über OpenRouter.")
        return MockProvider(), "mock"

    async def process_batch(session: Session, batch: dict, items: list[dict], provider, model: str) -> None:
        queue = iter(items)

        async def worker():
            for item in queue:
                if store.get(session.token) is None:
                    break
                try:
                    await process_item(session, item, provider, model)
                except Exception:
                    # Keep the other images running. Never expose provider payloads.
                    item.update(status="error", error="Interner Verarbeitungsfehler.", error_code="interrupted")

        try:
            await asyncio.gather(*(worker() for _ in range(min(settings.batch_parallelism, len(items)))))
        finally:
            batch["run"]["active"] = False

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        settings.validate()
        yield
        for task in tuple(tasks):
            task.cancel()
        await asyncio.gather(*tuple(tasks), return_exceptions=True)
        store.sessions.clear()

    app = FastAPI(title="Form Digitizer", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    app.add_middleware(SmallBodyLimit)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        details = [{key: error[key] for key in ('loc', 'msg', 'type')} for error in exc.errors()]
        return JSONResponse({'detail': details}, status_code=422)

    async def session_for(request: Request) -> Session:
        session = store.get(request.cookies.get("fd_session"))
        if session is None:
            raise HTTPException(401, "Nicht angemeldet oder Sitzung abgelaufen. Bitte neu anmelden.")
        if request.method in ("POST", "PATCH", "PUT", "DELETE"):
            csrf = request.headers.get("x-csrf-token", "")
            if not csrf or not hmac.compare_digest(csrf.encode(), session.csrf.encode()):
                raise HTTPException(403, "Ungültiger Formularschutz (CSRF).")
        return session

    async def admin_only(session: Session = Depends(session_for)) -> Session:
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
        # Bound authentication work independently of proxy IP forwarding.
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
        store.end(request.cookies.get("fd_session"))
        if len(store.sessions) >= settings.max_sessions:
            raise HTTPException(429, 'Zu viele aktive Sitzungen. Bitte später erneut anmelden.')
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
                "remaining_seconds": max(0, int(session.created_at + store.ttl_seconds - store.now())),
                "budget": budget(session), "provider": model_config["provider"],
                "model": model_config["model"] if model_config["provider"] == "openrouter" else "Demo ohne KI"}

    @app.post("/api/logout")
    async def logout(request: Request, response: Response, session: Session = Depends(session_for)):
        store.end(session.token)
        response.delete_cookie("fd_session", path="/", secure=settings.app_env == "production", httponly=True)
        return {"ok": True}

    @app.get("/api/admin/config")
    async def admin_config(session: Session = Depends(admin_only)):
        return {"provider": model_config["provider"], "model": model_config["model"],
                "openrouter_key_configured": bool(settings.openrouter_api_key),
                "provider_note": "Modelleinstellung gilt nur bis zum Serverneustart.",
                "total_live_calls": usage["sent"], "global_live_call_limit": settings.live_calls_global,
                "calls": usage, "budget": budget(session)}

    @app.post("/api/admin/config")
    async def update_model(payload: ModelPayload, session: Session = Depends(admin_only)):
        if payload.provider not in ("mock", "openrouter"):
            raise HTTPException(422, "Nur mock und openrouter unterstützt.")
        if payload.provider == "openrouter" and not settings.allow_live_model:
            raise HTTPException(403, "Live-Modell ist in dieser Bereitstellung deaktiviert.")
        if payload.provider == "openrouter" and (not settings.openrouter_api_key or not payload.model.strip()):
            raise HTTPException(422, "Für OpenRouter müssen API-Schlüssel und Modell-ID konfiguriert sein.")
        # Admin-controlled model id; server still validates and never accepts arbitrary endpoint URLs.
        model_config.update(provider=payload.provider, model=payload.model.strip())
        return {"provider": model_config["provider"], "model": model_config["model"]}

    @app.get("/api/batches")
    async def batches(session: Session = Depends(session_for)):
        return [batch_summary(x) for x in session.batches.values()]

    @app.post("/api/batches")
    async def create_batch(request: Request, session: Session = Depends(session_for)):
        if upload_slot.locked():
            raise HTTPException(429, 'Ein Upload läuft bereits. Bitte gleich erneut versuchen.')
        async with upload_slot:
            return await receive_batch(request, session)

    async def receive_batch(request: Request, session: Session):
        limit = settings.max_upload_mb * 1024 * 1024
        body_limit = min(settings.max_images_per_session * limit, settings.max_batch_upload_mb * 1024 * 1024) + 64 * 1024
        received = 0

        async def limited_receive():
            nonlocal received
            message = await request.receive()
            received += len(message.get("body", b""))
            if received > body_limit:
                # The multipart parser closes spooled files on this exception.
                raise MultiPartException("Gesamter Upload zu groß.")
            return message

        bounded_request = Request(request.scope, limited_receive)
        items: list[dict] = []
        first_error = None
        async with bounded_request.form(max_files=settings.max_images_per_session, max_fields=1) as form:
            name = form.get("name")
            images = form.getlist("images")
            if not isinstance(name, str) or not images or not all(isinstance(x, UploadFile) for x in images):
                raise HTTPException(422, "Vorgangsname und mindestens ein Bild erforderlich.")
            for index, upload in enumerate(images, 1):
                filename = upload.filename or f"bild_{index}.jpg"
                filename = filename.replace("\\", "/").split("/")[-1]
                try:
                    if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                        raise HTTPException(400, "Nur JPEG und PNG erlaubt.")
                    content = await upload.read(limit + 1)
                    normalized = normalize_image(content, settings.max_upload_mb, settings.image_max_edge, settings.image_jpeg_quality)
                    candidate = new_item(filename, normalized, index)
                    ensure_image_capacity(session, items + [candidate])
                    items.append(candidate)
                except HTTPException as exc:
                    if first_error is None:
                        first_error = exc
                    item = new_item(filename, None, index)
                    item.update(status="error", error=exc.detail, error_code="invalid_image")
                    items.append(item)
        if first_error is not None and all(item["image"] is None for item in items):
            raise first_error
        if store.get(session.token) is None:
            raise HTTPException(401, "Sitzung abgelaufen.")
        ensure_image_capacity(session, items)
        batch = new_batch(name, items)
        session.batches[batch["id"]] = batch
        return batch_summary(batch)

    @app.post("/api/demo")
    async def add_demo(full_batch: bool = False, session: Session = Depends(session_for)):
        fixtures = make_demo_items()
        if full_batch:
            fixtures = [fixtures[0]] * 26 + [fixtures[1]] * 4
        existing_count = sum(len(batch["items"]) for batch in session.batches.values())
        if existing_count + len(fixtures) > settings.max_images_per_session:
            raise HTTPException(429, "Bildlimit erreicht.")
        items = []
        for seq, (filename, photo, parsed) in enumerate(fixtures, 1):
            if full_batch:
                filename = f"demo_{seq:02d}.jpg"
            item = new_item(filename, photo, seq, source="synthetic_demo")
            item["raw"] = parsed.model_dump()
            item["raw_text"] = json.dumps(item["raw"], ensure_ascii=False)
            item["status"] = item["classification"] = parsed.recommended_status
            items.append(item)
        ensure_image_capacity(session, items)
        name = "Batch-Demo · 30 synthetische Bögen" if full_batch else "Synthetische Demo – keine KI-Verarbeitung"
        batch = new_batch(name, items, synthetic=True)
        session.batches[batch["id"]] = batch
        return batch_summary(batch)

    def handwriting_items() -> list[dict]:
        return [
            new_item(name, normalize_image((EXAMPLE_FORMS / name).read_bytes(),
                                           settings.max_upload_mb, settings.image_max_edge,
                                           settings.image_jpeg_quality),
                     number, source="handwriting_example")
            for number, name in enumerate(HANDWRITING_FORMS, 1)
        ]

    @app.post("/api/examples/handwriting")
    async def add_handwriting_examples(session: Session = Depends(session_for)):
        existing_count = sum(len(batch["items"]) for batch in session.batches.values())
        if existing_count + len(HANDWRITING_FORMS) > settings.max_images_per_session:
            raise HTTPException(429, "Bildlimit erreicht.")
        if upload_slot.locked():
            raise HTTPException(429, "Bilder werden bereits vorbereitet. Bitte gleich erneut versuchen.")
        async with upload_slot:
            items = await asyncio.to_thread(handwriting_items)
            if store.get(session.token) is None:
                raise HTTPException(401, "Sitzung abgelaufen.")
            ensure_image_capacity(session, items)
            batch = new_batch("Handschrift-Beispiele · 5 Testbögen", items)
            session.batches[batch["id"]] = batch
        return batch_summary(batch)

    @app.get("/api/examples/blank-form")
    async def download_blank_form(session: Session = Depends(session_for)):
        return FileResponse(EXAMPLE_FORMS / BLANK_FORM, media_type="image/png", filename=BLANK_FORM)

    @app.get("/api/batches/{batch_id}")
    async def batch_detail(batch_id: str, session: Session = Depends(session_for)):
        return {**batch_summary(get_batch(session, batch_id)), "budget": budget(session)}

    @app.patch("/api/batches/{batch_id}")
    async def rename_batch(batch_id: str, payload: RenamePayload, session: Session = Depends(session_for)):
        batch = get_batch(session, batch_id)
        batch["name"] = clean_name(payload.name)
        return batch_summary(batch)

    @app.delete("/api/batches/{batch_id}", status_code=204)
    async def delete_batch(batch_id: str, session: Session = Depends(session_for)):
        batch = get_batch(session, batch_id)
        if (batch["run"] and batch["run"]["active"]) or any(
            item["status"] in ("queued", "processing") for item in batch["items"].values()
        ):
            raise HTTPException(409, "Der Vorgang wird noch verarbeitet. Bitte warte bis zum Ende.")
        del session.batches[batch_id]
        return Response(status_code=204)

    @app.get("/api/batches/{batch_id}/items/{item_id}/thumbnail")
    async def thumbnail(batch_id: str, item_id: str, session: Session = Depends(session_for)):
        item = get_item(get_batch(session, batch_id), item_id)
        if item["thumbnail"] is None:
            raise HTTPException(404, "Keine Bildvorschau vorhanden.")
        return Response(item["thumbnail"], media_type="image/jpeg")

    @app.get("/api/batches/{batch_id}/items/{item_id}")
    async def item_detail(batch_id: str, item_id: str, session: Session = Depends(session_for)):
        item = get_item(get_batch(session, batch_id), item_id)
        return {
            **item_summary(item),
            "image_url": ("data:image/jpeg;base64," + base64.b64encode(item["image"]).decode("ascii")
                          if item["image"] is not None else None),
            "raw": item["raw"], "raw_text": item["raw_text"], "final": item["final"], "draft": item["draft"], "runs": item["runs"], "corrections": item["corrections"],
        }

    @app.post("/api/batches/{batch_id}/items/{item_id}/recognize")
    async def recognize_item(batch_id: str, item_id: str, expected_provider: str | None = None,
                             session: Session = Depends(session_for)):
        batch = get_batch(session, batch_id)
        item = get_item(batch, item_id)
        if item["status"] == "confirmed":
            raise HTTPException(409, "Ein bestätigter Datensatz kann nicht erneut automatisch verarbeitet werden.")
        if item["source"] == "synthetic_demo":
            raise HTTPException(409, "Synthetische Fixdaten sind keine echte Bilderkennung.")
        if item["status"] not in ("pending", "error") or item["image"] is None:
            raise HTTPException(409, "Dieses Foto kann derzeit nicht erkannt werden.")
        await process_item(session, item, *configured_provider(
            expected_provider, requires_live=item["source"] == "handwriting_example"))
        if item["status"] == "error":
            raise HTTPException(429 if item["error_code"] in ("budget", "rate_limit") else 502, item["error"])
        return item_summary(item)

    @app.post("/api/batches/{batch_id}/process", status_code=202)
    async def start_processing(batch_id: str, retry_failed: bool = False, expected_provider: str | None = None,
                               session: Session = Depends(session_for)):
        batch = get_batch(session, batch_id)
        if batch["run"] and batch["run"]["active"]:
            return batch_summary(batch)
        expected = "error" if retry_failed else "pending"
        items = [item for item in batch["items"].values()
                 if item["status"] == expected and item["image"] is not None]
        if not items:
            raise HTTPException(409, "Keine passenden Bögen zur Verarbeitung.")
        provider, model = configured_provider(
            expected_provider, requires_live=any(item["source"] == "handwriting_example" for item in items))
        if not batch["synthetic"] and model_config["provider"] == "openrouter" and budget(session)["remaining"] <= 0:
            raise HTTPException(429, "Technisches Modellaufrufbudget erschöpft.")
        for item in items:
            item["status"] = "queued"
        batch["run"] = {"id": str(uuid4()), "active": True, "item_ids": [item["id"] for item in items]}
        task = asyncio.create_task(process_batch(session, batch, items, provider, model))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        return batch_summary(batch)

    @app.get("/api/batches/{batch_id}/process")
    async def processing_status(batch_id: str, session: Session = Depends(session_for)):
        return {**batch_summary(get_batch(session, batch_id)), "budget": budget(session)}


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
        item["review_mode"] = item["confirmation_source"] = None
        return item_summary(item)

    @app.post("/api/batches/{batch_id}/items/{item_id}/confirm")
    async def confirm_item(batch_id: str, item_id: str, payload: Confirmation,
                           session: Session = Depends(session_for)):
        item = get_item(get_batch(session, batch_id), item_id)
        if item["status"] not in ("ready", "review_required") or item["raw"] is None:
            raise HTTPException(409, "Zuerst Bild erkennen oder offenes Ergebnis prüfen.")
        original = Recognition.model_validate(item["raw"])
        changed_fields = [
            field for field in ("q1", "q2", "q3", "q4", "q5")
            if getattr(payload, field).model_dump() != getattr(original, field).model_dump()
        ]
        if payload.text.german_translation != original.text.german_translation:
            changed_fields.append("text")
        if changed_fields and not payload.evidence_confirmed:
            raise HTTPException(422, "Für jede geänderte Antwort oder Übersetzung ist ein sichtbarer Beleg zu bestätigen.")
        reasons = {}
        for field in changed_fields:
            if field == "text" or getattr(original, field).status != "multiple" or getattr(payload, field).status != "answered":
                continue
            reason = payload.multiple_reasons.get(field, "").strip()
            if reason:
                reasons[field] = reason
        clean_final = payload.model_dump(exclude={"evidence_confirmed", "multiple_reasons"})
        if clean_final["text"]["text_status"] == "unreadable" and clean_final["text"]["german_translation"].strip():
            raise HTTPException(422, "Nicht lesbarer Freitext darf nicht durch erfundenen Text ersetzt werden.")
        baseline = suggestion(original)
        changed_fields = [field for field in baseline if clean_final[field] != baseline[field]]
        if changed_fields and len(item["corrections"]) >= 20:
            raise HTTPException(409, "Korrekturlimit dieses Bogens erreicht.")
        item["review_mode"] = "corrected" if changed_fields else "unchanged"
        item["confirmation_source"] = "sample" if item["sample_selected"] else "individual"
        if item["sample_selected"]:
            item["sample_reviewed"] = True
            item["sample_corrected"] |= item["review_mode"] == "corrected"
            item["sample_selected"] = False
        if changed_fields:
            item["corrections"].append({
                "fields": changed_fields, "attested_by_role": session.role,
                "evidence_confirmed": payload.evidence_confirmed, "multiple_reasons": reasons,
                "before": {key: baseline[key] for key in changed_fields},
                "after": {key: clean_final[key] for key in changed_fields},
                "attested_at": datetime.now(timezone.utc).isoformat(),
                "confirmation_source": item["confirmation_source"],
            })
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
            if item["status"] != "ready" or not item["raw"] or item["review_started"]:
                continue
            baseline = suggestion(Recognition.model_validate(item["raw"]))
            # A 'ready' case cannot contain review_required text by construction.
            Confirmation.model_validate(baseline)
            item["final"] = baseline
            item["review_mode"] = "unchanged"
            item["confirmation_source"] = "bulk"
            item["sample_selected"] = False
            item["status"] = "confirmed"
            accepted += 1
        return {"accepted": accepted, "batch": batch_summary(batch)}

    @app.post("/api/batches/{batch_id}/sample")
    async def suggest_sample(batch_id: str, session: Session = Depends(session_for)):
        batch = get_batch(session, batch_id)
        items = batch["items"].values()
        if not any(item["sample_selected"] for item in items):
            candidates = sorted((item for item in items if item["status"] == "ready"
                                 and not item["sample_reviewed"] and not item["review_started"]),
                                key=lambda item: item["id"])
            for item in candidates[:5]:
                item["sample_selected"] = True
        return batch_summary(batch)

    @app.get("/api/batches/{batch_id}/evaluation")
    async def evaluation_data(batch_id: str, session: Session = Depends(session_for)):
        batch = get_batch(session, batch_id)
        return {"source": "live", "cases": [
            {"id": item["id"], "filename": item["filename"], "recognition": item["raw"],
             "classification": item["classification"], "review_mode": item["review_mode"], "final": item["final"],
             "confirmation_source": item["confirmation_source"], "runs": item["runs"]}
            for item in batch["items"].values() if item["source"] in ("upload", "handwriting_example") and item["runs"]
            and any(run["calls"] for run in item["runs"])
        ]}

    @app.get("/api/batches/{batch_id}/corrections")
    async def current_corrections(batch_id: str, session: Session = Depends(session_for)):
        batch = get_batch(session, batch_id)
        changes = []
        for item in batch["items"].values():
            if item["status"] != "confirmed" or item["review_mode"] != "corrected" or not item["corrections"]:
                continue
            latest = item["corrections"][-1]
            changes.extend({
                "sequence": item["sequence"], "field": field, "before": latest["before"][field],
                "after": latest["after"][field], "reason": latest.get("multiple_reasons", {}).get(field),
            } for field in latest["fields"])
        return {"changes": changes}

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
    app.state.settings = settings
    app.state.workspaces = store
    app.state.model_config = model_config
    return app


# Keep import-time bootstrapping explicit. The service fails closed without secrets.
app = build_app()

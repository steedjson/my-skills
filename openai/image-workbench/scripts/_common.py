#!/usr/bin/env python3
"""Shared provider, model-discovery, HTTP, image, and size helpers."""

from __future__ import annotations

import base64
import json
import math
import os
import re
import ssl
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

OFFICIAL_BASE_URL = "https://api.openai.com/v1"
OFFICIAL_IMAGE_GUIDE = "https://developers.openai.com/api/docs/guides/image-generation.md"
FALLBACK_OFFICIAL_MODELS = (
    "gpt-image-2",
    "gpt-image-1.5",
    "gpt-image-1",
    "gpt-image-1-mini",
)


class WorkbenchError(RuntimeError):
    """A user-actionable workbench error."""


class ApiError(WorkbenchError):
    def __init__(self, status: int | None, message: str, url: str):
        self.status = status
        self.url = url
        super().__init__(message)


@dataclass
class ProviderConfig:
    base_url: str
    base_source: str
    provider_name: str
    api_key: str | None
    key_source: str
    codex_home: str

    @property
    def is_official(self) -> bool:
        host = (urllib.parse.urlparse(self.base_url).hostname or "").lower()
        return host == "api.openai.com"

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("api_key", None)
        data["api_key_configured"] = bool(self.api_key)
        data["provider_category"] = "official_openai" if self.is_official else "third_party"
        return data


def _codex_home(value: str | None = None) -> Path:
    if value:
        return Path(value).expanduser()
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib

        value = tomllib.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def resolve_provider(
    *,
    base_url: str | None = None,
    api_key_env: str | None = None,
    codex_home: str | None = None,
) -> ProviderConfig:
    home = _codex_home(codex_home)
    config = _read_toml(home / "config.toml")
    active_name = str(config.get("model_provider") or "openai")
    providers = config.get("model_providers")
    active_provider = providers.get(active_name, {}) if isinstance(providers, dict) else {}

    if base_url:
        resolved_base = base_url
        base_source = "explicit_argument"
        provider_name = "explicit"
    elif os.environ.get("OPENAI_BASE_URL"):
        resolved_base = os.environ["OPENAI_BASE_URL"]
        base_source = "environment:OPENAI_BASE_URL"
        provider_name = "environment"
    elif os.environ.get("OPENAI_API_BASE"):
        resolved_base = os.environ["OPENAI_API_BASE"]
        base_source = "environment:OPENAI_API_BASE"
        provider_name = "environment"
    elif isinstance(active_provider, dict) and active_provider.get("base_url"):
        resolved_base = str(active_provider["base_url"])
        base_source = f"codex_config:model_providers.{active_name}.base_url"
        provider_name = active_name
    else:
        resolved_base = OFFICIAL_BASE_URL
        base_source = "official_default"
        provider_name = "openai"

    resolved_base = resolved_base.strip().rstrip("/")
    parsed = urllib.parse.urlparse(resolved_base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise WorkbenchError(f"Invalid Base URL: {resolved_base!r}")

    auth = _read_json(home / "auth.json")
    auth_candidate = auth.get("OPENAI_API_KEY")
    auth_key = auth_candidate if isinstance(auth_candidate, str) and auth_candidate.strip() else None

    if api_key_env:
        api_key = os.environ.get(api_key_env)
        key_source = f"environment:{api_key_env}" if api_key else f"missing_environment:{api_key_env}"
    elif base_source.startswith("codex_config:"):
        # Keep the active Codex provider and its Codex-managed API key paired.
        # A stray OPENAI_API_KEY may belong to a different provider.
        api_key = auth_key
        key_source = "codex_auth:OPENAI_API_KEY" if auth_key else "not_found_in_codex_auth"
    elif base_source.startswith("environment:"):
        api_key = os.environ.get("OPENAI_API_KEY")
        key_source = "environment:OPENAI_API_KEY" if api_key else "not_found_in_environment"
    elif base_source == "explicit_argument":
        api_key = os.environ.get("OPENAI_API_KEY")
        key_source = "environment:OPENAI_API_KEY" if api_key else "not_found_for_explicit_provider"
    elif os.environ.get("OPENAI_API_KEY"):
        api_key = os.environ["OPENAI_API_KEY"]
        key_source = "environment:OPENAI_API_KEY"
    else:
        api_key = auth_key
        key_source = "codex_auth:OPENAI_API_KEY" if api_key else "not_found"

    return ProviderConfig(
        base_url=resolved_base,
        base_source=base_source,
        provider_name=provider_name,
        api_key=api_key,
        key_source=key_source,
        codex_home=str(home),
    )


def endpoint_candidates(base_url: str, endpoint: str) -> list[str]:
    base = base_url.rstrip("/")
    suffix = "/" + endpoint.lstrip("/")
    candidates = [base + suffix]
    if not base.lower().endswith("/v1"):
        candidates.append(base + "/v1" + suffix)
    return list(dict.fromkeys(candidates))


def _safe_error_body(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")[:1800]
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                return str(error.get("message") or error.get("code") or "API error")[:1000]
            if isinstance(error, str):
                return error[:1000]
            return str(payload.get("message") or "API error")[:1000]
    except ValueError:
        pass
    return re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", text)[:1000]


def request_bytes(
    *,
    url: str,
    method: str = "GET",
    api_key: str | None = None,
    body: bytes | None = None,
    content_type: str | None = None,
    timeout: int = 180,
) -> tuple[bytes, str]:
    headers = {"User-Agent": "image-workbench/1.0", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as response:
            return response.read(), response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        raise ApiError(exc.code, _safe_error_body(raw), url) from None
    except urllib.error.URLError as exc:
        raise ApiError(None, f"Network error: {exc.reason}", url) from None


def request_json(
    *,
    url: str,
    method: str = "GET",
    api_key: str | None = None,
    payload: dict[str, Any] | None = None,
    body: bytes | None = None,
    content_type: str | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        content_type = "application/json"
    raw, _ = request_bytes(
        url=url,
        method=method,
        api_key=api_key,
        body=body,
        content_type=content_type,
        timeout=timeout,
    )
    try:
        result = json.loads(raw)
    except ValueError as exc:
        raise ApiError(None, f"Provider returned non-JSON data: {exc}", url) from None
    if not isinstance(result, dict):
        raise ApiError(None, "Provider returned an unexpected JSON shape", url)
    return result


def request_json_with_path_probe(
    *,
    config: ProviderConfig,
    endpoint: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    body_factory: Any = None,
    timeout: int = 180,
) -> tuple[dict[str, Any], str]:
    last_error: ApiError | None = None
    for index, url in enumerate(endpoint_candidates(config.base_url, endpoint)):
        try:
            if body_factory is None:
                return request_json(
                    url=url,
                    method=method,
                    api_key=config.api_key,
                    payload=payload,
                    timeout=timeout,
                ), url
            body, content_type = body_factory()
            return request_json(
                url=url,
                method=method,
                api_key=config.api_key,
                body=body,
                content_type=content_type,
                timeout=timeout,
            ), url
        except ApiError as exc:
            last_error = exc
            if exc.status not in {404, 405} or index == len(endpoint_candidates(config.base_url, endpoint)) - 1:
                raise
    assert last_error is not None
    raise last_error


def _extract_models(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("data", payload.get("models", []))
    values: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                values.append(item)
            elif isinstance(item, dict) and isinstance(item.get("id"), str):
                values.append(item["id"])
    return sorted(set(values))


def fetch_provider_models(config: ProviderConfig, timeout: int = 30) -> tuple[list[str], str]:
    if not config.api_key:
        raise WorkbenchError("No API key is configured for provider model discovery")
    payload, url = request_json_with_path_probe(config=config, endpoint="models", timeout=timeout)
    return _extract_models(payload), url


def _model_sort_key(model: str) -> tuple[Any, ...]:
    match = re.fullmatch(r"gpt-image-(\d+(?:\.\d+)?)(?:-(.*))?", model)
    if not match:
        return (0, model)
    number = tuple(int(part) for part in match.group(1).split("."))
    suffix = match.group(2) or ""
    stable_bonus = 1 if not suffix else 0
    mini_penalty = -1 if "mini" in suffix else 0
    return (1, number, stable_bonus, mini_penalty, model)


def fetch_official_image_models(timeout: int = 30) -> tuple[list[str], str, str | None]:
    warning: str | None = None
    try:
        raw, _ = request_bytes(url=OFFICIAL_IMAGE_GUIDE, timeout=timeout)
        text = raw.decode("utf-8", errors="replace")
        models = set(re.findall(r"\bgpt-image-[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)?(?:-[a-zA-Z0-9]+)*\b", text))
        cleaned = sorted((m.rstrip(".,;:)]") for m in models), key=_model_sort_key, reverse=True)
        if cleaned:
            return cleaned, "live_official_guide", None
        warning = "Official guide was reachable but no image model names were parsed"
    except WorkbenchError as exc:
        warning = str(exc)
    return list(FALLBACK_OFFICIAL_MODELS), "bundled_fallback", warning


def discover_models(config: ProviderConfig, timeout: int = 30) -> dict[str, Any]:
    official, official_source, official_warning = fetch_official_image_models(timeout=timeout)
    provider_models: list[str] = []
    provider_url: str | None = None
    provider_error: str | None = None
    try:
        provider_models, provider_url = fetch_provider_models(config, timeout=timeout)
    except WorkbenchError as exc:
        provider_error = str(exc)

    official_set = set(official)
    provider_set = set(provider_models)
    available = sorted(official_set & provider_set, key=_model_sort_key, reverse=True)
    unavailable = sorted(official_set - provider_set, key=_model_sort_key, reverse=True) if provider_models else official
    provider_only = sorted(
        m for m in provider_set - official_set if re.search(r"(?:image|dall-?e)", m, re.I)
    )
    return {
        "provider": config.public_dict(),
        "official_models": official,
        "official_source": official_source,
        "official_warning": official_warning,
        "provider_models_endpoint": provider_url,
        "provider_model_count": len(provider_models),
        "official_available_from_provider": available,
        "official_unavailable_from_provider": unavailable,
        "provider_only_image_like_models": provider_only,
        "provider_discovery_error": provider_error,
    }


def choose_model(discovery: dict[str, Any], requested: str, require_transparency: bool = False) -> str:
    available = list(discovery.get("official_available_from_provider") or [])
    provider_models_known = not discovery.get("provider_discovery_error")
    provider_only = list(discovery.get("provider_only_image_like_models") or [])
    all_known = set(available) | set(provider_only)
    if requested != "auto":
        if provider_models_known and requested not in all_known:
            raise WorkbenchError(f"Requested model {requested!r} is not exposed by the configured provider")
        if require_transparency and requested == "gpt-image-2":
            raise WorkbenchError("gpt-image-2 does not support transparent backgrounds")
        return requested

    compatible = [m for m in available if not (require_transparency and m == "gpt-image-2")]
    if compatible:
        return compatible[0]
    if provider_only:
        raise WorkbenchError(
            "Only provider-specific image-like models were found; choose one explicitly after checking its capabilities"
        )
    if discovery.get("provider_discovery_error"):
        official = [
            m for m in discovery.get("official_models", []) if not (require_transparency and m == "gpt-image-2")
        ]
        if official:
            return official[0]
    raise WorkbenchError("No compatible image model could be selected")


def parse_size(value: str) -> tuple[int, int] | None:
    if value.lower() == "auto":
        return None
    match = re.fullmatch(r"\s*(\d+)\s*[x×]\s*(\d+)\s*", value, re.I)
    if not match:
        raise WorkbenchError("Size must be 'auto' or WIDTHxHEIGHT, for example 1920x1080")
    width, height = int(match.group(1)), int(match.group(2))
    if width < 1 or height < 1:
        raise WorkbenchError("Width and height must be positive")
    return width, height


def _round_up(value: float, multiple: int = 16) -> int:
    return int(math.ceil(value / multiple) * multiple)


def _round_down(value: float, multiple: int = 16) -> int:
    return max(multiple, int(math.floor(value / multiple) * multiple))


def _constrain_gpt_image_2(width: int, height: int) -> tuple[int, int, list[str]]:
    notes: list[str] = []
    w, h = _round_up(width), _round_up(height)
    if (w, h) != (width, height):
        notes.append("rounded API dimensions up to multiples of 16")

    long_edge, short_edge = max(w, h), min(w, h)
    if long_edge / short_edge > 3:
        if w >= h:
            h = _round_up(w / 3)
        else:
            w = _round_up(h / 3)
        notes.append("expanded the short edge to satisfy the 3:1 API aspect-ratio limit")

    pixels = w * h
    if pixels < 655_360:
        scale = math.sqrt(655_360 / pixels)
        w, h = _round_up(w * scale), _round_up(h * scale)
        notes.append("scaled API dimensions up to the minimum pixel count")

    if max(w, h) > 3840:
        scale = 3840 / max(w, h)
        w, h = _round_down(w * scale), _round_down(h * scale)
        notes.append("scaled API dimensions down to the maximum edge")

    pixels = w * h
    if pixels > 8_294_400:
        scale = math.sqrt(8_294_400 / pixels)
        w, h = _round_down(w * scale), _round_down(h * scale)
        notes.append("scaled API dimensions down to the maximum pixel count")

    if max(w, h) / min(w, h) > 3 or w * h < 655_360 or w * h > 8_294_400:
        raise WorkbenchError("Could not derive a valid gpt-image-2 API size for the requested dimensions")
    return w, h, notes


def normalize_size(requested: str, model: str, fit: str) -> dict[str, Any]:
    if fit not in {"crop", "contain", "stretch", "none"}:
        raise WorkbenchError("fit must be crop, contain, stretch, or none")
    parsed = parse_size(requested)
    if parsed is None:
        return {
            "requested_size": "auto",
            "api_size": "auto",
            "final_size": "provider_selected",
            "fit": fit,
            "postprocess_required": False,
            "notes": [],
        }
    width, height = parsed
    notes: list[str] = []
    if model == "gpt-image-2":
        api_w, api_h, notes = _constrain_gpt_image_2(width, height)
    else:
        ratio = width / height
        if ratio > 1.2:
            api_w, api_h = 1536, 1024
        elif ratio < 1 / 1.2:
            api_w, api_h = 1024, 1536
        else:
            api_w, api_h = 1024, 1024
        notes.append("selected a documented GPT Image preset by aspect ratio; verify provider support")
    api_size = f"{api_w}x{api_h}"
    final_size = f"{width}x{height}"
    return {
        "requested_size": final_size,
        "api_size": api_size,
        "final_size": final_size,
        "fit": fit,
        "postprocess_required": (api_w, api_h) != (width, height),
        "notes": notes,
    }


def encode_multipart(fields: dict[str, str], files: Iterable[tuple[str, Path]]) -> tuple[bytes, str]:
    boundary = "----image-workbench-" + os.urandom(12).hex()
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    for field_name, path in files:
        mime = "image/png" if path.suffix.lower() == ".png" else "application/octet-stream"
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{field_name}"; filename="{path.name}"\r\n'
                    f"Content-Type: {mime}\r\n\r\n"
                ).encode(),
                path.read_bytes(),
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def save_image_response(payload: dict[str, Any], out: Path, timeout: int = 60) -> Path:
    data = payload.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise WorkbenchError("Provider response did not contain data[0]")
    item = data[0]
    raw: bytes
    if isinstance(item.get("b64_json"), str):
        try:
            raw = base64.b64decode(item["b64_json"], validate=True)
        except ValueError as exc:
            raise WorkbenchError(f"Provider returned invalid base64 image data: {exc}") from None
    elif isinstance(item.get("url"), str):
        raw, _ = request_bytes(url=item["url"], timeout=timeout)
    else:
        raise WorkbenchError("Provider response contained neither b64_json nor url")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)
    return out


def postprocess_image(source: Path, destination: Path, requested: str, fit: str) -> dict[str, Any]:
    parsed = parse_size(requested)
    if parsed is None:
        if source != destination:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
        return {"postprocessed": False, "final_size": "provider_selected"}
    try:
        from PIL import Image, ImageOps
    except ImportError:
        raise WorkbenchError("Pillow is required for exact-size post-processing: install it with 'uv pip install pillow'")

    target = parsed
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        actual = image.size
        if actual == target:
            image.save(destination)
            return {"postprocessed": False, "source_size": f"{actual[0]}x{actual[1]}", "final_size": requested}
        if fit == "none":
            raise WorkbenchError(
                f"Provider returned {actual[0]}x{actual[1]}, but exact {requested} was requested with fit=none"
            )
        if fit == "crop":
            result = ImageOps.fit(image, target, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        elif fit == "contain":
            contained = ImageOps.contain(image, target, method=Image.Resampling.LANCZOS)
            mode = "RGBA" if "A" in image.getbands() else "RGB"
            background = (0, 0, 0, 0) if mode == "RGBA" else (255, 255, 255)
            result = Image.new(mode, target, background)
            result.paste(contained, ((target[0] - contained.width) // 2, (target[1] - contained.height) // 2))
        else:
            result = image.resize(target, Image.Resampling.LANCZOS)
        result.save(destination)
        return {
            "postprocessed": True,
            "source_size": f"{actual[0]}x{actual[1]}",
            "final_size": requested,
            "fit": fit,
        }


def default_output_path(prefix: str, extension: str = "png") -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path("output") / "image-workbench" / f"{prefix}-{stamp}.{extension}"


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)

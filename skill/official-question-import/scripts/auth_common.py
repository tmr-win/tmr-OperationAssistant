#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_OPS_ADMIN_BASE_URL = "https://admin.tmr.win/admin/questions/list"
DEFAULT_IDENTITY_BASE_URL = "https://tmr.win/identity-service"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30
STATE_DIR = Path.home() / ".official-question-import-skill"
CREDENTIALS_PATH = STATE_DIR / "credentials.json"
PENDING_BIND_PATH = STATE_DIR / "pending-bind.json"
REFRESH_SKEW_SECONDS = 60


class AuthError(RuntimeError):
    def __init__(self, code: str, message: str, *, http_status: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


@dataclass
class AuthConfig:
    base_url: str
    gateway_root_url: str
    identity_base_url: str
    timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_text(value: str | None) -> str:
    return (value or "").strip()


def resolve_gateway_root_url(base_url: str | None) -> str:
    normalized = normalize_text(base_url)
    if not normalized:
        return ""
    if "://" not in normalized:
        trimmed = normalized.rstrip("/")
        if trimmed.endswith("/intention-market"):
            trimmed = trimmed.removesuffix("/intention-market")
        admin_index = trimmed.find("/admin")
        if admin_index >= 0:
            trimmed = trimmed[:admin_index]
        return trimmed
    try:
        from urllib.parse import urlparse

        parsed = urlparse(normalized)
        pathname = parsed.path.rstrip("/")
        if pathname.endswith("/intention-market"):
            pathname = pathname[: -len("/intention-market")]
        elif pathname == "/":
            pathname = ""
        else:
            admin_index = pathname.find("/admin")
            if admin_index >= 0:
                pathname = pathname[:admin_index]
        return f"{parsed.scheme}://{parsed.netloc}{pathname}"
    except Exception:
        return normalized.rstrip("/").replace("/intention-market", "")


def resolve_identity_base_url(identity_base_url: str | None) -> str:
    normalized = normalize_text(identity_base_url)
    if not normalized:
        return ""
    if "://" not in normalized:
        trimmed = normalized.rstrip("/")
        identity_index = trimmed.find("/identity-service")
        if identity_index >= 0:
            return trimmed[: identity_index + len("/identity-service")]
        return f"{trimmed}/identity-service"
    try:
        from urllib.parse import urlparse

        parsed = urlparse(normalized)
        pathname = parsed.path.rstrip("/")
        identity_index = pathname.find("/identity-service")
        if identity_index >= 0:
            pathname = pathname[: identity_index + len("/identity-service")]
        elif pathname == "/":
            pathname = "/identity-service"
        else:
            pathname = f"{pathname}/identity-service"
        return f"{parsed.scheme}://{parsed.netloc}{pathname}"
    except Exception:
        trimmed = normalized.rstrip("/")
        if "/identity-service" in trimmed:
            return trimmed.split("/identity-service", 1)[0] + "/identity-service"
        return f"{trimmed}/identity-service"


def build_config(base_url: str | None = None, identity_base_url: str | None = None) -> AuthConfig:
    effective_base_url = normalize_text(base_url) or DEFAULT_OPS_ADMIN_BASE_URL
    gateway_root_url = resolve_gateway_root_url(effective_base_url)
    effective_identity_base_url = resolve_identity_base_url(identity_base_url) or DEFAULT_IDENTITY_BASE_URL
    if not gateway_root_url:
        raise AuthError("invalid_base_url", "未提供可用的运营后台地址")
    if not effective_identity_base_url:
        raise AuthError("invalid_identity_base_url", "未提供可用的 identity-service 地址")
    return AuthConfig(
        base_url=effective_base_url,
        gateway_root_url=gateway_root_url,
        identity_base_url=effective_identity_base_url,
    )


def ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuthError("invalid_state", f"本地状态文件损坏：{path.name}") from exc
    if not isinstance(payload, dict):
        raise AuthError("invalid_state", f"本地状态文件格式无效：{path.name}")
    return payload


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    ensure_state_dir()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_credentials() -> dict[str, Any] | None:
    return read_json_file(CREDENTIALS_PATH)


def save_credentials(payload: dict[str, Any]) -> None:
    write_json_file(CREDENTIALS_PATH, payload)


def clear_credentials() -> None:
    if CREDENTIALS_PATH.exists():
        CREDENTIALS_PATH.unlink()


def load_pending_bind() -> dict[str, Any] | None:
    return read_json_file(PENDING_BIND_PATH)


def save_pending_bind(payload: dict[str, Any]) -> None:
    write_json_file(PENDING_BIND_PATH, payload)


def clear_pending_bind() -> None:
    if PENDING_BIND_PATH.exists():
        PENDING_BIND_PATH.unlink()


def unwrap_api_payload(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload.get("data")
    return payload


def request_json(
    *,
    url: str,
    method: str,
    timeout_seconds: int,
    body: dict[str, Any] | None = None,
    access_token: str | None = None,
) -> Any:
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    request = urllib.request.Request(url=url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw_body = response.read().decode("utf-8")
            payload = json.loads(raw_body) if raw_body else None
            return unwrap_api_payload(payload)
    except urllib.error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8") if exc.fp is not None else ""
        message = f"请求失败，状态码 {exc.code}"
        if raw_body:
            try:
                payload = json.loads(raw_body)
                detail = unwrap_api_payload(payload)
                if isinstance(detail, dict):
                    message = str(detail.get("message") or detail.get("detail") or message)
                elif isinstance(payload, dict):
                    payload_detail = payload.get("detail")
                    detail_message = payload_detail.get("message") if isinstance(payload_detail, dict) else payload_detail
                    message = str(
                        payload.get("message")
                        or detail_message
                        or message
                    )
            except json.JSONDecodeError:
                message = raw_body
        raise AuthError("http_error", message, http_status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise AuthError("network_error", f"请求运营后台失败：{exc.reason}") from exc


def create_ops_admin_bind_session(config: AuthConfig, *, requested_by: str, skill_name: str) -> dict[str, Any]:
    payload = request_json(
        url=f"{config.identity_base_url}/api/v1/ops-admin-bind/sessions",
        method="POST",
        timeout_seconds=config.timeout_seconds,
        body={"requested_by": requested_by, "skill_name": skill_name},
    )
    if not isinstance(payload, dict) or not payload.get("poll_token"):
        raise AuthError("invalid_response", "创建运营后台授权会话失败：返回结果不完整")
    pending = {
        "base_url": config.base_url,
        "identity_base_url": config.identity_base_url,
        "session_id": payload.get("session_id"),
        "session_token": payload.get("session_token"),
        "poll_token": payload.get("poll_token"),
        "bind_url": payload.get("bind_url"),
        "expires_at": payload.get("expires_at"),
        "requested_by": requested_by,
        "skill_name": skill_name,
        "created_at": utc_now().isoformat(),
    }
    save_pending_bind(pending)
    return pending


def poll_ops_admin_bind_session(config: AuthConfig, *, poll_token: str) -> dict[str, Any]:
    payload = request_json(
        url=f"{config.identity_base_url}/api/v1/ops-admin-bind/sessions/poll",
        method="POST",
        timeout_seconds=config.timeout_seconds,
        body={"poll_token": poll_token},
    )
    if not isinstance(payload, dict):
        raise AuthError("invalid_response", "运营后台授权轮询返回格式无效")
    return payload


def refresh_ops_admin_session(config: AuthConfig, *, refresh_token: str) -> dict[str, Any]:
    payload = request_json(
        url=f"{config.identity_base_url}/api/v1/auth/ops-admin/token/refresh",
        method="POST",
        timeout_seconds=config.timeout_seconds,
        body={"refresh_token": refresh_token},
    )
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise AuthError("invalid_response", "刷新运营后台登录态失败：未返回 access_token")
    return payload


def get_ops_admin_me(config: AuthConfig, *, access_token: str) -> dict[str, Any]:
    payload = request_json(
        url=f"{config.identity_base_url}/api/v1/auth/ops-admin/me",
        method="GET",
        timeout_seconds=config.timeout_seconds,
        access_token=access_token,
    )
    if not isinstance(payload, dict) or not payload.get("user_id"):
        raise AuthError("invalid_response", "读取运营后台当前账号信息失败")
    return payload


def logout_ops_admin_session(config: AuthConfig, *, access_token: str) -> None:
    request_json(
        url=f"{config.identity_base_url}/api/v1/auth/ops-admin/logout",
        method="POST",
        timeout_seconds=config.timeout_seconds,
        access_token=access_token,
        body={},
    )


def is_token_fresh(credentials: dict[str, Any]) -> bool:
    expires_at_text = normalize_text(str(credentials.get("expires_at") or ""))
    if not expires_at_text:
        return False
    try:
        expires_at = datetime.fromisoformat(expires_at_text)
    except ValueError:
        return False
    return expires_at > utc_now() + timedelta(seconds=REFRESH_SKEW_SECONDS)


def build_authenticated_payload(credentials: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "authenticated",
        "base_url": credentials.get("base_url"),
        "identity_base_url": credentials.get("identity_base_url"),
        "access_token": credentials.get("access_token"),
        "refresh_token": credentials.get("refresh_token"),
        "expires_at": credentials.get("expires_at"),
        "user_id": credentials.get("user_id"),
        "email": credentials.get("email"),
        "display_name": credentials.get("display_name"),
        "updated_at": credentials.get("updated_at"),
        "summary": "运营后台登录态可用",
    }


def build_binding_required_payload(pending: dict[str, Any], *, message: str | None = None) -> dict[str, Any]:
    payload = {
        "status": "binding_required",
        "base_url": pending.get("base_url"),
        "identity_base_url": pending.get("identity_base_url"),
        "session_id": pending.get("session_id"),
        "bind_url": pending.get("bind_url"),
        "expires_at": pending.get("expires_at"),
        "summary": "请打开登录链接，在浏览器完成运营后台登录授权",
    }
    if message:
        payload["message"] = message
    return payload


def ensure_login(
    *,
    base_url: str | None = None,
    identity_base_url: str | None = None,
    requested_by: str = "official-question-import",
    skill_name: str = "official-question-import",
    force_rebind: bool = False,
) -> dict[str, Any]:
    config = build_config(base_url, identity_base_url)
    if force_rebind:
        clear_credentials()
        clear_pending_bind()

    credentials = load_credentials()
    if credentials is not None:
        if is_token_fresh(credentials):
            try:
                me = get_ops_admin_me(config, access_token=str(credentials.get("access_token") or ""))
                credentials["user_id"] = me.get("user_id")
                credentials["email"] = me.get("email")
                credentials["display_name"] = me.get("display_name")
                credentials["updated_at"] = utc_now().isoformat()
                credentials["base_url"] = config.base_url
                credentials["identity_base_url"] = config.identity_base_url
                save_credentials(credentials)
                return build_authenticated_payload(credentials)
            except AuthError as exc:
                if exc.http_status != 401:
                    raise
        refresh_token = normalize_text(str(credentials.get("refresh_token") or ""))
        if refresh_token:
            try:
                refreshed = refresh_ops_admin_session(config, refresh_token=refresh_token)
                me = get_ops_admin_me(config, access_token=str(refreshed.get("access_token") or ""))
                refreshed_credentials = {
                    "base_url": config.base_url,
                    "identity_base_url": config.identity_base_url,
                    "access_token": refreshed.get("access_token"),
                    "refresh_token": refreshed.get("refresh_token") or refresh_token,
                    "expires_at": refreshed.get("expires_at"),
                    "user_id": me.get("user_id"),
                    "email": me.get("email"),
                    "display_name": me.get("display_name"),
                    "updated_at": utc_now().isoformat(),
                }
                save_credentials(refreshed_credentials)
                return build_authenticated_payload(refreshed_credentials)
            except AuthError as exc:
                if exc.http_status not in {None, 401}:
                    raise
        clear_credentials()

    pending = load_pending_bind()
    if pending and normalize_text(str(pending.get("poll_token") or "")):
        pending_config = build_config(
            str(pending.get("base_url") or config.base_url),
            str(pending.get("identity_base_url") or config.identity_base_url),
        )
        try:
            polled = poll_ops_admin_bind_session(
                pending_config,
                poll_token=str(pending.get("poll_token") or ""),
            )
        except AuthError as exc:
            clear_pending_bind()
            if exc.http_status == 404:
                pending = create_ops_admin_bind_session(
                    config,
                    requested_by=requested_by,
                    skill_name=skill_name,
                )
                return build_binding_required_payload(
                    pending,
                    message="上一次授权会话已失效，已为你重新生成登录链接。",
                )
            raise

        if polled.get("status") == "bound" and polled.get("access_token") and polled.get("refresh_token"):
            detail = polled.get("detail") if isinstance(polled.get("detail"), dict) else {}
            new_credentials = {
                "base_url": pending_config.base_url,
                "identity_base_url": pending_config.identity_base_url,
                "access_token": polled.get("access_token"),
                "refresh_token": polled.get("refresh_token"),
                "expires_at": polled.get("access_token_expires_at"),
                "user_id": detail.get("user_id"),
                "email": detail.get("email"),
                "display_name": detail.get("display_name"),
                "updated_at": utc_now().isoformat(),
            }
            save_credentials(new_credentials)
            clear_pending_bind()
            return build_authenticated_payload(new_credentials)

        if polled.get("status") == "pending":
            pending["expires_at"] = polled.get("expires_at") or pending.get("expires_at")
            save_pending_bind(pending)
            return build_binding_required_payload(pending)

        clear_pending_bind()
        pending = create_ops_admin_bind_session(
            config,
            requested_by=requested_by,
            skill_name=skill_name,
        )
        return build_binding_required_payload(
            pending,
            message="上一次授权会话已过期或已被消费，已为你重新生成登录链接。",
        )

    pending = create_ops_admin_bind_session(
        config,
        requested_by=requested_by,
        skill_name=skill_name,
    )
    return build_binding_required_payload(pending)


def clear_local_state(base_url: str | None = None, identity_base_url: str | None = None) -> dict[str, Any]:
    config = build_config(base_url, identity_base_url)
    credentials = load_credentials()
    if credentials and credentials.get("access_token"):
        try:
            logout_ops_admin_session(config, access_token=str(credentials.get("access_token")))
        except AuthError:
            pass
    clear_credentials()
    clear_pending_bind()
    return {
        "status": "ok",
        "summary": "已清理本地运营后台登录态和待处理授权会话",
    }

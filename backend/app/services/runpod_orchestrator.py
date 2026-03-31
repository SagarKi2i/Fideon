"""Resume RunPod pod via GraphQL, wait until RUNNING, then wait for ML HTTP (health/docs).

HTTP-first: optional SSH only when RUNPOD_SSH_ENABLED and ML HTTP is still down after resume.
Used by /api/v1/runpod/query and /api/v1/ml/acord/extract (BFF → RunPod ML backend).
"""

from __future__ import annotations

import asyncio
import os
import time
from io import StringIO
from typing import Any, Optional

import httpx
import paramiko
import structlog
from fastapi import HTTPException

from app.core.config import (
    RUNPOD_API_KEY,
    RUNPOD_ML_HEALTH_BACKOFF_MAX_SEC,
    RUNPOD_ML_HEALTH_PATH,
    RUNPOD_ML_HEALTH_POLL_INITIAL_SEC,
    RUNPOD_ML_READY_TIMEOUT_SEC,
    RUNPOD_POD_ID,
    RUNPOD_POD_RUNNING_POLL_INITIAL_SEC,
    RUNPOD_POD_RUNNING_POLL_MAX_SEC,
    RUNPOD_POD_RUNNING_TIMEOUT_SEC,
    RUNPOD_POST_RESUME_GRACE_SEC,
    RUNPOD_PRE_SSH_DELAY_SEC,
    RUNPOD_REMOTE_START_SCRIPT,
    RUNPOD_SSH_ENABLED,
    RUNPOD_SSH_HOST,
    RUNPOD_SSH_KEY_PATH,
    RUNPOD_SSH_MAX_RETRIES,
    RUNPOD_SSH_PORT,
    RUNPOD_SSH_PRIVATE_KEY,
    RUNPOD_SSH_RETRY_DELAY_SEC,
    RUNPOD_SSH_USER,
    runpod_proxy_base_url,
)

log = structlog.get_logger("runpod_orchestrator")
RUNPOD_GRAPHQL = "https://api.runpod.io/graphql"


def _normalize_ml_path(path: str) -> str:
    p = (path or "").strip()
    if not p.startswith("/"):
        p = "/" + p
    return p


def _health_paths_from_config() -> list[str]:
    raw = (RUNPOD_ML_HEALTH_PATH or "/health,/readyz,/docs,/openapi.json").strip()
    paths = [_normalize_ml_path(p) for p in raw.split(",") if p.strip()]
    return paths or ["/health", "/readyz", "/docs", "/openapi.json"]


_WAIT_ML_LOG_INTERVAL_SEC = 30.0


async def _ml_http_probe_one(base: str, path: str) -> tuple[bool, str]:
    """GET one URL; return (ok, detail) where detail explains failure (HTTP code, timeout, DNS, etc.)."""
    path = _normalize_ml_path(path)
    url = f"{base.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, follow_redirects=True)
            if 200 <= r.status_code < 300:
                return True, "ok"
            snippet = (r.text or "")[:200].replace("\n", " ").strip()
            return False, f"HTTP {r.status_code} {url!r} body_prefix={snippet!r}"
    except httpx.TimeoutException as e:
        return False, f"Timeout {url!r}: {type(e).__name__} {str(e)[:180]}"
    except httpx.RequestError as e:
        return False, f"RequestError {url!r}: {type(e).__name__} {str(e)[:180]}"
    except Exception as e:
        return False, f"{type(e).__name__} {url!r}: {str(e)[:180]}"


async def ml_http_probe_paths(base: str, paths: list[str]) -> tuple[bool, str, Optional[str]]:
    """Try each path in order. Returns (ok, failure_details, path_that_worked_if_ok).

    On failure, the second value lists every path tried (not only the last), so logs are
    easier to read when debugging wrong RUNPOD_PROXY_BASE_URL vs RUNPOD_POD_ID.
    """
    failures: list[str] = []
    for p in paths:
        ok, detail = await _ml_http_probe_one(base, p)
        if ok:
            return True, "ok", p
        failures.append(f"{p}: {detail}")
    return False, " | ".join(failures), None


def _backoff_sleep_sec(attempt: int, initial: float, cap: float) -> float:
    """Exponential backoff, capped (attempt 0 → initial, then ×2 each step)."""
    return min(cap, initial * (2 ** min(attempt, 12)))


def _graphql_headers() -> dict[str, str]:
    if not RUNPOD_API_KEY:
        raise HTTPException(status_code=503, detail="RUNPOD_API_KEY is not configured")
    return {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json",
    }


async def _graphql(body: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(RUNPOD_GRAPHQL, json=body, headers=_graphql_headers())
        r.raise_for_status()
        data = r.json()
    if data.get("errors"):
        raise HTTPException(status_code=502, detail=str(data["errors"]))
    return data


async def is_pod_running_graphql() -> bool:
    if not RUNPOD_POD_ID:
        return False
    data = await _graphql(
        {
            "query": f"""
            query {{
                pod(input: {{ podId: "{RUNPOD_POD_ID}" }}) {{
                    desiredStatus
                }}
            }}
            """
        }
    )
    pod = (data.get("data") or {}).get("pod")
    if not pod:
        return False
    return str(pod.get("desiredStatus", "")).upper() == "RUNNING"


async def pod_resume_graphql() -> dict[str, Any]:
    if not RUNPOD_POD_ID:
        raise HTTPException(status_code=503, detail="RUNPOD_POD_ID is not configured")
    data = await _graphql(
        {
            "query": f"""
            mutation {{
                podResume(input: {{ podId: "{RUNPOD_POD_ID}" }}) {{
                    id
                    desiredStatus
                }}
            }}
            """
        }
    )
    pod_data = (data.get("data") or {}).get("podResume")
    if pod_data is None:
        return {"error": "Failed to start pod", "full_response": data}
    return {
        "message": "Pod starting...",
        "pod_id": pod_data.get("id"),
        "status": pod_data.get("desiredStatus"),
    }


async def wait_for_pod_running_graphql(timeout_sec: float) -> None:
    """Poll RunPod GraphQL until desiredStatus == RUNNING or timeout (exponential backoff)."""
    deadline = time.monotonic() + timeout_sec
    attempt = 0
    while time.monotonic() < deadline:
        if await is_pod_running_graphql():
            log.info(
                "runpod.pod_graphql_running",
                pod_id=RUNPOD_POD_ID,
                remaining_s=round(max(0.0, deadline - time.monotonic()), 1),
            )
            return
        sleep_sec = _backoff_sleep_sec(
            attempt, RUNPOD_POD_RUNNING_POLL_INITIAL_SEC, RUNPOD_POD_RUNNING_POLL_MAX_SEC
        )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        sleep_sec = min(sleep_sec, remaining)
        log.info(
            "runpod.wait_pod_running_poll",
            attempt=attempt + 1,
            sleep_sec=round(sleep_sec, 2),
            remaining_s=round(remaining, 1),
        )
        await asyncio.sleep(sleep_sec)
        attempt += 1

    raise HTTPException(
        status_code=504,
        detail=(
            f"RunPod pod {RUNPOD_POD_ID} did not reach RUNNING in GraphQL within {timeout_sec}s"
        ),
    )


async def wait_for_ml_http_ready(
    base: str, paths: list[str], timeout_sec: float
) -> tuple[bool, str]:
    """Poll ML HTTP with exponential backoff until one path returns 2xx or deadline. Returns (ok, last_probe_detail)."""
    deadline = time.monotonic() + timeout_sec
    attempt = 0
    last_detail = ""
    last_info_at = time.monotonic()
    t0 = time.monotonic()
    while time.monotonic() < deadline:
        ok, detail, path_ok = await ml_http_probe_paths(base, paths)
        last_detail = detail
        if ok and path_ok:
            log.info(
                "runpod.ml_http_ready",
                base=base,
                path=path_ok,
                attempts=attempt + 1,
                waited_s=round(time.monotonic() - t0, 1),
            )
            return True, detail

        sleep_sec = _backoff_sleep_sec(
            attempt, RUNPOD_ML_HEALTH_POLL_INITIAL_SEC, RUNPOD_ML_HEALTH_BACKOFF_MAX_SEC
        )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        sleep_sec = min(sleep_sec, remaining)

        now = time.monotonic()
        if now - last_info_at >= _WAIT_ML_LOG_INTERVAL_SEC:
            log.info(
                "runpod.wait_ml_http_poll",
                paths=paths,
                attempt=attempt + 1,
                sleep_sec=round(sleep_sec, 2),
                remaining_s=round(remaining, 1),
                waited_s=round(now - t0, 1),
                probe_detail=detail,
            )
            last_info_at = now
        else:
            log.debug(
                "runpod.wait_ml_http_poll",
                attempt=attempt + 1,
                probe_detail=detail,
            )

        await asyncio.sleep(sleep_sec)
        attempt += 1
    return False, last_detail


def _normalize_pem(pem: str) -> str:
    """Support single-line env secrets with literal \\n sequences."""
    pem = pem.strip()
    if "\\n" in pem and "-----BEGIN" in pem and pem.count("\n") < 2:
        pem = pem.replace("\\n", "\n")
    return pem


def _load_ssh_private_key():
    """Prefer PEM in env (deploy-friendly); else load from RUNPOD_SSH_KEY_PATH / SSH_KEY_PATH."""
    pem_raw = (RUNPOD_SSH_PRIVATE_KEY or "").strip()
    if pem_raw:
        pem = _normalize_pem(pem_raw)
        key = None
        last_err: Optional[Exception] = None
        buf = StringIO(pem)
        for key_cls in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
            try:
                buf.seek(0)
                key = key_cls.from_private_key(buf)
                break
            except Exception as e:
                last_err = e
        if key is None:
            raise RuntimeError(
                f"Could not parse RUNPOD_SSH_PRIVATE_KEY (SSH_PRIVATE_KEY): {last_err}"
            ) from last_err
        return key

    path = RUNPOD_SSH_KEY_PATH.strip()
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(
            "Set RUNPOD_SSH_PRIVATE_KEY (recommended for production) or RUNPOD_SSH_KEY_PATH to a "
            "readable private key file that matches the RunPod PUBLIC_KEY."
        )
    key = None
    last_err: Optional[Exception] = None
    for key_cls in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
        try:
            key = key_cls.from_private_key_file(path)
            break
        except Exception as e:
            last_err = e
    if key is None:
        raise RuntimeError(f"Could not load SSH private key from file: {last_err}") from last_err
    return key


def run_remote_start_script_sync() -> None:
    """Blocking: SSH and run RUNPOD_REMOTE_START_SCRIPT (must nohup uvicorn if long-running)."""
    host = RUNPOD_SSH_HOST.strip()
    if not host:
        raise RuntimeError("RUNPOD_SSH_HOST is not set")

    key = _load_ssh_private_key()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    log.info(
        "runpod.ssh_connect",
        host=host,
        port=RUNPOD_SSH_PORT,
        user=RUNPOD_SSH_USER,
    )

    connected = False
    for attempt in range(1, RUNPOD_SSH_MAX_RETRIES + 1):
        try:
            client.connect(
                host,
                port=RUNPOD_SSH_PORT,
                username=RUNPOD_SSH_USER,
                pkey=key,
                timeout=30,
                banner_timeout=30,
                auth_timeout=30,
            )
            connected = True
            log.info("runpod.ssh_ok", attempt=attempt)
            break
        except Exception as exc:
            if attempt >= RUNPOD_SSH_MAX_RETRIES:
                log.warning("runpod.ssh_failed", attempt=attempt, error=str(exc))
                break
            sleep_sec = min(60.0, RUNPOD_SSH_RETRY_DELAY_SEC * (2 ** (attempt - 1)))
            log.warning(
                "runpod.ssh_retry",
                attempt=attempt,
                next_sleep_sec=round(sleep_sec, 2),
                error=str(exc),
            )
            time.sleep(sleep_sec)

    if not connected:
        client.close()
        raise RuntimeError("SSH not ready after maximum retries")

    script = RUNPOD_REMOTE_START_SCRIPT.strip() or "/workspace/start_backend.sh"
    try:
        log.info("runpod.ssh_exec", script=script)
        _stdin, stdout, stderr = client.exec_command(f"bash {script}", timeout=120)
        err_b = stderr.read().decode("utf-8", errors="replace")
        out_b = stdout.read().decode("utf-8", errors="replace")
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            log.warning("runpod.ssh_script_nonzero", exit_status=exit_status, stderr=err_b[:2000])
        else:
            log.info("runpod.ssh_script_ok")
        if out_b.strip():
            log.debug("runpod.ssh_stdout_tail", tail=out_b[-1500:])
    finally:
        client.close()


async def ensure_runpod_ml_ready() -> None:
    """
    1) Resume pod via GraphQL if not RUNNING.
    2) wait_for_pod_running_graphql — poll until GraphQL reports RUNNING.
    3) Optional post-resume grace (proxy / GPU).
    4) If ML HTTP (RUNPOD_ML_HEALTH_PATH) is already 2xx, return.
    5) Optional SSH start script if enabled and configured.
    6) wait_for_ml_http_ready — exponential backoff until ML responds or timeout.
    """
    if not RUNPOD_POD_ID:
        raise HTTPException(status_code=503, detail="RUNPOD_POD_ID is not configured")

    base = runpod_proxy_base_url().strip().rstrip("/")
    if not base:
        raise HTTPException(
            status_code=503,
            detail="RunPod proxy base URL not configured (RUNPOD_PROXY_BASE_URL or RUNPOD_GENERATE_URL)",
        )

    # RunPod HTTPS URLs are typically https://{pod_id}-{port}.proxy.runpod.net — if the hostname
    # does not contain RUNPOD_POD_ID, probes hit the wrong pod (404 on /health).
    try:
        from urllib.parse import urlparse

        host = (urlparse(base).hostname or "").lower()
        pid = (RUNPOD_POD_ID or "").strip().lower()
        if pid and host and pid not in host:
            log.warning(
                "runpod.proxy_pod_mismatch",
                pod_id=RUNPOD_POD_ID,
                proxy_base=base,
                msg="Set RUNPOD_PROXY_BASE_URL to the same pod as RUNPOD_POD_ID (dashboard → HTTP for that port).",
            )
    except Exception:
        pass

    health_paths = _health_paths_from_config()

    did_resume = False
    if not await is_pod_running_graphql():
        did_resume = True
        log.info("runpod.resume_pod", pod_id=RUNPOD_POD_ID)
        err = await pod_resume_graphql()
        if err.get("error"):
            raise HTTPException(status_code=502, detail=err)

    await wait_for_pod_running_graphql(RUNPOD_POD_RUNNING_TIMEOUT_SEC)

    if did_resume and RUNPOD_POST_RESUME_GRACE_SEC > 0:
        log.info(
            "runpod.post_resume_grace",
            sleep_sec=RUNPOD_POST_RESUME_GRACE_SEC,
            msg="Extra wait after RUNNING so container HTTP proxy and GPU can initialize.",
        )
        await asyncio.sleep(RUNPOD_POST_RESUME_GRACE_SEC)

    ok_early, probe_early, path_early = await ml_http_probe_paths(base, health_paths)
    if ok_early and path_early:
        log.info("runpod.ml_already_up", base=base, path=path_early, paths_configured=health_paths)
        return

    log.warning(
        "runpod.ml_http_not_ready_yet",
        base=base,
        paths_tried=health_paths,
        probe_detail=probe_early,
        msg=(
            "ML HTTP not 2xx on any configured path — see probe_detail (all paths). "
            "502 = nothing on that port yet; connection errors = proxy not routing; "
            "404 on every path often means RUNPOD_PROXY_BASE_URL is a different pod/endpoint than RUNPOD_POD_ID "
            "(copy the HTTP URL from the same pod in the RunPod dashboard). "
            "Fix: align PROXY_URL with the pod you resume, start uvicorn on 0.0.0.0:PORT, or enable SSH."
        ),
    )

    if RUNPOD_SSH_ENABLED and RUNPOD_SSH_HOST.strip():
        if RUNPOD_PRE_SSH_DELAY_SEC > 0:
            log.info(
                "runpod.pre_ssh_delay",
                sleep_sec=RUNPOD_PRE_SSH_DELAY_SEC,
                msg="Waiting before SSH so RunPod opens the SSH port and sshd accepts connections.",
            )
            await asyncio.sleep(RUNPOD_PRE_SSH_DELAY_SEC)
        log.info("runpod.ssh_start_script")
        try:
            await asyncio.to_thread(run_remote_start_script_sync)
        except FileNotFoundError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"SSH start failed: {e}") from e
    elif RUNPOD_SSH_HOST.strip() and not RUNPOD_SSH_ENABLED:
        log.info(
            "runpod.ssh_skipped",
            msg="RUNPOD_SSH_ENABLED=false — not attempting SSH; ensure ML starts via image CMD/ENTRYPOINT.",
        )
    else:
        log.warning(
            "runpod.no_ssh_waiting_ml_http",
            msg="ML HTTP not up; RUNPOD_SSH_HOST empty — configure pod startup or enable SSH with key.",
        )

    ready, last_probe = await wait_for_ml_http_ready(base, health_paths, RUNPOD_ML_READY_TIMEOUT_SEC)
    if not ready:
        raise HTTPException(
            status_code=504,
            detail=(
                f"RunPod ML HTTP did not become ready within {RUNPOD_ML_READY_TIMEOUT_SEC}s. "
                f"base={base} paths={health_paths!r}. Last probe: {last_probe}"
            ),
        )
    log.info("runpod.ml_ready", paths=health_paths)

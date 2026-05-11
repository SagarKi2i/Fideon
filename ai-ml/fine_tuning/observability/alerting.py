"""
Alerting — send a notification when a new model version is promoted.

Configure via environment variables:
  ALERT_WEBHOOK_URL   — Slack incoming-webhook or generic HTTP endpoint
  ALERT_CHANNEL       — Slack channel (optional, default #ml-alerts)

If ALERT_WEBHOOK_URL is not set, alerts are printed to stdout only.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

import httpx


class Alerter:
    def __init__(self) -> None:
        self._webhook_url = os.getenv("ALERT_WEBHOOK_URL", "").strip()
        self._channel     = os.getenv("ALERT_CHANNEL", "#ml-alerts").strip()

    def send_promotion(
        self,
        adapter_id: str,
        version: int,
        status: str,
        base_model: str,
        seaweedfs_path: Optional[str] = None,  # kept for backward compat; value is Azure Blob path
        storage_path: Optional[str] = None,
        eval_scores: Optional[dict] = None,
    ) -> None:
        scores_str = ""
        if eval_scores:
            parts = [f"{k}={v:.4f}" for k, v in eval_scores.items() if isinstance(v, float)]
            scores_str = "  |  " + "  ".join(parts) if parts else ""

        msg = (
            f":white_check_mark: *Fideon SLM v1.{version} promoted* "
            f"(adapter `{adapter_id[:8]}…`)  "
            f"status=`{status}`{scores_str}"
        )
        blob_path = storage_path or seaweedfs_path
        if blob_path:
            msg += f"\n> Azure Blob: `{blob_path}`"

        print(f"[alerting] {msg}")

        if not self._webhook_url:
            return

        payload: dict[str, Any] = {"text": msg}
        if self._channel:
            payload["channel"] = self._channel

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    self._webhook_url,
                    content=json.dumps(payload),
                    headers={"Content-Type": "application/json"},
                )
            if resp.status_code >= 400:
                print(f"[alerting] webhook returned {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:
            print(f"[alerting] webhook failed: {exc}")


# Module-level singleton
alerter = Alerter()

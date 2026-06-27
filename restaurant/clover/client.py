"""Minimal Clover REST client — sandbox + production via env vars."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from dotenv import load_dotenv

load_dotenv()


class CloverError(Exception):
    def __init__(self, status: int, payload: Any):
        self.status = status
        self.payload = payload
        super().__init__(f"Clover HTTP {status}: {payload}")


class CloverClient:
    def __init__(
        self,
        base_url: str | None = None,
        merchant_id: str | None = None,
        token: str | None = None,
    ):
        self.base_url = (base_url or os.environ["CLOVER_BASE_URL"]).rstrip("/")
        self.merchant_id = merchant_id or os.environ["CLOVER_MID"]
        self.token = token or os.environ["CLOVER_API_TOKEN"]

    def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"raw": raw[:500]}
            raise CloverError(e.code, payload) from e

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post(self, path: str, body: dict) -> Any:
        return self._request("POST", path, body)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    def merchant_path(self, suffix: str) -> str:
        suffix = suffix if suffix.startswith("/") else f"/{suffix}"
        return f"/v3/merchants/{self.merchant_id}{suffix}"

    def fetch_all(self, resource: str, *, limit: int = 100) -> list[dict]:
        """Paginate a merchant collection endpoint (returns elements[])."""
        out: list[dict] = []
        offset = 0
        while True:
            path = self.merchant_path(f"/{resource}?limit={limit}&offset={offset}")
            data = self.get(path)
            batch = data.get("elements", []) if isinstance(data, dict) else []
            out.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return out

    @classmethod
    def from_env(cls) -> "CloverClient":
        missing = [k for k in ("CLOVER_BASE_URL", "CLOVER_MID", "CLOVER_API_TOKEN") if not os.environ.get(k)]
        if missing:
            raise SystemExit(f"Missing env vars: {', '.join(missing)}")
        return cls()

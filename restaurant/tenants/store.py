"""SQLite tenant store — one Bizbull row for demo; schema ready for N tenants later."""

from __future__ import annotations

import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(os.getenv("TENANT_DB_PATH", "data/tenants.db"))


@dataclass
class Tenant:
    tenant_id: str
    name: str
    clover_merchant_id: str
    clover_base_url: str
    clover_api_token: str
    order_type_pickup_id: str | None
    order_type_delivery_id: str | None
    phone_number: str | None
    voice_labels_path: str
    menu_cache_path: str
    menu_cache_updated_at: str | None
    delivery_charge: float
    min_order_delivery: float
    restaurant_name: str
    restaurant_name_en: str

    def cache_path(self) -> Path:
        return Path(self.menu_cache_path)


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | None = None) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                tenant_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                clover_merchant_id TEXT NOT NULL,
                clover_base_url TEXT NOT NULL,
                clover_api_token TEXT NOT NULL,
                order_type_pickup_id TEXT,
                order_type_delivery_id TEXT,
                phone_number TEXT,
                voice_labels_path TEXT NOT NULL DEFAULT 'data/clover_voice_labels.json',
                menu_cache_path TEXT NOT NULL,
                menu_cache_updated_at TEXT,
                delivery_charge REAL NOT NULL DEFAULT 5,
                min_order_delivery REAL NOT NULL DEFAULT 20,
                restaurant_name TEXT NOT NULL DEFAULT 'ਬਿਜ਼ਬਲ ਰੈਸਟੋਰੈਂਟ',
                restaurant_name_en TEXT NOT NULL DEFAULT 'Bizbull Restaurant'
            )
            """
        )
        conn.commit()


def _row_to_tenant(row: sqlite3.Row) -> Tenant:
    return Tenant(
        tenant_id=row["tenant_id"],
        name=row["name"],
        clover_merchant_id=row["clover_merchant_id"],
        clover_base_url=row["clover_base_url"],
        clover_api_token=row["clover_api_token"],
        order_type_pickup_id=row["order_type_pickup_id"],
        order_type_delivery_id=row["order_type_delivery_id"],
        phone_number=row["phone_number"],
        voice_labels_path=row["voice_labels_path"],
        menu_cache_path=row["menu_cache_path"],
        menu_cache_updated_at=row["menu_cache_updated_at"],
        delivery_charge=row["delivery_charge"],
        min_order_delivery=row["min_order_delivery"],
        restaurant_name=row["restaurant_name"],
        restaurant_name_en=row["restaurant_name_en"],
    )


def list_tenants(db_path: Path | None = None) -> list[Tenant]:
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM tenants ORDER BY name").fetchall()
    return [_row_to_tenant(r) for r in rows]


def get_tenant(tenant_id: str, db_path: Path | None = None) -> Tenant | None:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM tenants WHERE tenant_id = ?", (tenant_id,)).fetchone()
    return _row_to_tenant(row) if row else None


def upsert_tenant(tenant: Tenant, db_path: Path | None = None) -> None:
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO tenants (
                tenant_id, name, clover_merchant_id, clover_base_url, clover_api_token,
                order_type_pickup_id, order_type_delivery_id, phone_number,
                voice_labels_path, menu_cache_path, menu_cache_updated_at,
                delivery_charge, min_order_delivery, restaurant_name, restaurant_name_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id) DO UPDATE SET
                name = excluded.name,
                clover_merchant_id = excluded.clover_merchant_id,
                clover_base_url = excluded.clover_base_url,
                clover_api_token = excluded.clover_api_token,
                order_type_pickup_id = excluded.order_type_pickup_id,
                order_type_delivery_id = excluded.order_type_delivery_id,
                phone_number = excluded.phone_number,
                voice_labels_path = excluded.voice_labels_path,
                menu_cache_path = excluded.menu_cache_path,
                menu_cache_updated_at = excluded.menu_cache_updated_at,
                delivery_charge = excluded.delivery_charge,
                min_order_delivery = excluded.min_order_delivery,
                restaurant_name = excluded.restaurant_name,
                restaurant_name_en = excluded.restaurant_name_en
            """,
            (
                tenant.tenant_id,
                tenant.name,
                tenant.clover_merchant_id,
                tenant.clover_base_url,
                tenant.clover_api_token,
                tenant.order_type_pickup_id,
                tenant.order_type_delivery_id,
                tenant.phone_number,
                tenant.voice_labels_path,
                tenant.menu_cache_path,
                tenant.menu_cache_updated_at,
                tenant.delivery_charge,
                tenant.min_order_delivery,
                tenant.restaurant_name,
                tenant.restaurant_name_en,
            ),
        )
        conn.commit()


def mark_menu_synced(tenant_id: str, db_path: Path | None = None) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE tenants SET menu_cache_updated_at = ? WHERE tenant_id = ?",
            (ts, tenant_id),
        )
        conn.commit()


def bootstrap_bizbull_from_env(db_path: Path | None = None) -> Tenant:
    """Create or update the single demo tenant from environment variables."""
    init_db(db_path)
    mid = os.environ["CLOVER_MID"]
    tenant_id = os.getenv("TENANT_ID", "bizbull")
    tenant = Tenant(
        tenant_id=tenant_id,
        name=os.getenv("TENANT_NAME", "Bizbull Restaurant"),
        clover_merchant_id=mid,
        clover_base_url=os.environ["CLOVER_BASE_URL"],
        clover_api_token=os.environ["CLOVER_API_TOKEN"],
        order_type_pickup_id=os.getenv("CLOVER_ORDER_TYPE_PICKUP_ID"),
        order_type_delivery_id=os.getenv("CLOVER_ORDER_TYPE_DELIVERY_ID"),
        phone_number=os.getenv("TWILIO_PHONE_NUMBER"),
        voice_labels_path=os.getenv("VOICE_LABELS_PATH", "data/clover_voice_labels.json"),
        menu_cache_path=os.getenv("MENU_CACHE_PATH", f"data/menu_cache_{tenant_id}.json"),
        menu_cache_updated_at=None,
        delivery_charge=float(os.getenv("DELIVERY_CHARGE", "5")),
        min_order_delivery=float(os.getenv("MIN_ORDER_DELIVERY", "20")),
        restaurant_name=os.getenv("RESTAURANT_NAME", "ਬਿਜ਼ਬਲ ਰੈਸਟੋਰੈਂਟ"),
        restaurant_name_en=os.getenv("RESTAURANT_NAME_EN", "Bizbull Restaurant"),
    )
    existing = get_tenant(tenant_id, db_path)
    if existing and existing.menu_cache_updated_at:
        tenant.menu_cache_updated_at = existing.menu_cache_updated_at
    upsert_tenant(tenant, db_path)
    return tenant


def new_tenant_id() -> str:
    return str(uuid.uuid4())

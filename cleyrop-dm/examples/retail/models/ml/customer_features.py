"""Python model: ML features derived from customer_orders.

Python models are for logic that is awkward in pure SQL -- feature engineering,
scoring, calling a model. They receive a context with ``ref(...)`` returning
Arrow, and return an Arrow table. Everything else (WAP, audits, publish, time
travel) works exactly as it does for SQL models.
"""

from __future__ import annotations

import pyarrow as pa
import pyarrow.compute as pc

META = {
    "name": "customer_features",
    "materialization": "table",
    "depends_on": ["customer_orders"],
    "audits": [
        "not_null(customer_id)",
        "unique(customer_id)",
        "accepted_values(value_tier, 'none', 'low', 'high')",
    ],
    "tags": ["ml", "features"],
    "description": "Per-customer features for downstream ML/segmentation.",
}


def model(ctx) -> pa.Table:
    co = ctx.ref("customer_orders")
    ltv = co.column("lifetime_value")

    value_tier = pc.if_else(
        pc.equal(ltv, 0),
        pa.scalar("none"),
        pc.if_else(pc.greater(ltv, 100.0), pa.scalar("high"), pa.scalar("low")),
    )
    is_active = pc.greater(co.column("n_orders"), 0)

    return pa.table(
        {
            "customer_id": co.column("customer_id"),
            "country": co.column("country"),
            "lifetime_value": ltv,
            "n_orders": co.column("n_orders"),
            "value_tier": value_tier,
            "is_active": is_active,
        }
    )

#!/usr/bin/env python3
"""
validate_contracts.py
CI validator for governed-metrics-starter-kit dbt metric contracts.
See contracts.md for the full specification.

Contracts are split into three groups:

  Baseline  (B1–B2) — apply to every metric in every model, project-wide.
                       New models/metrics are picked up automatically.

  Tiered    (T1–T2) — stricter or looser requirements based on a metric's
                       declared tier tag (official / supported / experimental).

  Special   (S1–S4) — targeted checks for specific high-value models and
                       metrics (revenue labels, join safety, PII, raw columns).

Exit codes:
  0 — all contracts pass
  1 — one or more contracts fail

Usage (run from project root):
  python3 validate_contracts.py
"""

import sys
from pathlib import Path
import yaml

MODELS_DIR = Path("models")

# Every metric must carry exactly one of these as a tag.
VALID_TIER_TAGS = {"official", "supported", "experimental"}

# Required fields per tier (cumulative — each tier is a superset of experimental).
TIER_REQUIRED_FIELDS: dict[str, list[str]] = {
    "official":     ["label", "description", "type", "sql", "owner", "format"],
    "supported":    ["label", "description", "type", "sql", "owner"],
    "experimental": ["label", "description", "type", "sql"],
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_yaml(path: Path) -> dict:
    """Load a YAML file. Exits with a clear message if the file is missing."""
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"  ERROR: Required file not found: {path}")
        sys.exit(1)


def get_model(data: dict, model_name: str) -> dict | None:
    for model in data.get("models", []):
        if model.get("name") == model_name:
            return model
    return None


def get_column(model: dict, column_name: str) -> dict | None:
    for col in model.get("columns", []):
        if col.get("name") == column_name:
            return col
    return None


def is_hidden(col: dict) -> bool:
    """Return True only if config.meta.dimension.hidden is exactly True."""
    dimension = col.get("config", {}).get("meta", {}).get("dimension", {})
    if not isinstance(dimension, dict):
        return False
    return dimension.get("hidden") is True


def get_tier(metric_def: dict) -> str | None:
    """Return the single tier tag for a metric, or None if missing/ambiguous."""
    tags = metric_def.get("tags") or []
    tier_tags = [t for t in tags if t in VALID_TIER_TAGS]
    return tier_tags[0] if len(tier_tags) == 1 else None


def discover_metrics() -> list[tuple[str, str, str, dict]]:
    """
    Scan all YAML files under models/ and return every metric found as:
      (file_path, model_name, metric_name, metric_def)

    New models added to the project are picked up automatically.
    """
    results = []
    for yaml_path in sorted(MODELS_DIR.rglob("*.yml")):
        data = load_yaml(yaml_path)
        for model in data.get("models", []):
            model_name = model.get("name", "<unnamed>")
            metrics = (
                model.get("config", {}).get("meta", {}).get("metrics", {}) or {}
            )
            for metric_name, metric_def in metrics.items():
                results.append(
                    (str(yaml_path), model_name, metric_name, metric_def or {})
                )
    return results


# ── Baseline contracts ────────────────────────────────────────────────────────

def check_b1(all_metrics: list) -> tuple[bool, list[str]]:
    """B1: Every metric must declare label, description, type, sql."""
    violations = []
    required = TIER_REQUIRED_FIELDS["experimental"]  # minimum baseline

    for _, model_name, metric_name, metric_def in all_metrics:
        if not isinstance(metric_def, dict):
            violations.append(
                f"{model_name} → {metric_name}: empty or null definition"
            )
            continue
        for field in required:
            if not metric_def.get(field):
                violations.append(
                    f"{model_name} → {metric_name}: missing required field '{field}'"
                )

    return len(violations) == 0, violations


def check_b2(all_metrics: list) -> tuple[bool, list[str]]:
    """B2: Every metric must declare exactly one tier tag: official, supported, or experimental."""
    violations = []

    for _, model_name, metric_name, metric_def in all_metrics:
        tags = metric_def.get("tags") or []
        tier_tags = [t for t in tags if t in VALID_TIER_TAGS]

        if len(tier_tags) == 0:
            violations.append(
                f"{model_name} → {metric_name}: no tier tag found — "
                f"must be one of {sorted(VALID_TIER_TAGS)}, tags present: {tags}"
            )
        elif len(tier_tags) > 1:
            violations.append(
                f"{model_name} → {metric_name}: multiple tier tags {tier_tags} — "
                f"must be exactly one"
            )

    return len(violations) == 0, violations


# ── Tiered contracts ──────────────────────────────────────────────────────────

def check_t1_official(all_metrics: list) -> tuple[bool, list[str]]:
    """T1 (official): Must declare owner and format in addition to baseline fields."""
    violations = []
    extra_fields = ["owner", "format"]  # fields beyond the baseline

    for _, model_name, metric_name, metric_def in all_metrics:
        if get_tier(metric_def) != "official":
            continue
        for field in extra_fields:
            if not metric_def.get(field):
                violations.append(
                    f"{model_name} → {metric_name}: official metrics must declare '{field}'"
                )

    return len(violations) == 0, violations


def check_t2_supported(all_metrics: list) -> tuple[bool, list[str]]:
    """T2 (supported): Must declare owner in addition to baseline fields."""
    violations = []

    for _, model_name, metric_name, metric_def in all_metrics:
        if get_tier(metric_def) != "supported":
            continue
        if not metric_def.get("owner"):
            violations.append(
                f"{model_name} → {metric_name}: supported metrics must declare 'owner'"
            )

    return len(violations) == 0, violations


# ── Special contracts ─────────────────────────────────────────────────────────

def check_s1_revenue_labels(fct_orders_data: dict) -> tuple[bool, list[str]]:
    """S1: revenue_net and revenue_gross must use unambiguous governance labels."""
    violations = []
    expected_labels = {
        "revenue_net":   "Net Revenue (Official)",
        "revenue_gross": "Gross Revenue (Topline)",
    }

    model = get_model(fct_orders_data, "fct_orders")
    if model is None:
        return False, ["Model 'fct_orders' not found"]

    metrics = model.get("config", {}).get("meta", {}).get("metrics", {}) or {}

    for metric_name, expected_label in expected_labels.items():
        if metric_name not in metrics:
            violations.append(f"Metric '{metric_name}' not found in fct_orders")
            continue
        actual = (metrics[metric_name] or {}).get("label")
        if actual != expected_label:
            violations.append(
                f"'{metric_name}' label must be \"{expected_label}\", got \"{actual}\""
            )

    return len(violations) == 0, violations


def check_s2_join_safety(
    fct_orders_data: dict,
    dim_customers_data: dict,
) -> tuple[bool, list[str]]:
    """S2: If fct_orders joins dim_customers, both must declare primary_key
    and the join must declare relationship: many-to-one."""
    violations = []

    fct_model = get_model(fct_orders_data, "fct_orders")
    dim_model = get_model(dim_customers_data, "dim_customers")

    if fct_model is None:
        return False, ["Model 'fct_orders' not found"]
    if dim_model is None:
        return False, ["Model 'dim_customers' not found"]

    fct_meta = fct_model.get("config", {}).get("meta", {})
    dim_join = next(
        (j for j in fct_meta.get("joins", []) if j.get("join") == "dim_customers"),
        None,
    )

    if dim_join is None:
        return True, []  # vacuously safe — contract only applies when join exists

    fct_pk = fct_meta.get("primary_key")
    if fct_pk != "order_id":
        violations.append(
            f"fct_orders must declare primary_key: order_id, got: {fct_pk!r}"
        )

    dim_pk = dim_model.get("config", {}).get("meta", {}).get("primary_key")
    if dim_pk != "customer_id":
        violations.append(
            f"dim_customers must declare primary_key: customer_id, got: {dim_pk!r}"
        )

    rel = dim_join.get("relationship")
    if rel != "many-to-one":
        violations.append(
            f"Join to dim_customers must declare relationship: many-to-one, got: {rel!r}"
        )

    return len(violations) == 0, violations


def check_s3_sensitive_fields_hidden(dim_customers_data: dict) -> tuple[bool, list[str]]:
    """S3: email, first_name, last_name must have hidden: true in dim_customers."""
    violations = []
    model = get_model(dim_customers_data, "dim_customers")
    if model is None:
        return False, ["Model 'dim_customers' not found"]

    for col_name in ["email", "first_name", "last_name"]:
        col = get_column(model, col_name)
        if col is None:
            violations.append(f"Column '{col_name}' not found in dim_customers.yml")
        elif not is_hidden(col):
            violations.append(
                f"Column '{col_name}' must have hidden: true under config.meta.dimension"
            )

    return len(violations) == 0, violations


def check_s4_raw_revenue_hidden(fct_orders_data: dict) -> tuple[bool, list[str]]:
    """S4: Raw revenue columns must have hidden: true so users consume via metrics, not dimensions."""
    violations = []
    model = get_model(fct_orders_data, "fct_orders")
    if model is None:
        return False, ["Model 'fct_orders' not found"]

    for col_name in ["gross_revenue", "net_revenue", "discount_amount", "refund_amount"]:
        col = get_column(model, col_name)
        if col is None:
            violations.append(f"Column '{col_name}' not found in fct_orders.yml")
        elif not is_hidden(col):
            violations.append(
                f"Column '{col_name}' must have hidden: true under config.meta.dimension"
            )

    return len(violations) == 0, violations


# ── Runner ────────────────────────────────────────────────────────────────────

def run_contract(label: str, result: tuple[bool, list[str]]) -> bool:
    passed, violations = result
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {label}")
    for v in violations:
        print(f"       - {v}")
    return passed


def main() -> int:
    all_metrics = discover_metrics()
    fct_orders_data = load_yaml(Path("models/marts/fct_orders.yml"))
    dim_customers_data = load_yaml(Path("models/marts/dim_customers.yml"))

    model_names = sorted({m for _, m, _, _ in all_metrics})
    tier_counts = {t: 0 for t in VALID_TIER_TAGS}
    for _, _, _, metric_def in all_metrics:
        tier = get_tier(metric_def)
        if tier:
            tier_counts[tier] += 1

    print("Running governed-metrics contract validation...")
    print(
        f"Discovered {len(all_metrics)} metric(s) across "
        f"{len(model_names)} model(s): {', '.join(model_names)}"
    )
    tier_summary = ", ".join(
        f"{count} {tier}" for tier, count in sorted(tier_counts.items()) if count
    )
    print(f"Tier breakdown: {tier_summary or 'none tagged yet'}\n")

    all_passed = True

    print("── Baseline Contracts (every metric, every model) ──────────────────")
    for label, result in [
        ("B1: Every metric must declare label, description, type, sql",
         check_b1(all_metrics)),
        ("B2: Every metric must declare exactly one tier tag  (official / supported / experimental)",
         check_b2(all_metrics)),
    ]:
        if not run_contract(label, result):
            all_passed = False

    print()
    print("── Tiered Contracts ─────────────────────────────────────────────────")
    for label, result in [
        ("T1 (official):    Must also declare owner and format",
         check_t1_official(all_metrics)),
        ("T2 (supported):   Must also declare owner",
         check_t2_supported(all_metrics)),
    ]:
        if not run_contract(label, result):
            all_passed = False
    print("     T3 (experimental): only baseline fields required — no additional checks")

    print()
    print("── Special Contracts (governance & high-value metrics) ──────────────")
    for label, result in [
        ("S1: Revenue metric labels must include governance qualifiers",
         check_s1_revenue_labels(fct_orders_data)),
        ("S2: Joins must declare primary keys and cardinality",
         check_s2_join_safety(fct_orders_data, dim_customers_data)),
        ("S3: Sensitive customer fields must be hidden",
         check_s3_sensitive_fields_hidden(dim_customers_data)),
        ("S4: Raw revenue columns must not be exposed as dimensions",
         check_s4_raw_revenue_hidden(fct_orders_data)),
    ]:
        if not run_contract(label, result):
            all_passed = False

    print()
    if all_passed:
        print("All contracts passed.")
        return 0

    print("One or more contracts failed. See violations above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

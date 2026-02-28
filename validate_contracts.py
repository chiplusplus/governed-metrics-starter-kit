#!/usr/bin/env python3
"""
validate_contracts.py
CI validator for governed-metrics-starter-kit dbt metric contracts.
See contracts.md for the full specification.

Exit codes:
  0 — all contracts pass
  1 — one or more contracts fail

Usage:
  python validate_contracts.py
"""

import sys
import yaml

FCT_ORDERS_PATH = "models/marts/fct_orders.yml"
DIM_CUSTOMERS_PATH = "models/marts/dim_customers.yml"


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_yaml(path: str) -> dict:
    """Load a YAML file. Exits with a clear message if the file is missing."""
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"  ERROR: Required file not found: {path}")
        sys.exit(1)


def get_model(data: dict, model_name: str) -> dict | None:
    """Return the model entry matching model_name, or None."""
    for model in data.get("models", []):
        if model.get("name") == model_name:
            return model
    return None


def get_column(model: dict, column_name: str) -> dict | None:
    """Return the column entry matching column_name, or None."""
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


# ── Contract checks ───────────────────────────────────────────────────────────

def check_contract_1(fct_orders_data: dict) -> tuple[bool, list[str]]:
    """
    Contract 1: Every metric in fct_orders config.meta.metrics must have
    label, description, type, and sql.
    """
    violations = []
    required_fields = ["label", "description", "type", "sql"]

    model = get_model(fct_orders_data, "fct_orders")
    if model is None:
        return False, ["Model 'fct_orders' not found in fct_orders.yml"]

    metrics = model.get("config", {}).get("meta", {}).get("metrics", {})
    if not metrics:
        return False, ["No metrics found under config.meta.metrics in fct_orders.yml"]

    for metric_name, metric_def in metrics.items():
        if not isinstance(metric_def, dict):
            violations.append(
                f"Metric '{metric_name}' has no definition (empty or null body)"
            )
            continue
        for field in required_fields:
            value = metric_def.get(field)
            if value is None or value == "":
                violations.append(
                    f"Metric '{metric_name}' is missing required field: '{field}'"
                )

    return len(violations) == 0, violations


def check_contract_2(fct_orders_data: dict) -> tuple[bool, list[str]]:
    """
    Contract 2: revenue_net label must be 'Net Revenue (Official)';
    revenue_gross label must be 'Gross Revenue (Topline)'.
    """
    violations = []
    expected_labels = {
        "revenue_net": "Net Revenue (Official)",
        "revenue_gross": "Gross Revenue (Topline)",
    }

    model = get_model(fct_orders_data, "fct_orders")
    if model is None:
        return False, ["Model 'fct_orders' not found in fct_orders.yml"]

    metrics = model.get("config", {}).get("meta", {}).get("metrics", {})

    for metric_name, expected_label in expected_labels.items():
        if metric_name not in metrics:
            violations.append(
                f"Metric '{metric_name}' not found under config.meta.metrics"
            )
            continue
        actual_label = (metrics[metric_name] or {}).get("label")
        if actual_label != expected_label:
            violations.append(
                f"Metric '{metric_name}' label must be \"{expected_label}\", "
                f"got \"{actual_label}\""
            )

    return len(violations) == 0, violations


def check_contract_3(dim_customers_data: dict) -> tuple[bool, list[str]]:
    """
    Contract 3: In dim_customers.yml, columns email, first_name, last_name
    must each have hidden: true under config.meta.dimension.
    """
    violations = []
    sensitive_columns = ["email", "first_name", "last_name"]

    model = get_model(dim_customers_data, "dim_customers")
    if model is None:
        return False, ["Model 'dim_customers' not found in dim_customers.yml"]

    for col_name in sensitive_columns:
        col = get_column(model, col_name)
        if col is None:
            violations.append(f"Column '{col_name}' not found in dim_customers.yml")
        elif not is_hidden(col):
            violations.append(
                f"Column '{col_name}' must have hidden: true under "
                f"config.meta.dimension"
            )

    return len(violations) == 0, violations


def check_contract_4(
    fct_orders_data: dict,
    dim_customers_data: dict,
) -> tuple[bool, list[str]]:
    """
    Contract 4: If fct_orders joins dim_customers, both models must declare
    a primary_key and the join must declare relationship: many-to-one.
    Vacuously passes if no join to dim_customers exists.
    """
    violations = []

    fct_model = get_model(fct_orders_data, "fct_orders")
    if fct_model is None:
        return False, ["Model 'fct_orders' not found in fct_orders.yml"]

    dim_model = get_model(dim_customers_data, "dim_customers")
    if dim_model is None:
        return False, ["Model 'dim_customers' not found in dim_customers.yml"]

    fct_meta = fct_model.get("config", {}).get("meta", {})
    joins = fct_meta.get("joins", [])

    dim_join = next((j for j in joins if j.get("join") == "dim_customers"), None)
    if dim_join is None:
        # No join declared — contract is not applicable
        return True, []

    fct_pk = fct_meta.get("primary_key")
    if fct_pk != "order_id":
        violations.append(
            f"fct_orders must declare primary_key: order_id under config.meta, "
            f"got: {fct_pk!r}"
        )

    dim_pk = dim_model.get("config", {}).get("meta", {}).get("primary_key")
    if dim_pk != "customer_id":
        violations.append(
            f"dim_customers must declare primary_key: customer_id under config.meta, "
            f"got: {dim_pk!r}"
        )

    relationship = dim_join.get("relationship")
    if relationship != "many-to-one":
        violations.append(
            f"Join to dim_customers must declare relationship: many-to-one, "
            f"got: {relationship!r}"
        )

    return len(violations) == 0, violations


def check_contract_5(fct_orders_data: dict) -> tuple[bool, list[str]]:
    """
    Contract 5: In fct_orders.yml, raw revenue columns must not be exposed
    as dimensions — gross_revenue, net_revenue, discount_amount, refund_amount
    must each have hidden: true under config.meta.dimension.
    """
    violations = []
    raw_columns = ["gross_revenue", "net_revenue", "discount_amount", "refund_amount"]

    model = get_model(fct_orders_data, "fct_orders")
    if model is None:
        return False, ["Model 'fct_orders' not found in fct_orders.yml"]

    for col_name in raw_columns:
        col = get_column(model, col_name)
        if col is None:
            violations.append(f"Column '{col_name}' not found in fct_orders.yml")
        elif not is_hidden(col):
            violations.append(
                f"Column '{col_name}' must have hidden: true under "
                f"config.meta.dimension"
            )

    return len(violations) == 0, violations


# ── Runner ────────────────────────────────────────────────────────────────────

def main() -> int:
    print("Running governed-metrics contract validation...\n")

    fct_orders_data = load_yaml(FCT_ORDERS_PATH)
    dim_customers_data = load_yaml(DIM_CUSTOMERS_PATH)

    contracts = [
        (
            "Contract 1: Every metric must be fully documented",
            lambda: check_contract_1(fct_orders_data),
        ),
        (
            "Contract 2: Revenue metric labels must be unambiguous",
            lambda: check_contract_2(fct_orders_data),
        ),
        (
            "Contract 3: Sensitive customer fields must be hidden",
            lambda: check_contract_3(dim_customers_data),
        ),
        (
            "Contract 4: Joins must declare primary keys and cardinality",
            lambda: check_contract_4(fct_orders_data, dim_customers_data),
        ),
        (
            "Contract 5: Raw revenue columns must not be exposed as dimensions",
            lambda: check_contract_5(fct_orders_data),
        ),
    ]

    all_passed = True

    for name, check_fn in contracts:
        passed, violations = check_fn()
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {name}")
        if not passed:
            all_passed = False
            for v in violations:
                print(f"       - {v}")

    print()
    if all_passed:
        print("All contracts passed.")
        return 0

    print("One or more contracts failed. See violations above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

"""
test_validate_contracts.py
Unit tests for validate_contracts.py.

Each contract function is tested in isolation using minimal fixture dicts —
no YAML files are read from disk.

Run from project root:
  pytest test_validate_contracts.py -v
"""

import pytest
from validate_contracts import (
    check_b1,
    check_b2,
    check_t1_official,
    check_t2_supported,
    check_s1_revenue_labels,
    check_s2_join_safety,
    check_s3_sensitive_fields_hidden,
    check_s4_raw_revenue_hidden,
)


# ── Fixture helpers ───────────────────────────────────────────────────────────

def make_metric(
    label="Test Metric",
    description="A test metric.",
    type="sum",
    sql="${some_column}",
    tags=None,
    owner=None,
    format=None,
    **extra,
) -> dict:
    """Build a minimal valid metric definition dict."""
    defn: dict = {
        "label": label,
        "description": description,
        "type": type,
        "sql": sql,
    }
    if tags is not None:
        defn["tags"] = tags
    if owner is not None:
        defn["owner"] = owner
    if format is not None:
        defn["format"] = format
    defn.update(extra)
    return defn


def metric_row(model="fct_orders", name="test_metric", **kwargs) -> tuple:
    """Build a (path, model_name, metric_name, metric_def) tuple."""
    return ("models/marts/test.yml", model, name, make_metric(**kwargs))


def fct_orders_doc(
    metrics: dict = None,
    columns: list = None,
    primary_key: str = "order_id",
    joins: list = None,
) -> dict:
    """Build a minimal fct_orders YAML dict."""
    meta: dict = {"primary_key": primary_key, "metrics": metrics or {}}
    if joins is not None:
        meta["joins"] = joins
    return {
        "models": [{
            "name": "fct_orders",
            "config": {"meta": meta},
            "columns": columns or [],
        }]
    }


def dim_customers_doc(columns: list, primary_key: str = "customer_id") -> dict:
    """Build a minimal dim_customers YAML dict."""
    return {
        "models": [{
            "name": "dim_customers",
            "config": {"meta": {"primary_key": primary_key}},
            "columns": columns,
        }]
    }


def hidden_col(name: str) -> dict:
    """Column with hidden: true."""
    return {"name": name, "config": {"meta": {"dimension": {"hidden": True}}}}


def visible_col(name: str) -> dict:
    """Column with no hidden flag."""
    return {"name": name, "config": {"meta": {"dimension": {}}}}


def explicit_false_col(name: str) -> dict:
    """Column with hidden: false explicitly set."""
    return {"name": name, "config": {"meta": {"dimension": {"hidden": False}}}}


def valid_join() -> list:
    return [{"join": "dim_customers", "relationship": "many-to-one"}]


# ── B1: every metric must have baseline fields ────────────────────────────────

class TestB1BaselineDocumentation:

    def test_passes_with_all_required_fields(self):
        passed, violations = check_b1([metric_row()])
        assert passed
        assert violations == []

    def test_fails_when_description_is_missing(self):
        _, model, name, defn = metric_row()
        del defn["description"]
        passed, violations = check_b1([("p", model, name, defn)])
        assert not passed
        assert any("description" in v for v in violations)

    def test_fails_when_sql_is_missing(self):
        _, model, name, defn = metric_row()
        del defn["sql"]
        passed, violations = check_b1([("p", model, name, defn)])
        assert not passed
        assert any("sql" in v for v in violations)

    def test_fails_when_label_is_missing(self):
        _, model, name, defn = metric_row()
        del defn["label"]
        passed, violations = check_b1([("p", model, name, defn)])
        assert not passed
        assert any("label" in v for v in violations)

    def test_fails_when_type_is_missing(self):
        _, model, name, defn = metric_row()
        del defn["type"]
        passed, violations = check_b1([("p", model, name, defn)])
        assert not passed
        assert any("type" in v for v in violations)

    def test_fails_when_description_is_empty_string(self):
        passed, violations = check_b1([metric_row(description="")])
        assert not passed
        assert any("description" in v for v in violations)

    def test_fails_when_metric_body_is_null(self):
        passed, violations = check_b1([("p", "fct_orders", "broken", None)])
        assert not passed
        assert any("broken" in v for v in violations)

    def test_reports_all_violations_across_multiple_metrics(self):
        _, m, _, defn1 = metric_row(name="m1")
        del defn1["description"]
        _, _, _, defn2 = metric_row(name="m2")
        del defn2["sql"]
        passed, violations = check_b1([("p", m, "m1", defn1), ("p", m, "m2", defn2)])
        assert not passed
        assert len(violations) == 2


# ── B2: every metric must declare exactly one tier tag ────────────────────────

class TestB2TierTagRequired:

    def test_passes_with_official_tag(self):
        passed, _ = check_b2([metric_row(tags=["official", "revenue"])])
        assert passed

    def test_passes_with_supported_tag(self):
        passed, _ = check_b2([metric_row(tags=["supported"])])
        assert passed

    def test_passes_with_experimental_tag(self):
        passed, _ = check_b2([metric_row(tags=["experimental"])])
        assert passed

    def test_fails_when_no_tier_tag(self):
        passed, violations = check_b2([metric_row(tags=["revenue", "finance"])])
        assert not passed
        assert any("no tier tag" in v for v in violations)

    def test_fails_when_tags_field_absent(self):
        passed, violations = check_b2([metric_row()])  # tags kwarg omitted
        assert not passed

    def test_fails_when_multiple_tier_tags(self):
        passed, violations = check_b2([metric_row(tags=["official", "supported"])])
        assert not passed
        assert any("multiple tier tags" in v for v in violations)


# ── T1: official tier requires owner and format ───────────────────────────────

class TestT1OfficialTierRequirements:

    def test_passes_when_official_has_owner_and_format(self):
        metrics = [metric_row(tags=["official"], owner="Finance", format="[$]#,##0.00")]
        passed, _ = check_t1_official(metrics)
        assert passed

    def test_fails_when_official_metric_lacks_format(self):
        metrics = [metric_row(tags=["official"], owner="Finance")]
        passed, violations = check_t1_official(metrics)
        assert not passed
        assert any("format" in v for v in violations)

    def test_fails_when_official_metric_lacks_owner(self):
        metrics = [metric_row(tags=["official"], format="[$]#,##0.00")]
        passed, violations = check_t1_official(metrics)
        assert not passed
        assert any("owner" in v for v in violations)

    def test_skips_supported_metrics(self):
        # A supported metric with no owner/format must not trigger T1
        metrics = [metric_row(tags=["supported"])]
        passed, violations = check_t1_official(metrics)
        assert passed
        assert violations == []

    def test_skips_experimental_metrics(self):
        metrics = [metric_row(tags=["experimental"])]
        passed, violations = check_t1_official(metrics)
        assert passed


# ── T2: supported tier requires owner ────────────────────────────────────────

class TestT2SupportedTierRequirements:

    def test_passes_when_supported_has_owner(self):
        metrics = [metric_row(tags=["supported"], owner="Growth")]
        passed, _ = check_t2_supported(metrics)
        assert passed

    def test_fails_when_supported_metric_lacks_owner(self):
        metrics = [metric_row(tags=["supported"])]
        passed, violations = check_t2_supported(metrics)
        assert not passed
        assert any("owner" in v for v in violations)

    def test_skips_official_metrics(self):
        # T1 handles official — T2 must not double-flag
        metrics = [metric_row(tags=["official"])]
        passed, violations = check_t2_supported(metrics)
        assert passed
        assert violations == []

    def test_skips_experimental_metrics(self):
        metrics = [metric_row(tags=["experimental"])]
        passed, violations = check_t2_supported(metrics)
        assert passed


# ── S1: revenue metric labels must be unambiguous ────────────────────────────

class TestS1RevenueLabelGovernance:

    def _valid(self):
        return fct_orders_doc(metrics={
            "revenue_net":   make_metric(label="Net Revenue (Official)"),
            "revenue_gross": make_metric(label="Gross Revenue (Topline)"),
        })

    def test_passes_with_correct_labels(self):
        passed, _ = check_s1_revenue_labels(self._valid())
        assert passed

    def test_fails_when_official_metric_has_wrong_label(self):
        data = fct_orders_doc(metrics={
            "revenue_net":   make_metric(label="Revenue"),          # ambiguous
            "revenue_gross": make_metric(label="Gross Revenue (Topline)"),
        })
        passed, violations = check_s1_revenue_labels(data)
        assert not passed
        assert any("revenue_net" in v and "Net Revenue (Official)" in v for v in violations)

    def test_fails_when_revenue_gross_label_is_wrong(self):
        data = fct_orders_doc(metrics={
            "revenue_net":   make_metric(label="Net Revenue (Official)"),
            "revenue_gross": make_metric(label="Gross Revenue"),    # missing qualifier
        })
        passed, violations = check_s1_revenue_labels(data)
        assert not passed
        assert any("revenue_gross" in v for v in violations)

    def test_fails_when_revenue_net_metric_is_absent(self):
        data = fct_orders_doc(metrics={
            "revenue_gross": make_metric(label="Gross Revenue (Topline)"),
        })
        passed, violations = check_s1_revenue_labels(data)
        assert not passed
        assert any("revenue_net" in v for v in violations)

    def test_fails_when_both_revenue_metrics_absent(self):
        data = fct_orders_doc(metrics={})
        passed, violations = check_s1_revenue_labels(data)
        assert not passed
        assert len(violations) == 2


# ── S2: join safety ───────────────────────────────────────────────────────────

class TestS2JoinSafety:

    def test_passes_vacuously_when_no_join_declared(self):
        fct = fct_orders_doc(joins=[])
        passed, _ = check_s2_join_safety(fct, dim_customers_doc([]))
        assert passed

    def test_passes_with_all_requirements_satisfied(self):
        fct = fct_orders_doc(joins=valid_join())
        passed, _ = check_s2_join_safety(fct, dim_customers_doc([]))
        assert passed

    def test_fails_when_fct_orders_missing_primary_key(self):
        fct = fct_orders_doc(primary_key=None, joins=valid_join())
        passed, violations = check_s2_join_safety(fct, dim_customers_doc([]))
        assert not passed
        assert any("fct_orders" in v and "primary_key" in v for v in violations)

    def test_fails_when_dim_customers_missing_primary_key(self):
        fct = fct_orders_doc(joins=valid_join())
        dim = dim_customers_doc([], primary_key=None)
        passed, violations = check_s2_join_safety(fct, dim)
        assert not passed
        assert any("dim_customers" in v and "primary_key" in v for v in violations)

    def test_fails_when_relationship_cardinality_is_wrong(self):
        bad_join = [{"join": "dim_customers", "relationship": "one-to-many"}]
        fct = fct_orders_doc(joins=bad_join)
        passed, violations = check_s2_join_safety(fct, dim_customers_doc([]))
        assert not passed
        assert any("many-to-one" in v for v in violations)

    def test_fails_when_relationship_field_absent(self):
        no_rel_join = [{"join": "dim_customers"}]
        fct = fct_orders_doc(joins=no_rel_join)
        passed, violations = check_s2_join_safety(fct, dim_customers_doc([]))
        assert not passed


# ── S3: sensitive customer fields must be hidden ──────────────────────────────

class TestS3PiiFieldsHidden:

    def test_passes_when_all_pii_fields_are_hidden(self):
        data = dim_customers_doc([
            hidden_col("email"),
            hidden_col("first_name"),
            hidden_col("last_name"),
        ])
        passed, _ = check_s3_sensitive_fields_hidden(data)
        assert passed

    def test_fails_when_email_is_not_hidden(self):
        data = dim_customers_doc([
            visible_col("email"),
            hidden_col("first_name"),
            hidden_col("last_name"),
        ])
        passed, violations = check_s3_sensitive_fields_hidden(data)
        assert not passed
        assert any("email" in v for v in violations)

    def test_fails_when_first_name_is_not_hidden(self):
        data = dim_customers_doc([
            hidden_col("email"),
            visible_col("first_name"),
            hidden_col("last_name"),
        ])
        passed, violations = check_s3_sensitive_fields_hidden(data)
        assert not passed
        assert any("first_name" in v for v in violations)

    def test_fails_when_hidden_is_explicitly_false(self):
        data = dim_customers_doc([
            explicit_false_col("email"),
            hidden_col("first_name"),
            hidden_col("last_name"),
        ])
        passed, violations = check_s3_sensitive_fields_hidden(data)
        assert not passed
        assert any("email" in v for v in violations)

    def test_fails_when_pii_column_is_missing_from_yaml(self):
        # email column absent entirely
        data = dim_customers_doc([
            hidden_col("first_name"),
            hidden_col("last_name"),
        ])
        passed, violations = check_s3_sensitive_fields_hidden(data)
        assert not passed
        assert any("email" in v for v in violations)

    def test_reports_all_exposed_pii_columns(self):
        data = dim_customers_doc([
            visible_col("email"),
            visible_col("first_name"),
            hidden_col("last_name"),
        ])
        passed, violations = check_s3_sensitive_fields_hidden(data)
        assert not passed
        assert len(violations) == 2


# ── S4: raw revenue columns must be hidden ────────────────────────────────────

class TestS4RawRevenueHidden:

    def _all_hidden(self):
        return fct_orders_doc(columns=[
            hidden_col("gross_revenue"),
            hidden_col("net_revenue"),
            hidden_col("discount_amount"),
            hidden_col("refund_amount"),
        ])

    def test_passes_when_all_raw_revenue_columns_are_hidden(self):
        passed, _ = check_s4_raw_revenue_hidden(self._all_hidden())
        assert passed

    def test_fails_when_gross_revenue_is_exposed(self):
        data = fct_orders_doc(columns=[
            visible_col("gross_revenue"),
            hidden_col("net_revenue"),
            hidden_col("discount_amount"),
            hidden_col("refund_amount"),
        ])
        passed, violations = check_s4_raw_revenue_hidden(data)
        assert not passed
        assert any("gross_revenue" in v for v in violations)

    def test_fails_when_net_revenue_is_exposed(self):
        data = fct_orders_doc(columns=[
            hidden_col("gross_revenue"),
            visible_col("net_revenue"),
            hidden_col("discount_amount"),
            hidden_col("refund_amount"),
        ])
        passed, violations = check_s4_raw_revenue_hidden(data)
        assert not passed
        assert any("net_revenue" in v for v in violations)

    def test_reports_all_exposed_raw_columns(self):
        data = fct_orders_doc(columns=[
            visible_col("gross_revenue"),
            visible_col("net_revenue"),
            hidden_col("discount_amount"),
            hidden_col("refund_amount"),
        ])
        passed, violations = check_s4_raw_revenue_hidden(data)
        assert not passed
        assert len(violations) == 2

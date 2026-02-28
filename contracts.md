# Metric Contracts

## Purpose

Metrics are APIs. Once a metric is published, downstream consumers — dashboards, AI agents, analysts — depend on it behaving consistently. A contract is a set of rules that every metric must satisfy before it can be considered "published". Breaking a contract is a breaking change. These rules exist so that the metric layer can be trusted as a source of truth, not just a collection of SQL.

---

## Contract Rules

### Contract 1 — Every metric must be documented

**Applies to:** `fct_orders.yml` → each entry under `config.meta.metrics`

**Rule:** Every metric must declare all four fields:
- `label` — a stable identifier, human display name
- `description` — what it measures and any governance context
- `type` — the aggregation type (`sum`, `count_distinct`, `number`, etc.)
- `sql` — the column or expression being aggregated

**Why:** Trust and AI rely on well-described metrics. An undescribed metric is indistinguishable from an accident.

| | Example |
|---|---|
| ✅ Pass | `revenue_net` has `label`, `description`, `type: sum`, `sql: ${net_revenue}` |
| ❌ Fail | A metric exists in the YAML but `description` is missing or empty |

---

### Contract 2 — Revenue metrics must be unambiguous

**Applies to:** `fct_orders.yml` → `revenue_net`, `revenue_gross`

**Rule:** Revenue metric labels must include a governance qualifier that makes the definition unambiguous:
- `revenue_net` → label must be **"Net Revenue (Official)"**
- `revenue_gross` → label must be **"Gross Revenue (Topline)"**

**Why:** Two definitions of revenue exist in this project. Without explicit qualifiers, consumers will pick the wrong one. Metric chaos starts with a label like "Revenue".

| | Example |
|---|---|
| ✅ Pass | `label: "Net Revenue (Official)"`, `owner: Finance`, `tags: [official, revenue]` |
| ❌ Fail | `label: "Revenue"` with no qualifier, or both metrics sharing the same label |

---

### Contract 3 — Sensitive customer fields must be hidden

**Applies to:** `dim_customers.yml` → column-level `config.meta.dimension`

**Rule:** The following columns must have `hidden: true` set under their dimension config and must never be exposed to self-serve consumers:
- `email`
- `first_name`
- `last_name`

**Why:** AI-assisted self-serve tools surface every visible dimension automatically. Hiding PII fields by default is safety by design, not an afterthought.

| | Example |
|---|---|
| ✅ Pass | `email` column has `dimension: { type: string, hidden: true }` |
| ❌ Fail | `email` column has no `hidden` field, or `hidden: false` |

---

### Contract 4 — Joins must be safe by construction

**Applies to:** `fct_orders.yml` and `dim_customers.yml`

**Rule:** If `fct_orders` declares a join to `dim_customers`, then all three of the following must hold:
1. `fct_orders` declares `primary_key: order_id` under `config.meta`
2. `dim_customers` declares `primary_key: customer_id` under `config.meta`
3. The join declares `relationship: many-to-one`

**Why:** Without a declared primary key and relationship cardinality, Lightdash cannot protect against SQL fanout. A missing `primary_key` silently inflates every aggregated metric on the joined explore.

| | Example |
|---|---|
| ✅ Pass | Both models declare `primary_key`; join has `relationship: many-to-one` |
| ❌ Fail | Join exists in `fct_orders` but either model is missing `primary_key`, or `relationship` is absent |

---

### Contract 5 — Raw revenue columns must not be exposed as dimensions

**Applies to:** `fct_orders.yml` → column-level `config.meta.dimension`

**Rule:** The following columns must have `hidden: true` set under their dimension config:
- `gross_revenue`
- `net_revenue`
- `discount_amount`
- `refund_amount`

**Why:** Users should consume revenue through governed metrics (`revenue_net`, `revenue_gross`, etc.), not by dragging raw numeric columns into a chart. Exposing raw revenue columns as dimensions makes double-aggregation trivially easy and silently wrong.

| | Example |
|---|---|
| ✅ Pass | `gross_revenue` column has `dimension: { type: number, hidden: true }` |
| ❌ Fail | `net_revenue` column has no `hidden` field, making it selectable as a dimension |

---

## How Enforced

These contracts are enforced via a CI validator — currently in development. On every pull request, the validator will parse the relevant YAML files and fail the build if any contract rule is violated. No metric may be merged without passing all five contracts.

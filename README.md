# governed-metrics-starter-kit

Every analytics team hits the same wall: two dashboards show different revenue. Finance has one figure. Growth has another. A new analyst learns which to use from Slack. Three months later, nobody's sure anymore.

That's not a data quality problem. It's a governance problem.

---

## What this is

A working dbt + Lightdash reference project demonstrating **metrics-as-code with enforced governance**. Not a dbt tutorial. A template for the patterns that make a semantic layer trustworthy enough to build on.

---

## The Lightdash approach

Lightdash's core idea: metric definitions belong in your dbt project, version-controlled alongside the models they describe - not in dashboards, not in ad-hoc SQL. Metrics are defined once, reviewed in PRs, and served consistently to every consumer.

This project takes that further. Metrics are treated like APIs: they have owners, they have contracts, and breaking changes are caught in CI before they reach production.

---

## The governance model

Three tiers, each progressively stricter:

| Tier | Tag | Required fields | Owned by |
|------|-----|-----------------|----------|
| Official | `official` | label, description, type, sql, **owner, format** | Finance |
| Supported | `supported` | label, description, type, sql, **owner** | Growth / Finance |
| Experimental | `experimental` | label, description, type, sql | Anyone |

Every metric must declare exactly one tier. Promotion is a deliberate PR, not a quiet edit.

Two revenue metrics exist by design. `revenue_net` (Net Revenue, Finance, official) and `revenue_gross` (Gross Revenue, Growth, supported) are both valid — they just mean different things. The contracts enforce that their labels make the distinction unambiguous:

```yaml
revenue_net:
  label: "Net Revenue (Official)"   # must include the governance qualifier — enforced in CI
  tags: [official, revenue]
  owner: Finance

revenue_gross:
  label: "Gross Revenue (Topline)"  # must include the governance qualifier — enforced in CI
  tags: [supported, revenue]
  owner: Growth
```

Governance also applies at the column level. Raw revenue columns (`gross_revenue`, `net_revenue`) and PII fields (`email`, `first_name`, `last_name`) are marked `hidden: true` in the Lightdash dimension config — they don't appear in the explore UI. Analysts and AI agents can only access them through the governed metrics above, not as raw dimensions they can accidentally aggregate themselves.

---

## Contracts in CI

Every PR to `master` runs three parallel checks:

| Check | Tool | What it catches |
|-------|------|-----------------|
| **Governance contracts** | `validate_contracts.py` | Missing fields, wrong tier tags, ambiguous revenue labels, exposed PII, raw revenue columns surfaced as dimensions, unsafe join config |
| **dbt compile** | `dbt-postgres` | Broken `ref()`, Jinja errors, invalid SQL |
| **Lightdash lint** | `@lightdash/cli` | Invalid Lightdash YAML schemas |

Lightdash lint catches structural problems. The custom validator catches governance problems. They complement each other.

The validator covers three layers: baseline rules (every metric, every model), tiered rules (stricter as trust increases), and special rules (specific high-value models). Full spec in [contracts.md](contracts.md).

### What a failing PR looks like

Change `revenue_net`'s label from `"Net Revenue (Official)"` to `"Revenue"` and open a PR. The `Governance contracts` job fails:

```
[FAIL] S1: Revenue metric labels must include governance qualifiers
       - 'revenue_net' label must be "Net Revenue (Official)", got "Revenue"

One or more contracts failed. See violations above.
Error: Process completed with exit code 1.
```

![PR checks panel](docs/screenshots/pr-checks-failing.png)
![Validator output](docs/screenshots/validator-output.png)

---

## Why this matters for AI analytics

When an AI agent queries a semantic layer, it uses whatever definitions exist. If `revenue` is ambiguous, the AI picks one arbitrarily. If `email` isn't hidden, it surfaces it.

Governed metrics are the prerequisite for safe self-serve — human or AI.

---

## What to adapt for your project

- **The tier system** — swap tiers and owners to match your org structure
- **`contracts.md`** — write the rules in plain language before making them machine-enforced
- **`validate_contracts.py`** — add new special contracts for your high-value models; the pattern scales to any dbt project
- **Hidden columns** — mark raw and sensitive fields `hidden: true` and surface them only through governed metrics

---

## Quick start

**Prerequisites:** Python 3.10+, a Postgres database (the project uses [Neon](https://neon.tech) — any Postgres works).

```bash
pip install -r requirements.txt   # pyyaml, pytest, dbt-postgres (dbt-core installed transitively)
dbt build --profiles-dir .        # requires profiles.yml (gitignored — add your credentials)
python validate_contracts.py      # run governance checks locally
pytest test_validate_contracts.py # run validator unit tests
```

`profiles.yml` is gitignored. Use this template:

```yaml
governed_metrics:
  target: dev
  outputs:
    dev:
      type: postgres
      host: your-host
      port: 5432
      user: your-user
      password: your-password
      dbname: your-db
      schema: public
      threads: 4
      sslmode: require
```

For CI, set `DBT_HOST`, `DBT_USER`, `DBT_PASSWORD`, `DBT_DBNAME` as repository secrets. The dbt compile job skips automatically when secrets are absent, so external contributors aren't blocked.

---

## Project structure

```
governed-metrics-starter-kit/
├── contracts.md                    # contract specification (human-readable)
├── validate_contracts.py           # CI validator: baseline / tiered / special
├── test_validate_contracts.py      # pytest unit tests for the validator
├── requirements.txt
├── .github/workflows/
│   └── validate_contracts.yml      # governance + dbt compile + lightdash lint
├── seeds/
│   ├── customers.csv               # 5 customers
│   ├── orders.csv                  # 15 orders
│   └── order_items.csv             # 38 line items
├── models/
│   ├── staging/                    # views: type casts and renames only
│   └── marts/
│       ├── dim_customers.yml       # primary_key, PII hidden, Lightdash dimensions
│       ├── fct_orders.yml          # 8 governed metrics, joins, group_details
│       └── fct_order_items.yml
└── tests/                          # singular business-logic tests
```

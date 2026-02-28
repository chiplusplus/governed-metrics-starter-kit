# governed-metrics-starter-kit

A minimal dbt project using DuckDB and CSV seeds that demonstrates a staging-to-marts architecture with fact and dimension tables.

## Models

| Model | Layer | Materialization | Description |
|-------|-------|-----------------|-------------|
| `stg_customers` | Staging | View | Cleaned customer records |
| `stg_orders` | Staging | View | Cleaned order headers |
| `stg_order_items` | Staging | View | Cleaned order line items |
| `dim_customers` | Marts | Table | One row per customer |
| `fct_order_items` | Marts | Table | One row per line item, with `item_revenue` |
| `fct_orders` | Marts | Table | One row per order, with `gross_revenue` and `net_revenue` |

## Lineage

```
seeds/customers   → stg_customers   → dim_customers
seeds/orders      → stg_orders      ──────────────────────────┐
seeds/order_items → stg_order_items → fct_order_items → fct_orders
```

## Key metrics

| Metric | Model | Definition |
|--------|-------|------------|
| `item_revenue` | `fct_order_items` | `quantity × unit_price` |
| `gross_revenue` | `fct_orders` | `sum(item_revenue)` across all line items |
| `net_revenue` | `fct_orders` | `gross_revenue − refund_amount − discount_amount` |

## Materialization rationale

| Layer | Strategy | Why |
|-------|----------|-----|
| Staging | `view` | Zero storage cost; always reads fresh seed data; only lightweight type casts and renames |
| Marts | `table` | Aggregations (`SUM`, `COUNT`) are expensive to recompute on every query; analysts hit these models directly |

## Setup

### Prerequisites

- Python 3.9+
- pip

### Install

```bash
pip install dbt-duckdb
```

### Configure profile

**Option A** — copy to the default dbt location:

```bash
cp profiles.yml ~/.dbt/profiles.yml
dbt build
```

**Option B** — pass the project root as the profiles directory on every command:

```bash
dbt build --profiles-dir .
```

### Run

```bash
# Load seed CSV data into DuckDB
dbt seed --profiles-dir .

# Build all models
dbt run --profiles-dir .

# Run all tests (schema + singular business-logic)
dbt test --profiles-dir .

# Or do everything in one command
dbt build --profiles-dir .
```

The `dev.duckdb` file will be created in the project root on first run and is already `.gitignore`d.

## Tests

Schema tests (`unique`, `not_null`, `relationships`, `accepted_values`) are defined in the `_*__models.yml` files alongside each model.

Three business-logic singular tests live in `tests/`:

| Test file | Rule enforced |
|-----------|---------------|
| `assert_discount_amount_non_negative` | `discount_amount >= 0` on every order |
| `assert_refund_amount_non_negative` | `refund_amount >= 0` on every order |
| `assert_net_revenue_calculation` | `net_revenue = gross_revenue − refund_amount − discount_amount` |

## Project structure

```
governed-metrics-starter-kit/
├── dbt_project.yml
├── profiles.yml
├── seeds/
│   ├── customers.csv        # 5 customers
│   ├── orders.csv           # 15 orders
│   └── order_items.csv      # 38 line items
├── models/
│   ├── staging/
│   │   ├── _staging__models.yml
│   │   ├── stg_customers.sql
│   │   ├── stg_orders.sql
│   │   └── stg_order_items.sql
│   └── marts/
│       ├── _marts__models.yml
│       ├── dim_customers.sql
│       ├── fct_order_items.sql
│       └── fct_orders.sql
└── tests/
    ├── assert_discount_amount_non_negative.sql
    ├── assert_refund_amount_non_negative.sql
    └── assert_net_revenue_calculation.sql
```

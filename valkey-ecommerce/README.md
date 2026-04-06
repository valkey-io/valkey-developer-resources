# ValkeyMart

A product discovery demo powered by Valkey vector search. Search the full Amazon Berkeley Objects catalog with natural language, build a favourites collection, and get recommendations that adapt to your taste.

![Search results with sidebar filters](img/search-results.png)

## How it works

1. Type a natural language query like "comfortable jacket" or "modern minimalist furniture"
2. The backend encodes your query with a sentence transformer, extracts filterable keywords, and runs a hybrid ANN + TEXT search against the ABO product catalog
3. Browse results and filter by category, color, or material using the sidebar
4. Click "More like this" on any product to find nearest neighbors
5. Add items to your favourites, which builds a preference vector from your collection
6. Recommendations on the favourites page update as you add/remove items, based on your full collection

## What it demonstrates

- Text embeddings of product metadata (name, color, material, style, keywords) using sentence-transformers
- Natural language search: describe what you want in plain English
- Hybrid keyword + vector search: recognized terms (materials, colors, styles) are extracted and used as fuzzy TEXT filters alongside ANN
- Faceted filtering with category, color, and material facets computed from the KNN result set
- Similar items via nearest neighbor lookup on any product's embedding
- Favourites-based recommendations using per-item KNN queries with round-robin interleaving for diversity
- Cart bundle suggestions: cross-category ANN queries with TAG pre-filtering to suggest complementary products

Note on attribute filters: the ABO dataset does not include a "size" field, so filtering is limited to category, color, and material. These three cover the most common product attributes in the dataset and are enough to show how TAG filtering works in ValkeySearch.

## Tech stack

- Valkey + valkey-search: HNSW vector index (384-dim) with TAG filtering
- sentence-transformers (all-MiniLM-L6-v2): text embedding model (~80 MB, CPU-only)
- FastAPI: Python backend
- React + Vite: frontend
- Amazon Berkeley Objects: full product catalog across all categories

## Quick start (Docker)

Requires Docker Compose (or Finch) and [uv](https://docs.astral.sh/uv/) (Python package manager).

### 1. Start the services

```bash
cd valkey-ecommerce
docker compose up
```

This starts three services:
- valkey: Valkey server with the search module
- backend: FastAPI on port 8001
- frontend: Vite dev server on port 3001

### 2. Ingest the dataset

Ingest runs on your host machine (outside Docker) for better performance:

```bash
uv sync
uv run python scripts/ingest.py
```

This downloads the ABO metadata, generates text embeddings, and indexes everything into Valkey on `localhost:6379`. First run takes a few minutes (model download + encoding ~100k products). Subsequent runs skip if the index already exists.

Wait about 15 seconds after ingest finishes for Valkey to build the HNSW index in the background before searching. You can check by running `valkey-cli FT.INFO product_idx` after it finishes building.

### 3. Open the app

Go to http://localhost:3001 once ingest completes.

To stop:
```bash
docker compose down
```

Data persists across restarts. To wipe everything:
```bash
docker compose down -v
```

## Manual setup

If you prefer running things locally without Docker.

### Prerequisites

- Valkey server with the `valkey-search` module loaded
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 18+

### 1. Start Valkey with the search module

```bash
valkey-server --loadmodule /path/to/libsearch.so
```

### 2. Ingest the dataset

```bash
cd valkey-ecommerce
uv sync
uv run python scripts/ingest.py
```

Downloads ABO metadata, generates text embeddings, and indexes them into Valkey. First run takes a bit (model download + encoding).

### 3. Start the backend

```bash
uv run uvicorn backend.main:app --reload --port 8001
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3001 in your browser.

## API endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/search` | GET | Natural language product search (`q`, `product_type`, `color`, `material`, `sort_by`, `limit`, `min_price`, `max_price` params) |
| `/api/featured` | GET | Featured products |
| `/api/product/{item_id}` | GET | Full product details |
| `/api/similar/{item_id}` | GET | Similar items for a product (`limit`, `product_type`, `color`, `material` params) |
| `/api/favourites` | GET | Current favourite items |
| `/api/favourites/add` | POST | Add item to favourites |
| `/api/favourites/remove` | POST | Remove item from favourites |
| `/api/recommendations` | GET | Recommendations based on favourites (`product_type`, `limit` params) |
| `/api/cart` | GET | Cart items with full product details |
| `/api/cart/add` | POST | Add item to cart |
| `/api/cart/remove` | POST | Remove item from cart |
| `/api/cart/bundle` | GET | Complementary product suggestions based on cart contents (`limit` param) |

## Dataset

Uses the [Amazon Berkeley Objects Dataset](https://amazon-berkeley-objects.s3.amazonaws.com/index.html) (CC BY 4.0). Product metadata includes multilingual names, brand, color, material, style, and keywords across all product categories.

## How the vector pipeline works

### 1. Data loading

The ingest script (`scripts/ingest.py`) downloads 16 gzipped JSON listing files from the ABO S3 bucket. Products without a `product_type` or main image are dropped.

### 2. Text embedding generation

For each product, a searchable text string is built by concatenating:
- Product name (English)
- Color, material, style, brand
- Up to 5 keywords from the ABO metadata

A typical string looks like: `"Modern Oak Desk. color: Natural. material: Oak Wood. style: Modern. brand: West Elm. office furniture desk"`

This text is encoded into a 384-dimensional vector using the `all-MiniLM-L6-v2` sentence transformer. Embeddings are L2-normalized, so cosine similarity reduces to a dot product.

### 3. Storage in Valkey

Each product is stored as a Valkey Hash at key `product:{item_id}` with fields:
- `embedding`: 384-dim float32 vector (1536 bytes, binary packed)
- `item_id`, `item_name`, `brand`, `color`, `material`, `style`, `product_type`, `image_id`, `desc`

After all hashes are inserted, a ValkeySearch index is created:

```
FT.CREATE product_idx SCHEMA
  embedding VECTOR HNSW 6 TYPE FLOAT32 DIM 384 DISTANCE_METRIC COSINE
  product_type TAG
  color TAG
  material TAG
  desc TEXT
```

HNSW (Hierarchical Navigable Small World) is a graph-based index for approximate nearest neighbor search. The ingest script inserts all data first, then creates the index.

See the [FT.CREATE command reference](https://valkey.io/commands/ft.create/) for full index options.

### 4. Query and retrieval

At search time, the query text is encoded with the same model. The backend also extracts recognized terms (materials like "walnut", colors like "white", styles like "rustic") from the query string and uses them as fuzzy TEXT filters. The resulting hybrid query looks like:

```
FT.SEARCH product_idx "(@desc:%walnut% @desc:%rustic%)=>[KNN 1000 @embedding $vec]"
  PARAMS 2 vec <query_vector_bytes>
  DIALECT 2
```

This finds nearest neighbors in embedding space among products matching the text filter. `%keyword%` enables fuzzy matching (Levenshtein distance 1), so "walnuts" or "walnt" still match. When users select facet filters in the sidebar, TAG clauses like `@product_type:{DESK}` and `@color:{White}` are appended to narrow results further.

See the [FT.SEARCH command reference](https://valkey.io/commands/ft.search/) for query syntax.

### 5. Tag filtering

ValkeySearch TAG fields do exact-match filtering before the vector search runs:
- `@product_type:{SOFA|COUCH}`: one or more categories (OR semantics)
- `@color:{White|Brown}`: one or more color values

Multiple TAG filters can be combined in a single query. The frontend has multi-select checkboxes for category, color, and material. Toggling a sidebar facet triggers a new request to the backend with the corresponding TAG parameters, so ValkeySearch handles the filtering server-side. Facet counts come from the KNN result set, not the full index, so the numbers in the sidebar always match what is on screen.

### 6. Favourites and recommendations

The recommendations endpoint runs a separate KNN query for each favourited item and interleaves the results using round-robin. This ensures every favourited item contributes equally to the recommendations, regardless of how many items share a category. Items already in favourites are excluded from results. Favourite embeddings are fetched in a single pipelined batch before the per-item queries are issued.

### 7. Cart bundle suggestions

The cart drawer suggests products from categories not already in the cart. The backend walks through predefined category groups (seating, tables, lighting, rugs, etc.) and runs an ANN query with TAG pre-filtering for each missing group. The query vector is the user's favourites vector if one exists, otherwise a generic seed.

### 8. Facet computation

Facet distributions (product type counts, color counts, material counts) are computed in Python from the KNN result set. Aggregating against the full index would count products outside the KNN window, making sidebar numbers larger than the actual result set. Computing facets from the returned products avoids that mismatch.

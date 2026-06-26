"""Ingest ABO products into Valkey with text embeddings."""

import gzip
import json
import os
import struct
import time
import urllib.request
from pathlib import Path

from glide_sync import (
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
    Batch,
    ft,
    VectorField,
    VectorAlgorithm,
    VectorFieldAttributesHnsw,
    VectorType,
    DistanceMetricType,
    TagField,
    TextField,
)

VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = 6379
DATA_DIR = Path(__file__).parent / "data"
BASE_URL = "https://amazon-berkeley-objects.s3.amazonaws.com/listings/metadata"
LISTING_FILES = [f"listings_{x}.json.gz" for x in "0123456789abcdef"]

# No product type filter — ingest all items from the dataset

DIM = 384  # sentence-transformers/all-MiniLM-L6-v2 output dim


def get_en_value(field_list, fallback=""):
    """Extract English value from ABO multilingual field."""
    if not field_list:
        return fallback
    for item in field_list:
        if isinstance(item, dict):
            lang = item.get("language_tag", "")
            if lang.startswith("en"):
                return item.get("value", fallback)
    # Fallback to first value
    if isinstance(field_list[0], dict):
        return field_list[0].get("value", fallback)
    return fallback


def build_text(product: dict) -> str:
    """Build a searchable text string from product metadata."""
    parts = []
    name = get_en_value(product.get("item_name"))
    if name:
        parts.append(name)
    color = get_en_value(product.get("color"))
    if color:
        parts.append(f"color: {color}")
    material = get_en_value(product.get("material"))
    if material:
        parts.append(f"material: {material}")
    style = get_en_value(product.get("style"))
    if style:
        parts.append(f"style: {style}")
    brand = get_en_value(product.get("brand"))
    if brand:
        parts.append(f"brand: {brand}")
    keywords = product.get("item_keywords", [])
    kw_vals = [get_en_value([kw]) for kw in keywords[:5]]
    if kw_vals:
        parts.append(" ".join(kw_vals))
    return ". ".join(parts)


def download_listings():
    """Download and parse all ABO listing files."""
    DATA_DIR.mkdir(exist_ok=True)
    products = []
    for fname in LISTING_FILES:
        local = DATA_DIR / fname
        if not local.exists():
            print(f"  Downloading {fname}...")
            urllib.request.urlretrieve(f"{BASE_URL}/{fname}", local)
        with gzip.open(local, "rt") as f:
            for line in f:
                p = json.loads(line)
                # Only skip products with no product_type at all
                ptypes = {pt.get("value", "") for pt in p.get("product_type", [])}
                if ptypes:
                    products.append(p)
    return products


def _connect_valkey(host: str, port: int, retries: int = 30, delay: float = 2.0, request_timeout: int = None):
    """Connect to Valkey with retries so the container can start before Valkey is ready."""
    for attempt in range(1, retries + 1):
        try:
            config = GlideClientConfiguration(
                [NodeAddress(host=host, port=port)],
                request_timeout=request_timeout,
            )
            client = GlideClient.create(config)
            client.ping()
            return client
        except Exception:
            if attempt == retries:
                raise
            print(f"Waiting for Valkey at {host}:{port} (attempt {attempt}/{retries})...")
            time.sleep(delay)


def main():
    # Wait for Valkey to be ready, then check idempotency
    r = _connect_valkey(VALKEY_HOST, VALKEY_PORT)
    try:
        ft.info(r, "product_idx")
        print("product_idx already exists — skipping ingest.")
        return
    except Exception:
        pass  # Index doesn't exist, proceed with ingest

    print("Downloading ABO listings...")
    products = download_listings()
    print(f"Found {len(products)} products")

    # Build text descriptions
    texts = []
    valid_products = []
    for p in products:
        text = build_text(p)
        if len(text) > 20 and p.get("main_image_id"):
            texts.append(text)
            valid_products.append(p)
    print(f"After filtering: {len(valid_products)} products with text + images")

    # Embed with sentence-transformers
    print("Loading embedding model (all-MiniLM-L6-v2)...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")

    print("Encoding product descriptions...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=256, normalize_embeddings=True)

    # Drop stale index if it exists so FT.CREATE succeeds with a fresh schema
    try:
        ft.dropindex(r, "product_idx")
    except Exception:
        pass  # Index doesn't exist, nothing to drop

    # Only flush keys matching our product namespace rather than the entire DB.
    cursor = b"0"
    while True:
        result = r.scan(cursor, match="product:*", count=500)
        cursor = result[0]
        keys = result[1]
        if keys:
            r.delete(keys)
        if cursor == b"0":
            break

    # Insert data FIRST, then create index (bulk backfill is much faster than
    # incremental HNSW builds during HSET)
    print("Ingesting products...")
    total = len(valid_products)
    start = time.time()
    BATCH_SIZE = 500
    for batch_start in range(0, total, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total)
        batch = Batch(is_atomic=False)
        for i in range(batch_start, batch_end):
            p = valid_products[i]
            emb = embeddings[i]
            item_id = p["item_id"]
            key = f"product:{item_id}"
            vec_bytes = struct.pack(f"{DIM}f", *emb.tolist())
            ptypes = [pt.get("value", "") for pt in p.get("product_type", [])]
            batch.hset(key, {
                "embedding": vec_bytes,
                "item_id": item_id.encode(),
                "item_name": get_en_value(p.get("item_name")).encode(),
                "brand": get_en_value(p.get("brand")).encode(),
                "color": get_en_value(p.get("color")).encode(),
                "material": get_en_value(p.get("material")).encode(),
                "style": get_en_value(p.get("style")).encode(),
                "product_type": (ptypes[0] if ptypes else "").encode(),
                "image_id": (p.get("main_image_id") or "").encode(),
                "desc": build_text(p).encode(),
            })
        r.exec(batch, raise_on_error=True)
        elapsed = time.time() - start
        rate = batch_end / elapsed
        remaining = (total - batch_end) / rate if rate > 0 else 0
        print(f"  {batch_end}/{total} ({remaining:.0f}s remaining)")

    print(f"Ingested {total} products in {time.time() - start:.1f}s.")

    print("Creating index (backfill will build HNSW in background)...")
    # FT.CREATE with a large dataset can take longer than the default timeout.
    # Use a dedicated client with a 30s timeout just for this command.
    r_create = _connect_valkey(VALKEY_HOST, VALKEY_PORT, request_timeout=30000)
    ft.create(
        r_create,
        "product_idx",
        schema=[
            VectorField(
                "embedding",
                algorithm=VectorAlgorithm.HNSW,
                attributes=VectorFieldAttributesHnsw(
                    dimensions=DIM,
                    distance_metric=DistanceMetricType.COSINE,
                    type=VectorType.FLOAT32,
                ),
            ),
            TagField("product_type"),
            TagField("color"),
            TagField("material"),
            TextField("desc"),
        ],
    )
    print("Index created. Backfill running — search will work once indexing completes.")
    print("Check progress with: valkey-cli FT.INFO product_idx")


if __name__ == "__main__":
    main()

"""Valkey eCommerce backend powered by Valkey vector search."""

import hashlib
import os
import re
import struct
import time
import uuid
import numpy as np
import string
from glide_sync import (
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
    Batch,
    ft,
    FtSearchOptions,
    FtSearchLimit,
    ReturnField,
    RangeByIndex,
)
from fastapi import FastAPI, Cookie, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentence_transformers import SentenceTransformer

app = FastAPI()

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3001").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


def _connect_valkey(host: str, port: int = 6379, retries: int = 30, delay: float = 2.0):
    """Connect to Valkey with retries so the container can start before Valkey is ready."""
    for attempt in range(1, retries + 1):
        try:
            config = GlideClientConfiguration(
                [NodeAddress(host=host, port=port)],
                request_timeout=5000,
            )
            client = GlideClient.create(config)
            client.ping()
            return client
        except Exception:
            if attempt == retries:
                raise
            print(f"Waiting for Valkey at {host}:{port} (attempt {attempt}/{retries})...")
            time.sleep(delay)


EMBEDDING_MODEL = "all-MiniLM-L6-v2"
r = _connect_valkey(os.environ.get("VALKEY_HOST", "localhost"))
model = SentenceTransformer(EMBEDDING_MODEL)

DIM = 384
SESSION_TTL_SECONDS = 30 * 86400  # 30-day TTL for session-scoped keys
RETURN_FIELDS = ["item_id", "item_name", "brand", "color", "material", "style", "product_type", "image_id"]
KNN_RETURN_FIELDS = RETURN_FIELDS + ["__embedding_score"]

# Product category groups — one item per group for bundle/complementary suggestions
# Each tuple is (group_name, [category_tags_to_query])
CATEGORY_GROUPS = [
    ("Seating", ["CHAIR", "SOFA", "COUCH", "OTTOMAN", "BENCH", "BEAN_BAG_CHAIR", "STOOL_SEATING"]),
    ("Table", ["TABLE", "COFFEE_TABLE", "DINING_TABLE", "END_TABLE"]),
    ("Desk", ["DESK"]),
    ("Lighting", ["LAMP", "FLOOR_LAMP", "TABLE_LAMP", "LIGHT_FIXTURE", "LIGHT_BULB", "STRING_LIGHT",
                   "HOME_LIGHTING_AND_LAMPS", "HOME_LIGHTING_ACCESSORY"]),
    ("Rug", ["RUG"]),
    ("Curtains", ["CURTAIN", "WINDOW_SHADE"]),
    ("Wall Art", ["WALL_ART", "PICTURE_FRAME"]),
    ("Mirror", ["MIRROR", "HOME_MIRROR"]),
    ("Pillow", ["PILLOW", "THROW_PILLOW", "CUSHION"]),
    ("Throw Blanket", ["THROW_BLANKET", "FLAT_SHEET", "BLANKET", "TOWEL_HOLDER"]),
    ("Planter", ["PLANTER", "VASE"]),
    ("Candle", ["CANDLE", "CANDLE_HOLDER"]),
    ("Storage", ["CABINET", "BOOKCASE", "SHELVING", "SHELF"]),
    ("Dresser", ["DRESSER", "CHEST_OF_DRAWERS", "WARDROBE"]),
    ("Bed", ["BED", "BED_FRAME", "HEADBOARD"]),
    ("Basket", ["BASKET"]),
    ("Clock", ["CLOCK"]),
    ("Furniture", ["HOME_FURNITURE_AND_DECOR", "FURNITURE"]),
    ("Textiles", ["HOME_BED_AND_BATH"]),
    ("Sports", ["SHOES", "SPORTING_GOODS", "RECREATION_BALL", "EXERCISE_MAT", "BACKPACK",
                 "EXERCISE_BAND", "TECHNICAL_SPORT_SHOE"]),
    ("Electronics", ["HEADPHONES", "SPEAKERS", "KEYBOARDS", "INPUT_MOUSE", "MICROPHONE",
                      "CHARGING_ADAPTER", "BATTERY", "COMPUTER_ADD_ON", "COMPUTER_COMPONENT",
                      "ELECTRONIC_ADAPTER", "OFFICE_ELECTRONICS", "CONSUMER_ELECTRONICS",
                      "SCREEN_PROTECTOR"]),
]

# Price ranges by product_type prefix (min, max)
_FURNITURE_TYPES = {"BED", "SOFA", "COUCH", "DESK", "TABLE", "CABINET", "WARDROBE", "DRESSER",
                    "COFFEE_TABLE", "DINING_TABLE", "END_TABLE", "NIGHTSTAND", "BOOKCASE",
                    "SHELVING", "SHELF", "CHEST_OF_DRAWERS", "BED_FRAME", "HEADBOARD", "BENCH",
                    "OTTOMAN", "CHAIR", "VANITY"}
_LIGHTING_TYPES = {"LAMP", "FLOOR_LAMP", "TABLE_LAMP", "LIGHT_FIXTURE", "STRING_LIGHT"}
_TEXTILE_TYPES = {"RUG", "CURTAIN", "PILLOW", "THROW_PILLOW", "CUSHION", "THROW_BLANKET",
                  "FLAT_SHEET", "MATTRESS"}


def generate_price(item_id: str, product_type: str = "") -> float:
    """Deterministically generate a realistic price based on item_id and product_type."""
    h = int(hashlib.md5(item_id.encode()).hexdigest(), 16)
    pt = product_type.upper()
    if pt in _FURNITURE_TYPES:
        price = 100 + (h % 401)   # $100-$500
    elif pt in _LIGHTING_TYPES:
        price = 30 + (h % 221)    # $30-$250
    elif pt in _TEXTILE_TYPES:
        price = 20 + (h % 181)    # $20-$200
    else:
        price = 10 + (h % 241)    # $10-$250 for all other categories
    return round(price + (h % 100) / 100.0, 2)


def generate_rating(item_id: str) -> dict:
    """Deterministically generate a rating and review count based on item_id."""
    h = int(hashlib.md5(item_id.encode()).hexdigest(), 16)
    rating = round(1.0 + (h % 400) / 100.0, 1)  # 1.0–5.0
    review_count = 10 + (h % 1990)
    return {"rating": rating, "review_count": review_count}


def _build_category_filter(cats: list[str]) -> str:
    """Build a TAG filter for a group's categories."""
    return f"@product_type:{{{('|'.join(cats))}}}"


# Curated vocabulary for hybrid TEXT + KNN keyword extraction
FILTERABLE_TERMS: set[str] = {
    # Materials
    "walnut", "oak", "pine", "maple", "birch", "teak", "bamboo", "mahogany",
    "cherry", "cedar", "wood", "metal", "steel", "iron", "brass", "copper",
    "aluminum", "chrome", "glass", "leather", "fabric", "velvet", "linen",
    "cotton", "silk", "wool", "polyester", "suede", "canvas", "jute",
    "rattan", "wicker", "marble", "granite", "stone", "ceramic", "porcelain",
    "concrete", "resin", "acrylic", "plastic",
    # Colors
    "white", "black", "brown", "gray", "grey", "beige", "cream", "ivory",
    "tan", "navy", "blue", "green", "red", "pink", "yellow", "orange",
    "purple", "gold", "silver", "bronze", "natural", "espresso", "charcoal",
    # Style terms
    "rustic", "modern", "vintage", "antique", "industrial", "farmhouse",
    "coastal", "bohemian", "scandinavian", "minimalist", "mid-century",
    "contemporary", "traditional",
}


def extract_keywords(query: str) -> list[str]:
    """Extract filterable terms from a search query."""
    seen: set[str] = set()
    result: list[str] = []

    def _add(term: str) -> None:
        if term not in seen:
            seen.add(term)
            result.append(term)

    def _match_token(token: str) -> None:
        if token in FILTERABLE_TERMS:
            _add(token)
            return
        for term in FILTERABLE_TERMS:
            if token.startswith(term):
                _add(term)

    for raw_token in query.split():
        cleaned = raw_token.lower().strip(string.punctuation)
        if not cleaned:
            continue
        _match_token(cleaned)
        if "-" in cleaned:
            for part in cleaned.split("-"):
                if part:
                    _match_token(part)

    return result


def build_filter(keywords: list[str], product_type: str | None, fuzzy: bool = True) -> str:
    """Build the filter portion of an FT.SEARCH query."""
    if fuzzy:
        parts: list[str] = [f"@desc:%{kw}%" for kw in keywords]
    else:
        parts = [f"@desc:{kw}" for kw in keywords]
    if product_type:
        parts.append(f"@product_type:{{{product_type}}}")
    return " ".join(parts) if parts else "*"



def pack_vector(v: np.ndarray) -> bytes:
    return struct.pack(f"{DIM}f", *v.tolist())


def unpack_vector(b: bytes) -> np.ndarray:
    return np.array(struct.unpack(f"{DIM}f", b), dtype=np.float32)


def get_session_id(sid: str | None) -> str:
    return sid or str(uuid.uuid4())


# Regex: only allow alphanumeric, underscores, and hyphens in TAG filter values.
# This prevents FT.SEARCH query syntax injection via crafted product_type/color params.
_SAFE_TAG_RE = re.compile(r"[^a-zA-Z0-9_ -]")


def sanitize_tag(value: str) -> str:
    """Strip characters that could break or manipulate FT.SEARCH TAG filter syntax."""
    return _SAFE_TAG_RE.sub("", value).strip()


def _decode(value) -> str:
    """Decode bytes to str, pass through if already str."""
    return value.decode() if isinstance(value, bytes) else value


def _refresh_session_ttl(sid: str) -> None:
    """Reset the TTL on all session-scoped keys so they expire together."""
    for key in (f"cart:{sid}", f"fav:{sid}", f"favvec:{sid}"):
        if r.exists([key]):
            r.expire(key, SESSION_TTL_SECONDS)


def _set_session_cookie(resp: JSONResponse, sid: str) -> JSONResponse:
    """Set the session cookie with proper security attributes."""
    # Production environments should also set secure=True
    resp.set_cookie("session_id", sid, httponly=True, samesite="lax")
    _refresh_session_ttl(sid)
    return resp


def _ft_search(query_str: str, vec: bytes, return_fields: list[str],
               limit: int) -> list:
    """Execute an FT.SEARCH KNN query via the ft module and return structured results."""
    options = FtSearchOptions(
        return_fields=[ReturnField(field_identifier=f) for f in return_fields],
        params={"vec": vec},
        limit=FtSearchLimit(offset=0, count=limit),
    )
    return ft.search(r, "product_idx", query_str, options=options)


def parse_results(results) -> list[dict]:
    """Parse FtSearchResponse into a list of dicts.

    Expected shape from ft.search (glide_sync):
        [count: int, {doc_name: {field: value}, ...}]
    The second element is a Mapping keyed by document name, with values
    that are themselves Mappings of field -> value (both bytes).
    """
    if not results or results[0] == 0:
        return []
    doc_map = results[1] if len(results) > 1 else {}
    items = []
    for doc_name, field_map in doc_map.items():
        item = {}
        for k, v in field_map.items():
            item[_decode(k)] = _decode(v)
        if item:
            # Extract similarity score from __embedding_score if present
            if "__embedding_score" in item:
                try:
                    score = float(item["__embedding_score"])
                    item["similarity_score"] = round((1 - score) * 100)
                except (ValueError, TypeError):
                    pass
                del item["__embedding_score"]
            # Build image URL
            img_id = item.get("image_id", "")
            if img_id:
                item["image_url"] = f"https://m.media-amazon.com/images/I/{img_id}._AC_US256_.jpg"
            # Inject price and rating
            item_id = item.get("item_id", "")
            if item_id:
                product_type = item.get("product_type", "")
                item["price"] = generate_price(item_id, product_type)
                rating_data = generate_rating(item_id)
                item["rating"] = rating_data["rating"]
                item["review_count"] = rating_data["review_count"]
            items.append(item)
    return items



@app.get("/api/search")
def search(
    q: str,
    product_type: str = "",
    color: str = "",
    material: str = "",
    sort_by: str = "",
    limit: int = 1000,
    min_price: float = Query(default=None),
    max_price: float = Query(default=None),
):
    """Search products by natural language description.

    Returns all matching products (up to `limit`) so the frontend can paginate
    client-side while facets reflect the true total counts.

    Supports min_price and max_price query params to filter results by price.
    product_type, color, and material accept comma-separated values for multi-select filtering.
    """
    query_emb = model.encode(q, normalize_embeddings=True).astype(np.float32)
    keywords = extract_keywords(q)

    base_filter = build_filter(keywords, None, fuzzy=True)

    filter_str = base_filter

    selected_types = [sanitize_tag(t) for t in product_type.split(",") if sanitize_tag(t)] if product_type else []
    if selected_types:
        type_clause = f"@product_type:{{{('|'.join(selected_types))}}}"
        filter_str = type_clause if filter_str == "*" else f"{filter_str} {type_clause}"

    selected_colors = [sanitize_tag(c) for c in color.split(",") if sanitize_tag(c)] if color else []
    if selected_colors:
        color_clause = f"@color:{{{('|'.join(selected_colors))}}}"
        filter_str = color_clause if filter_str == "*" else f"{filter_str} {color_clause}"

    selected_materials = [sanitize_tag(m) for m in material.split(",") if sanitize_tag(m)] if material else []
    if selected_materials:
        material_clause = f"@material:{{{('|'.join(selected_materials))}}}"
        filter_str = material_clause if filter_str == "*" else f"{filter_str} {material_clause}"

    fetch_limit = limit
    query = f"({filter_str})=>[KNN {fetch_limit} @embedding $vec]"
    results = _ft_search(query, pack_vector(query_emb), KNN_RETURN_FIELDS, fetch_limit)

    products = parse_results(results)

    # Apply price filtering
    if min_price is not None:
        products = [p for p in products if p.get("price", 0) >= min_price]
    if max_price is not None:
        products = [p for p in products if p.get("price", 0) <= max_price]

    if sort_by == "product_type":
        products.sort(key=lambda p: p.get("product_type", "").lower())

    # Compute facets directly from the KNN result set so counts always match
    # what's displayed. A separate FT.AGGREGATE over the full index would count
    # products outside the KNN window, causing the sidebar counts to exceed the
    # actual number of results shown.
    type_counts: dict[str, int] = {}
    color_counts: dict[str, dict] = {}
    mat_counts: dict[str, dict] = {}
    for p in products:
        pt = p.get("product_type", "")
        if pt:
            type_counts[pt] = type_counts.get(pt, 0) + 1
        c = p.get("color", "").strip()
        if c:
            key = c.lower()
            if key not in color_counts:
                color_counts[key] = {"name": c.title(), "count": 0}
            color_counts[key]["count"] += 1
        m = p.get("material", "").strip()
        if m:
            key = m.lower()
            if key not in mat_counts:
                mat_counts[key] = {"name": m.title(), "count": 0}
            mat_counts[key]["count"] += 1
    facets = [{"name": k, "count": v} for k, v in sorted(type_counts.items(), key=lambda x: -x[1])]
    color_facets = sorted(color_counts.values(), key=lambda x: -x["count"])
    material_facets = sorted(mat_counts.values(), key=lambda x: -x["count"])

    return {"products": products, "facets": facets, "color_facets": color_facets, "material_facets": material_facets}


@app.get("/api/featured")
def featured():
    """Return 8 featured products using a fixed seed query."""
    seed_query = "popular trending products"
    query_emb = model.encode(seed_query, normalize_embeddings=True).astype(np.float32)
    query = f"(*)=>[KNN 8 @embedding $vec]"
    results = _ft_search(query, pack_vector(query_emb), KNN_RETURN_FIELDS, 8)
    products = parse_results(results)
    return {"products": products}


@app.get("/api/product/{item_id}")
def get_product(item_id: str):
    """Return full product details including price, rating, and review_count."""
    all_fields = RETURN_FIELDS + ["desc"]
    raw = r.hmget(f"product:{item_id}", all_fields)
    item = {}
    for k, v in zip(all_fields, raw):
        if v is not None:
            item[k] = _decode(v)
    if not item:
        return JSONResponse({"detail": "Product not found"}, status_code=404)
    img_id = item.get("image_id", "")
    if img_id:
        item["image_url"] = f"https://m.media-amazon.com/images/I/{img_id}._AC_US256_.jpg"
    product_type = item.get("product_type", "")
    item["price"] = generate_price(item_id, product_type)
    rating_data = generate_rating(item_id)
    item["rating"] = rating_data["rating"]
    item["review_count"] = rating_data["review_count"]
    return item


@app.post("/api/cart/add")
def cart_add(body: dict, session_id: str | None = Cookie(default=None)):
    """Add an item to the cart. Cart stored as hash cart:{session_id}."""
    sid = get_session_id(session_id)
    item_id = body.get("item_id")
    quantity = int(body.get("quantity", 1))
    if not item_id:
        return JSONResponse({"detail": "item_id required"}, status_code=400)
    cart_key = f"cart:{sid}"
    existing = r.hget(cart_key, item_id)
    current_qty = int(_decode(existing)) if existing else 0
    r.hset(cart_key, {item_id: str(current_qty + quantity)})
    resp = JSONResponse({"ok": True, "session_id": sid})
    return _set_session_cookie(resp, sid)


@app.post("/api/cart/remove")
def cart_remove(body: dict, session_id: str | None = Cookie(default=None)):
    """Remove an item from the cart."""
    sid = get_session_id(session_id)
    item_id = body.get("item_id")
    if not item_id:
        return JSONResponse({"detail": "item_id required"}, status_code=400)
    r.hdel(f"cart:{sid}", [item_id])
    resp = JSONResponse({"ok": True, "session_id": sid})
    return _set_session_cookie(resp, sid)


@app.get("/api/cart")
def get_cart(session_id: str | None = Cookie(default=None)):
    """Return cart items with full product details."""
    sid = get_session_id(session_id)
    cart_data = r.hgetall(f"cart:{sid}")
    if not cart_data:
        resp = JSONResponse({"items": [], "session_id": sid})
        return _set_session_cookie(resp, sid)

    # Decode cart entries and batch-fetch product details
    cart_entries = []
    batch = Batch(is_atomic=False)
    for item_id_bytes, qty_bytes in cart_data.items():
        item_id = _decode(item_id_bytes)
        quantity = int(_decode(qty_bytes))
        cart_entries.append((item_id, quantity))
        batch.hmget(f"product:{item_id}", RETURN_FIELDS)
    raw_results = r.exec(batch, raise_on_error=True)

    items = []
    for (item_id, quantity), raw in zip(cart_entries, raw_results):
        item = {}
        for k, v in zip(RETURN_FIELDS, raw):
            if v is not None:
                item[k] = _decode(v)
        if item:
            img_id = item.get("image_id", "")
            if img_id:
                item["image_url"] = f"https://m.media-amazon.com/images/I/{img_id}._AC_US256_.jpg"
            product_type = item.get("product_type", "")
            item["price"] = generate_price(item_id, product_type)
            rating_data = generate_rating(item_id)
            item["rating"] = rating_data["rating"]
            item["review_count"] = rating_data["review_count"]
            item["quantity"] = quantity
            items.append(item)

    resp = JSONResponse({"items": items, "session_id": sid})
    return _set_session_cookie(resp, sid)



@app.get("/api/cart/bundle")
def cart_bundle(limit: int = 8, session_id: str | None = Cookie(default=None)):
    """Return frequently bought together items based on cart contents."""
    sid = get_session_id(session_id)
    cart_data = r.hgetall(f"cart:{sid}")

    # Decode cart item IDs
    cart_ids: list[str] = []
    cart_types: set[str] = set()
    batch = Batch(is_atomic=False)
    for item_id_bytes in cart_data.keys():
        item_id = _decode(item_id_bytes)
        cart_ids.append(item_id)
        batch.hget(f"product:{item_id}", "product_type")

    pt_results = r.exec(batch, raise_on_error=True)
    for pt in pt_results:
        if pt:
            cart_types.add(_decode(pt))

    # Use favourites vector if available, else encode a generic seed
    fav_vec_raw = r.get(f"favvec:{sid}")
    if fav_vec_raw:
        search_vec = unpack_vector(fav_vec_raw)
    else:
        seed_text = "popular trending products"
        search_vec = model.encode(seed_text, normalize_embeddings=True).astype(np.float32)

    # Find complementary items from groups not represented in cart
    products = []
    seen_ids = set(cart_ids)
    for group_name, cats in CATEGORY_GROUPS:
        if len(products) >= limit:
            break
        if any(c in cart_types for c in cats):
            continue
        group_filter = _build_category_filter(cats)
        query = f"({group_filter})=>[KNN 5 @embedding $vec]"
        try:
            results = _ft_search(query, pack_vector(search_vec), KNN_RETURN_FIELDS, 5)
            candidates = parse_results(results)
            for c in candidates:
                if c.get("item_id") not in seen_ids:
                    products.append(c)
                    seen_ids.add(c["item_id"])
                    break
        except Exception:
            continue

    return {"products": products[:limit]}


@app.get("/api/favourites")
def get_favourites(session_id: str | None = Cookie(default=None)):
    """Get current favourite items."""
    sid = get_session_id(session_id)
    raw_ids = r.smembers(f"fav:{sid}")
    if not raw_ids:
        resp = JSONResponse({"items": [], "session_id": sid})
        return _set_session_cookie(resp, sid)

    # Decode all item IDs and batch-fetch product details
    item_ids = []
    batch = Batch(is_atomic=False)
    for iid in raw_ids:
        parsed_id = _decode(iid)
        item_ids.append(parsed_id)
        batch.hmget(f"product:{parsed_id}", RETURN_FIELDS)
    raw_results = r.exec(batch, raise_on_error=True)

    items = []
    for iid, raw in zip(item_ids, raw_results):
        item = {}
        for k, v in zip(RETURN_FIELDS, raw):
            if v is not None:
                item[k] = _decode(v)
        if item:
            img_id = item.get("image_id", "")
            if img_id:
                item["image_url"] = f"https://m.media-amazon.com/images/I/{img_id}._AC_US256_.jpg"
            product_type = item.get("product_type", "")
            item["price"] = generate_price(iid, product_type)
            rating_data = generate_rating(iid)
            item["rating"] = rating_data["rating"]
            item["review_count"] = rating_data["review_count"]
            items.append(item)

    resp = JSONResponse({"items": items, "session_id": sid})
    return _set_session_cookie(resp, sid)


@app.post("/api/favourites/add")
def add_to_favourites(body: dict, session_id: str | None = Cookie(default=None)):
    """Add item to favourites and return updated recommendations."""
    sid = get_session_id(session_id)
    item_id = body.get("item_id")
    if not item_id:
        return JSONResponse({"detail": "item_id required"}, status_code=400)
    r.sadd(f"fav:{sid}", [item_id])

    # NOTE: Vector recomputation is synchronous and blocks the response.
    # For large favourite sets this adds latency, but keeps the demo simple
    # by avoiding background task infrastructure.
    _update_favourites_vector(sid)

    resp = JSONResponse({"ok": True, "session_id": sid})
    return _set_session_cookie(resp, sid)


@app.post("/api/favourites/remove")
def remove_from_favourites(body: dict, session_id: str | None = Cookie(default=None)):
    """Remove item from favourites."""
    sid = get_session_id(session_id)
    item_id = body.get("item_id")
    if not item_id:
        return JSONResponse({"detail": "item_id required"}, status_code=400)
    r.srem(f"fav:{sid}", [item_id])

    # NOTE: Vector recomputation is synchronous and blocks the response.
    # For large favourite sets this adds latency, but keeps the demo simple
    # by avoiding background task infrastructure.
    _update_favourites_vector(sid)

    resp = JSONResponse({"ok": True, "session_id": sid})
    return _set_session_cookie(resp, sid)


@app.get("/api/recommendations")
def recommendations(session_id: str | None = Cookie(default=None), product_type: str = "", limit: int = 20):
    """Get recommendations based on favourites using per-item KNN with round-robin interleaving."""
    sid = get_session_id(session_id)
    fav_ids_raw = r.smembers(f"fav:{sid}")
    if not fav_ids_raw:
        resp = JSONResponse({"products": [], "session_id": sid})
        return _set_session_cookie(resp, sid)

    fav_ids = {_decode(x) for x in fav_ids_raw}

    filters = []
    if product_type:
        safe_pt = sanitize_tag(product_type)
        if safe_pt:
            filters.append(f"@product_type:{{{safe_pt}}}")
    filter_str = " ".join(filters) if filters else "*"

    # Batch-fetch all favourite embeddings
    batch = Batch(is_atomic=False)
    fav_id_list = list(fav_ids)
    for fav_id in fav_id_list:
        batch.hget(f"product:{fav_id}", "embedding")
    raw_vecs = r.exec(batch, raise_on_error=True)

    # KNN per favourite item, fetching enough candidates to fill limit after deduplication
    candidates_per_item = limit + len(fav_ids) + 5
    query = f"({filter_str})=>[KNN {candidates_per_item} @embedding $vec]"
    per_item_results = []
    for raw in raw_vecs:
        if not raw:
            continue
        vec = unpack_vector(raw)
        results = _ft_search(query, pack_vector(vec), KNN_RETURN_FIELDS, candidates_per_item)
        candidates = [p for p in parse_results(results) if p.get("item_id") not in fav_ids]
        per_item_results.append(candidates)

    # Round-robin interleave across per-item result lists
    seen_ids: set[str] = set()
    products: list[dict] = []
    iters = [iter(lst) for lst in per_item_results]
    while len(products) < limit and iters:
        next_iters = []
        for it in iters:
            if len(products) >= limit:
                break
            try:
                p = next(it)
                item_id = p.get("item_id")
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    products.append(p)
                next_iters.append(it)
            except StopIteration:
                pass
        iters = next_iters

    resp = JSONResponse({"products": products, "session_id": sid})
    return _set_session_cookie(resp, sid)



@app.get("/api/similar/{item_id}")
def similar(
    item_id: str,
    limit: int = 12,
    product_type: str = "",
    color: str = "",
    material: str = "",
    session_id: str | None = Cookie(default=None),
):
    """Find nearest neighbors for a specific item.

    Accepts optional product_type, color, and material TAG filters (comma-separated)
    so sidebar filtering is performed server-side, keeping result counts accurate.
    """
    sid = get_session_id(session_id)

    raw = r.hget(f"product:{item_id}", "embedding")
    if not raw:
        return {"products": []}

    item_vec = unpack_vector(raw)

    # Build TAG filter string from any active sidebar filters
    filter_parts: list[str] = []
    selected_types = [sanitize_tag(t) for t in product_type.split(",") if sanitize_tag(t)] if product_type else []
    if selected_types:
        filter_parts.append(f"@product_type:{{{('|'.join(selected_types))}}}")
    selected_colors = [sanitize_tag(c) for c in color.split(",") if sanitize_tag(c)] if color else []
    if selected_colors:
        filter_parts.append(f"@color:{{{('|'.join(selected_colors))}}}")
    selected_materials = [sanitize_tag(m) for m in material.split(",") if sanitize_tag(m)] if material else []
    if selected_materials:
        filter_parts.append(f"@material:{{{('|'.join(selected_materials))}}}")
    filter_str = " ".join(filter_parts) if filter_parts else "*"

    fetch_limit = limit + 1 # Excludes itself
    query = f"({filter_str})=>[KNN {fetch_limit} @embedding $vec]"
    results = _ft_search(query, pack_vector(item_vec), KNN_RETURN_FIELDS, fetch_limit)
    products = [p for p in parse_results(results) if p.get("item_id") != item_id][:limit]

    # Build facets from similarity results
    type_counts: dict[str, int] = {}
    color_counts: dict[str, dict] = {}
    material_counts: dict[str, dict] = {}
    for p in products:
        pt = p.get("product_type", "")
        if pt:
            type_counts[pt] = type_counts.get(pt, 0) + 1
        c = p.get("color", "").strip()
        if c:
            key = c.lower()
            if key not in color_counts:
                color_counts[key] = {"name": c.title(), "count": 0}
            color_counts[key]["count"] += 1
        m = p.get("material", "").strip()
        if m:
            key = m.lower()
            if key not in material_counts:
                material_counts[key] = {"name": m.title(), "count": 0}
            material_counts[key]["count"] += 1
    facets = [{"name": k, "count": v} for k, v in sorted(type_counts.items(), key=lambda x: -x[1])]
    color_facets = sorted(color_counts.values(), key=lambda x: -x["count"])
    material_facets = sorted(material_counts.values(), key=lambda x: -x["count"])

    resp = JSONResponse({"products": products, "facets": facets, "color_facets": color_facets, "material_facets": material_facets})
    return _set_session_cookie(resp, sid)


def _update_favourites_vector(sid: str):
    """Recompute the equal-weighted average embedding of all favourite items."""
    fav_ids = r.smembers(f"fav:{sid}")
    if not fav_ids:
        r.delete([f"favvec:{sid}"])
        return

    batch = Batch(is_atomic=False)
    for iid in fav_ids:
        batch.hget(f"product:{_decode(iid)}", "embedding")
    raw_vecs = r.exec(batch, raise_on_error=True)

    vecs = [unpack_vector(raw) for raw in raw_vecs if raw]

    if not vecs:
        r.delete([f"favvec:{sid}"])
        return

    avg = np.mean(np.stack(vecs).astype(np.float64), axis=0).astype(np.float32)
    norm = np.linalg.norm(avg)
    if norm > 0:
        avg = avg / norm
    r.set(f"favvec:{sid}", pack_vector(avg))

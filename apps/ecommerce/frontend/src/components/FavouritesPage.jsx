import { useState, useEffect } from "react";
import ProductCard from "./ProductCard";

const API = "/api";

export default function FavouritesPage({
  favouriteIds, onAddToCart, onMoreLikeThis, onAddToFavourites,
  onRemoveFromFavourites, onProductClick, onHome, onError,
}) {
  const [items, setItems] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch(`${API}/favourites`, { credentials: "include" }).then((r) => r.json()),
      fetch(`${API}/recommendations?limit=5`, { credentials: "include" }).then((r) => r.json()),
    ])
      .then(([favData, recData]) => {
        setItems(favData.items || []);
        setRecommendations(recData.products || []);
      })
      .catch(() => onError?.("Failed to load favourites."))
      .finally(() => setLoading(false));
  }, [favouriteIds]);

  return (
    <div style={styles.wrapper}>
      <div style={styles.breadcrumb}>
        <span style={styles.breadcrumbLink} onClick={onHome} role="button" tabIndex={0}
          onKeyDown={(e) => e.key === "Enter" && onHome()}>Home</span>
        <span style={styles.sep}>/</span>
        <span style={styles.breadcrumbCurrent}>Favourites</span>
      </div>

      <div style={styles.titleRow}>
        <h1 style={styles.title}>Favourites</h1>
        {items.length > 0 && (
          <span style={styles.count}>{items.length} item{items.length !== 1 ? "s" : ""}</span>
        )}
      </div>

      {loading ? (
        <div style={styles.empty}>Loading...</div>
      ) : items.length === 0 ? (
        <div style={styles.emptyState}>
          <span className="material-symbols-outlined" style={{ fontSize: 48, color: "#c2c6d2" }}>favorite</span>
          <p style={styles.emptyTitle}>No favourites yet</p>
          <p style={styles.emptySub}>Tap the heart on any product to save it here.</p>
          <button style={styles.browseBtn} onClick={onHome}>Browse products</button>
        </div>
      ) : (
        <div style={styles.grid}>
          {items.map((p) => (
            <div key={p.item_id} style={{ position: "relative" }}>
              <div onClick={() => onProductClick?.(p.item_id)} style={{ cursor: "pointer" }}>
                <ProductCard
                  product={p}
                  onAddToCart={onAddToCart}
                  onMoreLikeThis={onMoreLikeThis}
                  onAddToFavourites={onAddToFavourites}
                  onRemoveFromFavourites={onRemoveFromFavourites}
                  isFavourited={favouriteIds?.has(p.item_id)}
                />
              </div>
              <button
                style={styles.removeBtn}
                onClick={() => onRemoveFromFavourites(p.item_id)}
                title="Remove from favourites"
              >
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span>
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Recommendations based on favourites */}
      {recommendations.length > 0 && (
        <div style={styles.recsSection}>
          <h2 style={styles.recsTitle}>Recommended for you</h2>
          <p style={styles.recsSub}>Based on your favourites collection.</p>
          <div style={styles.recsGrid}>
            {recommendations.map((p) => (
              <div key={p.item_id} onClick={() => onProductClick?.(p.item_id)} style={{ cursor: "pointer" }}>
                <ProductCard
                  product={p}
                  onAddToCart={onAddToCart}
                  onMoreLikeThis={onMoreLikeThis}
                  onAddToFavourites={onAddToFavourites}
                  onRemoveFromFavourites={onRemoveFromFavourites}
                  isFavourited={favouriteIds?.has(p.item_id)}
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


const styles = {
  wrapper: { maxWidth: 1440, margin: "0 auto", padding: "32px 32px 80px" },
  breadcrumb: { display: "flex", gap: 8, fontSize: 11, color: "#43474f", marginBottom: 20, alignItems: "center" },
  breadcrumbLink: { cursor: "pointer", fontWeight: 500 },
  sep: { color: "#c2c6d2" },
  breadcrumbCurrent: { fontWeight: 700, color: "#191c1d" },
  titleRow: { display: "flex", alignItems: "baseline", gap: 12, marginBottom: 32 },
  title: { fontSize: 28, fontWeight: 900, letterSpacing: "-0.02em", color: "#191c1d" },
  count: { fontSize: 14, color: "#43474f" },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
    gap: 1, background: "rgba(194,198,210,0.1)",
  },
  empty: { textAlign: "center", padding: 80, color: "#43474f", fontSize: 15 },
  emptyState: {
    display: "flex", flexDirection: "column", alignItems: "center",
    justifyContent: "center", padding: "120px 32px", gap: 12,
  },
  emptyTitle: { fontSize: 18, fontWeight: 700, color: "#191c1d" },
  emptySub: { fontSize: 14, color: "#43474f" },
  browseBtn: {
    marginTop: 12, padding: "12px 28px",
    background: "#001736", color: "#fff",
    border: "none", borderRadius: 6,
    fontSize: 13, fontWeight: 700, cursor: "pointer",
  },
  removeBtn: {
    position: "absolute", top: 8, right: 8, zIndex: 4,
    width: 28, height: 28, borderRadius: "50%",
    background: "rgba(255,255,255,0.9)", border: "1px solid rgba(194,198,210,0.4)",
    cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
    color: "#43474f", transition: "background 0.15s",
  },
  recsSection: {
    marginTop: 64, paddingTop: 40,
    borderTop: "1px solid rgba(194,198,210,0.3)",
  },
  recsTitle: { fontSize: 22, fontWeight: 900, letterSpacing: "-0.02em", color: "#001736", marginBottom: 4 },
  recsSub: { fontSize: 13, color: "#43474f", marginBottom: 24 },
  recsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
    gap: 1, background: "rgba(194,198,210,0.1)",
  },
};

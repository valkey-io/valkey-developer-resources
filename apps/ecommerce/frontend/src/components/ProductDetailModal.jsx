import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { formatProductType, StarRating } from "../utils";

const API = "/api";

export default function ProductDetailModal({ itemId, onClose, onAddToCart, onMoreLikeThis }) {
  const [product, setProduct] = useState(null);
  const [similar, setSimilar] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addedCart, setAddedCart] = useState(false);

  useEffect(() => {
    if (!itemId) return;
    setLoading(true);
    Promise.all([
      fetch(`${API}/product/${itemId}`, { credentials: "include" }).then((r) => r.json()),
      fetch(`${API}/similar/${itemId}?limit=4`, { credentials: "include" }).then((r) => r.json()),
    ]).then(([prod, sim]) => {
      setProduct(prod);
      setSimilar(sim.products || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [itemId]);

  const handleAddCart = () => {
    onAddToCart?.(itemId);
    setAddedCart(true);
    setTimeout(() => setAddedCart(false), 2000);
  };

  return (
    <AnimatePresence>
      {itemId && (
        <>
          <motion.div
            style={styles.backdrop}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            style={styles.modal}
            initial={{ opacity: 0, x: "-50%", y: "calc(-50% + 20px)" }}
            animate={{ opacity: 1, x: "-50%", y: "-50%" }}
            exit={{ opacity: 0, x: "-50%", y: "calc(-50% + 20px)" }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
          >
            <button style={styles.closeBtn} onClick={onClose}>
              <span className="material-symbols-outlined">close</span>
            </button>

            {loading ? (
              <div style={styles.loading}>Loading...</div>
            ) : product ? (
              <div style={styles.content}>
                {/* Gallery */}
                <div style={styles.gallery}>
                  <div style={styles.mainImg}>
                    {product.image_url && (
                      <img src={product.image_url} alt={product.item_name} style={styles.img} />
                    )}
                  </div>
                </div>

                {/* Info */}
                <div style={styles.info}>
                  <nav style={styles.breadcrumb}>
                    <span>{formatProductType(product.product_type)}</span>
                    {product.brand && <><span style={{ color: "#c2c6d2" }}>/</span><span>{product.brand}</span></>}
                  </nav>

                  <h1 style={styles.title}>{product.item_name}</h1>

                  <div style={styles.ratingRow}>
                    <StarRating rating={product.rating} size={14} />
                    <span style={styles.reviewCount}>{product.review_count?.toLocaleString()} Reviews</span>
                  </div>

                  <div style={styles.price}>${product.price?.toFixed(2)}</div>

                  {product.desc && (
                    <p style={styles.desc}>{product.desc}</p>
                  )}

                  {/* Attributes */}
                  <div style={styles.attrs}>
                    {product.color && (
                      <div style={styles.attr}>
                        <span style={styles.attrLabel}>Color</span>
                        <span style={styles.attrVal}>{product.color}</span>
                      </div>
                    )}
                    {product.material && (
                      <div style={styles.attr}>
                        <span style={styles.attrLabel}>Material</span>
                        <span style={styles.attrVal}>{product.material}</span>
                      </div>
                    )}
                    {product.style && (
                      <div style={styles.attr}>
                        <span style={styles.attrLabel}>Style</span>
                        <span style={styles.attrVal}>{product.style}</span>
                      </div>
                    )}
                  </div>

                  {/* CTAs */}
                  <div style={styles.ctas}>
                    <motion.button
                      style={{ ...styles.cartBtn, ...(addedCart ? styles.cartBtnAdded : {}) }}
                      onClick={handleAddCart}
                      whileHover={{ opacity: 0.9 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
                        {addedCart ? "check" : "shopping_cart"}
                      </span>
                      {addedCart ? "Added to Cart" : "Add to Cart"}
                    </motion.button>
                    {onMoreLikeThis && (
                      <button style={styles.similarBtn} onClick={() => { onMoreLikeThis(itemId, product.item_name); onClose(); }}>
                        More like this
                      </button>
                    )}
                  </div>

                  <div style={styles.badges}>
                    <div style={styles.badge}>
                      <span className="material-symbols-outlined" style={{ fontSize: 16, color: "#001736" }}>local_shipping</span>
                      <span>Same-Day Delivery</span>
                    </div>
                    <div style={styles.badge}>
                      <span className="material-symbols-outlined" style={{ fontSize: 16, color: "#001736" }}>verified</span>
                      <span>Lifetime Warranty</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div style={styles.loading}>Product not found.</div>
            )}

            {/* Curated Pairings */}
            {similar.length > 0 && (
              <div style={styles.pairings}>
                <div style={styles.pairingsHeader}>
                  <span style={styles.pairingsLabel}>Complete the set</span>
                  <h2 style={styles.pairingsTitle}>You might also like</h2>
                </div>
                <div style={styles.pairingsGrid}>
                  {similar.map((p) => (
                    <div key={p.item_id} style={styles.pairingCard} onClick={() => onMoreLikeThis?.(p.item_id, p.item_name)}>
                      <div style={styles.pairingImg}>
                        {p.image_url && <img src={p.image_url} alt={p.item_name} style={{ width: "100%", height: "100%", objectFit: "contain" }} />}
                        <div style={styles.pairingPrice}>${p.price?.toFixed(2)}</div>
                      </div>
                      <p style={styles.pairingName}>{p.item_name?.slice(0, 50)}</p>
                      <p style={styles.pairingType}>{formatProductType(p.product_type)}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

const styles = {
  backdrop: {
    position: "fixed", inset: 0, background: "rgba(25,28,29,0.5)",
    zIndex: 300, backdropFilter: "blur(8px)",
  },
  modal: {
    position: "fixed", top: "50%", left: "50%",
    width: "90vw", maxWidth: 1000, maxHeight: "90vh",
    background: "#f8fafa", borderRadius: 16, zIndex: 301,
    overflowY: "auto",
    boxShadow: "0 24px 80px rgba(0,0,0,0.2)",
  },
  closeBtn: {
    position: "absolute", top: 16, right: 16, zIndex: 10,
    background: "#fff", border: "none", borderRadius: "50%",
    width: 40, height: 40, cursor: "pointer",
    display: "flex", alignItems: "center", justifyContent: "center",
    boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
    color: "#191c1d",
  },
  loading: { padding: 80, textAlign: "center", color: "#43474f" },
  content: {
    display: "grid", gridTemplateColumns: "1fr 1fr",
    gap: 0, padding: 0,
  },
  gallery: { background: "#f2f4f4", borderRadius: "16px 0 0 0", padding: 32 },
  mainImg: {
    aspectRatio: "4/5", background: "#eceeee",
    borderRadius: 12, overflow: "hidden",
    display: "flex", alignItems: "center", justifyContent: "center",
  },
  img: { width: "100%", height: "100%", objectFit: "contain" },
  info: { padding: 40 },
  breadcrumb: {
    display: "flex", gap: 8, fontSize: 10,
    fontWeight: 700, letterSpacing: "0.15em",
    textTransform: "uppercase", color: "#43474f",
    marginBottom: 16,
  },
  title: {
    fontSize: "clamp(24px, 3vw, 40px)", fontWeight: 900,
    letterSpacing: "-0.02em", color: "#001736",
    lineHeight: 1.1, marginBottom: 16,
  },
  ratingRow: { display: "flex", alignItems: "center", gap: 8, marginBottom: 20 },
  reviewCount: { fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#43474f" },
  price: { fontSize: 28, fontWeight: 300, color: "#001736", marginBottom: 20 },
  desc: { fontSize: 15, color: "#43474f", lineHeight: 1.7, marginBottom: 24, fontWeight: 300 },
  attrs: { display: "flex", flexDirection: "column", gap: 12, marginBottom: 28 },
  attr: { display: "flex", justifyContent: "space-between", paddingBottom: 12, borderBottom: "1px solid rgba(194,198,210,0.2)" },
  attrLabel: { fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#43474f" },
  attrVal: { fontSize: 13, fontWeight: 500, color: "#191c1d" },
  ctas: { display: "flex", flexDirection: "column", gap: 10, marginBottom: 24 },
  cartBtn: {
    width: "100%", padding: "18px 0",
    background: "linear-gradient(135deg, #003469, #004b91)",
    color: "#fff", border: "none", borderRadius: 8,
    fontSize: 14, fontWeight: 700, cursor: "pointer",
    display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
    letterSpacing: "0.05em", transition: "opacity 0.2s",
  },
  cartBtnAdded: { background: "#1a6b6a" },
  similarBtn: {
    width: "100%", padding: "16px 0",
    background: "#fff", color: "#001736",
    border: "1px solid rgba(0,23,54,0.2)", borderRadius: 8,
    fontSize: 13, fontWeight: 700, cursor: "pointer",
    letterSpacing: "0.05em", transition: "background 0.2s",
  },
  badges: { display: "flex", gap: 24 },
  badge: {
    display: "flex", flexDirection: "column", gap: 4,
    fontSize: 10, fontWeight: 700, letterSpacing: "0.1em",
    textTransform: "uppercase", color: "#191c1d",
  },
  pairings: {
    padding: "40px 40px 48px",
    borderTop: "1px solid rgba(194,198,210,0.2)",
  },
  pairingsHeader: { marginBottom: 24 },
  pairingsLabel: {
    fontSize: 10, fontWeight: 700, letterSpacing: "0.3em",
    textTransform: "uppercase", color: "#8a5100",
    display: "block", marginBottom: 6,
  },
  pairingsTitle: {
    fontSize: 24, fontWeight: 900, letterSpacing: "-0.02em",
    color: "#001736", textTransform: "uppercase",
  },
  pairingsGrid: { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 },
  pairingCard: { cursor: "pointer" },
  pairingImg: {
    aspectRatio: "4/5", background: "#f2f4f4",
    borderRadius: 12, overflow: "hidden",
    position: "relative", marginBottom: 10,
  },
  pairingPrice: {
    position: "absolute", bottom: 10, left: 10,
    background: "rgba(255,255,255,0.9)", backdropFilter: "blur(4px)",
    padding: "4px 10px", borderRadius: 20,
    fontSize: 12, fontWeight: 700,
  },
  pairingName: { fontSize: 12, fontWeight: 600, color: "#001736", lineHeight: 1.3, marginBottom: 2 },
  pairingType: { fontSize: 9, fontWeight: 700, letterSpacing: "0.15em", textTransform: "uppercase", color: "#43474f" },
};

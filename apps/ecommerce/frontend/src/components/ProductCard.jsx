import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { formatProductType, StarRating } from "../utils";

export default function ProductCard({ product: p, onAddToCart, onMoreLikeThis, onAddToFavourites, onRemoveFromFavourites, isFavourited }) {
  const [imgLoaded, setImgLoaded] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [addedCart, setAddedCart] = useState(false);

  const handleAddCart = () => {
    onAddToCart?.(p.item_id);
    setAddedCart(true);
    setTimeout(() => setAddedCart(false), 2000);
  };

  return (
    <motion.div
      style={styles.card}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.12 }}
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
    >
      {/* Image */}
      <div style={styles.imgWrap}>
        {p.similarity_score != null && (
          <div style={styles.matchBadge}>{p.similarity_score}%</div>
        )}
        {p.image_url ? (
          <>
            {!imgLoaded && <div style={styles.skeleton} />}
            <motion.img
              src={p.image_url}
              alt={p.item_name}
              style={{ ...styles.img, opacity: imgLoaded ? 1 : 0 }}
              loading="lazy"
              onLoad={() => setImgLoaded(true)}
              animate={hovered ? { scale: 1.06 } : { scale: 1 }}
              transition={{ duration: 0.4 }}
            />
          </>
        ) : (
          <div style={styles.noImg}>No image</div>
        )}

        {/* Hover overlay actions */}
        <AnimatePresence>
          {hovered && (
            <motion.div
              style={styles.overlay}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              {onMoreLikeThis && (
                <button style={styles.overlayBtn} onClick={(e) => { e.stopPropagation(); onMoreLikeThis(p.item_id, p.item_name); }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>search</span>
                  More like this
                </button>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Info */}
      <div style={styles.info}>
        {p.product_type && (
          <span style={styles.category}>{formatProductType(p.product_type)}</span>
        )}
        <p style={styles.name}>{p.item_name || "Unnamed product"}</p>

        {/* Rating */}
        {p.rating && (
          <div style={styles.ratingRow}>
            <StarRating rating={p.rating} size={11} gap={1} />
            <span style={styles.reviewCount}>({p.review_count?.toLocaleString()})</span>
          </div>
        )}

        {/* Tags */}
        <div style={styles.tags}>
          {p.color && <span style={styles.tag}>{p.color}</span>}
          {p.material && <span style={styles.tag}>{p.material}</span>}
        </div>

        {/* Price + CTA */}
        <div style={styles.footer}>
          <span style={styles.price}>${p.price?.toFixed(2)}</span>
          <div style={styles.ctaRow}>
            {onAddToFavourites && (
              <motion.button
                style={{ ...styles.favBtn, ...(isFavourited ? styles.favBtnActive : {}) }}
                onClick={(e) => { e.stopPropagation(); isFavourited ? onRemoveFromFavourites?.(p.item_id) : onAddToFavourites(p.item_id); }}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                title={isFavourited ? "Remove from favourites" : "Add to favourites"}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 14, fontVariationSettings: `'FILL' ${isFavourited ? 1 : 0}` }}>
                  favorite
                </span>
              </motion.button>
            )}
            <motion.button
              style={{ ...styles.cartBtn, ...(addedCart ? styles.cartBtnAdded : {}) }}
              onClick={(e) => { e.stopPropagation(); handleAddCart(); }}
              whileHover={{ opacity: 0.9 }}
              whileTap={{ scale: 0.97 }}
            >
              <AnimatePresence mode="wait">
                <motion.span
                  key={addedCart ? "added" : "add"}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.12 }}
                  style={{ display: "flex", alignItems: "center", gap: 4 }}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: 14 }}>
                    {addedCart ? "check" : "shopping_cart"}
                  </span>
                  {addedCart ? "Added" : "Add to Cart"}
                </motion.span>
              </AnimatePresence>
            </motion.button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

const styles = {
  card: {
    background: "#fff", borderRadius: 2,
    overflow: "hidden", cursor: "pointer",
    transition: "box-shadow 0.3s",
  },
  imgWrap: {
    width: "100%", aspectRatio: "1",
    background: "#eceeee", overflow: "hidden",
    position: "relative",
  },
  skeleton: {
    position: "absolute", inset: 0,
    background: "linear-gradient(110deg, #eceeee 30%, #f2f4f4 50%, #eceeee 70%)",
    backgroundSize: "200% 100%",
    animation: "shimmer 1.5s infinite",
  },
  img: {
    width: "100%", height: "100%", objectFit: "contain",
    transition: "opacity 0.3s",
  },
  noImg: {
    display: "flex", alignItems: "center", justifyContent: "center",
    height: "100%", color: "#c2c6d2", fontSize: 12,
  },
  matchBadge: {
    position: "absolute", top: 8, left: 8, zIndex: 2,
    background: "#003469", color: "#fff",
    fontSize: 10, fontWeight: 700, padding: "3px 8px", borderRadius: 4,
  },
  overlay: {
    position: "absolute", inset: 0, zIndex: 3,
    background: "rgba(0,23,54,0.15)",
    display: "flex", alignItems: "flex-end", justifyContent: "center",
    padding: 12,
  },
  overlayBtn: {
    background: "rgba(255,255,255,0.92)", backdropFilter: "blur(8px)",
    border: "none", borderRadius: 8, padding: "8px 16px",
    fontSize: 11, fontWeight: 600, cursor: "pointer",
    display: "flex", alignItems: "center", gap: 4, color: "#001736",
  },
  info: { padding: "12px 14px 14px" },
  category: {
    fontSize: 9, fontWeight: 700, letterSpacing: "0.15em",
    textTransform: "uppercase", color: "#535f70",
    display: "block", marginBottom: 4,
  },
  name: {
    fontSize: 13, fontWeight: 600, color: "#191c1d",
    lineHeight: 1.4, marginBottom: 6,
    overflow: "hidden", display: "-webkit-box",
    WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
  },
  ratingRow: {
    display: "flex", alignItems: "center", gap: 4, marginBottom: 6,
  },
  reviewCount: { fontSize: 10, color: "#43474f" },
  tags: { display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 10 },
  tag: {
    fontSize: 9, fontWeight: 500, padding: "2px 7px",
    background: "#e6e8e8", borderRadius: 3, color: "#43474f",
    textTransform: "uppercase", letterSpacing: "0.05em",
  },
  footer: { display: "flex", flexDirection: "column", gap: 8 },
  price: { fontSize: 17, fontWeight: 700, color: "#001736" },
  ctaRow: { display: "flex", gap: 6 },
  favBtn: {
    width: 36, height: 36, flexShrink: 0,
    background: "#f2f4f4", border: "none", borderRadius: 6,
    cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
    color: "#43474f", transition: "all 0.2s",
  },
  favBtnActive: {
    background: "#d4e1f5", color: "#003469",
  },
  cartBtn: {
    flex: 1, padding: "9px 0",
    background: "linear-gradient(135deg, #003469, #004b91)",
    color: "#fff", border: "none", borderRadius: 6,
    fontSize: 11, fontWeight: 700, cursor: "pointer",
    display: "flex", alignItems: "center", justifyContent: "center",
    letterSpacing: "0.03em", transition: "opacity 0.2s",
  },
  cartBtnAdded: {
    background: "#1a6b6a",
  },
};

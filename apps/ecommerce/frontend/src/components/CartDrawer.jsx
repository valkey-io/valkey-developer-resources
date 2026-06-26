import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { formatProductType } from "../utils";

const API = "/api";

export default function CartDrawer({ open, onClose, onCartCountChange }) {
  const [items, setItems] = useState([]);
  const [bundle, setBundle] = useState([]);
  const [loading, setLoading] = useState(false);
  const [checkedOut, setCheckedOut] = useState(false);
  const [checkoutTotal, setCheckoutTotal] = useState(0);

  // sample numbers
  const SHIPPING_PERCENTAGE = 0.05;
  const TAX_PERCENTAGE = 0.0815;

  useEffect(() => {
    if (open) {
      loadCart();
    }
  }, [open]);

  const loadCart = async () => {
    setLoading(true);
    try {
      const [cartRes, bundleRes] = await Promise.all([
        fetch(`${API}/cart`, { credentials: "include" }),
        fetch(`${API}/cart/bundle`, { credentials: "include" }),
      ]);
      const cartData = await cartRes.json();
      const bundleData = await bundleRes.json();
      setItems(cartData.items || []);
      setBundle(bundleData.products || []);
      onCartCountChange?.((cartData.items || []).reduce((s, i) => s + (i.quantity || 1), 0));
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const removeItem = async (item_id) => {
    try {
      await fetch(`${API}/cart/remove`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ item_id }),
      });
      loadCart();
    } catch (e) {
      console.error("Failed to remove item:", e);
    }
  };

  const addBundle = async (item_id) => {
    try {
      await fetch(`${API}/cart/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ item_id }),
      });
      loadCart();
    } catch (e) {
      console.error("Failed to add bundle item:", e);
    }
  };

  const subtotal = items.reduce((s, i) => s + (i.price || 0) * (i.quantity || 1), 0);
  const tax = subtotal * TAX_PERCENTAGE;
  const total = subtotal + tax;

  const handleCheckout = async () => {
    const finalTotal = total;
    try {
      await Promise.all(
        items.map((item) =>
          fetch(`${API}/cart/remove`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ item_id: item.item_id }),
          })
        )
      );
      setCheckoutTotal(finalTotal);
      setCheckedOut(true);
      setItems([]);
      setBundle([]);
      onCartCountChange?.(0);
    } catch (e) {
      console.error("Checkout failed:", e);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            style={styles.backdrop}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          {/* Drawer */}
          <motion.div
            style={styles.drawer}
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
          >
            {/* Header */}
            <div style={styles.header}>
              <h2 style={styles.title}>Your Cart</h2>
              <button style={styles.closeBtn} onClick={onClose}>
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            <div style={styles.body}>
              {loading ? (
                <div style={styles.loading}>Loading...</div>
              ) : items.length === 0 ? (
                <div style={styles.empty}>
                  <span className="material-symbols-outlined" style={{ fontSize: 48, color: "#c2c6d2" }}>shopping_bag</span>
                  <p style={{ color: "#43474f", marginTop: 12 }}>Your cart is empty.</p>
                </div>
              ) : (
                <>
                  {/* Cart items */}
                  <div style={styles.itemList}>
                    {items.map((item) => (
                      <div key={item.item_id} style={styles.cartItem}>
                        <div style={styles.itemImg}>
                          {item.image_url && (
                            <img src={item.image_url} alt={item.item_name} style={styles.img} />
                          )}
                        </div>
                        <div style={styles.itemInfo}>
                          <span style={styles.itemCategory}>{formatProductType(item.product_type)}</span>
                          <p style={styles.itemName}>{item.item_name}</p>
                          {item.color && <p style={styles.itemMeta}>{item.color}</p>}
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
                            <span style={styles.itemPrice}>${item.price?.toFixed(2)}</span>
                            <button style={styles.removeBtn} onClick={() => removeItem(item.item_id)}>
                              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>delete</span>
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Bundle section */}
                  {bundle.length > 0 && (
                    <div style={styles.bundleSection}>
                      <div style={styles.bundleHeader}>
                        <span className="material-symbols-outlined" style={{ color: "#8a5100", fontSize: 18, fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
                        <h3 style={styles.bundleTitle}>Frequently bought together</h3>
                      </div>
                      <div style={styles.bundleGrid}>
                        {bundle.slice(0, 3).map((p) => (
                          <div key={p.item_id} style={styles.bundleCard}>
                            <div style={styles.bundleImg}>
                              {p.image_url && <img src={p.image_url} alt={p.item_name} style={{ width: "100%", height: "100%", objectFit: "contain" }} />}
                            </div>
                            <p style={styles.bundleName}>{p.item_name?.slice(0, 40)}</p>
                            <p style={styles.bundlePrice}>${p.price?.toFixed(2)}</p>
                            <button style={styles.bundleAddBtn} onClick={() => addBundle(p.item_id)}>
                              Add
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Order summary */}
                  <div style={styles.summary}>
                    <div style={styles.summaryRow}>
                      <span style={styles.summaryLabel}>Subtotal</span>
                      <span style={styles.summaryVal}>${subtotal.toFixed(2)}</span>
                    </div>
                    <div style={styles.summaryRow}>
                      <span style={styles.summaryLabel}>Shipping</span>
                      <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ textDecoration: "line-through", color: "#999", fontSize: 12 }}>${(subtotal * SHIPPING_PERCENTAGE).toFixed(2)}</span>
                        <span style={{ ...styles.summaryVal, color: "#8a5100" }}>FREE</span>
                      </span>
                    </div>
                    <div style={styles.summaryRow}>
                      <span style={styles.summaryLabel}>Estimated Tax</span>
                      <span style={styles.summaryVal}>${tax.toFixed(2)}</span>
                    </div>
                    <div style={styles.divider} />
                    <div style={styles.summaryRow}>
                      <span style={{ fontWeight: 700, fontSize: 14 }}>Total</span>
                      <span style={{ fontWeight: 900, fontSize: 20, color: "#001736" }}>${total.toFixed(2)}</span>
                    </div>
                    <button style={styles.checkoutBtn} onClick={handleCheckout}>
                      Proceed to Checkout
                      <span className="material-symbols-outlined" style={{ fontSize: 18 }}>arrow_forward</span>
                    </button>
                    <div style={styles.trustBadges}>
                      <div style={styles.trustRow}>
                        <span className="material-symbols-outlined" style={{ fontSize: 14, color: "#8a5100" }}>verified_user</span>
                        <span>Secure encrypted checkout</span>
                      </div>
                      <div style={styles.trustRow}>
                        <span className="material-symbols-outlined" style={{ fontSize: 14, color: "#8a5100" }}>local_shipping</span>
                        <span>Same-day delivery included</span>
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Checkout success overlay */}
            <AnimatePresence>
              {checkedOut && (
                <motion.div
                  style={styles.successOverlay}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  <motion.div
                    style={styles.successCard}
                    initial={{ scale: 0.7, opacity: 0, y: 40 }}
                    animate={{ scale: 1, opacity: 1, y: 0 }}
                    exit={{ scale: 0.8, opacity: 0, y: 20 }}
                    transition={{ type: "spring", stiffness: 400, damping: 22, delay: 0.05 }}
                  >
                    <motion.div
                      style={styles.successIcon}
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ type: "spring", stiffness: 500, damping: 18, delay: 0.2 }}
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 40, color: "#fff", fontVariationSettings: "'FILL' 1" }}>check_circle</span>
                    </motion.div>
                    <motion.p
                      style={styles.successLabel}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.3 }}
                    >
                      Order placed!
                    </motion.p>
                    <motion.p
                      style={styles.successAmount}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.4 }}
                    >
                      You've spent ${checkoutTotal.toFixed(2)}
                    </motion.p>
                    <motion.p
                      style={styles.successSub}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.5 }}
                    >
                      Your package will arrive in a few hours.
                    </motion.p>
                    <motion.button
                      style={styles.successBtn}
                      onClick={() => { setCheckedOut(false); onClose(); }}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.55 }}
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                    >
                      Continue Shopping
                    </motion.button>
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

const styles = {
  backdrop: {
    position: "fixed", inset: 0, background: "rgba(25,28,29,0.4)",
    zIndex: 200, backdropFilter: "blur(4px)",
  },
  drawer: {
    position: "fixed", top: 0, right: 0, bottom: 0,
    width: 480, maxWidth: "100vw",
    background: "#f8fafa", zIndex: 201,
    display: "flex", flexDirection: "column",
    boxShadow: "0 0 64px rgba(0,0,0,0.15)",
    overflow: "hidden",
  },
  header: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    padding: "24px 28px", borderBottom: "1px solid rgba(194,198,210,0.3)",
    background: "#fff",
  },
  title: { fontSize: 22, fontWeight: 900, letterSpacing: "-0.02em", color: "#001736" },
  closeBtn: {
    background: "none", border: "none", cursor: "pointer",
    color: "#43474f", padding: 4, display: "flex",
  },
  body: { flex: 1, overflowY: "auto", padding: "20px 28px" },
  loading: { textAlign: "center", padding: 48, color: "#43474f" },
  empty: { textAlign: "center", padding: 64, display: "flex", flexDirection: "column", alignItems: "center" },
  itemList: { display: "flex", flexDirection: "column", gap: 16, marginBottom: 24 },
  cartItem: {
    display: "flex", gap: 16, background: "#fff",
    padding: 16, borderRadius: 12,
    boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
  },
  itemImg: {
    width: 80, height: 80, flexShrink: 0,
    background: "#f3f3f3", borderRadius: 8, overflow: "hidden",
  },
  img: { width: "100%", height: "100%", objectFit: "contain" },
  itemInfo: { flex: 1, minWidth: 0 },
  itemCategory: {
    fontSize: 9, fontWeight: 700, letterSpacing: "0.15em",
    textTransform: "uppercase", color: "#535f70", display: "block", marginBottom: 4,
  },
  itemName: { fontSize: 13, fontWeight: 600, color: "#191c1d", lineHeight: 1.3, marginBottom: 2 },
  itemMeta: { fontSize: 11, color: "#43474f" },
  itemPrice: { fontSize: 15, fontWeight: 700, color: "#001736" },
  removeBtn: {
    background: "none", border: "none", cursor: "pointer",
    color: "#727782", display: "flex", padding: 4,
    transition: "color 0.2s",
  },
  bundleSection: {
    background: "rgba(243,243,243,0.5)", borderRadius: 16,
    padding: 20, marginBottom: 24,
    border: "1px solid rgba(0,23,54,0.05)",
  },
  bundleHeader: { display: "flex", alignItems: "center", gap: 8, marginBottom: 16 },
  bundleTitle: { fontSize: 15, fontWeight: 700, color: "#191c1d" },
  bundleGrid: { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 },
  bundleCard: {
    background: "#fff", borderRadius: 10, padding: 12,
    display: "flex", flexDirection: "column", gap: 6,
    boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
  },
  bundleImg: {
    width: "100%", aspectRatio: "1", background: "#f3f3f3",
    borderRadius: 6, overflow: "hidden",
  },
  bundleName: { fontSize: 10, fontWeight: 600, color: "#191c1d", lineHeight: 1.3 },
  bundlePrice: { fontSize: 12, fontWeight: 700, color: "#8a5100" },
  bundleAddBtn: {
    background: "#001736", color: "#fff", border: "none",
    borderRadius: 6, padding: "6px 0", fontSize: 11, fontWeight: 700,
    cursor: "pointer", transition: "opacity 0.2s",
  },
  summary: {
    background: "#fff", borderRadius: 16, padding: 24,
    boxShadow: "0 1px 8px rgba(0,0,0,0.06)",
  },
  summaryRow: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    marginBottom: 12,
  },
  summaryLabel: { fontSize: 13, color: "#43474f" },
  summaryVal: { fontSize: 13, fontWeight: 600, color: "#191c1d" },
  divider: { height: 1, background: "rgba(194,198,210,0.3)", margin: "16px 0" },
  checkoutBtn: {
    width: "100%", padding: "18px 0",
    background: "#001736", color: "#fff",
    border: "none", borderRadius: 12, cursor: "pointer",
    fontSize: 14, fontWeight: 900, letterSpacing: "0.05em",
    display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
    marginTop: 20, marginBottom: 16,
    boxShadow: "0 8px 24px rgba(0,23,54,0.25)",
    transition: "transform 0.15s",
  },
  trustBadges: { display: "flex", flexDirection: "column", gap: 8 },
  trustRow: {
    display: "flex", alignItems: "center", gap: 8,
    fontSize: 11, color: "#43474f",
  },
  successOverlay: {
    position: "absolute", inset: 0, zIndex: 10,
    background: "rgba(0, 23, 54, 0.35)",
    backdropFilter: "blur(6px)",
    display: "flex", alignItems: "center", justifyContent: "center",
    padding: 32,
  },
  successCard: {
    background: "linear-gradient(145deg, #1a7a4a, #22a05a)",
    borderRadius: 20, padding: "48px 40px",
    display: "flex", flexDirection: "column", alignItems: "center",
    textAlign: "center", width: "100%", maxWidth: 360,
    boxShadow: "0 24px 64px rgba(0,0,0,0.25)",
  },
  successIcon: {
    width: 72, height: 72, borderRadius: "50%",
    background: "rgba(255,255,255,0.2)",
    display: "flex", alignItems: "center", justifyContent: "center",
    marginBottom: 24,
  },
  successLabel: {
    fontSize: 13, fontWeight: 700, letterSpacing: "0.15em",
    textTransform: "uppercase", color: "rgba(255,255,255,0.75)",
    marginBottom: 8,
  },
  successAmount: {
    fontSize: 36, fontWeight: 900, color: "#fff",
    letterSpacing: "-0.02em", marginBottom: 10,
  },
  successSub: {
    fontSize: 14, color: "rgba(255,255,255,0.7)",
    marginBottom: 36, lineHeight: 1.5,
  },
  successBtn: {
    background: "#fff", color: "#1a7a4a",
    border: "none", borderRadius: 10,
    padding: "14px 36px", fontSize: 14, fontWeight: 700,
    cursor: "pointer", letterSpacing: "0.02em",
  },
};

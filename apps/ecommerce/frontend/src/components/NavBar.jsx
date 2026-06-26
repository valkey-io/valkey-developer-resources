import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Logo from "./Logo";
import { SEARCH_CATEGORIES } from "../utils";

const NAV_LINKS = [
  { label: "Furniture", query: "furniture", tags: SEARCH_CATEGORIES.find((c) => c.label === "Furniture")?.tags || "" },
  { label: "Electronics", query: "electronics", tags: SEARCH_CATEGORIES.find((c) => c.label === "Electronics")?.tags || "" },
  { label: "Home & Garden", query: "home garden", tags: "HOME,PLANTER,VASE,RUG,CURTAIN,CANDLE,HOME_MIRROR,OUTDOOR_LIVING,KITCHEN,ABIS_LAWN_AND_GARDEN,TRASH_CAN" },
  { label: "Clothing", query: "clothing apparel", tags: "SHOES,HAT,BACKPACK,BOOT,SANDAL,HANDBAG,ACCESSORY,WALLET,LUGGAGE,SUITCASE,EYEWEAR" },
  { label: "Sports", query: "sports", tags: SEARCH_CATEGORIES.find((c) => c.label === "Sports")?.tags || "" },
];

export default function NavBar({ cartCount, onCartOpen, onSearch, onHome, favouritesCount, onFavouritesOpen }) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchVal, setSearchVal] = useState("");
  const [selectedCats, setSelectedCats] = useState(new Set());
  const [inputFocused, setInputFocused] = useState(false);
  const panelRef = useRef(null);
  const inputRef = useRef(null);

  // Focus input when panel opens
  useEffect(() => {
    if (searchOpen) inputRef.current?.focus();
  }, [searchOpen]);

  // Close panel on outside click
  useEffect(() => {
    if (!searchOpen) return;
    const handler = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setSearchOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [searchOpen]);

  const toggleCat = (tags) => {
    setSelectedCats((prev) => {
      const next = new Set(prev);
      if (next.has(tags)) next.delete(tags); else next.add(tags);
      return next;
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const q = searchVal.trim();
    if (!q) return;
    const cats = [...selectedCats].join(",");
    onSearch(q, cats);
    setSearchOpen(false);
    setSearchVal("");
    setSelectedCats(new Set());
  };

  return (
    <nav style={styles.nav}>
      <div style={styles.inner}>
        <Logo size="md" onClick={onHome} />

        <div style={styles.links}>
          {NAV_LINKS.map((cat) => (
            <button key={cat.label} style={styles.link} onClick={() => onSearch(cat.query, cat.tags)}>
              {cat.label}
            </button>
          ))}
        </div>

        <div style={styles.actions}>
          {/* Search toggle */}
          <button style={styles.iconBtn} onClick={() => setSearchOpen((o) => !o)}>
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>
              {searchOpen ? "close" : "search"}
            </span>
          </button>

          <button style={styles.iconBtn} onClick={onFavouritesOpen}>
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>favorite</span>
            {favouritesCount > 0 && <span style={styles.badge}>{favouritesCount}</span>}
          </button>

          <button style={styles.iconBtn} onClick={onCartOpen}>
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>shopping_bag</span>
            {cartCount > 0 && <span style={styles.badge}>{cartCount}</span>}
          </button>
        </div>
      </div>

      {/* Search panel dropdown */}
      <AnimatePresence>
        {searchOpen && (
          <motion.div
            ref={panelRef}
            style={styles.panel}
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            <form onSubmit={handleSubmit} style={styles.panelForm}>
              <div style={{ ...styles.panelInputRow, ...(inputFocused ? styles.panelInputRowFocused : {}) }}>
                <span className="material-symbols-outlined" style={{ fontSize: 20, color: "#727782" }}>search</span>
                <input
                  ref={inputRef}
                  style={styles.panelInput}
                  value={searchVal}
                  onChange={(e) => setSearchVal(e.target.value)}
                  placeholder="Describe what you're looking for..."
                  onFocus={() => setInputFocused(true)}
                  onBlur={() => setInputFocused(false)}
                />
                <button type="submit" style={styles.panelSearchBtn}>
                  Search
                </button>
              </div>
              <div style={styles.panelCatRow}>
                <span style={styles.panelCatLabel}>TAG filter by category:</span>
                <div style={styles.panelChips}>
                  {SEARCH_CATEGORIES.map((cat) => {
                    const active = selectedCats.has(cat.tags);
                    return (
                      <button
                        key={cat.tags}
                        type="button"
                        style={{ ...styles.panelChip, ...(active ? styles.panelChipActive : {}) }}
                        onClick={() => toggleCat(cat.tags)}
                      >
                        {cat.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}

const styles = {
  nav: {
    position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
    background: "rgba(255,255,255,0.85)",
    backdropFilter: "blur(20px)",
    WebkitBackdropFilter: "blur(20px)",
    borderBottom: "1px solid rgba(194,198,210,0.2)",
  },
  inner: {
    maxWidth: 1440, margin: "0 auto",
    padding: "0 32px", height: 72,
    display: "flex", alignItems: "center", justifyContent: "space-between",
    gap: 24,
  },
  links: { display: "flex", gap: 32, alignItems: "center" },
  link: {
    fontSize: 13, fontWeight: 500, color: "#43474f",
    background: "none", border: "none", cursor: "pointer",
    letterSpacing: "0.02em", transition: "color 0.2s",
  },
  actions: { display: "flex", alignItems: "center", gap: 8 },
  iconBtn: {
    position: "relative",
    background: "none", border: "none", cursor: "pointer",
    color: "#191c1d", padding: 8, borderRadius: 8,
    display: "flex", alignItems: "center", transition: "color 0.2s",
  },
  badge: {
    position: "absolute", top: 2, right: 2,
    background: "#8a5100", color: "#fff",
    fontSize: 9, fontWeight: 700,
    width: 16, height: 16, borderRadius: "50%",
    display: "flex", alignItems: "center", justifyContent: "center",
  },
  panel: {
    position: "absolute", top: 72, left: 0, right: 0,
    background: "#fff",
    borderBottom: "1px solid rgba(194,198,210,0.3)",
    boxShadow: "0 12px 32px rgba(0,0,0,0.08)",
    zIndex: 99,
  },
  panelForm: {
    maxWidth: 720, margin: "0 auto",
    padding: "20px 32px 24px",
  },
  panelInputRow: {
    display: "flex", alignItems: "center", gap: 10,
    background: "#f2f4f4", borderRadius: 10,
    padding: "10px 10px 10px 16px",
    borderWidth: 1, borderStyle: "solid", borderColor: "rgba(194,198,210,0.3)",
    transition: "border-color 0.2s, box-shadow 0.2s",
  },
  panelInputRowFocused: {
    boxShadow: "0 0 0 2px rgba(0,52,105,0.2)",
  },
  panelInput: {
    flex: 1, border: "none", outline: "none",
    fontSize: 14, color: "#191c1d", fontFamily: "inherit",
    background: "none",
  },
  panelSearchBtn: {
    background: "linear-gradient(135deg, #003469, #004b91)",
    color: "#fff", border: "none", borderRadius: 6,
    padding: "10px 20px", fontSize: 13, fontWeight: 700,
    cursor: "pointer", whiteSpace: "nowrap",
  },
  panelCatRow: {
    marginTop: 14, display: "flex", alignItems: "center", gap: 12,
  },
  panelCatLabel: {
    fontSize: 10, fontWeight: 700, letterSpacing: "0.1em",
    textTransform: "uppercase", color: "#535f70",
    whiteSpace: "nowrap",
  },
  panelChips: { display: "flex", flexWrap: "wrap", gap: 6 },
  panelChip: {
    padding: "5px 12px", borderRadius: 20,
    fontSize: 11, fontWeight: 600,
    background: "#f2f4f4", color: "#43474f",
    borderWidth: 1, borderStyle: "solid", borderColor: "rgba(194,198,210,0.4)",
    cursor: "pointer", transition: "all 0.15s",
  },
  panelChipActive: {
    background: "#001736", color: "#fff",
    borderColor: "#001736",
  },
};

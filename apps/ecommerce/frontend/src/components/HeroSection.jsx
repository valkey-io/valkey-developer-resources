import { useState } from "react";
import { motion } from "framer-motion";
import { SEARCH_CATEGORIES } from "../utils";

export default function HeroSection({ onSearch }) {
  const [searchVal, setSearchVal] = useState("");
  const [selectedCats, setSelectedCats] = useState(new Set());
  const [inputFocused, setInputFocused] = useState(false);

  const toggleCat = (tags) => {
    setSelectedCats((prev) => {
      const next = new Set(prev);
      if (next.has(tags)) next.delete(tags); else next.add(tags);
      return next;
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const q = searchVal.trim() || "popular trending products";
    const cats = [...selectedCats].join(",");
    onSearch(q, cats);
  };

  return (
    <section style={styles.section}>
      <div style={styles.inner}>
        <motion.div
          style={styles.textCol}
          initial={{ opacity: 0, y: 32 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.25, 0.46, 0.45, 0.94] }}
        >
          <h1 style={styles.headline}>
            Discover<br />Everything.
          </h1>
          <p style={styles.sub}>
            Explore the Amazon Berkeley Objects collection powered by semantic search. Select categories to apply TAG filters.
          </p>

          {/* Search bar with category chips */}
          <form onSubmit={handleSubmit} style={styles.searchForm}>
            <div style={{ ...styles.inputRow, ...(inputFocused ? styles.inputRowFocused : {}) }}>
              <span className="material-symbols-outlined" style={{ fontSize: 20, color: "#727782" }}>search</span>
              <input
                style={styles.searchInput}
                value={searchVal}
                onChange={(e) => setSearchVal(e.target.value)}
                placeholder="Describe what you're looking for..."
                onFocus={() => setInputFocused(true)}
                onBlur={() => setInputFocused(false)}
              />
              <button type="submit" style={styles.searchBtn}>
                Search
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>arrow_forward</span>
              </button>
            </div>
            <div style={styles.catRow}>
              <span style={styles.catLabel}>Filter by category:</span>
              <div style={styles.chips}>
                {SEARCH_CATEGORIES.map((cat) => {
                  const active = selectedCats.has(cat.tags);
                  return (
                    <button
                      key={cat.tags}
                      type="button"
                      style={{ ...styles.chip, ...(active ? styles.chipActive : {}) }}
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

        <motion.div
          style={styles.imgCol}
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8, delay: 0.1, ease: [0.25, 0.46, 0.45, 0.94] }}
        >
          <div style={styles.imgBg} />
          <img
            src="https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=900&q=80"
            alt="Shopping products"
            style={styles.img}
          />
          <div style={styles.featureCard}>
            <span style={styles.featureLabel}>Powered by Valkey</span>
            <h3 style={styles.featureTitle}>Semantic + TAG Search</h3>
            <p style={styles.featureDesc}>Combine natural language with category TAG filters for precise results.</p>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

const styles = {
  section: {
    minHeight: "calc(100vh - 72px)",
    display: "flex", alignItems: "center",
    padding: "80px 32px 60px",
    overflow: "hidden",
  },
  inner: {
    maxWidth: 1440, margin: "0 auto", width: "100%",
    display: "grid", gridTemplateColumns: "5fr 7fr",
    gap: 48, alignItems: "center",
  },
  textCol: { zIndex: 1 },
  headline: {
    fontSize: "clamp(56px, 8vw, 96px)",
    fontWeight: 900, letterSpacing: "-0.03em",
    color: "#001736", lineHeight: 1,
    marginBottom: 24,
  },
  sub: {
    fontSize: 17, color: "#43474f", lineHeight: 1.6,
    maxWidth: 420, marginBottom: 32,
  },
  searchForm: {
    maxWidth: 480,
  },
  inputRow: {
    display: "flex", alignItems: "center", gap: 10,
    background: "#fff", borderRadius: 10,
    padding: "10px 10px 10px 16px",
    boxShadow: "0 4px 20px rgba(0,0,0,0.08)",
    borderWidth: 1, borderStyle: "solid", borderColor: "rgba(194,198,210,0.3)",
    transition: "border-color 0.2s, box-shadow 0.2s",
  },
  inputRowFocused: {
    boxShadow: "0 4px 20px rgba(0,0,0,0.08), 0 0 0 2px rgba(0,52,105,0.2)",
  },
  searchInput: {
    flex: 1, border: "none", outline: "none",
    fontSize: 14, color: "#191c1d", fontFamily: "inherit",
    background: "none",
  },
  searchBtn: {
    display: "flex", alignItems: "center", gap: 6,
    background: "linear-gradient(135deg, #003469, #004b91)",
    color: "#fff", border: "none", borderRadius: 6,
    padding: "10px 20px", fontSize: 13, fontWeight: 700,
    cursor: "pointer", whiteSpace: "nowrap",
    transition: "opacity 0.2s",
  },
  catRow: {
    marginTop: 14, display: "flex", flexDirection: "column", gap: 8,
  },
  catLabel: {
    fontSize: 10, fontWeight: 700, letterSpacing: "0.12em",
    textTransform: "uppercase", color: "#535f70",
  },
  chips: {
    display: "flex", flexWrap: "wrap", gap: 6,
  },
  chip: {
    padding: "6px 14px", borderRadius: 20,
    fontSize: 12, fontWeight: 600,
    background: "#fff", color: "#43474f",
    borderWidth: 1, borderStyle: "solid", borderColor: "rgba(194,198,210,0.5)",
    cursor: "pointer", transition: "all 0.15s",
  },
  chipActive: {
    background: "#001736", color: "#fff",
    borderColor: "#001736",
  },
  imgCol: {
    position: "relative", height: 600,
  },
  imgBg: {
    position: "absolute", inset: 0,
    background: "#eceeee", borderRadius: 16,
    transform: "rotate(-2deg) scale(1.05)",
  },
  img: {
    position: "absolute", inset: 0,
    width: "100%", height: "100%",
    objectFit: "cover", borderRadius: 16,
    transform: "translate(12px, 12px)",
    boxShadow: "0 24px 64px rgba(0,0,0,0.15)",
    zIndex: 1,
  },
  featureCard: {
    position: "absolute", bottom: -32, left: -32,
    background: "#fff", padding: 24, borderRadius: 12,
    boxShadow: "0 12px 32px rgba(25,28,29,0.08)",
    borderLeft: "4px solid #003469",
    zIndex: 2, maxWidth: 260,
  },
  featureLabel: {
    fontSize: 10, fontWeight: 700, letterSpacing: "0.15em",
    textTransform: "uppercase", color: "#535f70",
    display: "block", marginBottom: 6,
  },
  featureTitle: {
    fontSize: 16, fontWeight: 700, color: "#001736", marginBottom: 4,
  },
  featureDesc: { fontSize: 12, color: "#43474f", lineHeight: 1.5 },
};

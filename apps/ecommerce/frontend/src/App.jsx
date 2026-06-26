import { useState, useCallback, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import NavBar from "./components/NavBar";
import HeroSection from "./components/HeroSection";
import SearchResults from "./components/SearchResults";
import ProductCard from "./components/ProductCard";
import CartDrawer from "./components/CartDrawer";
import ProductDetailModal from "./components/ProductDetailModal";
import FavouritesPage from "./components/FavouritesPage";
import Footer from "./components/Footer";

const API = "/api";
const PAGE_SIZE = 60;

export default function App() {
  const [view, setView] = useState("home"); // home | search | similar | favourites
  const [query, setQuery] = useState("");
  const [allResults, setAllResults] = useState([]); // full unfiltered result set
  const [facets, setFacets] = useState([]);
  const [colorFacets, setColorFacets] = useState([]);
  const [materialFacets, setMaterialFacets] = useState([]);
  const [featured, setFeatured] = useState([]);
  const [searching, setSearching] = useState(false);
  const [activeProductType, setActiveProductType] = useState("");
  const [activeColor, setActiveColor] = useState("");
  const [activeMaterial, setActiveMaterial] = useState("");
  const [favouriteIds, setFavouriteIds] = useState(new Set());
  const [cartCount, setCartCount] = useState(0);
  const [cartOpen, setCartOpen] = useState(false);
  const [detailItemId, setDetailItemId] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [errorMsg, setErrorMsg] = useState(null);

  const showError = useCallback((msg) => {
    setErrorMsg(msg);
    setTimeout(() => setErrorMsg(null), 4000);
  }, []);

  // Pagination — apply sidebar filters client-side on the KNN result set
  // so filtering narrows the original results rather than re-querying.
  // Server-side TAG filtering is still used in the initial KNN query
  // (see /api/search and /api/similar endpoints).
  const filteredResults = useMemo(() => {
    let items = allResults;
    if (activeProductType) {
      const types = new Set(activeProductType.split(",").map((s) => s.trim()));
      items = items.filter((p) => types.has(p.product_type));
    }
    if (activeColor) {
      const colors = new Set(activeColor.split(",").map((s) => s.trim()));
      items = items.filter((p) => colors.has(p.color));
    }
    if (activeMaterial) {
      const materials = new Set(activeMaterial.split(",").map((s) => s.trim()));
      items = items.filter((p) => materials.has(p.material));
    }
    return items;
  }, [allResults, activeProductType, activeColor, activeMaterial]);

  const totalPages = Math.max(1, Math.ceil(filteredResults.length / PAGE_SIZE));
  const paginatedResults = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filteredResults.slice(start, start + PAGE_SIZE);
  }, [filteredResults, currentPage]);

  // Reset to page 1 when sidebar filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [activeProductType, activeColor, activeMaterial]);

  // Load featured products on mount
  useEffect(() => {
    fetch(`${API}/featured`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setFeatured(d.products || []))
      .catch(() => showError("Failed to load featured products"));
    // Load cart count
    fetch(`${API}/cart`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setCartCount((d.items || []).reduce((s, i) => s + (i.quantity || 1), 0)))
      .catch(() => showError("Failed to load cart"));
    // Load favourites
    fetch(`${API}/favourites`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const ids = (d.items || []).map((i) => i.item_id).filter(Boolean);
        if (ids.length) setFavouriteIds(new Set(ids));
      })
      .catch(() => showError("Failed to load favourites"));
  }, [showError]);

  // Scroll to top on view change
  useEffect(() => { window.scrollTo(0, 0); }, [view]);

  const doSearch = useCallback(async (q, categories = "") => {
    setSearching(true);
    setQuery(q);
    setView("search");
    setActiveProductType("");
    setActiveColor("");
    setActiveMaterial("");
    setCurrentPage(1);
    try {
      const params = new URLSearchParams({ q });
      if (categories) params.set("product_type", categories);
      const res = await fetch(`${API}/search?${params}`, { credentials: "include" });
      const data = await res.json();
      setAllResults(data.products || []);
      setFacets(data.facets || []);
      setColorFacets(data.color_facets || []);
      setMaterialFacets(data.material_facets || []);
    } catch (e) {
      showError("Search failed. Please try again.");
      console.error(e);
    } finally {
      setSearching(false);
    }
  }, []);

  const handleProductTypeToggle = useCallback((name) => {
    if (!name) { setActiveProductType(""); setCurrentPage(1); return; }
    const current = new Set(activeProductType ? activeProductType.split(",").map((s) => s.trim()) : []);
    if (current.has(name)) current.delete(name); else current.add(name);
    setActiveProductType([...current].join(","));
    setCurrentPage(1);
  }, [activeProductType]);

  const handleColorToggle = useCallback((name) => {
    if (!name) { setActiveColor(""); setCurrentPage(1); return; }
    const current = new Set(activeColor ? activeColor.split(",").map((s) => s.trim()) : []);
    if (current.has(name)) current.delete(name); else current.add(name);
    setActiveColor([...current].join(","));
    setCurrentPage(1);
  }, [activeColor]);

  const handleMaterialToggle = useCallback((name) => {
    if (!name) { setActiveMaterial(""); setCurrentPage(1); return; }
    const current = new Set(activeMaterial ? activeMaterial.split(",").map((s) => s.trim()) : []);
    if (current.has(name)) current.delete(name); else current.add(name);
    setActiveMaterial([...current].join(","));
    setCurrentPage(1);
  }, [activeMaterial]);

  const handleClearAllFilters = useCallback(() => {
    setActiveProductType("");
    setActiveColor("");
    setActiveMaterial("");
    setCurrentPage(1);
  }, []);

  const handleMoreLikeThis = useCallback(async (itemId, itemName) => {
    setSearching(true);
    setView("similar");
    setQuery(`Similar to: ${itemName}`);
    setActiveProductType("");
    setActiveColor("");
    setActiveMaterial("");
    setCurrentPage(1);
    try {
      const res = await fetch(`${API}/similar/${itemId}?limit=200`, { credentials: "include" });
      const data = await res.json();
      setAllResults(data.products || []);
      setFacets(data.facets || []);
      setColorFacets(data.color_facets || []);
      setMaterialFacets(data.material_facets || []);
    } catch (e) {
      showError("Failed to load similar products.");
      console.error(e);
    } finally {
      setSearching(false);
    }
  }, []);

  const handleAddToCart = useCallback(async (itemId) => {
    try {
      await fetch(`${API}/cart/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ item_id: itemId }),
      });
      setCartCount((c) => c + 1);
    } catch {
      showError("Failed to add item to cart.");
    }
  }, []);

  const handleAddToFavourites = useCallback(async (itemId) => {
    try {
      await fetch(`${API}/favourites/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ item_id: itemId }),
      });
      setFavouriteIds((prev) => new Set([...prev, itemId]));
    } catch {
      showError("Failed to add to favourites.");
    }
  }, []);

  const handleRemoveFromFavourites = useCallback(async (itemId) => {
    try {
      await fetch(`${API}/favourites/remove`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ item_id: itemId }),
      });
      setFavouriteIds((prev) => {
        const next = new Set(prev);
        next.delete(itemId);
        return next;
      });
    } catch {
      showError("Failed to remove from favourites.");
    }
  }, []);

  return (
    <div style={{ minHeight: "100vh", background: "#f8fafa" }}>
      <NavBar
        cartCount={cartCount}
        onCartOpen={() => setCartOpen(true)}
        onSearch={doSearch}
        onHome={() => setView("home")}
        favouritesCount={favouriteIds.size}
        onFavouritesOpen={() => setView("favourites")}
      />

      <main style={{ paddingTop: 72 }}>
        <AnimatePresence mode="wait">
          {view === "home" && (
            <motion.div
              key="home"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
            >
              <HeroSection onSearch={doSearch} />

              {/* Featured Products */}
              {featured.length > 0 && (
                <section style={styles.featuredSection}>
                  <div style={styles.sectionInner}>
                    <div style={styles.sectionHeader}>
                      <div>
                        <h2 style={styles.sectionTitle}>Inspired by your trends</h2>
                        <p style={styles.sectionSub}>Objects curated based on recent architectural interests.</p>
                      </div>
                    </div>
                    <div className="hide-scrollbar" style={styles.carousel}>
                      {featured.map((p) => (
                        <div key={p.item_id} style={styles.carouselItem} onClick={() => setDetailItemId(p.item_id)}>
                          <ProductCard
                            product={p}
                            onAddToCart={handleAddToCart}
                            onMoreLikeThis={handleMoreLikeThis}
                            onAddToFavourites={handleAddToFavourites}
                            onRemoveFromFavourites={handleRemoveFromFavourites}
                            isFavourited={favouriteIds.has(p.item_id)}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                </section>
              )}

              {/* Bundle CTA */}
              <section style={styles.bundleCta}>
                <div style={styles.bundleCtaInner}>
                  <div style={styles.bundleCtaImg}>
                    <img
                      src="https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=800&q=80"
                      alt="Product bundle"
                      style={{ width: "100%", height: "100%", objectFit: "cover", mixBlendMode: "overlay" }}
                    />
                  </div>
                  <div style={styles.bundleCtaText}>
                    <span style={styles.bundleCtaLabel}>Bundle &amp; Save</span>
                    <h2 style={styles.bundleCtaTitle}>Complete the Study Room</h2>
                    <p style={styles.bundleCtaSub}>Curate your entire workspace in one click. Our design team has harmonized these core elements for peak productivity.</p>
                    <button style={styles.bundleCtaBtn} onClick={() => doSearch("office desk chair lamp")}>
                      Shop the Bundle
                    </button>
                  </div>
                </div>
              </section>

              {/* Related grid */}
              {featured.length > 4 && (
                <section style={styles.relatedSection}>
                  <div style={styles.sectionInner}>
                    <h2 style={styles.sectionTitle}>Featured Items:</h2>
                    <div style={styles.relatedGrid}>
                      {featured.slice(4).map((p) => (
                        <div
                          key={p.item_id}
                          style={styles.relatedCard}
                          onClick={() => setDetailItemId(p.item_id)}
                        >
                          <img
                            src={p.image_url}
                            alt={p.item_name}
                            style={styles.relatedImg}
                          />
                          <h4 style={styles.relatedName}>{p.item_name?.slice(0, 40)}</h4>
                          <p style={styles.relatedPrice}>${p.price?.toFixed(2)}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>
              )}
            </motion.div>
          )}

          {(view === "search" || view === "similar") && (
            <motion.div
              key="search"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
            >
              {searching ? (
                <div style={styles.searchingState}>
                  <motion.div
                    animate={{ opacity: [0.4, 1, 0.4] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                    style={{ fontSize: 14, color: "#43474f" }}
                  >
                    Searching...
                  </motion.div>
                </div>
              ) : (
                <SearchResults
                  query={query}
                  results={paginatedResults}
                  filtering={false}
                  facets={facets}
                  colorFacets={colorFacets}
                  materialFacets={materialFacets}
                  activeProductType={activeProductType}
                  activeColor={activeColor}
                  activeMaterial={activeMaterial}
                  onProductTypeToggle={handleProductTypeToggle}
                  onColorToggle={handleColorToggle}
                  onMaterialToggle={handleMaterialToggle}
                  onClearAllFilters={handleClearAllFilters}
                  onAddToCart={handleAddToCart}
                  onMoreLikeThis={handleMoreLikeThis}
                  onAddToFavourites={handleAddToFavourites}
                  onRemoveFromFavourites={handleRemoveFromFavourites}
                  favouriteIds={favouriteIds}
                  onProductClick={setDetailItemId}
                  totalCount={filteredResults.length}
                  currentPage={currentPage}
                  totalPages={totalPages}
                  onPageChange={(page) => { setCurrentPage(page); window.scrollTo(0, 0); }}
                  onHome={() => setView("home")}
                />
              )}
            </motion.div>
          )}

          {view === "favourites" && (
            <motion.div
              key="favourites"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
            >
              <FavouritesPage
                favouriteIds={favouriteIds}
                onAddToCart={handleAddToCart}
                onMoreLikeThis={handleMoreLikeThis}
                onAddToFavourites={handleAddToFavourites}
                onRemoveFromFavourites={handleRemoveFromFavourites}
                onProductClick={setDetailItemId}
                onHome={() => setView("home")}
                onError={showError}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <Footer />

      {/* Cart Drawer */}
      <CartDrawer
        open={cartOpen}
        onClose={() => setCartOpen(false)}
        onCartCountChange={setCartCount}
      />

      {/* Product Detail Modal */}
      <ProductDetailModal
        itemId={detailItemId}
        onClose={() => setDetailItemId(null)}
        onAddToCart={handleAddToCart}
        onMoreLikeThis={(id, name) => { setDetailItemId(null); handleMoreLikeThis(id, name); }}
      />

      {/* Error Toast */}
      <AnimatePresence>
        {errorMsg && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.25 }}
            style={styles.errorToast}
            onClick={() => setErrorMsg(null)}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>error</span>
            {errorMsg}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

const styles = {
  featuredSection: {
    background: "#f2f4f4", padding: "80px 0",
  },
  sectionInner: { maxWidth: 1440, margin: "0 auto", padding: "0 32px" },
  sectionHeader: {
    display: "flex", justifyContent: "space-between",
    alignItems: "flex-end", marginBottom: 40,
  },
  sectionTitle: {
    fontSize: 28, fontWeight: 700, letterSpacing: "-0.02em", color: "#001736",
  },
  sectionSub: { fontSize: 14, color: "#43474f", marginTop: 6 },
  carousel: {
    display: "flex", gap: 24, overflowX: "auto",
    paddingBottom: 16, margin: "0 -8px", padding: "0 8px 16px",
  },
  carouselItem: { minWidth: 280, cursor: "pointer" },
  bundleCta: {
    background: "#001736", color: "#fff",
    padding: "80px 32px",
  },
  bundleCtaInner: {
    maxWidth: 1440, margin: "0 auto",
    display: "grid", gridTemplateColumns: "1fr 1fr",
    gap: 64, alignItems: "center",
  },
  bundleCtaImg: {
    aspectRatio: "1", background: "rgba(255,255,255,0.1)",
    overflow: "hidden", borderRadius: 4,
  },
  bundleCtaText: {},
  bundleCtaLabel: {
    fontSize: 11, fontWeight: 700, letterSpacing: "0.2em",
    textTransform: "uppercase", color: "#ffb86f",
    display: "block", marginBottom: 16,
  },
  bundleCtaTitle: {
    fontSize: "clamp(32px, 4vw, 56px)", fontWeight: 700,
    lineHeight: 1.1, marginBottom: 20,
  },
  bundleCtaSub: {
    fontSize: 16, color: "rgba(255,255,255,0.7)",
    lineHeight: 1.6, marginBottom: 36,
  },
  bundleCtaBtn: {
    background: "#fff", color: "#001736",
    border: "none", borderRadius: 6,
    padding: "16px 36px", fontSize: 14, fontWeight: 700,
    cursor: "pointer", transition: "background 0.2s",
  },
  relatedSection: { padding: "80px 0" },
  relatedGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
    gap: 1, background: "rgba(194,198,210,0.15)",
  },
  relatedCard: {
    background: "#fff", padding: 20,
    cursor: "pointer", transition: "background 0.2s",
  },
  relatedImg: { width: "100%", aspectRatio: "1", objectFit: "contain", marginBottom: 12 },
  relatedName: { fontSize: 13, fontWeight: 600, color: "#001736", marginBottom: 6, lineHeight: 1.3 },
  relatedPrice: { fontSize: 14, fontWeight: 700, color: "#191c1d" },
  searchingState: {
    display: "flex", alignItems: "center", justifyContent: "center",
    minHeight: "60vh",
  },
  errorToast: {
    position: "fixed", top: 16, left: "50%", transform: "translateX(-50%)",
    zIndex: 500, background: "#5c1a1a", color: "#fdd", borderRadius: 10,
    padding: "12px 24px", fontSize: 13, fontWeight: 600,
    display: "flex", alignItems: "center", gap: 8, cursor: "pointer",
    boxShadow: "0 8px 24px rgba(92,26,26,0.35)",
  },
};

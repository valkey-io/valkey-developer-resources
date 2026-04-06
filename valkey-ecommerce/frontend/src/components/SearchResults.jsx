import { useMemo, useState } from "react";
import ProductCard from "./ProductCard";
import { formatProductType } from "../utils";

function SidebarFilter({ title, items, activeSet, onToggle, formatFn }) {
  return (
    <div style={styles.filterGroup}>
      <h3 style={styles.filterTitle}>{title}</h3>
      <div style={styles.filterItems}>
        {items.slice(0, 8).map((item) => {
          const name = typeof item === "string" ? item : item.name;
          const count = typeof item === "object" ? item.count : null;
          const active = activeSet.has(name);
          return (
            <label key={name} style={styles.filterLabel}>
              <input
                type="checkbox"
                checked={active}
                onChange={() => onToggle(name)}
                style={styles.checkbox}
              />
              <span style={{ ...styles.filterText, ...(active ? styles.filterTextActive : {}) }}>
                {formatFn ? formatFn(name) : name}
              </span>
              {count != null && <span style={styles.filterCount}>{count}</span>}
            </label>
          );
        })}
      </div>
    </div>
  );
}

export default function SearchResults({
  query, results, filtering, facets, colorFacets, materialFacets,
  activeProductType, activeColor, activeMaterial,
  onProductTypeToggle, onColorToggle, onMaterialToggle, onClearAllFilters,
  onAddToCart, onMoreLikeThis, onAddToFavourites, onRemoveFromFavourites, favouriteIds,
  onProductClick, totalCount, currentPage, totalPages, onPageChange, onHome,
}) {
  const activeTypes = new Set(activeProductType ? activeProductType.split(",").map((s) => s.trim()) : []);
  const activeColors = new Set(activeColor ? activeColor.split(",").map((s) => s.trim()) : []);
  const activeMaterials = new Set(activeMaterial ? activeMaterial.split(",").map((s) => s.trim()) : []);
  const filterKey = useMemo(() => `${activeProductType}|${activeColor}|${activeMaterial}`, [activeProductType, activeColor, activeMaterial]);

  return (
    <div style={styles.wrapper}>
      <div style={styles.breadcrumb}>
        <span style={styles.breadcrumbLink} onClick={onHome} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && onHome()}>Home</span>
        <span style={styles.sep}>/</span>
        <span style={styles.breadcrumbCurrent}>Search Results</span>
      </div>

      <div style={styles.titleRow}>
        <div style={styles.titleLeft}>
          <h1 style={styles.title}>"{query}"</h1>
          {totalCount != null && (
            <span style={styles.resultCount}>({totalCount} results)</span>
          )}
        </div>
      </div>

      <div style={styles.layout}>
        <aside style={styles.sidebar}>
          {facets.length > 0 && (
            <SidebarFilter
              title="Category"
              items={facets}
              activeSet={activeTypes}
              onToggle={onProductTypeToggle}
              formatFn={formatProductType}
            />
          )}
          {colorFacets.length > 0 && (
            <SidebarFilter
              title="Color"
              items={colorFacets}
              activeSet={activeColors}
              onToggle={onColorToggle}
            />
          )}
          {materialFacets.length > 0 && (
            <SidebarFilter
              title="Material"
              items={materialFacets}
              activeSet={activeMaterials}
              onToggle={onMaterialToggle}
            />
          )}
          {(activeTypes.size > 0 || activeColors.size > 0 || activeMaterials.size > 0) && (
            <button
              style={styles.clearFilters}
              onClick={() => { onClearAllFilters(); }}
            >
              Clear all filters
            </button>
          )}
        </aside>

        <div style={{ ...styles.gridArea, opacity: filtering ? 0.4 : 1, transition: "opacity 0.2s ease" }}>
          <div>
          {results.length === 0 && !filtering ? (
            <div style={styles.empty}>No results found. Try a different search.</div>
          ) : (
            <div key={filterKey} className="grid-fade-in" style={styles.grid}>
                {results.map((p) => (
                  <div key={p.item_id} onClick={() => onProductClick?.(p.item_id)} style={{ cursor: "pointer" }}>
                    <ProductCard
                      product={p}
                      onAddToCart={(id) => { onAddToCart(id); }}
                      onMoreLikeThis={onMoreLikeThis}
                      onAddToFavourites={onAddToFavourites}
                      onRemoveFromFavourites={onRemoveFromFavourites}
                      isFavourited={favouriteIds?.has(p.item_id)}
                    />
                  </div>
                ))}
            </div>
          )}

          {results.length > 0 && totalPages > 1 && (
            <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={onPageChange} />
          )}

          {results.length > 0 && (
            <CompleteTheOrder results={results} onAddToCart={onAddToCart} onProductClick={onProductClick} />
          )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Pagination({ currentPage, totalPages, onPageChange }) {
  // Show a window of page numbers around the current page
  const pages = [];
  const maxVisible = 7;
  let start = Math.max(1, currentPage - Math.floor(maxVisible / 2));
  let end = Math.min(totalPages, start + maxVisible - 1);
  if (end - start + 1 < maxVisible) start = Math.max(1, end - maxVisible + 1);

  for (let i = start; i <= end; i++) pages.push(i);

  return (
    <nav style={styles.pagination} aria-label="Search results pagination">
      <button
        style={{ ...styles.pageBtn, ...(currentPage === 1 ? styles.pageBtnDisabled : {}) }}
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        aria-label="Previous page"
      >
        ‹ Prev
      </button>
      {start > 1 && (
        <>
          <button style={styles.pageBtn} onClick={() => onPageChange(1)}>1</button>
          {start > 2 && <span style={styles.pageEllipsis}>…</span>}
        </>
      )}
      {pages.map((p) => (
        <button
          key={p}
          style={{ ...styles.pageBtn, ...(p === currentPage ? styles.pageBtnActive : {}) }}
          onClick={() => onPageChange(p)}
          aria-current={p === currentPage ? "page" : undefined}
        >
          {p}
        </button>
      ))}
      {end < totalPages && (
        <>
          {end < totalPages - 1 && <span style={styles.pageEllipsis}>…</span>}
          <button style={styles.pageBtn} onClick={() => onPageChange(totalPages)}>{totalPages}</button>
        </>
      )}
      <button
        style={{ ...styles.pageBtn, ...(currentPage === totalPages ? styles.pageBtnDisabled : {}) }}
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        aria-label="Next page"
      >
        Next ›
      </button>
    </nav>
  );
}

function CompleteTheOrderCard({ p, onAddToCart, onProductClick }) {
  const [added, setAdded] = useState(false);

  const handleAdd = (e) => {
    e.stopPropagation();
    onAddToCart(p.item_id);
    setAdded(true);
    setTimeout(() => setAdded(false), 2000);
  };

  return (
    <div key={p.item_id} style={styles.completeCard} onClick={() => onProductClick?.(p.item_id)}>
      <div style={styles.completeImg}>
        {p.image_url && <img src={p.image_url} alt={p.item_name} style={{ width: "100%", height: "100%", objectFit: "contain" }} />}
      </div>
      <p style={styles.completeName}>{p.item_name?.slice(0, 40)}</p>
      <p style={styles.completePrice}>${p.price?.toFixed(2)}</p>
      <button
        style={{ ...styles.completeAddBtn, ...(added ? styles.completeAddBtnAdded : {}) }}
        onClick={handleAdd}
      >
        {added ? "Added!" : "Add to Cart"}
      </button>
    </div>
  );
}

function CompleteTheOrder({ results, onAddToCart, onProductClick }) {
  const seen = new Set();
  const complementary = results.filter((p) => {
    const pt = p.product_type;
    if (!pt || seen.has(pt)) return false;
    seen.add(pt);
    return true;
  }).slice(0, 4);

  if (complementary.length < 2) return null;

  return (
    <div style={styles.completeSection}>
      <div style={styles.completeSectionHeader}>
        <div>
          <h2 style={styles.completeSectionTitle}>Complete the Order</h2>
          <p style={styles.completeSectionSub}>Accessories often purchased together.</p>
        </div>
      </div>
      <div style={styles.completeGrid}>
        {complementary.map((p) => (
          <CompleteTheOrderCard key={p.item_id} p={p} onAddToCart={onAddToCart} onProductClick={onProductClick} />
        ))}
      </div>
    </div>
  );
}

const styles = {
  wrapper: { maxWidth: 1440, margin: "0 auto", padding: "32px 32px 80px" },
  breadcrumb: { display: "flex", gap: 8, fontSize: 11, color: "#43474f", marginBottom: 20, alignItems: "center" },
  breadcrumbLink: { cursor: "pointer", fontWeight: 500 },
  sep: { color: "#c2c6d2" },
  breadcrumbCurrent: { fontWeight: 700, color: "#191c1d" },
  titleRow: { display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 32 },
  titleLeft: { display: "flex", alignItems: "baseline", gap: 12 },
  title: { fontSize: 28, fontWeight: 900, letterSpacing: "-0.02em", color: "#191c1d" },
  resultCount: { fontSize: 14, color: "#43474f" },
  layout: { display: "flex", gap: 40, alignItems: "flex-start" },
  sidebar: { width: 220, flexShrink: 0, display: "flex", flexDirection: "column", gap: 28 },
  filterGroup: {},
  filterTitle: {
    fontSize: 11, fontWeight: 700, letterSpacing: "0.1em",
    textTransform: "uppercase", color: "#191c1d",
    marginBottom: 14, paddingBottom: 10,
    borderBottom: "1px solid rgba(194,198,210,0.4)",
  },
  filterItems: { display: "flex", flexDirection: "column", gap: 10 },
  filterLabel: { display: "flex", alignItems: "center", gap: 10, cursor: "pointer" },
  checkbox: { accentColor: "#001736", width: 14, height: 14, cursor: "pointer" },
  filterText: { fontSize: 13, color: "#43474f", flex: 1, transition: "color 0.15s" },
  filterTextActive: { color: "#191c1d", fontWeight: 600 },
  filterCount: { fontSize: 11, color: "#727782" },
  clearFilters: {
    background: "none", border: "none", cursor: "pointer",
    fontSize: 12, fontWeight: 600, color: "#001736",
    textDecoration: "underline", padding: 0, textAlign: "left",
  },
  gridArea: { flex: 1, minWidth: 0 },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
    gap: 1, background: "rgba(194,198,210,0.1)",
    marginBottom: 48,
  },
  empty: { textAlign: "center", padding: 80, color: "#43474f", fontSize: 15 },
  completeSection: {
    background: "rgba(242,244,244,0.5)", borderRadius: 16,
    padding: 32, marginTop: 16,
    border: "1px solid rgba(194,198,210,0.3)",
  },
  completeSectionHeader: { display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 24 },
  completeSectionTitle: { fontSize: 22, fontWeight: 900, letterSpacing: "-0.02em", color: "#001736" },
  completeSectionSub: { fontSize: 13, color: "#43474f", marginTop: 4 },
  completeGrid: { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 },
  completeCard: {
    background: "#fff", borderRadius: 12, padding: 16,
    cursor: "pointer", transition: "box-shadow 0.2s",
  },
  completeImg: {
    width: "100%", aspectRatio: "1", background: "#f2f4f4",
    borderRadius: 8, overflow: "hidden", marginBottom: 10,
  },
  completeName: { fontSize: 12, fontWeight: 600, color: "#191c1d", lineHeight: 1.3, marginBottom: 4 },
  completePrice: { fontSize: 14, fontWeight: 700, color: "#001736", marginBottom: 10 },
  completeAddBtn: {
    width: "100%", padding: "8px 0",
    background: "#001736", color: "#fff",
    border: "none", borderRadius: 6,
    fontSize: 11, fontWeight: 700, cursor: "pointer",
    transition: "background 0.2s",
  },
  completeAddBtnAdded: {
    background: "#2e7d32",
  },
  pagination: {
    display: "flex", justifyContent: "center", alignItems: "center",
    gap: 6, padding: "32px 0 16px",
  },
  pageBtn: {
    background: "#fff", border: "1px solid #e0e2e8", borderRadius: 6,
    padding: "8px 14px", fontSize: 13, fontWeight: 600, color: "#43474f",
    cursor: "pointer", transition: "all 0.15s", minWidth: 40, textAlign: "center",
  },
  pageBtnActive: {
    background: "#001736", color: "#fff", borderColor: "#001736",
  },
  pageBtnDisabled: {
    opacity: 0.4, cursor: "default",
  },
  pageEllipsis: {
    fontSize: 14, color: "#727782", padding: "0 4px",
  },
};

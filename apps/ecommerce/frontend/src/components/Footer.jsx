import { useState } from "react";
import Logo from "./Logo";

export default function Footer() {
  const [emailFocused, setEmailFocused] = useState(false);

  return (
    <footer style={styles.footer}>
      {/* Sample footer buttons (these don't do anything) */}
      <div style={styles.inner}>
        <div style={styles.brand}>
          <Logo size="sm" />
          <p style={styles.tagline}>
            Finding what's perfect for you.
          </p>
        </div>
        <div style={styles.col}>
          <h4 style={styles.colTitle}>Navigation</h4>
          <ul style={styles.list}>
            {["Collections", "Objects", "Textiles", "Journal"].map((l) => (
              <li key={l}><a href="#" style={styles.link}>{l}</a></li>
            ))}
          </ul>
        </div>
        <div style={styles.col}>
          <h4 style={styles.colTitle}>Information</h4>
          <ul style={styles.list}>
            {["Sustainability", "Shipping", "Returns", "Privacy Policy"].map((l) => (
              <li key={l}><a href="#" style={styles.link}>{l}</a></li>
            ))}
          </ul>
        </div>
        <div style={styles.col}>
          <h4 style={styles.colTitle}>Journal</h4>
          <p style={styles.newsletterText}>Subscribe for hot discounts and exclusive drops.</p>
          <div style={{ ...styles.emailRow, ...(emailFocused ? styles.emailRowFocused : {}) }}>
            <input
              style={styles.emailInput}
              type="email"
              placeholder="email@example.com"
              onFocus={() => setEmailFocused(true)}
              onBlur={() => setEmailFocused(false)}
            />
            <button style={styles.emailBtn}>
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>send</span>
            </button>
          </div>
        </div>
      </div>
      <div style={styles.bottom}>
        <p style={styles.copy}>© 2026 Valkey Maintainers. Crafted for the curated eye.</p>
      </div>
    </footer>
  );
}

const styles = {
  footer: { background: "#f2f4f4", marginTop: 80, paddingTop: 64, paddingBottom: 32 },
  inner: {
    maxWidth: 1440, margin: "0 auto", padding: "0 32px",
    display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1.5fr",
    gap: 48, marginBottom: 48,
  },
  brand: {},
  tagline: { fontSize: 13, color: "#43474f", lineHeight: 1.7, maxWidth: 280 },
  col: {},
  colTitle: {
    fontSize: 10, fontWeight: 700, letterSpacing: "0.15em",
    textTransform: "uppercase", color: "#001736",
    marginBottom: 20,
  },
  list: { listStyle: "none", display: "flex", flexDirection: "column", gap: 12 },
  link: { fontSize: 13, color: "#43474f", textDecoration: "none", transition: "color 0.2s" },
  newsletterText: { fontSize: 12, color: "#43474f", lineHeight: 1.6, marginBottom: 16 },
  emailRow: {
    display: "flex",
    borderRadius: 6,
    transition: "box-shadow 0.2s",
  },
  emailRowFocused: {
    boxShadow: "0 0 0 2px rgba(0,52,105,0.25)",
  },
  emailInput: {
    flex: 1, background: "#fff", border: "none",
    padding: "10px 14px", fontSize: 12, borderRadius: "6px 0 0 6px",
    outline: "none", color: "#191c1d",
  },
  emailBtn: {
    background: "#001736", color: "#fff", border: "none",
    padding: "10px 14px", borderRadius: "0 6px 6px 0",
    cursor: "pointer", display: "flex", alignItems: "center",
  },
  bottom: {
    maxWidth: 1440, margin: "0 auto", padding: "24px 32px 0",
    borderTop: "1px solid rgba(194,198,210,0.4)",
  },
  copy: { fontSize: 11, color: "#727782" },
};

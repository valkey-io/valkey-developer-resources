export default function Logo({ size = "md", onClick }) {
  const sizes = {
    sm: { icon: 20, text: 14, gap: 6 },
    md: { icon: 28, text: 20, gap: 8 },
    lg: { icon: 36, text: 26, gap: 10 },
  };
  const s = sizes[size] || sizes.md;

  return (
    <button
      onClick={onClick}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: s.gap,
        background: "none",
        border: "none",
        cursor: onClick ? "pointer" : "default",
        padding: 0,
      }}
      aria-label="Valkey Mart — go to homepage"
    >
      {/* Logomark: shopping bag with V accent */}
      <svg
        width={s.icon}
        height={s.icon}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        {/* Bag body */}
        <path
          d="M6 14h28l-3 22H9L6 14z"
          fill="#001736"
        />
        {/* Bag handle */}
        <path
          d="M14 14V10a6 6 0 0 1 12 0v4"
          stroke="#001736"
          strokeWidth="2.5"
          strokeLinecap="round"
          fill="none"
        />
        {/* V mark on bag */}
        <path
          d="M15 20l5 10 5-10"
          stroke="#fff"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </svg>

      {/* Wordmark */}
      <span
        style={{
          fontSize: s.text,
          fontWeight: 900,
          letterSpacing: "-0.04em",
          textTransform: "uppercase",
          color: "#001736",
          lineHeight: 1,
        }}
      >
        Valkey<span style={{ color: "#8a5100" }}>Mart</span>
      </span>
    </button>
  );
}

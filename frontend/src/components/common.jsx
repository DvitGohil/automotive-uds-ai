export function ErrorBanner({ message }) {
  if (!message) return null;
  return (
    <div
      style={{
        background: "#fdecec",
        border: "1px solid #e39",
        color: "#a11",
        padding: "0.6rem 0.8rem",
        borderRadius: 6,
        margin: "0.6rem 0",
        fontSize: "0.9rem",
      }}
    >
      {message}
    </div>
  );
}

export function EmptyState({ text }) {
  return <p style={{ color: "var(--text)", opacity: 0.7, fontStyle: "italic" }}>{text}</p>;
}

export function JsonBlock({ data }) {
  if (data === null || data === undefined) return null;
  return (
    <pre
      style={{
        background: "var(--code-bg)",
        border: "1px solid var(--border)",
        borderRadius: 6,
        padding: "0.8rem",
        overflowX: "auto",
        fontSize: "0.85rem",
      }}
    >
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

const STATUS_COLORS = {
  PASS: { bg: "#e6f7ed", border: "#1f9d55", text: "#1f9d55" },
  FAIL: { bg: "#fdecec", border: "#e33", text: "#a11" },
  UNKNOWN: { bg: "#fff8e6", border: "#c98a00", text: "#8a6200" },
};

export function StatusBadge({ status }) {
  const c = STATUS_COLORS[status] || STATUS_COLORS.UNKNOWN;
  return (
    <span
      style={{
        display: "inline-block",
        background: c.bg,
        border: `1px solid ${c.border}`,
        color: c.text,
        borderRadius: 999,
        padding: "0.15rem 0.7rem",
        fontWeight: 600,
        fontSize: "0.85rem",
      }}
    >
      {status}
    </span>
  );
}

export function Field({ label, children }) {
  return (
    <label style={{ display: "block", marginBottom: "0.6rem", fontSize: "0.9rem" }}>
      <span style={{ display: "block", marginBottom: "0.2rem", color: "var(--text)" }}>{label}</span>
      {children}
    </label>
  );
}

export const inputStyle = {
  width: "100%",
  padding: "0.4rem 0.5rem",
  border: "1px solid var(--border)",
  borderRadius: 6,
  fontSize: "0.9rem",
  boxSizing: "border-box",
};

export const buttonStyle = {
  background: "var(--accent)",
  color: "#fff",
  border: "none",
  borderRadius: 6,
  padding: "0.5rem 1rem",
  fontSize: "0.9rem",
  cursor: "pointer",
};

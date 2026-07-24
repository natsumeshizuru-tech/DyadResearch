import { CircleNotch, WarningCircle, X } from "@phosphor-icons/react";

export function Panel({ title, actions, className = "", children }) {
  return (
    <section className={`panel ${className}`}>
      {(title || actions) && (
        <header className="panel-header">
          <h2>{title}</h2>
          <div className="panel-actions">{actions}</div>
        </header>
      )}
      {children}
    </section>
  );
}

export function Field({ label, children, help }) {
  return (
    <label className="field">
      <span className="field-label">{label}{help && <small>{help}</small>}</span>
      {children}
    </label>
  );
}

export function Loading({ label = "计算中…" }) {
  return <span className="loading"><CircleNotch size={16} className="spin" /> {label}</span>;
}

export function ErrorNotice({ message, onClose }) {
  if (!message) return null;
  return (
    <div className="error-notice" role="alert">
      <WarningCircle size={17} />
      <span>{message}</span>
      {onClose && <button type="button" onClick={onClose} aria-label="关闭"><X size={14} /></button>}
    </div>
  );
}

export function Tabs({ items, value, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {items.map((item) => (
        <button
          key={item.value}
          type="button"
          role="tab"
          aria-selected={value === item.value}
          className={value === item.value ? "active" : ""}
          onClick={() => onChange(item.value)}
        >
          {item.label}
          {item.count !== undefined && <span className="tab-count">{item.count}</span>}
        </button>
      ))}
    </div>
  );
}

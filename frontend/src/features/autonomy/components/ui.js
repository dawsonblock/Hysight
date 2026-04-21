export function PanelMessage({ text, tone = "default" }) {
  return <div className={`autonomy-panelMessage autonomy-panelMessage--${tone}`}>{text}</div>;
}

export function StatusPill({ value, tone = "neutral" }) {
  return <span className={`autonomy-status autonomy-status--${tone}`}>{value}</span>;
}

export function SectionHeader({ title, description, count, actions }) {
  return (
    <div className="autonomy-sectionHeader">
      <div>
        <div className="autonomy-sectionTitleRow">
          <h3 className="autonomy-sectionTitle">{title}</h3>
          {count !== undefined ? <span className="autonomy-sectionCount">{count}</span> : null}
        </div>
        {description ? <p className="autonomy-sectionDescription">{description}</p> : null}
      </div>
      {actions ? <div className="autonomy-sectionActions">{actions}</div> : null}
    </div>
  );
}

export function MetricCard({ label, value, hint, tone = "neutral" }) {
  return (
    <article className={`autonomy-metric autonomy-metric--${tone}`}>
      <div className="autonomy-metricLabel">{label}</div>
      <div className="autonomy-metricValue">{value}</div>
      {hint ? <div className="autonomy-metricHint">{hint}</div> : null}
    </article>
  );
}

export function ActionButton({ children, busy, tone = "default", ...props }) {
  return (
    <button
      {...props}
      className={`autonomy-button autonomy-button--${tone}${props.className ? ` ${props.className}` : ""}`}
      disabled={busy || props.disabled}
      type={props.type || "button"}
    >
      {busy ? "Working…" : children}
    </button>
  );
}

export function TableCell({ children, ...props }) {
  return <td className="autonomy-tableCell" {...props}>{children}</td>;
}

export function TableHeader({ children, ...props }) {
  return <th className="autonomy-tableHeader" {...props}>{children}</th>;
}
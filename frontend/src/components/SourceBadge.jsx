import React from "react";

const MAP = {
  live: { color: "#30D158", label: "LIVE API" },
  cached: { color: "#00C2FF", label: "CACHED" },
  default: { color: "#FF9F0A", label: "DEFAULT FALLBACK" },
  fallback: { color: "#FF9F0A", label: "FALLBACK" },
};

export const SourceBadge = ({ status = "live", label, testId }) => {
  const k = status.toString().toLowerCase().replace(/[\s_-]/g, "");
  const cfg = MAP[k] || MAP.live;
  return (
    <span
      data-testid={testId}
      className="mono inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] tracking-wider uppercase"
      style={{
        color: cfg.color,
        background: `${cfg.color}1A`,
        border: `1px solid ${cfg.color}55`,
        borderRadius: 0,
      }}
    >
      <span
        className="w-1.5 h-1.5 inline-block"
        style={{ background: cfg.color }}
      />
      {label || cfg.label}
    </span>
  );
};

export default SourceBadge;

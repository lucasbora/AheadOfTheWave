import React from "react";

const MAP = {
  high: "#30D158",
  medium: "#FF9F0A",
  med: "#FF9F0A",
  low: "#FF3B30",
};

export const ConfidenceBadge = ({ level = "medium", testId }) => {
  const k = (level || "medium").toString().toLowerCase();
  const color = MAP[k] || "#5C667A";
  return (
    <span
      data-testid={testId}
      className="mono inline-flex items-center px-2 py-0.5 text-[10px] tracking-[0.12em] uppercase"
      style={{
        color,
        background: `${color}1A`,
        border: `1px solid ${color}55`,
        borderRadius: 0,
      }}
    >
      Confidence · {k}
    </span>
  );
};

export default ConfidenceBadge;

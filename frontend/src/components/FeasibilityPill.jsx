import React from "react";
import { Check, X, HelpCircle } from "lucide-react";

const MAP = {
  feasible: {
    color: "#30D158",
    bg: "rgba(48,209,88,0.10)",
    label: "FEASIBLE",
    Icon: Check,
  },
  not_feasible: {
    color: "#FF3B30",
    bg: "rgba(255,59,48,0.10)",
    label: "NOT FEASIBLE",
    Icon: X,
  },
  unknown: {
    color: "#FF9F0A",
    bg: "rgba(255,159,10,0.10)",
    label: "UNKNOWN",
    Icon: HelpCircle,
  },
};

export const FeasibilityPill = ({ kind, status, testId }) => {
  const norm = (status || "unknown").toString().toLowerCase().replace(/[\s-]/g, "_");
  const cfg = MAP[norm] || MAP.unknown;
  const { Icon } = cfg;
  return (
    <div
      data-testid={testId}
      className="flex items-center gap-2 px-3 py-2 border"
      style={{
        background: cfg.bg,
        borderColor: `${cfg.color}55`,
        color: cfg.color,
        borderRadius: 0,
      }}
    >
      <Icon size={14} strokeWidth={2} />
      <div className="flex flex-col leading-tight">
        <span className="mono text-[10px] tracking-[0.12em] uppercase opacity-70">
          {kind}
        </span>
        <span className="mono text-[11px] font-medium tracking-wider">
          {cfg.label}
        </span>
      </div>
    </div>
  );
};

export default FeasibilityPill;

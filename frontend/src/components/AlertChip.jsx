import React from "react";
import { AlertTriangle, ShieldCheck, AlertOctagon } from "lucide-react";

const MAP = {
  green: { color: "#30D158", label: "OK", Icon: ShieldCheck },
  amber: { color: "#FF9F0A", label: "WATCH", Icon: AlertTriangle },
  red: { color: "#FF3B30", label: "ALERT", Icon: AlertOctagon },
};

export const AlertChip = ({ level = "green", label, testId }) => {
  const cfg = MAP[level] || MAP.green;
  const Icon = cfg.Icon;
  return (
    <span
      data-testid={testId}
      className="mono inline-flex items-center gap-1.5 px-2 py-1 text-[10px] tracking-wider uppercase"
      style={{
        color: cfg.color,
        background: `${cfg.color}1A`,
        border: `1px solid ${cfg.color}55`,
        borderRadius: 0,
      }}
    >
      <Icon size={12} strokeWidth={2} />
      {label || cfg.label}
    </span>
  );
};

export default AlertChip;

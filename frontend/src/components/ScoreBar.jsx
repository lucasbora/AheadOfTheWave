import React from "react";
import { gradeColor, gradeFromScore } from "../lib/grade";

export const ScoreBar = ({
  value,
  max = 100,
  grade,
  height = 6,
  showValue = false,
  label,
  testId,
}) => {
  const v = Number(value) || 0;
  const pct = Math.max(0, Math.min(100, (v / max) * 100));
  const g = grade || gradeFromScore(v);
  const color = gradeColor(g);

  return (
    <div className="w-full" data-testid={testId}>
      {(label || showValue) && (
        <div className="flex items-center justify-between mb-1.5">
          {label && <span className="label-overline">{label}</span>}
          {showValue && (
            <span className="mono text-[11px] text-white">
              {v.toFixed(2)}
              <span className="text-[#5C667A]"> / {max}</span>
            </span>
          )}
        </div>
      )}
      <div
        className="w-full bg-[#1E2535] relative overflow-hidden"
        style={{ height, borderRadius: 0 }}
      >
        <div
          className="bar-fill h-full"
          style={{
            width: `${pct}%`,
            background: color,
            boxShadow: `0 0 8px ${color}55`,
          }}
        />
      </div>
    </div>
  );
};

export default ScoreBar;

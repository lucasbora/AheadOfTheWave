import React from "react";

export const RiskDots = ({ value = 0, max = 5, testId }) => {
  const v = Math.max(0, Math.min(max, Math.round(Number(value) || 0)));
  return (
    <div className="flex items-center gap-1" data-testid={testId}>
      {Array.from({ length: max }).map((_, i) => (
        <span
          key={i}
          className={`risk-dot ${i < v ? `on-${v}` : ""}`}
          aria-hidden
        />
      ))}
    </div>
  );
};

export default RiskDots;

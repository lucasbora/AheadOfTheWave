import React from "react";
import { gradeToKey, gradeColor } from "../lib/grade";

export const GradeBadge = ({ grade, size = "sm", testId }) => {
  const k = gradeToKey(grade);
  const color = gradeColor(grade);
  const padX = size === "lg" ? "px-3 py-1" : "px-2 py-0.5";
  const fs = size === "lg" ? "text-sm" : "text-[11px]";
  return (
    <span
      data-testid={testId}
      className={`mono inline-flex items-center justify-center ${padX} ${fs} font-medium tracking-wider`}
      style={{
        color,
        background: `${color}1A`,
        border: `1px solid ${color}55`,
        borderRadius: 0,
        minWidth: 36,
      }}
    >
      {grade || "—"}
      <span className="sr-only">grade {k}</span>
    </span>
  );
};

export default GradeBadge;

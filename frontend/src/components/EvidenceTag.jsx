import React from "react";

export const EvidenceTag = ({ children, testId }) => (
  <span
    data-testid={testId}
    className="mono inline-flex items-center px-2 py-0.5 text-[10px] text-[#8B95A5] bg-[#0A0E1A] border border-[#1E2535]"
    style={{ borderRadius: 0 }}
  >
    {children}
  </span>
);

export default EvidenceTag;

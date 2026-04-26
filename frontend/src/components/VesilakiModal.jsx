import React, { useEffect, useState } from "react";
import { X } from "lucide-react";
import { ext } from "../lib/api";

export const VesilakiModal = ({ open, onClose, syke }) => {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setErr("");
    setText("");
    ext
      .legalVesilaki({ syke })
      .then((r) => {
        if (cancelled) return;
        const t =
          r?.assessment ||
          r?.text ||
          r?.legal_assessment ||
          (typeof r === "string" ? r : JSON.stringify(r, null, 2));
        setText(t || "");
      })
      .catch((e) => {
        if (cancelled) return;
        setErr(e?.message || "Failed to fetch legal assessment");
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [open, JSON.stringify(syke)]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[2000] bg-black/70 flex items-center justify-center p-4"
      onClick={onClose}
      data-testid="vesilaki-modal-overlay"
    >
      <div
        className="panel w-full max-w-3xl max-h-[88vh] flex flex-col panel-in"
        onClick={(e) => e.stopPropagation()}
        data-testid="vesilaki-modal"
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-[#1E2535]">
          <div>
            <div className="label-overline">LEGAL ASSESSMENT</div>
            <div className="text-[14px] mt-0.5">
              Vesilaki 587/2011 — Finnish Water Act Compliance
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-[#8B95A5] hover:text-white"
            data-testid="vesilaki-close"
          >
            <X size={16} />
          </button>
        </div>

        <div className="px-5 py-3 border-b border-[#1E2535] grid grid-cols-3 gap-3 bg-[#0A0E1A]">
          <div>
            <div className="label-overline">FLOOD ZONE</div>
            <div className="mono text-[12px] text-white mt-1">
              {syke?.flood_zone || "—"}
            </div>
          </div>
          <div>
            <div className="label-overline">GROUNDWATER CLASS</div>
            <div className="mono text-[12px] text-white mt-1">
              {syke?.groundwater_class || "—"}
            </div>
          </div>
          <div>
            <div className="label-overline">ABSTRACTION</div>
            <div className="mono text-[12px] text-white mt-1">
              {syke?.abstraction_m3_day != null
                ? `${syke.abstraction_m3_day} m³/day`
                : "—"}
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-5">
          {loading && (
            <div className="mono text-[12px] text-[#FF9F0A]">
              ▸ Calling Claude legal reasoning…
            </div>
          )}
          {err && (
            <div className="mono text-[12px] text-[#FF3B30]">
              ✕ {err}
            </div>
          )}
          {!loading && !err && (
            <pre
              className="mono text-[12.5px] text-white whitespace-pre-wrap leading-relaxed"
              data-testid="vesilaki-text"
            >
              {text || "—"}
            </pre>
          )}
        </div>

        <div
          className="px-5 py-2.5 border-t border-[#1E2535] mono text-[10px] uppercase tracking-wider"
          style={{ background: "rgba(255,159,10,0.08)", color: "#FF9F0A" }}
        >
          ⚠ Not legal advice. Engage a Finnish environmental lawyer for binding
          guidance under Vesilaki 587/2011.
        </div>
      </div>
    </div>
  );
};

export default VesilakiModal;

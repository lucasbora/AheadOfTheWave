import React from "react";
import { X, Download } from "lucide-react";
import SourceBadge from "./SourceBadge";

export const DataLineageDrawer = ({ open, onClose, lineage, context }) => {
  if (!open) return null;

  const sources = lineage?.sources || lineage || [];
  const list = Array.isArray(sources) ? sources : [];

  const handleDownload = () => {
    const blob = new Blob(
      [JSON.stringify({ context, lineage: list }, null, 2)],
      { type: "application/json" }
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "lineage.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div
      className="fixed inset-0 z-[1500] flex"
      data-testid="lineage-drawer"
    >
      <div className="flex-1 bg-black/60" onClick={onClose} />
      <aside className="w-[400px] max-w-full h-full bg-[#0B101D] border-l border-[#1E2535] drawer-slide flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#1E2535]">
          <div>
            <div className="label-overline">DATA LINEAGE</div>
            <div className="text-[13px] mt-0.5">
              Source provenance for current score
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-[#8B95A5] hover:text-white"
            data-testid="lineage-close"
          >
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-4 space-y-2">
          {list.length === 0 && (
            <div className="mono text-[11px] text-[#5C667A]">
              No lineage data available.
            </div>
          )}
          {list.map((s, i) => {
            const status = (s.status || s.source_status || "live")
              .toString()
              .toLowerCase();
            return (
              <div
                key={i}
                className="border border-[#1E2535] p-3 bg-[#0A0E1A]"
                data-testid={`lineage-source-${i}`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[12.5px] text-white truncate">
                    {s.name || s.source || s.dataset || "Source"}
                  </span>
                  <SourceBadge status={status} />
                </div>
                <div className="grid grid-cols-2 gap-2 mono text-[10px]">
                  <div>
                    <span className="text-[#5C667A] uppercase tracking-wider">
                      dataset
                    </span>
                    <div className="text-white truncate">
                      {s.dataset_id || s.id || "—"}
                    </div>
                  </div>
                  <div>
                    <span className="text-[#5C667A] uppercase tracking-wider">
                      fetched
                    </span>
                    <div className="text-white truncate">
                      {s.fetch_date || s.fetched_at || "—"}
                    </div>
                  </div>
                  <div className="col-span-2">
                    <span className="text-[#5C667A] uppercase tracking-wider">
                      confidence
                    </span>
                    <div className="text-white">{s.confidence || "—"}</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="border-t border-[#1E2535] p-3 flex justify-end">
          <button
            onClick={handleDownload}
            className="mono text-[11px] inline-flex items-center gap-1.5 px-3 py-1.5 border border-[#1E2535] hover:border-[#00C2FF] hover:text-[#00C2FF] text-[#8B95A5]"
            style={{ borderRadius: 0 }}
            data-testid="lineage-download"
          >
            <Download size={12} />
            DOWNLOAD LINEAGE JSON
          </button>
        </div>
      </aside>
    </div>
  );
};

export default DataLineageDrawer;

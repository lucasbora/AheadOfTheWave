import React, { useEffect, useRef } from "react";
import L from "leaflet";
import { gradeToKey } from "../lib/grade";

// Fix default icon issue
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const DARK_TILES = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
const ATTRIB =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/attributions">CARTO</a>';

function makePinIcon(grade) {
  const key = gradeToKey(grade);
  return L.divIcon({
    className: "",
    html: `<div class="aotw-pin grade-${key}"></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });
}

function makeDotIcon(color) {
  return L.divIcon({
    className: "",
    html: `<div class="heatmap-dot" style="background:${color}; box-shadow:0 0 8px ${color}99"></div>`,
    iconSize: [10, 10],
    iconAnchor: [5, 5],
  });
}

export const LeafletMap = ({
  center = [60.1699, 24.9384],
  zoom = 5,
  marker, // {lat, lon}
  onClick, // (lat, lon) => void
  heatmapPoints, // [{lat, lon, color, label}]
  bbox, // {n,s,e,w}
  onBbox, // (bbox|null) => void
  height = "100%",
  testId = "leaflet-map",
}) => {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const heatLayerRef = useRef(null);
  const bboxLayerRef = useRef(null);
  const drawingRef = useRef(null);

  useEffect(() => {
    if (mapRef.current) return;
    const map = L.map(containerRef.current, {
      center,
      zoom,
      zoomControl: true,
      attributionControl: true,
      preferCanvas: true,
    });
    mapRef.current = map;
    L.tileLayer(DARK_TILES, {
      attribution: ATTRIB,
      subdomains: "abcd",
      maxZoom: 19,
    }).addTo(map);

    map.on("click", (e) => {
      if (drawingRef.current) return;
      onClick && onClick(e.latlng.lat, e.latlng.lng);
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Recenter when center or zoom change externally
  useEffect(() => {
    const m = mapRef.current;
    if (!m) return;
    if (Array.isArray(center) && center.length === 2) {
      m.setView(center, zoom, { animate: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [center?.[0], center?.[1]]);

  // Marker
  useEffect(() => {
    const m = mapRef.current;
    if (!m) return;
    if (markerRef.current) {
      m.removeLayer(markerRef.current);
      markerRef.current = null;
    }
    if (marker && marker.lat != null && marker.lon != null) {
      const mk = L.marker([marker.lat, marker.lon], {
        icon: makePinIcon(marker.grade),
      });
      mk.addTo(m);
      markerRef.current = mk;
    }
  }, [marker?.lat, marker?.lon, marker?.grade]);

  // Heatmap points
  useEffect(() => {
    const m = mapRef.current;
    if (!m) return;
    if (heatLayerRef.current) {
      m.removeLayer(heatLayerRef.current);
      heatLayerRef.current = null;
    }
    if (heatmapPoints && heatmapPoints.length) {
      const grp = L.layerGroup();
      heatmapPoints.forEach((p) => {
        const mk = L.marker([p.lat, p.lon], { icon: makeDotIcon(p.color) });
        if (p.label) {
          mk.bindTooltip(p.label, {
            direction: "top",
            offset: [0, -6],
            className: "aotw-tip",
          });
        }
        grp.addLayer(mk);
      });
      grp.addTo(m);
      heatLayerRef.current = grp;
    }
  }, [heatmapPoints]);

  // BBox draw
  useEffect(() => {
    const m = mapRef.current;
    if (!m) return;
    if (bboxLayerRef.current) {
      m.removeLayer(bboxLayerRef.current);
      bboxLayerRef.current = null;
    }
    if (bbox) {
      const b = L.rectangle(
        [
          [bbox.s, bbox.w],
          [bbox.n, bbox.e],
        ],
        {
          color: "#00C2FF",
          weight: 1,
          dashArray: "4 4",
          fillColor: "#00C2FF",
          fillOpacity: 0.06,
        }
      );
      b.addTo(m);
      bboxLayerRef.current = b;
    }
  }, [bbox?.n, bbox?.s, bbox?.e, bbox?.w]);

  // BBox drawing handlers (toggleable from outside via DOM event)
  useEffect(() => {
    const m = mapRef.current;
    if (!m) return;
    const onStartDraw = () => {
      drawingRef.current = { start: null, rect: null };
      m.dragging.disable();
      m.getContainer().style.cursor = "crosshair";
      const onDown = (e) => {
        drawingRef.current.start = e.latlng;
        const r = L.rectangle([e.latlng, e.latlng], {
          color: "#00C2FF",
          weight: 1,
          dashArray: "4 4",
          fillColor: "#00C2FF",
          fillOpacity: 0.06,
        }).addTo(m);
        drawingRef.current.rect = r;
        m.on("mousemove", onMove);
        m.on("mouseup", onUp);
      };
      const onMove = (e) => {
        if (!drawingRef.current?.start || !drawingRef.current?.rect) return;
        drawingRef.current.rect.setBounds([
          drawingRef.current.start,
          e.latlng,
        ]);
      };
      const onUp = (e) => {
        const start = drawingRef.current?.start;
        if (start) {
          const n = Math.max(start.lat, e.latlng.lat);
          const s = Math.min(start.lat, e.latlng.lat);
          const ee = Math.max(start.lng, e.latlng.lng);
          const w = Math.min(start.lng, e.latlng.lng);
          if (drawingRef.current.rect)
            m.removeLayer(drawingRef.current.rect);
          onBbox && onBbox({ n, s, e: ee, w });
        }
        m.off("mousedown", onDown);
        m.off("mousemove", onMove);
        m.off("mouseup", onUp);
        m.dragging.enable();
        m.getContainer().style.cursor = "";
        drawingRef.current = null;
      };
      m.once("mousedown", onDown);
    };
    const onClearDraw = () => {
      onBbox && onBbox(null);
    };
    window.addEventListener("aotw:start-bbox", onStartDraw);
    window.addEventListener("aotw:clear-bbox", onClearDraw);
    return () => {
      window.removeEventListener("aotw:start-bbox", onStartDraw);
      window.removeEventListener("aotw:clear-bbox", onClearDraw);
    };
  }, [onBbox]);

  return (
    <div
      ref={containerRef}
      data-testid={testId}
      style={{ height, width: "100%", background: "#0A0E1A" }}
    />
  );
};

export default LeafletMap;

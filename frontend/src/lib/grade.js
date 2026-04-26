// Helpers for grade colors & coercion

export const GRADES = ["A+", "A", "B", "C", "D", "F"];

export function gradeToKey(g) {
  if (!g) return "n";
  const s = String(g).trim().toUpperCase();
  if (s === "A+") return "aplus";
  if (s === "A") return "a";
  if (s === "B") return "b";
  if (s === "C") return "c";
  if (s === "D") return "d";
  if (s === "F") return "f";
  return "n";
}

export const GRADE_COLOR = {
  aplus: "#30D158",
  a: "#00C2FF",
  b: "#00D4B2",
  c: "#FF9F0A",
  d: "#FF6B00",
  f: "#FF3B30",
  n: "#5C667A",
};

export function gradeColor(g) {
  return GRADE_COLOR[gradeToKey(g)];
}

export function gradeFromScore(score) {
  if (score == null || isNaN(score)) return "—";
  const s = Number(score);
  if (s >= 90) return "A+";
  if (s >= 80) return "A";
  if (s >= 70) return "B";
  if (s >= 55) return "C";
  if (s >= 40) return "D";
  return "F";
}

export function fmt(n, d = 2) {
  if (n == null || isNaN(n)) return "—";
  return Number(n).toFixed(d);
}

export function fmtCoord(n) {
  if (n == null || isNaN(n)) return "—";
  const v = Number(n);
  return (v >= 0 ? "+" : "") + v.toFixed(4);
}

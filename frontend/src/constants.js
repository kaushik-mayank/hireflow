export const STAGES = [
  "Applied",
  "AI Ranked",
  "Shortlisted",
  "Contact Pending",
  "Contacted",
  "Interview Scheduled",
  "Interview Done",
  "Selected",
  "Rejected",
  "On Hold",
];

export const STAGE_COLORS = {
  Applied: { bg: "#f3f4f6", color: "#374151" },
  "AI Ranked": { bg: "#dbeafe", color: "#1e40af" },
  Shortlisted: { bg: "#ede9fe", color: "#7c3aed" },
  "Contact Pending": { bg: "#fef3c7", color: "#92400e" },
  Contacted: { bg: "#fef9c3", color: "#713f12" },
  "Interview Scheduled": { bg: "#ede9fe", color: "#7c3aed" },
  "Interview Done": { bg: "#ccfbf1", color: "#0d9488" },
  Selected: { bg: "#dcfce7", color: "#16a34a" },
  Rejected: { bg: "#fee2e2", color: "#ef4444" },
  "On Hold": { bg: "#ffedd5", color: "#7c2d12" },
};

export function scoreColor(score) {
  if (score == null) return { bg: "#f3f4f6", color: "#9ca3af" };
  if (score >= 75) return { bg: "#dcfce7", color: "#16a34a" };
  if (score >= 50) return { bg: "#fef3c7", color: "#92400e" };
  return { bg: "#fee2e2", color: "#ef4444" };
}

export function initials(name) {
  if (!name) return "?";
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");
}

export function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return "—";
  }
}

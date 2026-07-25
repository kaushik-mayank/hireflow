import {
  Linkedin, Search, Briefcase, Globe, UserPlus, Handshake,
  Database, DoorOpen, GraduationCap, Server, Tag,
} from "lucide-react";

/**
 * The single source of truth for candidate sources.
 *
 * Everything about resume sources — the mandatory upload dropdown, the badge in
 * the candidate list, and the source filter — reads from this one array. To add,
 * remove or rename a source, edit here and nowhere else.
 *
 * `id` is what gets stored on the candidate record and what Reports/analytics
 * group by, so keep ids stable once data exists. `label` is what users see.
 */
export const CANDIDATE_SOURCES = [
  { id: "LinkedIn", label: "LinkedIn", icon: Linkedin, color: "#0a66c2" },
  { id: "Indeed", label: "Indeed", icon: Search, color: "#2557a7" },
  { id: "Naukri", label: "Naukri", icon: Briefcase, color: "#4a90d9" },
  { id: "Company Careers Page", label: "Company Careers Page", icon: Globe, color: "#0d9488" },
  { id: "Employee Referral", label: "Employee Referral", icon: UserPlus, color: "#16a34a" },
  { id: "Recruitment Agency", label: "Recruitment Agency", icon: Handshake, color: "#7c3aed" },
  { id: "Offline Database", label: "Offline Database", icon: Database, color: "#92400e" },
  { id: "Walk-in", label: "Walk-in", icon: DoorOpen, color: "#f59e0b" },
  { id: "Campus Hiring", label: "Campus Hiring", icon: GraduationCap, color: "#4f6ef7" },
  { id: "Internal Database", label: "Internal Database", icon: Server, color: "#475569" },
  { id: "Other", label: "Other", icon: Tag, color: "#6b7280" },
];

/** Value stored on records that predate the mandatory-source requirement. */
export const UNKNOWN_SOURCE = "Unknown";

const BY_ID = Object.fromEntries(CANDIDATE_SOURCES.map((s) => [s.id, s]));

/** Look up a source's display metadata, tolerating legacy/free-text values. */
export function sourceMeta(id) {
  return (
    BY_ID[id] || {
      id: id || UNKNOWN_SOURCE,
      label: id || UNKNOWN_SOURCE,
      icon: Tag,
      color: "#9ca3af",
    }
  );
}

export const SOURCE_IDS = CANDIDATE_SOURCES.map((s) => s.id);

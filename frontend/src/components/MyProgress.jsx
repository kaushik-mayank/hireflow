import { useEffect, useState } from "react";
import { Target, CalendarClock } from "lucide-react";
import { reportsApi } from "@/api";
import { Card, ProgressBar, Pill } from "@/components/ui";
import { fmtDate } from "@/constants";

// A recruiter's own assignment targets and deadlines (from /reports/mine). Shown
// above their personal pipeline analytics. Never a comparison with colleagues.
const STATUS = {
  met: { l: "Met", t: "green", c: "#16a34a" },
  on_track: { l: "On track", t: "green", c: "#16a34a" },
  at_risk: { l: "At risk", t: "amber", c: "#f59e0b" },
  missed: { l: "Missed", t: "red", c: "#ef4444" },
  no_deadline: { l: "No deadline", t: "gray", c: "#6366f1" },
};

export default function MyProgress() {
  const [data, setData] = useState(null);

  useEffect(() => {
    reportsApi.mine().then((r) => setData(r.data)).catch(() => {});
  }, []);

  if (!data) return null;
  const attainment = data.target_attainment || [];
  const deadlines = data.deadline_health || [];
  if (!attainment.length && !deadlines.length) return null;

  return (
    <Card className="p-5 mb-6" data-testid="my-progress">
      <h3 className="font-semibold text-gray-800 flex items-center gap-2 mb-4">
        <Target size={16} className="text-indigo" /> My targets & deadlines
      </h3>

      {attainment.length > 0 && (
        <div className="space-y-3 mb-4">
          {attainment.map((row) =>
            row.metrics.map((m) => {
              const s = STATUS[m.status] || STATUS.no_deadline;
              return (
                <div key={`${row.assignment_id}-${m.kind}`}>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="text-gray-700">{row.job_title || "Job"} · {m.kind === "sourced" ? "Sourced" : "Shortlist"}</span>
                    <span className="flex items-center gap-2 text-gray-600">{m.actual}/{m.target} <Pill tone={s.t}>{s.l}</Pill></span>
                  </div>
                  <ProgressBar value={m.actual} max={m.target} color={s.c} />
                </div>
              );
            })
          )}
        </div>
      )}

      {deadlines.length > 0 && (
        <div className="space-y-1.5">
          {deadlines.map((d) => (
            <div key={d.assignment_id} className="flex items-center justify-between text-sm">
              <span className="text-gray-700 flex items-center gap-1.5"><CalendarClock size={14} className="text-gray-400" /> {d.job_title || "Job"}</span>
              <span className="flex items-center gap-2">
                <span className="text-xs text-gray-500">{fmtDate(d.deadline)}</span>
                {d.overdue ? <Pill tone="red">{Math.abs(d.days_remaining)}d overdue</Pill> : <Pill tone="gray">{d.days_remaining}d left</Pill>}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

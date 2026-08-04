import { useEffect, useState } from "react";
import {
  Users, Target, CalendarClock, Gauge, Lightbulb, AlertTriangle, CheckCircle2, BarChart3,
} from "lucide-react";
import { reportsApi } from "@/api";
import { Card, ProgressBar, Pill, Skeleton, EmptyState, Avatar } from "@/components/ui";
import { fmtDate } from "@/constants";

const INSIGHT_STYLE = {
  positive: { icon: CheckCircle2, className: "text-green", bg: "bg-green-light" },
  attention: { icon: AlertTriangle, className: "text-amber", bg: "bg-amber-light" },
  neutral: { icon: Lightbulb, className: "text-indigo", bg: "bg-indigo-light" },
};

// Attainment status -> label + Pill tone + progress-bar colour.
const STATUS_META = {
  met: { label: "Met", tone: "green", color: "#16a34a" },
  on_track: { label: "On track", tone: "green", color: "#16a34a" },
  at_risk: { label: "At risk", tone: "amber", color: "#f59e0b" },
  missed: { label: "Missed", tone: "red", color: "#ef4444" },
  no_deadline: { label: "No deadline", tone: "gray", color: "#6366f1" },
};

function Section({ icon: Icon, title, subtitle, children }) {
  return (
    <Card className="p-5">
      <div className="mb-4">
        <h3 className="font-semibold text-gray-800 flex items-center gap-2"><Icon size={16} className="text-indigo" /> {title}</h3>
        {subtitle && <p className="text-xs text-gray-600 mt-1">{subtitle}</p>}
      </div>
      {children}
    </Card>
  );
}

function pct(v) {
  return v == null ? "—" : `${v}%`;
}

export default function TeamReport() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    reportsApi.team()
      .then((r) => setData(r.data))
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="grid md:grid-cols-2 gap-6">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-64 rounded-xl" />)}</div>;
  }
  if (failed || !data) {
    return (
      <Card>
        <EmptyState icon={BarChart3} title="Couldn't load the team report"
          subtitle="This looks like a connection or server problem, not anything you did. Refresh to try again." />
      </Card>
    );
  }

  const { throughput = [], target_attainment: attainment = [], deadline_health: deadlines = [],
          workload = [], insights = [], totals = {} } = data;
  const nameOf = (row) => row.user_name || row.user_email || "—";

  if ((totals.recruiters || 0) === 0) {
    return (
      <Card>
        <EmptyState icon={Users} title="No teammates yet"
          subtitle="Approve teammates on the Team page and assign them to jobs. Their throughput, targets and deadlines will show here." />
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {insights.length > 0 && (
        <Card className="p-5">
          <h3 className="font-semibold text-gray-800 flex items-center gap-2 mb-4"><Lightbulb size={16} className="text-indigo" /> What this means</h3>
          <ul className="space-y-2.5">
            {insights.map((item, i) => {
              const s = INSIGHT_STYLE[item.tone] || INSIGHT_STYLE.neutral;
              const Icon = s.icon;
              return (
                <li key={i} className="flex items-start gap-3">
                  <span className={`mt-0.5 w-6 h-6 rounded-lg flex items-center justify-center shrink-0 ${s.bg}`}><Icon size={14} className={s.className} /></span>
                  <p className="text-sm text-gray-700 leading-relaxed">{item.text}</p>
                </li>
              );
            })}
          </ul>
        </Card>
      )}

      <Section icon={Users} title="Team throughput" subtitle="Candidates sourced, shortlisted, interviewed and hired per recruiter.">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-600 text-xs border-b border-gray-200">
                <th className="px-3 py-2 font-medium">Recruiter</th>
                <th className="px-3 py-2 font-medium">Sourced</th>
                <th className="px-3 py-2 font-medium">Shortlisted</th>
                <th className="px-3 py-2 font-medium">Interviewed</th>
                <th className="px-3 py-2 font-medium">Hired</th>
                <th className="px-3 py-2 font-medium">Shortlist rate</th>
                <th className="px-3 py-2 font-medium">Hire rate</th>
              </tr>
            </thead>
            <tbody>
              {throughput.map((r) => (
                <tr key={r.user_id} className="border-b border-gray-100 last:border-0">
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <Avatar name={nameOf(r)} size={28} />
                      <span className="font-medium text-gray-800">{nameOf(r)}</span>
                    </div>
                  </td>
                  <td className="px-3 py-2 text-gray-700">{r.sourced}</td>
                  <td className="px-3 py-2 text-gray-700">{r.shortlisted}</td>
                  <td className="px-3 py-2 text-gray-700">{r.interviewed}</td>
                  <td className="px-3 py-2 text-gray-700">{r.hired}</td>
                  <td className="px-3 py-2 text-gray-500">{pct(r.shortlist_rate)}</td>
                  <td className="px-3 py-2 text-gray-500">{pct(r.hire_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section icon={Target} title="Target attainment" subtitle="Progress against each target set on an assignment. Targets left blank are hidden.">
        {attainment.length ? (
          <div className="space-y-4">
            {attainment.map((row) =>
              row.metrics.map((m) => {
                const meta = STATUS_META[m.status] || STATUS_META.no_deadline;
                return (
                  <div key={`${row.assignment_id}-${m.kind}`}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-gray-700">
                        <span className="font-medium">{nameOf(row)}</span>
                        <span className="text-gray-400"> · {row.job_title || "Job"} · {m.kind === "sourced" ? "Sourced" : "Shortlist"}</span>
                      </span>
                      <span className="flex items-center gap-2 text-gray-600">
                        {m.actual}/{m.target} <Pill tone={meta.tone}>{meta.label}</Pill>
                      </span>
                    </div>
                    <ProgressBar value={m.actual} max={m.target} color={meta.color} />
                  </div>
                );
              })
            )}
          </div>
        ) : (
          <p className="text-sm text-gray-500">No targets have been set on assignments yet.</p>
        )}
      </Section>

      <div className="grid md:grid-cols-2 gap-6">
        <Section icon={CalendarClock} title="Deadline health" subtitle="Assignments with a deadline, most overdue first.">
          {deadlines.length ? (
            <ul className="space-y-2">
              {deadlines.map((d) => (
                <li key={d.assignment_id} className="flex items-center justify-between text-sm">
                  <span className="text-gray-700"><span className="font-medium">{nameOf(d)}</span> <span className="text-gray-400">· {d.job_title || "Job"}</span></span>
                  <span className="flex items-center gap-2">
                    <span className="text-gray-500 text-xs">{fmtDate(d.deadline)}</span>
                    {d.overdue
                      ? <Pill tone="red">{Math.abs(d.days_remaining)}d overdue</Pill>
                      : <Pill tone="gray">{d.days_remaining}d left</Pill>}
                  </span>
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-gray-500">No deadlines set.</p>}
        </Section>

        <Section icon={Gauge} title="Workload balance" subtitle="Open assignments and live candidate load per recruiter.">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-600 text-xs border-b border-gray-200">
                  <th className="px-3 py-2 font-medium">Recruiter</th>
                  <th className="px-3 py-2 font-medium">Open jobs</th>
                  <th className="px-3 py-2 font-medium">Active candidates</th>
                </tr>
              </thead>
              <tbody>
                {workload.map((w) => (
                  <tr key={w.user_id} className="border-b border-gray-100 last:border-0">
                    <td className="px-3 py-2 font-medium text-gray-800">{nameOf(w)}</td>
                    <td className="px-3 py-2 text-gray-700">{w.open_assignments}</td>
                    <td className="px-3 py-2 text-gray-700">{w.active_candidates}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      </div>
    </div>
  );
}

import { useEffect, useState, useCallback } from "react";
import {
  Users, Target, CalendarClock, Gauge, Lightbulb, AlertTriangle, CheckCircle2,
  BarChart3, Award, Activity, Cpu, Download,
} from "lucide-react";
import { reportsApi } from "@/api";
import { Card, ProgressBar, Pill, Skeleton, EmptyState, Avatar, Button } from "@/components/ui";
import { fmtDate } from "@/constants";
import { toast } from "sonner";

const INSIGHT_STYLE = {
  positive: { icon: CheckCircle2, className: "text-green", bg: "bg-green-light" },
  attention: { icon: AlertTriangle, className: "text-amber", bg: "bg-amber-light" },
  neutral: { icon: Lightbulb, className: "text-indigo", bg: "bg-indigo-light" },
};

const STATUS_META = {
  met: { label: "Met", tone: "green", color: "#16a34a" },
  on_track: { label: "On track", tone: "green", color: "#16a34a" },
  at_risk: { label: "At risk", tone: "amber", color: "#f59e0b" },
  missed: { label: "Missed", tone: "red", color: "#ef4444" },
  no_deadline: { label: "No deadline", tone: "gray", color: "#6366f1" },
};

const RANGES = [[7, "7d"], [30, "30d"], [90, "90d"], [0, "All"]];

function Section({ icon: Icon, title, subtitle, action, children }) {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-gray-800 flex items-center gap-2"><Icon size={16} className="text-indigo" /> {title}</h3>
          {subtitle && <p className="text-xs text-gray-600 mt-1">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </Card>
  );
}

const pct = (v) => (v == null ? "—" : `${v}%`);

export default function TeamReport() {
  const [range, setRange] = useState(30);
  const [member, setMember] = useState("all"); // filter panels to one teammate
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setFailed(false);
    reportsApi.team(range || undefined)
      .then((r) => setData(r.data))
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  }, [range]);
  useEffect(load, [load]);

  const downloadCsv = async (panel) => {
    try {
      const res = await reportsApi.teamCsv(panel, range || undefined);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `team-${panel}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Couldn't export that CSV. Please try again.");
    }
  };

  const csvBtn = (panel) => (
    <Button variant="secondary" className="!py-1 !px-2.5 !text-xs" onClick={() => downloadCsv(panel)} data-testid={`csv-${panel}`}>
      <Download size={13} /> CSV
    </Button>
  );

  const rangeToolbar = (
    <div className="flex gap-1 bg-gray-100 rounded-lg p-1 text-sm" data-testid="team-range">
      {RANGES.map(([v, label]) => (
        <button key={v} onClick={() => setRange(v)} className={`px-2.5 py-1 rounded-md font-medium ${range === v ? "bg-white text-gray-800 shadow-soft" : "text-gray-500"}`}>
          {label}
        </button>
      ))}
    </div>
  );

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex justify-end">{rangeToolbar}</div>
        <div className="grid md:grid-cols-2 gap-6">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-64 rounded-xl" />)}</div>
      </div>
    );
  }
  if (failed || !data) {
    return (
      <Card><EmptyState icon={BarChart3} title="Couldn't load the team report"
        subtitle="This looks like a connection or server problem, not anything you did. Refresh to try again." /></Card>
    );
  }

  const {
    throughput = [], quality_of_sourcing: quality = [], target_attainment: attainment = [],
    deadline_health: deadlines = [], workload = [], roles_needing_attention: roles = [],
    activity = [], ai_usage: aiUsage = [], insights = [], totals = {},
  } = data;
  const nameOf = (r) => r.user_name || r.user_email || "—";
  // Filter the per-recruiter panels to a single teammate when one is selected.
  const memberOptions = throughput.map((r) => ({ id: r.user_id, name: nameOf(r) }));
  const fm = (rows) => (member === "all" ? rows : rows.filter((r) => r.user_id === member));

  if ((totals.recruiters || 0) === 0) {
    return (
      <Card><EmptyState icon={Users} title="No teammates yet"
        subtitle="Approve teammates on the Team page and assign them to jobs. Their throughput, targets and deadlines will show here." /></Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-gray-500">{totals.recruiters} recruiters · {totals.candidates} candidates · {totals.hires} hires</p>
        <div className="flex items-center gap-2">
          <select value={member} onChange={(e) => setMember(e.target.value)} className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm bg-white outline-none focus:border-indigo" data-testid="team-member-filter">
            <option value="all">All members</option>
            {memberOptions.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
          {rangeToolbar}
        </div>
      </div>

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

      {roles.length > 0 && (
        <Section icon={AlertTriangle} title="Roles needing attention" subtitle="Open, unfilled roles that are unassigned, stalled, past a deadline or empty.">
          <ul className="space-y-2">
            {roles.map((r) => (
              <li key={r.job_id} className="flex items-center justify-between text-sm">
                <span className="text-gray-800 font-medium">{r.job_title || "Job"}</span>
                <span className="flex flex-wrap gap-1.5 justify-end">
                  {r.reasons.map((reason) => <Pill key={reason} tone="amber">{reason}</Pill>)}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section icon={Users} title="Team throughput" subtitle="Sourced, shortlisted, interviewed and hired per recruiter." action={csvBtn("throughput")}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-600 text-xs border-b border-gray-200">
                {["Recruiter", "Sourced", "Shortlisted", "Interviewed", "Hired", "Shortlist rate", "Hire rate"].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {fm(throughput).map((r) => (
                <tr key={r.user_id} className="border-b border-gray-100 last:border-0">
                  <td className="px-3 py-2"><div className="flex items-center gap-2"><Avatar name={nameOf(r)} size={28} /><span className="font-medium text-gray-800">{nameOf(r)}</span></div></td>
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

      <Section icon={Award} title="Quality of sourcing" subtitle="Conversion quality per recruiter (rates hidden below a 5-candidate sample)." action={csvBtn("quality")}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-600 text-xs border-b border-gray-200">
                {["Recruiter", "Sourced", "Shortlist", "Interview", "Hire", "Reject after screen"].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {fm(quality).map((r) => (
                <tr key={r.user_id} className="border-b border-gray-100 last:border-0">
                  <td className="px-3 py-2 font-medium text-gray-800">{nameOf(r)}</td>
                  <td className="px-3 py-2 text-gray-700">{r.sourced}</td>
                  <td className="px-3 py-2 text-gray-500">{pct(r.shortlist_rate)}</td>
                  <td className="px-3 py-2 text-gray-500">{pct(r.interview_rate)}</td>
                  <td className="px-3 py-2 text-gray-500">{pct(r.hire_rate)}</td>
                  <td className="px-3 py-2 text-gray-500">{pct(r.reject_after_screen_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section icon={Target} title="Target attainment" subtitle="Progress against each target set on an assignment. Blank targets are hidden.">
        {fm(attainment).length ? (
          <div className="space-y-4">
            {fm(attainment).map((row) =>
              row.metrics.map((m) => {
                const meta = STATUS_META[m.status] || STATUS_META.no_deadline;
                return (
                  <div key={`${row.assignment_id}-${m.kind}`}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-gray-700"><span className="font-medium">{nameOf(row)}</span><span className="text-gray-400"> · {row.job_title || "Job"} · {m.kind === "sourced" ? "Sourced" : "Shortlist"}</span></span>
                      <span className="flex items-center gap-2 text-gray-600">{m.actual}/{m.target} <Pill tone={meta.tone}>{meta.label}</Pill></span>
                    </div>
                    <ProgressBar value={m.actual} max={m.target} color={meta.color} />
                  </div>
                );
              })
            )}
          </div>
        ) : <p className="text-sm text-gray-500">No targets have been set on assignments yet.</p>}
      </Section>

      <div className="grid md:grid-cols-2 gap-6">
        <Section icon={CalendarClock} title="Deadline health" subtitle="Assignments with a deadline, most overdue first." action={csvBtn("deadlines")}>
          {fm(deadlines).length ? (
            <ul className="space-y-2">
              {fm(deadlines).map((d) => (
                <li key={d.assignment_id} className="flex items-center justify-between text-sm">
                  <span className="text-gray-700"><span className="font-medium">{nameOf(d)}</span> <span className="text-gray-400">· {d.job_title || "Job"}</span></span>
                  <span className="flex items-center gap-2">
                    <span className="text-gray-500 text-xs">{fmtDate(d.deadline)}</span>
                    {d.overdue ? <Pill tone="red">{Math.abs(d.days_remaining)}d overdue</Pill> : <Pill tone="gray">{d.days_remaining}d left</Pill>}
                  </span>
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-gray-500">No deadlines set.</p>}
        </Section>

        <Section icon={Gauge} title="Workload balance" subtitle="Open assignments and live candidate load." action={csvBtn("workload")}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-gray-600 text-xs border-b border-gray-200">{["Recruiter", "Open jobs", "Active candidates"].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
              <tbody>
                {fm(workload).map((w) => (
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

        <Section icon={Activity} title="Activity" subtitle="Events in range + last active, per recruiter." action={csvBtn("activity")}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-gray-600 text-xs border-b border-gray-200">{["Recruiter", "Events", "Last active"].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
              <tbody>
                {fm(activity).map((a) => (
                  <tr key={a.user_id} className="border-b border-gray-100 last:border-0">
                    <td className="px-3 py-2 font-medium text-gray-800">{nameOf(a)}</td>
                    <td className="px-3 py-2 text-gray-700">{a.events}</td>
                    <td className="px-3 py-2 text-gray-500 text-xs">{a.last_active ? fmtDate(a.last_active) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        <Section icon={Cpu} title="AI usage" subtitle="AI calls per recruiter (cost visibility)." action={csvBtn("ai_usage")}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-gray-600 text-xs border-b border-gray-200">{["Recruiter", "AI calls"].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
              <tbody>
                {fm(aiUsage).map((u) => (
                  <tr key={u.user_id} className="border-b border-gray-100 last:border-0">
                    <td className="px-3 py-2 font-medium text-gray-800">{nameOf(u)}</td>
                    <td className="px-3 py-2 text-gray-700">{u.ai_calls}</td>
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

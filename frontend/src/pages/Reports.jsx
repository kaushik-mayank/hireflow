import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Clock, Filter, Target, TrendingDown, TrendingUp, Lightbulb, AlertTriangle,
  CheckCircle2, Radio, BarChart3, Timer,
} from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  AreaChart, Area, Legend,
} from "recharts";
import { reportsApi } from "@/api";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, ProgressBar, Skeleton, EmptyState, Pill } from "@/components/ui";
import { STAGE_COLORS } from "@/constants";

const tooltipStyle = {
  borderRadius: 10, border: "1px solid #e5e7eb", fontSize: 12,
  boxShadow: "0 4px 12px rgba(15,22,41,0.1)",
};

const INSIGHT_STYLE = {
  positive: { icon: CheckCircle2, className: "text-green", bg: "bg-green-light" },
  attention: { icon: AlertTriangle, className: "text-amber", bg: "bg-amber-light" },
  neutral: { icon: Lightbulb, className: "text-indigo", bg: "bg-indigo-light" },
};

/** Shown instead of a chart when there genuinely isn't enough data yet — a new
 *  account should see an explanation, not an empty axis. */
function NotEnoughData({ icon, title, subtitle }) {
  return <EmptyState icon={icon} title={title} subtitle={subtitle} />;
}

function SectionCard({ icon: Icon, iconClass, title, subtitle, children, className = "" }) {
  return (
    <Card className={`p-5 ${className}`}>
      <div className="mb-4">
        <h3 className="font-semibold text-gray-800 flex items-center gap-2">
          <Icon size={16} className={iconClass} /> {title}
        </h3>
        {subtitle && <p className="text-xs text-gray-600 mt-1">{subtitle}</p>}
      </div>
      {children}
    </Card>
  );
}

function Insights({ insights }) {
  if (!insights?.length) return null;
  return (
    <Card className="p-5 mb-6" data-testid="report-insights">
      <h3 className="font-semibold text-gray-800 flex items-center gap-2 mb-4">
        <Lightbulb size={16} className="text-indigo" /> What this means
      </h3>
      <ul className="space-y-2.5">
        {insights.map((item, i) => {
          const style = INSIGHT_STYLE[item.tone] || INSIGHT_STYLE.neutral;
          const Icon = style.icon;
          return (
            <li key={i} className="flex items-start gap-3">
              <span className={`mt-0.5 w-6 h-6 rounded-lg flex items-center justify-center shrink-0 ${style.bg}`}>
                <Icon size={14} className={style.className} />
              </span>
              <p className="text-sm text-gray-700 leading-relaxed">{item.text}</p>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function HeadlineStats({ totals, tth }) {
  const trend =
    tth.recent_avg != null && tth.previous_avg != null
      ? tth.recent_avg - tth.previous_avg
      : null;

  const cards = [
    { label: "Open postings", value: totals.open_jobs, sub: `${totals.jobs} total` },
    { label: "Candidates", value: totals.candidates, sub: `${totals.hired} hired` },
    {
      label: "Avg time-to-hire",
      value: tth.overall_avg != null ? `${Math.round(tth.overall_avg)}d` : "—",
      sub: tth.total_hires ? `${tth.total_hires} hire${tth.total_hires === 1 ? "" : "s"}` : "no hires yet",
      trend,
    },
    { label: "Awaiting AI ranking", value: totals.unanalyzed, sub: totals.unanalyzed ? "needs attention" : "all analysed" },
  ];

  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {cards.map((c) => (
        <Card key={c.label} className="p-4">
          <div className="text-xs text-gray-600">{c.label}</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-gray-800">{c.value}</span>
            {c.trend != null && Math.abs(c.trend) >= 1 && (
              <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${c.trend < 0 ? "text-green" : "text-coral"}`}>
                {c.trend < 0 ? <TrendingDown size={13} /> : <TrendingUp size={13} />}
                {Math.abs(Math.round(c.trend))}d
              </span>
            )}
          </div>
          <div className="text-xs text-gray-400 mt-0.5">{c.sub}</div>
        </Card>
      ))}
    </div>
  );
}

function Funnel({ funnel, totalCandidates }) {
  if (!totalCandidates) {
    return (
      <NotEnoughData
        icon={Filter}
        title="No candidates yet"
        subtitle="Upload resumes to a posting and the conversion funnel will build itself."
      />
    );
  }
  const max = Math.max(1, ...funnel.map((f) => f.count));
  return (
    <div className="space-y-2" data-testid="conversion-funnel">
      {funnel.map((f) => {
        const colour = STAGE_COLORS[f.stage]?.color || "#4f6ef7";
        const width = Math.max((f.count / max) * 100, f.count ? 6 : 0);
        return (
          <div key={f.stage} className="flex items-center gap-3">
            <span className="text-xs text-gray-600 w-32 shrink-0 text-right">{f.stage}</span>
            <div className="flex-1 h-7 rounded-md bg-gray-100 overflow-hidden">
              <div
                className="h-full rounded-md flex items-center justify-end px-2 transition-all duration-500"
                style={{ width: `${width}%`, background: colour }}
              >
                {f.count > 0 && <span className="text-[11px] font-semibold text-white">{f.count}</span>}
              </div>
            </div>
            <span className="w-24 shrink-0 text-[11px] text-gray-600">
              {f.conversion_from_previous != null ? (
                <>
                  {f.conversion_from_previous}% through
                  {f.drop_off > 0 && <span className="text-coral"> · −{f.drop_off}</span>}
                </>
              ) : (
                <span className="text-gray-400">entry point</span>
              )}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function Reports() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    reportsApi.get()
      .then((r) => setData(r.data))
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <Layout>
        <Topbar title="Reports" />
        <PageBody>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
          </div>
          <div className="grid md:grid-cols-2 gap-6">
            {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-72 rounded-xl" />)}
          </div>
        </PageBody>
      </Layout>
    );
  }

  if (failed || !data) {
    return (
      <Layout>
        <Topbar title="Reports" />
        <PageBody>
          <Card>
            <EmptyState
              icon={BarChart3}
              title="Could not load reports"
              subtitle="Something went wrong fetching your analytics. Refresh to try again."
            />
          </Card>
        </PageBody>
      </Layout>
    );
  }

  const { time_to_hire: tth, funnel, sources, has_source_data, aging_postings: aging,
          postings_over_time: postings, quota_tracker: quota, insights, totals } = data;

  // A brand new account should get an explanation, not four broken charts.
  if (totals.jobs === 0) {
    return (
      <Layout>
        <Topbar title="Reports" subtitle="Hiring performance & pipeline analytics" />
        <PageBody>
          <Card>
            <EmptyState
              icon={BarChart3}
              title="No hiring data yet"
              subtitle="Create your first job posting and upload some resumes. Time-to-hire, conversion rates and source effectiveness will appear here as your pipeline moves."
              action={
                <Link
                  to="/jobs/create"
                  className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo px-4 py-2.5 text-sm font-medium text-white shadow-soft hover:brightness-110"
                >
                  Create a job posting
                </Link>
              }
            />
          </Card>
        </PageBody>
      </Layout>
    );
  }

  return (
    <Layout>
      <Topbar title="Reports" subtitle="Hiring performance & pipeline analytics" />
      <PageBody>
        <HeadlineStats totals={totals} tth={tth} />
        <Insights insights={insights} />

        <div className="grid md:grid-cols-2 gap-6">
          {/* Conversion funnel */}
          <SectionCard
            icon={Filter}
            iconClass="text-purple"
            title="Pipeline conversion"
            subtitle="How far candidates actually reach, including those later rejected"
            className="md:col-span-2"
          >
            <Funnel funnel={funnel} totalCandidates={totals.candidates} />
          </SectionCard>

          {/* Time to hire */}
          <SectionCard
            icon={Clock}
            iconClass="text-indigo"
            title="Time-to-hire by posting"
            subtitle="Days from application to hire"
          >
            {tth.per_job?.length ? (
              <div style={{ width: "100%", height: 240 }}>
                <ResponsiveContainer minHeight={240}>
                  <BarChart data={tth.per_job} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 11, fill: "#9ca3af" }} />
                    <YAxis type="category" dataKey="job" width={120} tick={{ fontSize: 11, fill: "#4b5563" }} />
                    <Tooltip contentStyle={tooltipStyle} formatter={(v, _n, p) => [`${v} days (${p.payload.hires} hires)`, "Average"]} />
                    <Bar dataKey="avg_days" fill="#4f6ef7" radius={[0, 4, 4, 0]} barSize={22} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <NotEnoughData
                icon={Timer}
                title="No completed hires yet"
                subtitle="Time-to-hire is measured once a candidate reaches Selected. It will appear here after your first hire."
              />
            )}
          </SectionCard>

          {/* Source effectiveness */}
          <SectionCard
            icon={Radio}
            iconClass="text-teal"
            title="Source effectiveness"
            subtitle="Which channels actually produce hires"
          >
            {has_source_data ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-600 text-xs border-b border-gray-200">
                      <th className="py-2 font-medium">Source</th>
                      <th className="py-2 font-medium">Candidates</th>
                      <th className="py-2 font-medium">Hired</th>
                      <th className="py-2 font-medium">Hire rate</th>
                      <th className="py-2 font-medium">Avg score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sources.map((s) => (
                      <tr key={s.source} className="border-b border-gray-100 last:border-0" data-testid={`source-${s.source}`}>
                        <td className="py-2.5 pr-2 font-medium text-gray-800">{s.source}</td>
                        <td className="py-2.5 pr-2 text-gray-700">{s.candidates}</td>
                        <td className="py-2.5 pr-2 text-gray-700">{s.hired}</td>
                        <td className="py-2.5 pr-2">
                          <Pill tone={s.hire_rate >= 20 ? "green" : s.hire_rate > 0 ? "amber" : "gray"}>
                            {s.hire_rate}%
                          </Pill>
                        </td>
                        <td className="py-2.5 text-gray-700">{s.avg_score ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <NotEnoughData
                icon={Radio}
                title="No source data yet"
                subtitle="Set “Where did these candidates come from?” when uploading resumes, and this will show which channels convert best."
              />
            )}
          </SectionCard>

          {/* Postings over time */}
          <SectionCard
            icon={BarChart3}
            iconClass="text-indigo"
            title="Open vs closed postings"
            subtitle="Last 12 weeks"
          >
            <div style={{ width: "100%", height: 220 }}>
              <ResponsiveContainer minHeight={220}>
                <AreaChart data={postings} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                  <XAxis dataKey="week" tick={{ fontSize: 10, fill: "#9ca3af" }} tickFormatter={(w) => w.slice(5)} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#9ca3af" }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Area type="monotone" dataKey="open" name="Open" stroke="#4f6ef7" fill="#4f6ef7" fillOpacity={0.18} />
                  <Area type="monotone" dataKey="closed" name="Closed" stroke="#9ca3af" fill="#9ca3af" fillOpacity={0.15} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </SectionCard>

          {/* Aging postings */}
          <SectionCard
            icon={AlertTriangle}
            iconClass="text-amber"
            title="Postings needing attention"
            subtitle="Open, unfilled, and quiet for over two weeks"
          >
            {aging?.length ? (
              <ul className="space-y-2.5" data-testid="aging-postings">
                {aging.map((a) => (
                  <li key={a.job_id} className="flex items-start justify-between gap-3 border-b border-gray-100 last:border-0 pb-2.5 last:pb-0">
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-gray-800 truncate">{a.job}</div>
                      <div className="text-xs text-gray-600 mt-0.5">
                        {a.no_candidates
                          ? "No candidates uploaded"
                          : `${a.candidates} candidate${a.candidates === 1 ? "" : "s"} · ${a.hired}/${a.needed} hired`}
                      </div>
                    </div>
                    <Pill tone="amber">{a.days_since_activity}d quiet</Pill>
                  </li>
                ))}
              </ul>
            ) : (
              <NotEnoughData
                icon={CheckCircle2}
                title="Everything is moving"
                subtitle="No open posting has been sitting without candidate activity."
              />
            )}
          </SectionCard>

          {/* Quota tracker */}
          <SectionCard
            icon={Target}
            iconClass="text-green"
            title="Hiring targets"
            subtitle="Progress against the number of openings on each posting"
            className="md:col-span-2"
          >
            {quota?.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-600 text-xs border-b border-gray-200">
                      <th className="py-2 font-medium">Posting</th>
                      <th className="py-2 font-medium">Progress</th>
                      <th className="py-2 font-medium">In pipeline</th>
                      <th className="py-2 font-medium">Still needed</th>
                      <th className="py-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {quota.map((q) => (
                      <tr key={q.job} className="border-b border-gray-100 last:border-0" data-testid={`quota-${q.job}`}>
                        <td className="py-3 pr-2 font-medium text-gray-800">{q.job}</td>
                        <td className="py-3 pr-2 w-40">
                          <div className="flex items-center gap-2">
                            <ProgressBar value={q.hired} max={q.needed} />
                            <span className="text-xs text-gray-600 whitespace-nowrap">{q.hired}/{q.needed}</span>
                          </div>
                        </td>
                        <td className="py-3 pr-2 text-gray-700">{q.in_pipeline}</td>
                        <td className="py-3 pr-2 text-gray-700">{q.remaining}</td>
                        <td className="py-3">
                          {q.complete
                            ? <Pill tone="green">Target met</Pill>
                            : <Pill tone={q.status === "active" ? "gray" : "amber"}>{q.status === "active" ? "Open" : q.status}</Pill>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <NotEnoughData icon={Target} title="No postings yet" subtitle="Create a job posting to track hiring targets." />
            )}
          </SectionCard>
        </div>
      </PageBody>
    </Layout>
  );
}

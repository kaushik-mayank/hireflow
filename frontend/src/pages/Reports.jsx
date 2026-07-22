import { useEffect, useState } from "react";
import { Clock, Filter, TrendingDown, Target } from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { reportsApi } from "@/api";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, ProgressBar, Skeleton, EmptyState } from "@/components/ui";
import { STAGE_COLORS, fmtDate } from "@/constants";

const tooltipStyle = { borderRadius: 10, border: "1px solid #e5e7eb", fontSize: 12, boxShadow: "0 4px 12px rgba(15,22,41,0.1)" };

export default function Reports() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    reportsApi.get().then((r) => setData(r.data)).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <Layout><Topbar title="Reports" /><PageBody><div className="grid md:grid-cols-2 gap-6">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-72 rounded-xl" />)}</div></PageBody></Layout>;
  }

  const funnelMax = Math.max(1, ...(data?.stage_funnel || []).map((f) => f.count));

  return (
    <Layout>
      <Topbar title="Reports" subtitle="Hiring performance & pipeline analytics" />
      <PageBody>
        <div className="grid md:grid-cols-2 gap-6">
          {/* Time to Hire */}
          <Card className="p-5">
            <h3 className="font-semibold text-gray-800 flex items-center gap-2 mb-4"><Clock size={16} className="text-indigo" /> Time-to-Hire (avg days)</h3>
            {data?.time_to_hire?.length ? (
              <div style={{ width: "100%", height: 240 }}>
                <ResponsiveContainer minHeight={240}>
                  <BarChart data={data.time_to_hire} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 11, fill: "#9ca3af" }} />
                    <YAxis type="category" dataKey="job" width={120} tick={{ fontSize: 11, fill: "#4b5563" }} />
                    <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${v} days`, "Avg"]} />
                    <Bar dataKey="avg_days" fill="#4f6ef7" radius={[0, 4, 4, 0]} barSize={22} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : <EmptyState icon={Clock} title="No hires yet" subtitle="Time-to-hire appears once candidates reach Selected." />}
          </Card>

          {/* Stage Funnel */}
          <Card className="p-5">
            <h3 className="font-semibold text-gray-800 flex items-center gap-2 mb-4"><Filter size={16} className="text-purple" /> Stage Funnel</h3>
            <div className="space-y-2.5" data-testid="stage-funnel">
              {(data?.stage_funnel || []).map((f) => {
                const c = STAGE_COLORS[f.stage];
                const pct = Math.round((f.count / funnelMax) * 100);
                return (
                  <div key={f.stage} className="flex items-center gap-3">
                    <span className="text-xs text-gray-600 w-32 shrink-0 text-right">{f.stage}</span>
                    <div className="flex-1 h-6 rounded-md bg-gray-100 overflow-hidden">
                      <div className="h-full rounded-md flex items-center justify-end px-2 transition-all duration-500" style={{ width: `${Math.max(pct, f.count ? 8 : 0)}%`, background: c.color }}>
                        {f.count > 0 && <span className="text-[11px] font-semibold text-white">{f.count}</span>}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* Skill Gap */}
          <Card className="p-5">
            <h3 className="font-semibold text-gray-800 flex items-center gap-2 mb-4"><TrendingDown size={16} className="text-coral" /> Top Missing Skills</h3>
            {data?.skill_gap?.length ? (
              <div style={{ width: "100%", height: 240 }}>
                <ResponsiveContainer minHeight={240}>
                  <BarChart data={data.skill_gap} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" horizontal={false} />
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: "#9ca3af" }} />
                    <YAxis type="category" dataKey="skill" width={110} tick={{ fontSize: 11, fill: "#4b5563" }} />
                    <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${v} candidates`, "Missing"]} />
                    <Bar dataKey="count" fill="#ef4444" radius={[0, 4, 4, 0]} barSize={18} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : <EmptyState icon={TrendingDown} title="No skill gap data" subtitle="Analyze candidates to surface common missing skills." />}
          </Card>

          {/* Quota Tracker */}
          <Card className="p-5">
            <h3 className="font-semibold text-gray-800 flex items-center gap-2 mb-4"><Target size={16} className="text-green" /> Hiring Quota Tracker</h3>
            {data?.quota_tracker?.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-600 text-xs border-b border-gray-200">
                      <th className="py-2 font-medium">Job</th>
                      <th className="py-2 font-medium">Progress</th>
                      <th className="py-2 font-medium">Pipeline</th>
                      <th className="py-2 font-medium">Est. Done</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.quota_tracker.map((q) => (
                      <tr key={q.job} className="border-b border-gray-100 last:border-0" data-testid={`quota-${q.job}`}>
                        <td className="py-3 pr-2 font-medium text-gray-800">{q.job}</td>
                        <td className="py-3 pr-2 w-32">
                          <div className="flex items-center gap-2">
                            <ProgressBar value={q.hired} max={q.needed} />
                            <span className="text-xs text-gray-600 whitespace-nowrap">{q.hired}/{q.needed}</span>
                          </div>
                        </td>
                        <td className="py-3 pr-2 text-gray-700">{q.in_pipeline}</td>
                        <td className="py-3 text-xs">{q.complete ? <span className="text-green font-medium">Complete</span> : <span className="text-gray-500">{fmtDate(q.est_completion)}</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <EmptyState icon={Target} title="No jobs yet" subtitle="Create jobs to track hiring quotas." />}
          </Card>
        </div>
      </PageBody>
    </Layout>
  );
}

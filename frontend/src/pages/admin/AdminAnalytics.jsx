import { useEffect, useState } from "react";
import { TrendingUp, UserPlus, Briefcase, FileText, Sparkles } from "lucide-react";
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar, AreaChart, Area,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import { adminApi } from "@/api";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, Skeleton } from "@/components/ui";

const shortDate = (iso) => {
  try { return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" }); } catch { return iso; }
};

const tooltipStyle = { borderRadius: 10, border: "1px solid #e5e7eb", fontSize: 12, boxShadow: "0 4px 12px rgba(15,22,41,0.1)" };

function ChartCard({ title, icon: Icon, children }) {
  return (
    <Card className="p-5">
      <h3 className="font-semibold text-gray-800 flex items-center gap-2 mb-4"><Icon size={16} className="text-indigo" /> {title}</h3>
      <div style={{ width: "100%", height: 240 }}>{children}</div>
    </Card>
  );
}

export default function AdminAnalytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminApi.analytics().then((r) => setData(r.data)).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const metrics = data?.metrics || {};
  const METRIC_CARDS = [
    { label: "Most Active User", value: metrics.most_active_user },
    { label: "Most Popular Job", value: metrics.most_popular_title },
    { label: "Avg Resumes / Job", value: metrics.avg_resumes_per_job },
    { label: "Avg AI Score", value: metrics.avg_ai_score },
  ];

  if (loading) {
    return <Layout><Topbar title="System Analytics" /><PageBody fullWidth><div className="grid md:grid-cols-2 gap-6">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-72 rounded-xl" />)}</div></PageBody></Layout>;
  }

  return (
    <Layout>
      <Topbar title="System Analytics" subtitle="Platform growth & usage trends" />
      <PageBody fullWidth>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {METRIC_CARDS.map((m) => (
            <Card key={m.label} className="p-4" data-testid={`metric-${m.label}`}>
              <div className="text-xs text-gray-500">{m.label}</div>
              <div className="text-lg font-bold text-gray-800 mt-1 truncate">{m.value ?? "—"}</div>
            </Card>
          ))}
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <ChartCard title="New Signups (30 days)" icon={UserPlus}>
            <ResponsiveContainer minHeight={240}>
              <LineChart data={data.signups} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 11, fill: "#9ca3af" }} interval="preserveStartEnd" />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#9ca3af" }} />
                <Tooltip contentStyle={tooltipStyle} labelFormatter={shortDate} />
                <Line type="monotone" dataKey="count" stroke="#4f6ef7" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Jobs Created (12 weeks)" icon={Briefcase}>
            <ResponsiveContainer minHeight={240}>
              <BarChart data={data.jobs_weekly} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis dataKey="week" tickFormatter={shortDate} tick={{ fontSize: 11, fill: "#9ca3af" }} interval="preserveStartEnd" />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#9ca3af" }} />
                <Tooltip contentStyle={tooltipStyle} labelFormatter={shortDate} />
                <Bar dataKey="count" fill="#7c3aed" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Resumes Uploaded (30 days)" icon={FileText}>
            <ResponsiveContainer minHeight={240}>
              <AreaChart data={data.resumes} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="tealGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0d9488" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#0d9488" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 11, fill: "#9ca3af" }} interval="preserveStartEnd" />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#9ca3af" }} />
                <Tooltip contentStyle={tooltipStyle} labelFormatter={shortDate} />
                <Area type="monotone" dataKey="count" stroke="#0d9488" strokeWidth={2} fill="url(#tealGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="AI Usage (30 days)" icon={Sparkles}>
            <ResponsiveContainer minHeight={240}>
              <LineChart data={data.ai_usage} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 11, fill: "#9ca3af" }} interval="preserveStartEnd" />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#9ca3af" }} />
                <Tooltip contentStyle={tooltipStyle} labelFormatter={shortDate} />
                <Line type="monotone" dataKey="count" stroke="#f59e0b" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      </PageBody>
    </Layout>
  );
}

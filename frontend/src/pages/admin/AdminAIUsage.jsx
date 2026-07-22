import { useEffect, useState } from "react";
import { Sparkles, Activity, TrendingUp, User, ChevronLeft, ChevronRight } from "lucide-react";
import { adminApi } from "@/api";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, Pill, Button, Skeleton, EmptyState } from "@/components/ui";

const fmtTime = (iso) => {
  try { return new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }); }
  catch { return "—"; }
};

export default function AdminAIUsage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 50;

  useEffect(() => {
    setLoading(true);
    adminApi.aiUsage(page, PAGE_SIZE).then((r) => setData(r.data)).catch(() => {}).finally(() => setLoading(false));
  }, [page]);

  const summary = data?.summary || {};
  const SUMMARY = [
    { label: "Calls This Month", value: summary.calls_this_month, icon: Activity, color: "#4f6ef7", bg: "#e8edff" },
    { label: "Total AI Calls", value: summary.total_calls, icon: Sparkles, color: "#92400e", bg: "#fef3c7" },
    { label: "Most Used Feature", value: summary.most_used_feature, icon: TrendingUp, color: "#0d9488", bg: "#ccfbf1" },
    { label: "Most Active User", value: summary.most_active_user, icon: User, color: "#7c3aed", bg: "#ede9fe" },
  ];
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <Layout>
      <Topbar title="AI Usage" subtitle="Track AI feature usage across the platform" />
      <PageBody fullWidth>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {loading ? [1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24 rounded-xl" />)
            : SUMMARY.map((s) => (
              <Card key={s.label} className="p-4" data-testid={`ai-summary-${s.label}`}>
                <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-3" style={{ background: s.bg }}>
                  <s.icon size={18} style={{ color: s.color }} />
                </div>
                <div className="text-lg font-bold text-gray-800 truncate">{s.value ?? "—"}</div>
                <div className="text-xs text-gray-600 mt-0.5">{s.label}</div>
              </Card>
            ))}
        </div>

        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-gray-800">Usage Log</h3>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Button variant="secondary" className="!px-2 !py-1.5" disabled={page <= 1} onClick={() => setPage(page - 1)} data-testid="ai-prev"><ChevronLeft size={16} /></Button>
            <span>Page {page} / {totalPages}</span>
            <Button variant="secondary" className="!px-2 !py-1.5" disabled={page >= totalPages} onClick={() => setPage(page + 1)} data-testid="ai-next"><ChevronRight size={16} /></Button>
          </div>
        </div>

        <Card className="overflow-hidden">
          {loading ? (
            <div className="p-4 space-y-3">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-10" />)}</div>
          ) : data?.items?.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-600 text-xs border-b border-gray-200">
                    <th className="px-4 py-3 font-medium">Timestamp</th>
                    <th className="px-4 py-3 font-medium">User</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                    <th className="px-4 py-3 font-medium">Reference</th>
                    <th className="px-4 py-3 font-medium">Est. Tokens</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((it) => (
                    <tr key={it.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50" data-testid={`ai-log-${it.id}`}>
                      <td className="px-4 py-3 text-gray-500 text-xs">{fmtTime(it.created_at)}</td>
                      <td className="px-4 py-3 text-gray-700">{it.user}</td>
                      <td className="px-4 py-3"><Pill tone="amber">{it.action}</Pill></td>
                      <td className="px-4 py-3 text-gray-400 text-xs font-mono truncate max-w-[180px]">{it.reference}</td>
                      <td className="px-4 py-3 text-gray-700">{it.tokens_used?.toLocaleString() ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <EmptyState icon={Sparkles} title="No AI usage yet" subtitle="AI feature calls will be logged here." />}
        </Card>
      </PageBody>
    </Layout>
  );
}

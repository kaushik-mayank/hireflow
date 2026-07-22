import { useEffect, useState } from "react";
import { Search, FileText, ChevronLeft, ChevronRight, Eye } from "lucide-react";
import { adminApi, apiErr } from "@/api";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, Avatar, ScoreBadge, StageBadge, Button, Skeleton, EmptyState, Modal, Spinner } from "@/components/ui";
import { fmtDate } from "@/constants";

export default function AdminResumes() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [detail, setDetail] = useState(null);
  const [detailFor, setDetailFor] = useState(null);
  const [detailError, setDetailError] = useState("");
  const PAGE_SIZE = 50;

  /* Opens the raw stored record for support and moderation. Deliberately not a
     link to /candidates/:id — that route is scoped to the owning HR user and
     403s for an admin looking at someone else's candidate. */
  const openDetail = async (row) => {
    setDetailFor(row);
    setDetail(null);
    setDetailError("");
    try {
      const res = await adminApi.resumeDetail(row.id);
      setDetail(res.data);
    } catch (err) {
      setDetailError(apiErr(err, "Could not load this record"));
    }
  };

  useEffect(() => {
    setLoading(true);
    adminApi.resumes(page, PAGE_SIZE).then((r) => setData(r.data)).catch(() => {}).finally(() => setLoading(false));
  }, [page]);

  const items = (data?.items || []).filter((i) =>
    `${i.candidate_name} ${i.file_name || ""}`.toLowerCase().includes(search.toLowerCase())
  );
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <Layout>
      <Topbar title="Uploaded Resumes" subtitle={data ? `${data.total} resumes across all HR users` : "Loading..."} />
      <PageBody fullWidth>
        <div className="flex items-center justify-between mb-4">
          <div className="relative w-72">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search candidate or file..." className="w-full rounded-lg border border-gray-200 pl-9 pr-3 py-2 text-sm bg-white outline-none focus:border-indigo" data-testid="resumes-search" />
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Button variant="secondary" className="!px-2 !py-1.5" disabled={page <= 1} onClick={() => setPage(page - 1)} data-testid="resumes-prev"><ChevronLeft size={16} /></Button>
            <span>Page {page} / {totalPages}</span>
            <Button variant="secondary" className="!px-2 !py-1.5" disabled={page >= totalPages} onClick={() => setPage(page + 1)} data-testid="resumes-next"><ChevronRight size={16} /></Button>
          </div>
        </div>

        <Card className="overflow-hidden">
          {loading ? (
            <div className="p-4 space-y-3">{[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-11" />)}</div>
          ) : items.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-600 text-xs border-b border-gray-200">
                    <th className="px-4 py-3 font-medium">Candidate</th>
                    <th className="px-4 py-3 font-medium">Job</th>
                    <th className="px-4 py-3 font-medium">HR User</th>
                    <th className="px-4 py-3 font-medium">Uploaded</th>
                    <th className="px-4 py-3 font-medium">Stage</th>
                    <th className="px-4 py-3 font-medium">Score</th>
                    <th className="px-4 py-3 font-medium">File</th>
                    <th className="px-4 py-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((c) => (
                    <tr key={c.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50" data-testid={`resume-row-${c.id}`}>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2"><Avatar name={c.candidate_name} size={30} /><span className="font-medium text-gray-800">{c.candidate_name}</span></div>
                      </td>
                      <td className="px-4 py-3 text-gray-700">{c.job_title}</td>
                      <td className="px-4 py-3 text-gray-600">{c.hr_user}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs">{fmtDate(c.uploaded_at)}</td>
                      <td className="px-4 py-3"><StageBadge stage={c.stage} /></td>
                      <td className="px-4 py-3"><ScoreBadge score={c.ai_score} /></td>
                      <td className="px-4 py-3 text-gray-500 text-xs truncate max-w-[160px]">{c.file_name || "—"}</td>
                      <td className="px-4 py-3 text-right">
                        <Button variant="ghost" className="!px-2 !py-1.5" onClick={() => openDetail(c)} title="View stored record" data-testid={`resume-view-${c.id}`}><Eye size={15} /></Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <EmptyState icon={FileText} title="No resumes found" subtitle="Resumes uploaded by any HR user will appear here." />}
        </Card>

        <Modal
          open={!!detailFor}
          onClose={() => setDetailFor(null)}
          title={detailFor ? `Stored record — ${detailFor.candidate_name}` : ""}
          width="max-w-3xl"
        >
          {detailError ? (
            <div className="bg-coral-light text-coral text-sm rounded-lg px-4 py-2.5">{detailError}</div>
          ) : !detail ? (
            <div className="flex justify-center py-10"><Spinner size={22} className="text-indigo" /></div>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs text-gray-600">
                <div><span className="font-semibold text-gray-700">Job: </span>{detail.job?.title || "—"}</div>
                <div><span className="font-semibold text-gray-700">HR user: </span>{detail.hr_user?.name || "—"}{detail.hr_user?.email ? ` (${detail.hr_user.email})` : ""}</div>
              </div>
              <div className="rounded-lg border border-amber bg-amber-light px-4 py-2.5 text-xs leading-relaxed text-[#92400e]">
                This is candidate personal data shown for support and moderation. Handle it accordingly.
              </div>
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-gray-600 mb-1.5">Raw record (JSON)</div>
                <pre className="max-h-[45vh] overflow-auto rounded-lg bg-gray-50 border border-gray-200 p-4 font-mono text-[11px] leading-relaxed text-gray-700 whitespace-pre-wrap break-words" data-testid="resume-json">
                  {JSON.stringify(detail.candidate, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </Modal>
      </PageBody>
    </Layout>
  );
}

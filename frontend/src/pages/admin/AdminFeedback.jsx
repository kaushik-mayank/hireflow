import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  MessageSquare, Star, Bug, Lightbulb, ChevronLeft, ChevronRight, Mail, MailWarning, Check, Eye,
} from "lucide-react";
import { feedbackApi, apiErr } from "@/api";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, Avatar, Button, Skeleton, EmptyState, Modal, Pill } from "@/components/ui";
import { fmtDate } from "@/constants";

const TYPE_META = {
  review: { icon: Star, label: "Review", tone: "text-amber" },
  bug: { icon: Bug, label: "Bug", tone: "text-coral" },
  feature: { icon: Lightbulb, label: "Feature", tone: "text-purple" },
};
const STATUS_TONE = { new: "amber", read: "gray", actioned: "green" };
const PAGE_SIZE = 50;

export default function AdminFeedback() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [open, setOpen] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    feedbackApi
      .adminList({ page, page_size: PAGE_SIZE, status, type })
      .then((r) => setData(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page, status, type]);

  useEffect(load, [load]);

  const mark = async (item, next) => {
    try {
      await feedbackApi.setStatus(item.id, next);
      toast.success(`Marked as ${next}`);
      load();
      setOpen((o) => (o && o.id === item.id ? { ...o, status: next } : o));
    } catch (err) {
      toast.error(apiErr(err));
    }
  };

  const openItem = (item) => {
    setOpen(item);
    if (item.status === "new") mark(item, "read");
  };

  const items = data?.items || [];
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const select = "rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white";

  return (
    <Layout>
      <Topbar
        title="Feedback & Support"
        subtitle={data ? `${data.total} message${data.total === 1 ? "" : "s"} from users` : "Loading..."}
      />
      <PageBody fullWidth>
        {data && !data.email_configured && (
          <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-amber bg-amber-light px-4 py-3 text-sm leading-relaxed text-[#92400e]">
            <MailWarning size={16} className="mt-0.5 shrink-0" />
            <p>
              <span className="font-semibold">Email delivery isn't configured.</span> Messages are
              still being captured here, but nothing is being emailed out. Set the SMTP environment
              variables on the backend to turn delivery on.
            </p>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3 mb-4">
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className={select} data-testid="feedback-status-filter">
            <option value="">All statuses</option>
            <option value="new">New</option>
            <option value="read">Read</option>
            <option value="actioned">Actioned</option>
          </select>
          <select value={type} onChange={(e) => { setType(e.target.value); setPage(1); }} className={select} data-testid="feedback-type-filter">
            <option value="">All types</option>
            <option value="review">Reviews</option>
            <option value="bug">Bug reports</option>
            <option value="feature">Feature requests</option>
          </select>
          {data?.counts?.new > 0 && <Pill tone="amber">{data.counts.new} new</Pill>}
          <div className="ml-auto flex items-center gap-2 text-sm text-gray-600">
            <Button variant="secondary" className="!px-2 !py-1.5" disabled={page <= 1} onClick={() => setPage(page - 1)}><ChevronLeft size={16} /></Button>
            <span>Page {page} / {totalPages}</span>
            <Button variant="secondary" className="!px-2 !py-1.5" disabled={page >= totalPages} onClick={() => setPage(page + 1)}><ChevronRight size={16} /></Button>
          </div>
        </div>

        <Card className="overflow-hidden">
          {loading ? (
            <div className="p-4 space-y-3">{[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-12" />)}</div>
          ) : items.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-600 text-xs border-b border-gray-200">
                    <th className="px-4 py-3 font-medium">Type</th>
                    <th className="px-4 py-3 font-medium">Subject</th>
                    <th className="px-4 py-3 font-medium">From</th>
                    <th className="px-4 py-3 font-medium">Sent</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Email</th>
                    <th className="px-4 py-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((f) => {
                    const meta = TYPE_META[f.type] || { icon: MessageSquare, label: f.type, tone: "text-gray-600" };
                    const Icon = meta.icon;
                    return (
                      <tr key={f.id} className={`border-b border-gray-100 last:border-0 hover:bg-gray-50 ${f.status === "new" ? "bg-amber-light/30" : ""}`} data-testid={`feedback-row-${f.id}`}>
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-700">
                            <Icon size={14} className={meta.tone} /> {meta.label}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-medium text-gray-800 max-w-[280px] truncate">{f.subject}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <Avatar name={f.user_name} size={28} />
                            <div className="min-w-0">
                              <div className="text-gray-800 truncate">{f.user_name || "—"}</div>
                              <div className="text-xs text-gray-400 truncate">{f.user_email}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">{fmtDate(f.created_at)}</td>
                        <td className="px-4 py-3"><Pill tone={STATUS_TONE[f.status] || "gray"}>{f.status}</Pill></td>
                        <td className="px-4 py-3">
                          {f.email_sent
                            ? <Mail size={15} className="text-green" title="Emailed successfully" />
                            : <MailWarning size={15} className="text-amber" title="Not emailed — saved here only" />}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Button variant="ghost" className="!px-2 !py-1.5" onClick={() => openItem(f)} title="Read message" data-testid={`feedback-open-${f.id}`}><Eye size={15} /></Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState icon={MessageSquare} title="No feedback yet" subtitle="Reviews, bug reports and feature requests from users will appear here." />
          )}
        </Card>

        <Modal
          open={!!open}
          onClose={() => setOpen(null)}
          title={open?.subject || ""}
          width="max-w-2xl"
          footer={open && (
            <>
              <Button variant="secondary" onClick={() => setOpen(null)}>Close</Button>
              <a
                href={`mailto:${open.user_email}?subject=${encodeURIComponent(`Re: ${open.subject}`)}`}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-white text-gray-700 border border-gray-200 px-4 py-2 text-sm font-medium hover:bg-gray-50"
              >
                <Mail size={15} /> Reply
              </a>
              {open.status !== "actioned" && (
                <Button onClick={() => mark(open, "actioned")} data-testid="feedback-mark-actioned">
                  <Check size={15} /> Mark actioned
                </Button>
              )}
            </>
          )}
        >
          {open && (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-x-6 gap-y-1.5 text-xs text-gray-600">
                <div><span className="font-semibold text-gray-700">From: </span>{open.user_name} ({open.user_email})</div>
                <div><span className="font-semibold text-gray-700">Company: </span>{open.company || "—"}</div>
                <div><span className="font-semibold text-gray-700">Type: </span>{TYPE_META[open.type]?.label || open.type}</div>
                <div><span className="font-semibold text-gray-700">Sent: </span>{fmtDate(open.created_at)}</div>
                {open.user_active === false && <Pill tone="red">Account deactivated</Pill>}
              </div>
              {!open.email_sent && (
                <div className="rounded-lg border border-amber bg-amber-light px-4 py-2.5 text-xs text-[#92400e]">
                  This message was not emailed out — it exists only here.
                </div>
              )}
              <p className="whitespace-pre-wrap text-sm text-gray-700 leading-relaxed bg-gray-50 border border-gray-200 rounded-lg p-4">
                {open.message}
              </p>
            </div>
          )}
        </Modal>
      </PageBody>
    </Layout>
  );
}

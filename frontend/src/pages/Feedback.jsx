import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Star, Bug, Lightbulb, Send, Check, Clock } from "lucide-react";
import { feedbackApi, apiErr } from "@/api";
import { useAuth } from "@/context/AuthContext";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, Button, Spinner, Pill, EmptyState, Skeleton } from "@/components/ui";
import { fmtDate } from "@/constants";

const TYPES = [
  { id: "review", icon: Star, label: "Review", hint: "Tell us how HireFlow is working out for you" },
  { id: "bug", icon: Bug, label: "Report an issue", hint: "Something broken, wrong or confusing" },
  { id: "feature", icon: Lightbulb, label: "Suggest a feature", hint: "Something missing you'd like to see" },
];

const TYPE_LABEL = { review: "Review", bug: "Issue", feature: "Feature request" };
const STATUS_TONE = { new: "amber", read: "gray", actioned: "green" };

const MAX_SUBJECT = 200;
const MAX_MESSAGE = 5000;

export default function Feedback() {
  const { user } = useAuth();
  const [type, setType] = useState("review");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [history, setHistory] = useState(null);

  const loadHistory = () => {
    feedbackApi.mine().then((r) => setHistory(r.data)).catch(() => setHistory([]));
  };
  useEffect(loadHistory, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!subject.trim() || !message.trim()) return;
    setSending(true);
    try {
      const res = await feedbackApi.submit({ type, subject, message });
      if (res.data.email_sent === false) {
        // Saved, but the relay didn't take it. Say so rather than imply delivery.
        toast.success("Thanks — your message was received", {
          description: "It's saved and we'll pick it up shortly.",
        });
      } else {
        toast.success("Thanks — your message is on its way", {
          description: "We read everything that comes in.",
        });
      }
      setSubject("");
      setMessage("");
      loadHistory();
    } catch (err) {
      toast.error(apiErr(err, "Could not send your message. Please try again."));
    } finally {
      setSending(false);
    }
  };

  const active = TYPES.find((t) => t.id === type);

  return (
    <Layout>
      <Topbar title="Send Feedback" subtitle="Reviews, issues and ideas — they all reach us directly" />
      <PageBody>
        <div className="grid lg:grid-cols-[1.4fr_1fr] gap-6 items-start">
          <Card className="p-6">
            <form onSubmit={submit}>
              <label className="text-sm font-medium text-gray-700">What kind of message is this?</label>
              <div className="mt-2.5 grid sm:grid-cols-3 gap-2.5">
                {TYPES.map(({ id, icon: Icon, label }) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setType(id)}
                    className={`flex flex-col items-center gap-2 rounded-lg border px-3 py-3.5 text-sm font-medium transition-all duration-150 ${
                      type === id
                        ? "border-indigo bg-indigo-light text-indigo ring-2 ring-indigo/20"
                        : "border-gray-200 bg-white text-gray-700 hover:bg-gray-50"
                    }`}
                    aria-pressed={type === id}
                    data-testid={`feedback-type-${id}`}
                  >
                    <Icon size={18} />
                    {label}
                  </button>
                ))}
              </div>
              <p className="mt-2 text-xs text-gray-600">{active?.hint}</p>

              <div className="mt-5">
                <div className="flex items-center justify-between">
                  <label htmlFor="fb-subject" className="text-sm font-medium text-gray-700">Subject</label>
                  <span className="text-[11px] text-gray-400">{subject.length}/{MAX_SUBJECT}</span>
                </div>
                <input
                  id="fb-subject"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value.slice(0, MAX_SUBJECT))}
                  required
                  placeholder="A short summary"
                  className="mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm outline-none focus:border-indigo focus:ring-2 focus:ring-indigo/20"
                  data-testid="feedback-subject"
                />
              </div>

              <div className="mt-4">
                <div className="flex items-center justify-between">
                  <label htmlFor="fb-message" className="text-sm font-medium text-gray-700">Message</label>
                  <span className="text-[11px] text-gray-400">{message.length}/{MAX_MESSAGE}</span>
                </div>
                <textarea
                  id="fb-message"
                  value={message}
                  onChange={(e) => setMessage(e.target.value.slice(0, MAX_MESSAGE))}
                  required
                  rows={8}
                  placeholder="As much or as little detail as you like. For an issue, what you expected and what happened instead is the most useful thing."
                  className="mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm outline-none focus:border-indigo focus:ring-2 focus:ring-indigo/20 resize-y"
                  data-testid="feedback-message"
                />
              </div>

              <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-gray-600">
                  Sent as <span className="font-medium text-gray-800">{user?.email}</span> so we can reply.
                </p>
                <Button type="submit" disabled={sending || !subject.trim() || !message.trim()} data-testid="feedback-submit">
                  {sending ? <Spinner size={16} /> : <><Send size={15} /> Send message</>}
                </Button>
              </div>
            </form>
          </Card>

          <Card className="p-5">
            <h3 className="font-semibold text-gray-800 flex items-center gap-2">
              <Clock size={16} className="text-indigo" /> Your previous messages
            </h3>
            {history === null ? (
              <div className="mt-4 space-y-2.5">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div>
            ) : history.length ? (
              <ul className="mt-4 space-y-3" data-testid="feedback-history">
                {history.map((f) => (
                  <li key={f.id} className="border-b border-gray-100 last:border-0 pb-3 last:pb-0">
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-sm font-medium text-gray-800 break-words">{f.subject}</span>
                      <Pill tone={STATUS_TONE[f.status] || "gray"}>
                        {f.status === "actioned" ? <><Check size={11} className="mr-0.5" />Actioned</> : f.status}
                      </Pill>
                    </div>
                    <div className="mt-1 text-xs text-gray-600">
                      {TYPE_LABEL[f.type] || f.type} · {fmtDate(f.created_at)}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                icon={Send}
                title="Nothing sent yet"
                subtitle="Anything you send will be listed here so you can see it was received."
              />
            )}
          </Card>
        </div>
      </PageBody>
    </Layout>
  );
}

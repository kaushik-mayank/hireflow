import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Sparkles, Check } from "lucide-react";
import { jobsApi, aiApi, apiErr } from "@/api";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, Button, AIButton, Modal, Spinner } from "@/components/ui";
import { toast } from "sonner";

export default function JobCreate() {
  const [form, setForm] = useState({ title: "", department: "", openings_needed: 1, deadline: "", jd_text: "" });
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [enhanceLoading, setEnhanceLoading] = useState(false);
  const [enhanceModal, setEnhanceModal] = useState(null);
  const navigate = useNavigate();

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const validate = () => {
    const er = {};
    if (!form.title.trim()) er.title = "Job title is required";
    if (!form.jd_text.trim()) er.jd_text = "Job description is required";
    if (!form.openings_needed || form.openings_needed < 1) er.openings_needed = "At least 1 opening required";
    setErrors(er);
    return Object.keys(er).length === 0;
  };

  const save = async (status) => {
    if (!validate()) return;
    setSaving(true);
    try {
      const res = await jobsApi.create({ ...form, openings_needed: Number(form.openings_needed), status });
      toast.success(status === "draft" ? "Draft saved" : "Job created");
      navigate(`/jobs/${res.data.id}`);
    } catch (err) {
      toast.error(apiErr(err));
    } finally {
      setSaving(false);
    }
  };

  const enhance = async () => {
    if (!form.jd_text.trim()) {
      setErrors({ ...errors, jd_text: "Add a description to enhance" });
      return;
    }
    setEnhanceLoading(true);
    try {
      const r = await aiApi.enhanceJD(form.jd_text, form.title || "this role");
      setEnhanceModal(r.data);
    } catch (err) {
      toast.error(apiErr(err, "AI enhancement failed"));
    } finally {
      setEnhanceLoading(false);
    }
  };

  const acceptEnhance = () => {
    setForm({ ...form, jd_text: enhanceModal.enhanced });
    setEnhanceModal(null);
    toast.success("Enhanced description applied");
  };

  const field = (k) => `w-full rounded-lg border px-3.5 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo/20 ${errors[k] ? "border-coral" : "border-gray-200 focus:border-indigo"}`;

  return (
    <Layout>
      <Topbar
        title="Create Job"
        actions={<Button variant="ghost" onClick={() => navigate("/jobs")}><ArrowLeft size={16} /> Back</Button>}
      />
      <PageBody>
        <Card className="p-6 max-w-2xl">
          <div className="space-y-5">
            <div>
              <label className="text-sm font-medium text-gray-700">Job Title <span className="text-coral">*</span></label>
              <input value={form.title} onChange={set("title")} className={`mt-1.5 ${field("title")}`} placeholder="e.g. Senior Backend Engineer" data-testid="job-title" />
              {errors.title && <p className="text-xs text-coral mt-1">{errors.title}</p>}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-gray-700">Department</label>
                <input value={form.department} onChange={set("department")} className={`mt-1.5 ${field("department")}`} placeholder="Engineering" data-testid="job-department" />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">Openings Needed <span className="text-coral">*</span></label>
                <input type="number" min="1" value={form.openings_needed} onChange={set("openings_needed")} className={`mt-1.5 ${field("openings_needed")}`} data-testid="job-openings" />
                {errors.openings_needed && <p className="text-xs text-coral mt-1">{errors.openings_needed}</p>}
              </div>
            </div>

            <div>
              <label className="text-sm font-medium text-gray-700">Application Deadline</label>
              <input type="date" value={form.deadline} onChange={set("deadline")} className={`mt-1.5 ${field("deadline")}`} data-testid="job-deadline" />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-sm font-medium text-gray-700">Job Description <span className="text-coral">*</span></label>
                <AIButton loading={enhanceLoading} onClick={enhance} className="!py-1.5 !px-3 text-xs" data-testid="enhance-jd-btn">
                  {enhanceLoading ? "Enhancing..." : "Enhance JD with AI"}
                </AIButton>
              </div>
              <textarea value={form.jd_text} onChange={set("jd_text")} rows={10} className={`${field("jd_text")} font-mono text-[13px] leading-relaxed`} placeholder="Describe the role, responsibilities, requirements, and skills..." data-testid="job-jd" />
              {errors.jd_text && <p className="text-xs text-coral mt-1">{errors.jd_text}</p>}
            </div>

            <div className="flex gap-3 pt-2">
              <Button onClick={() => save("active")} disabled={saving} data-testid="job-create-submit">
                {saving ? <Spinner size={16} /> : "Create Job"}
              </Button>
              <Button variant="secondary" onClick={() => save("draft")} disabled={saving} data-testid="job-save-draft">Save as Draft</Button>
            </div>
          </div>
        </Card>
      </PageBody>

      <Modal open={!!enhanceModal} onClose={() => setEnhanceModal(null)} title="AI-Enhanced Job Description" width="max-w-4xl"
        footer={<>
          <Button variant="secondary" onClick={() => setEnhanceModal(null)} data-testid="enhance-dismiss">Dismiss</Button>
          <Button onClick={acceptEnhance} data-testid="enhance-accept"><Check size={16} /> Accept & Replace</Button>
        </>}>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Original</div>
            <div className="bg-gray-50 rounded-lg p-3 text-[13px] text-gray-600 whitespace-pre-wrap max-h-[50vh] overflow-y-auto font-mono leading-relaxed">{enhanceModal?.original}</div>
          </div>
          <div>
            <div className="text-xs font-semibold text-amber uppercase tracking-wide mb-2 flex items-center gap-1"><Sparkles size={12} /> Enhanced</div>
            <div className="bg-amber-light/30 border border-amber/20 rounded-lg p-3 text-[13px] text-gray-700 whitespace-pre-wrap max-h-[50vh] overflow-y-auto leading-relaxed">{enhanceModal?.enhanced}</div>
          </div>
        </div>
      </Modal>
    </Layout>
  );
}

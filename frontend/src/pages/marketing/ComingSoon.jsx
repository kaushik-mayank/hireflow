import { Check, Info } from "lucide-react";
import {
  Section, SectionHeading, PageHero, CTABand,
} from "@/components/marketing";
import { COMING_SOON, FEATURES } from "@/data/marketing";

/**
 * Roadmap teaser. Deliberately has no signup form, no waitlist and no email
 * capture — it exists to show direction, not to collect addresses.
 */

const STATUS_TONES = {
  "In design": "bg-indigo-light text-indigo",
  Planned: "bg-purple-light text-purple",
  Exploring: "bg-gray-100 text-gray-700",
};

function RoadmapCard({ item }) {
  const { icon: Icon, title, status, description } = item;
  return (
    <div className="flex flex-col rounded-xl border border-gray-200 bg-white p-5 shadow-soft transition-shadow duration-200 hover:shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div className="w-11 h-11 rounded-xl bg-purple-light flex items-center justify-center shrink-0">
          <Icon size={20} className="text-purple" />
        </div>
        {status && (
          <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${STATUS_TONES[status] || STATUS_TONES.Exploring}`}>
            {status}
          </span>
        )}
      </div>
      <h3 className="mt-4 font-semibold text-gray-800">{title}</h3>
      <p className="mt-1.5 text-sm text-gray-600 leading-relaxed">{description}</p>
    </div>
  );
}

export default function ComingSoon() {
  return (
    <>
      <PageHero
        eyebrow="Roadmap"
        title="What is coming to HireFlow"
        subtitle="The hiring flow works today — posting roles, ranking resumes, screening questions, pipeline, emails and reports. These are the pieces being built on top of it."
      />

      <Section tone="muted">
        <div className="mx-auto max-w-3xl rounded-xl border border-amber bg-amber-light px-5 py-4">
          <div className="flex items-start gap-3">
            <Info size={18} className="mt-0.5 shrink-0 text-[#92400e]" />
            <div className="text-sm text-[#92400e] leading-relaxed">
              <span className="font-semibold">None of this is built yet.</span> Everything below is
              planned work, not a shipped feature or a delivery commitment. Priorities shift based on
              what customers actually ask for, and some of these may change or be dropped.
            </div>
          </div>
        </div>

        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3 items-start">
          {COMING_SOON.map((item) => (
            <RoadmapCard key={item.id} item={item} />
          ))}
        </div>
      </Section>

      <Section>
        <SectionHeading
          eyebrow="Available now"
          title="What you can already use"
          subtitle="Everything on this list is live in the product today, not on the roadmap."
        />
        <div className="mt-12 mx-auto max-w-3xl grid gap-3 sm:grid-cols-2">
          {FEATURES.map((f) => (
            <div key={f.id} className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3">
              <div className="w-7 h-7 rounded-full bg-green-light flex items-center justify-center shrink-0">
                <Check size={15} className="text-green" />
              </div>
              <span className="text-sm font-medium text-gray-800">{f.title}</span>
            </div>
          ))}
        </div>
      </Section>

      <CTABand
        title="Use what is ready today"
        subtitle="The full hiring flow is live and free during early access. The roadmap above arrives on top of it."
        primary={{ to: "/signup", label: "Create your account" }}
        secondary={{ to: "/", label: "Back to overview" }}
      />
    </>
  );
}

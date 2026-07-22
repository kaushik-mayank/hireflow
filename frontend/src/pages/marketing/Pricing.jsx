import { Check, Info } from "lucide-react";
import {
  Section, SectionHeading, PageHero, LinkButton, CTABand, PlaceholderNote,
} from "@/components/marketing";

/**
 * Nothing here is billable. HireFlow is in early access and no payment is
 * collected anywhere in the product, so this page must not imply otherwise —
 * every tier shows an unset price and a contact-us action.
 */
const TIERS = [
  {
    id: "starter",
    name: "Starter",
    blurb: "For a single hiring manager filling roles as they open.",
    price: "Not set",
    note: "Free during early access",
    features: [
      "Job postings and hiring quotas",
      "Resume upload and text extraction",
      "AI resume ranking and scoring",
      "Screening question generation",
      "Visual hiring pipeline",
      "Email drafting",
    ],
    cta: { label: "Start free", to: "/signup" },
    highlight: false,
  },
  {
    id: "team",
    name: "Team",
    blurb: "For teams hiring across several roles or sites at once.",
    price: "Not set",
    note: "Pricing being finalised",
    features: [
      "Everything in Starter",
      "Higher resume and AI usage limits",
      "Candidate comparison tools",
      "Reports and hiring analytics",
      "Pipeline health insights",
      "Priority support",
    ],
    cta: { label: "Contact us", to: "/about" },
    highlight: true,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    blurb: "For groups hiring continuously across many locations.",
    price: "Talk to us",
    note: "Tailored to your volume",
    features: [
      "Everything in Team",
      "Volume-based limits",
      "Onboarding and migration help",
      "Custom data retention terms",
      "Security and compliance review",
      "Named point of contact",
    ],
    cta: { label: "Contact us", to: "/about" },
    highlight: false,
  },
];

const FAQS = [
  {
    q: "Can I be charged today?",
    a: "No. There is no billing anywhere in HireFlow right now — no card is collected and no payment can be taken. Every account is free while we are in early access.",
  },
  {
    q: "What happens when pricing launches?",
    a: "You will be told well before anything changes, and no account will be moved onto a paid plan without you actively choosing it. If a plan does not suit you, your data stays exportable.",
  },
  {
    q: "Are the tiers above final?",
    a: "No. The names, the limits and the split of features between tiers are all still being worked out. Treat this page as a direction of travel rather than a commitment.",
  },
  {
    q: "Does it cost more to hire for certain roles?",
    a: "No. Pricing will be based on how much you use the product, not on what kind of work you are hiring for. A shift-work posting and a senior technical posting cost the same.",
  },
  {
    q: "What counts against usage limits?",
    a: "Broadly: how many resumes you process and how many AI actions you run. Exact limits will be published alongside final pricing.",
  },
];

function TierCard({ tier }) {
  const { name, blurb, price, note, features, cta, highlight } = tier;
  return (
    <div
      className={`flex flex-col rounded-2xl border bg-white p-6 ${
        highlight ? "border-indigo shadow-lift ring-1 ring-indigo/20" : "border-gray-200 shadow-soft"
      }`}
      data-testid={`pricing-tier-${tier.id}`}
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-lg font-semibold text-gray-800">{name}</h3>
        {highlight && (
          <span className="rounded-full bg-indigo-light px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-indigo">
            Most expected
          </span>
        )}
      </div>
      <p className="mt-1.5 text-sm text-gray-600 leading-relaxed">{blurb}</p>

      <div className="mt-6 pb-6 border-b border-gray-100">
        <div className="text-3xl font-bold text-gray-800">{price}</div>
        <div className="mt-1 text-xs text-gray-600">{note}</div>
      </div>

      <ul className="mt-6 space-y-2.5 flex-1">
        {features.map((f) => (
          <li key={f} className="flex items-start gap-2.5 text-sm text-gray-700">
            <Check size={16} className="mt-0.5 shrink-0 text-green" />
            {f}
          </li>
        ))}
      </ul>

      <LinkButton
        to={cta.to}
        variant={highlight ? "primary" : "secondary"}
        size="lg"
        className="mt-7 w-full"
      >
        {cta.label}
      </LinkButton>
    </div>
  );
}

export default function Pricing() {
  return (
    <>
      <PageHero
        eyebrow="Early access"
        title="Pricing is still being worked out"
        subtitle="HireFlow is in testing. There is no billing in the product today and nothing on this page can be purchased — the tiers below show where we are heading, not what you will be charged."
      />

      <Section tone="muted">
        <div className="mx-auto max-w-3xl rounded-xl border border-amber bg-amber-light px-5 py-4">
          <div className="flex items-start gap-3">
            <Info size={18} className="mt-0.5 shrink-0 text-[#92400e]" />
            <div className="text-sm text-[#92400e] leading-relaxed">
              <span className="font-semibold">In testing — no live billing.</span> Every account is
              currently free and no payment details are collected anywhere in HireFlow. Prices,
              limits and tier names are all placeholders and will change before launch.
            </div>
          </div>
        </div>

        <div className="mt-12 grid gap-6 lg:grid-cols-3 items-start">
          {TIERS.map((t) => (
            <TierCard key={t.id} tier={t} />
          ))}
        </div>

        <div className="mt-10 mx-auto max-w-3xl">
          <PlaceholderNote>
            Tier names, feature splits and every price on this page are provisional and need your
            sign-off before launch. Edit them in
            <code className="mx-1 rounded bg-gray-200 px-1 py-0.5 font-mono text-[11px]">src/pages/marketing/Pricing.jsx</code>.
          </PlaceholderNote>
        </div>
      </Section>

      <Section>
        <SectionHeading eyebrow="Questions" title="Before you ask" />
        <div className="mt-10 mx-auto max-w-3xl space-y-4">
          {FAQS.map(({ q, a }) => (
            <div key={q} className="rounded-xl border border-gray-200 bg-white p-5 shadow-soft">
              <h3 className="font-semibold text-gray-800">{q}</h3>
              <p className="mt-1.5 text-sm text-gray-600 leading-relaxed">{a}</p>
            </div>
          ))}
        </div>
      </Section>

      <CTABand
        title="Free while we are in early access"
        subtitle="Create an account and use the whole hiring flow today. Pricing will not arrive without warning."
        primary={{ to: "/signup", label: "Create your account" }}
        secondary={{ to: "/coming-soon", label: "See the roadmap" }}
      />
    </>
  );
}

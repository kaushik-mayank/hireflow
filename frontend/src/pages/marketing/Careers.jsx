import { Mail, MapPin, Clock3 } from "lucide-react";
import {
  Section, SectionHeading, PageHero, CTABand, PlaceholderNote, Prose, ProseHeading,
} from "@/components/marketing";

/**
 * Structure only. There are no live vacancies — OPEN_ROLES is intentionally
 * empty so the page renders its honest "nothing open right now" state.
 * Drop role objects in and the listing appears automatically.
 */

/** @type {{id: string, title: string, team: string, location: string, type: string, summary: string}[]} */
const OPEN_ROLES = [];

/** TODO(owner): replace with the real careers address before launch. */
const CAREERS_EMAIL = "careers@example.com";

const WHAT_WE_OFFER = [
  {
    id: "remote",
    icon: MapPin,
    title: "Work where you work best",
    body: "Placeholder — describe your location policy, whether that is remote-first, hybrid or a specific office.",
  },
  {
    id: "hours",
    icon: Clock3,
    title: "Sensible hours",
    body: "Placeholder — describe working hours, flexibility and any expectations around availability.",
  },
  {
    id: "growth",
    icon: Mail,
    title: "Room to grow",
    body: "Placeholder — describe progression, learning budget, or whatever you actually offer here.",
  },
];

function RoleCard({ role }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-4 rounded-xl border border-gray-200 bg-white p-5 shadow-soft">
      <div className="min-w-0 flex-1">
        <h3 className="font-semibold text-gray-800">{role.title}</h3>
        <p className="mt-1 text-sm text-gray-600 leading-relaxed">{role.summary}</p>
        <div className="mt-2.5 flex flex-wrap gap-2">
          {[role.team, role.location, role.type].filter(Boolean).map((meta) => (
            <span key={meta} className="rounded-md bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-700">
              {meta}
            </span>
          ))}
        </div>
      </div>
      <a
        href={`mailto:${CAREERS_EMAIL}?subject=${encodeURIComponent(`Application — ${role.title}`)}`}
        className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-soft transition-all duration-150 hover:bg-gray-50 active:translate-y-px shrink-0"
      >
        Apply
      </a>
    </div>
  );
}

function NoOpenRoles() {
  return (
    <div className="rounded-xl border border-dashed border-gray-400 bg-gray-50 px-6 py-12 text-center">
      <h3 className="font-semibold text-gray-800">No open positions right now</h3>
      <p className="mt-2 mx-auto max-w-md text-sm text-gray-600 leading-relaxed">
        We are not actively recruiting at the moment. If you think you would be a good fit anyway,
        send us a note — we keep speculative applications on file and come back to them when
        something opens up.
      </p>
      <a
        href={`mailto:${CAREERS_EMAIL}?subject=${encodeURIComponent("Speculative application")}`}
        className="mt-6 inline-flex items-center justify-center gap-2 rounded-lg bg-indigo px-5 py-3 text-[15px] font-medium text-white shadow-soft transition-all duration-150 hover:brightness-110 active:translate-y-px"
      >
        <Mail size={16} /> Send a speculative application
      </a>
    </div>
  );
}

export default function Careers() {
  return (
    <>
      <PageHero
        eyebrow="Careers"
        title="Come build hiring software for everyone else"
        subtitle="We are a small team working on a problem that affects almost every organisation and gets almost no good tooling outside of one narrow industry."
      />

      <Section>
        <div className="mx-auto max-w-3xl">
          <PlaceholderNote className="mb-10">
            This page is structure only. There are no real vacancies listed, and the culture, benefits
            and contact details below are all written as scaffolding. Add roles to the
            <code className="mx-1 rounded bg-gray-200 px-1 py-0.5 font-mono text-[11px]">OPEN_ROLES</code>
            array in
            <code className="mx-1 rounded bg-gray-200 px-1 py-0.5 font-mono text-[11px]">src/pages/marketing/Careers.jsx</code>
            and the listing below fills in automatically.
          </PlaceholderNote>

          <Prose>
            <ProseHeading>Working here</ProseHeading>
            <p>
              Placeholder — describe what it is actually like to work at your company. Team size, how
              decisions get made, what a normal week looks like, and what you expect from people.
            </p>
            <p>
              Placeholder — describe your hiring process honestly, including how many stages there are
              and roughly how long it takes. Candidates appreciate knowing this up front, and it is a
              reasonable thing to expect from a company selling hiring software.
            </p>
          </Prose>
        </div>
      </Section>

      <Section tone="muted">
        <SectionHeading eyebrow="Open positions" title="Roles we are hiring for" />
        <div className="mt-12 mx-auto max-w-3xl space-y-4">
          {OPEN_ROLES.length > 0 ? OPEN_ROLES.map((r) => <RoleCard key={r.id} role={r} />) : <NoOpenRoles />}
        </div>
      </Section>

      <Section>
        <SectionHeading eyebrow="What we offer" title="The practical bits" />
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {WHAT_WE_OFFER.map(({ id, icon: Icon, title, body }) => (
            <div key={id} className="rounded-xl border border-gray-200 bg-white p-5 shadow-soft">
              <div className="w-11 h-11 rounded-xl bg-indigo-light flex items-center justify-center">
                <Icon size={20} className="text-indigo" />
              </div>
              <h3 className="mt-4 font-semibold text-gray-800">{title}</h3>
              <p className="mt-1.5 text-sm text-gray-600 leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
        <div className="mt-10 mx-auto max-w-2xl">
          <PlaceholderNote>
            Replace all three of these with what you genuinely offer, and swap the careers address —
            it currently points at an example domain.
          </PlaceholderNote>
        </div>
      </Section>

      <CTABand
        title="Nothing listed that fits?"
        subtitle="Tell us what you do and why this problem interests you. We read everything that comes in."
        primary={{ to: "/about", label: "About us" }}
        secondary={{ to: "/", label: "Back to overview" }}
      />
    </>
  );
}

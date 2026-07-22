import { Mail } from "lucide-react";
import {
  Section, SectionHeading, PageHero, CTABand, PlaceholderNote, Prose, ProseHeading,
} from "@/components/marketing";

/**
 * Company facts the owner needs to supply are marked with PlaceholderNote and
 * kept short on purpose — easier to replace than to unpick from long prose.
 */

const VALUES = [
  {
    id: "every-role",
    title: "Every role deserves the same tooling",
    body: "Recruitment software has spent twenty years being built for office hiring. The people filling night shifts, ward rotas and workshop benches got spreadsheets. We think that is backwards, and we build accordingly.",
  },
  {
    id: "judgement",
    title: "AI does the reading, you do the deciding",
    body: "Nothing here hires or rejects anyone on its own. The AI does the first pass so a human spends their attention on the shortlist instead of the pile. Every score comes with its reasoning shown.",
  },
  {
    id: "candidates",
    title: "Candidates are people, not records",
    body: "Applicants hand over their work history and contact details in good faith. We treat that data carefully, and we build features — like replies that actually get sent — that make the process less painful from their side too.",
  },
  {
    id: "plain",
    title: "Plain language, no theatre",
    body: "No invented metrics, no fake urgency, no pricing you have to book a call to see. If something is unfinished, we say so — this whole site says so in several places.",
  },
];

/** TODO(owner): replace with the real contact address before launch. */
const CONTACT_EMAIL = "hello@example.com";

export default function About() {
  return (
    <>
      <PageHero
        eyebrow="About"
        title="Hiring software that does not assume a desk"
        subtitle="HireFlow started from a simple observation: the tools that make hiring bearable were only ever built for one kind of job."
      />

      <Section>
        <div className="mx-auto max-w-3xl">
          <PlaceholderNote className="mb-10">
            The story, founding details and contact address below are written as a starting point and
            need replacing with your real company facts. Everything on this page lives in
            <code className="mx-1 rounded bg-gray-200 px-1 py-0.5 font-mono text-[11px]">src/pages/marketing/About.jsx</code>.
          </PlaceholderNote>

          <Prose>
            <ProseHeading>Why we built it</ProseHeading>
            <p>
              Most hiring tools are designed around a familiar shape of job: salaried, office-based,
              hired once and kept for years. That shape describes a minority of the work actually
              being done. Hospitals hire in rotas. Warehouses hire in bursts before peak. Restaurants,
              building sites, care homes and schools all hire constantly, in volume, under time
              pressure — and mostly with a spreadsheet and an inbox.
            </p>
            <p>
              The result is that the teams with the hardest hiring problem get the least help with it.
              A recruiter filling twelve warehouse roles before December is doing more work, faster,
              than one filling a single engineering position, and has fewer tools to do it with.
            </p>
            <p>
              HireFlow is our attempt to close that gap. The same AI that ranks a backend engineer
              against a job description ranks a paramedic, a chef or a machine operator — because it
              reads what the role actually asks for instead of assuming.
            </p>

            <ProseHeading>What we are today</ProseHeading>
            <p>
              A small team, an early-access product, and a hiring flow that works end to end: post a
              role, upload the applications, let the AI rank and analyse them, move people through a
              visual pipeline, and send the replies. Reports and analytics sit on top of it.
            </p>
            <p>
              We are being deliberate about what comes next rather than shipping a long feature list
              badly. The roadmap is published openly, and the things on it are the things customers
              keep asking for.
            </p>

            <ProseHeading>Where we are going</ProseHeading>
            <p>
              The near-term work is about removing the remaining manual steps around the edges of the
              flow — connecting the inbox you already use, scheduling interviews against real shift
              patterns, publishing a posting to the boards that matter for your sector, and tracking
              the certifications a role legally requires.
            </p>
          </Prose>
        </div>
      </Section>

      <Section tone="muted">
        <SectionHeading eyebrow="What we believe" title="How we make decisions" />
        <div className="mt-12 grid gap-5 md:grid-cols-2">
          {VALUES.map((v) => (
            <div key={v.id} className="rounded-xl border border-gray-200 bg-white p-6 shadow-soft">
              <h3 className="font-semibold text-gray-800">{v.title}</h3>
              <p className="mt-2 text-sm text-gray-600 leading-relaxed">{v.body}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section>
        <div className="mx-auto max-w-2xl text-center">
          <SectionHeading
            eyebrow="Get in touch"
            title="Talk to us"
            subtitle="Questions about the product, pricing, a specific hiring problem, or whether HireFlow fits how your team works — we would rather hear it than guess."
          />
          <div className="mt-8 inline-flex items-center gap-2.5 rounded-xl border border-gray-200 bg-white px-5 py-3.5 shadow-soft">
            <Mail size={17} className="text-indigo" />
            <a href={`mailto:${CONTACT_EMAIL}`} className="text-[15px] font-medium text-gray-800 hover:text-indigo">
              {CONTACT_EMAIL}
            </a>
          </div>
          <div className="mt-6 mx-auto max-w-lg">
            <PlaceholderNote>
              Replace this with your real contact address — it currently points at an example domain.
            </PlaceholderNote>
          </div>
        </div>
      </Section>

      <CTABand
        title="See whether it fits how you hire"
        subtitle="Free while we are in early access. Create an account and run your own roles through it."
        primary={{ to: "/signup", label: "Create your account" }}
        secondary={{ to: "/", label: "Back to overview" }}
      />
    </>
  );
}

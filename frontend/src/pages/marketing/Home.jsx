import { useEffect, useState } from "react";
import { ArrowRight, Check, Clock, Users, FileQuestion } from "lucide-react";
import {
  Section, SectionHeading, Eyebrow, FeatureCard, LinkButton, CTABand,
  TestimonialCard, PlaceholderNote, CONTAINER,
} from "@/components/marketing";
import { FEATURES, STEPS, INDUSTRIES, TESTIMONIALS, HERO_ROLES, COMING_SOON } from "@/data/marketing";

const ROTATE_MS = 2400;

/** Cycles job titles in the hero. Sits on its own line so the changing word
 *  length never reflows the rest of the headline. */
function RotatingRole() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    if (reduced) return undefined;
    const timer = setInterval(() => setIndex((i) => (i + 1) % HERO_ROLES.length), ROTATE_MS);
    return () => clearInterval(timer);
  }, []);

  return (
    <span key={index} className="text-indigo inline-block animate-fade-in">
      {HERO_ROLES[index]}.
    </span>
  );
}

function Hero() {
  return (
    <section className="bg-navy relative overflow-hidden">
      <div className={`${CONTAINER} pt-20 pb-20 sm:pt-24 sm:pb-24 relative z-10`}>
        <div className="max-w-3xl">
          <Eyebrow tone="navy">Built for every kind of hiring</Eyebrow>

          <h1 className="mt-5 text-4xl sm:text-[52px] font-semibold text-white tracking-tight leading-[1.1]">
            Hire your next
            <br />
            <RotatingRole />
          </h1>

          <p className="mt-6 text-white/60 text-base sm:text-lg leading-relaxed max-w-xl">
            HireFlow reads every resume, ranks it against your role, writes the screening questions
            and drafts the replies — so a stack of applications becomes a shortlist the same day it
            arrives.
          </p>

          <div className="mt-9 flex flex-wrap gap-3">
            <LinkButton to="/signup" variant="onNavy" size="lg" data-testid="hero-register">
              Get started free <ArrowRight size={16} />
            </LinkButton>
            <LinkButton to="/coming-soon" variant="outlineNavy" size="lg">
              See what's next
            </LinkButton>
          </div>

          <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2">
            {["No credit card required", "Early access", "Set up in minutes"].map((item) => (
              <div key={item} className="flex items-center gap-2 text-white/45 text-sm">
                <Check size={15} className="text-green" />
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="absolute -right-32 -bottom-40 w-[28rem] h-[28rem] rounded-full bg-indigo/20 blur-3xl" aria-hidden="true" />
      <div className="absolute right-1/4 -top-24 w-72 h-72 rounded-full bg-purple/20 blur-3xl" aria-hidden="true" />
    </section>
  );
}

const PROBLEMS = [
  {
    icon: Clock,
    title: "The good ones are gone by Friday",
    body: "Strong applicants take the first offer they get. When screening takes a week, you are competing for whoever is left.",
  },
  {
    icon: Users,
    title: "Too many resumes, too little time",
    body: "One posting can pull hundreds of applications. Reading them properly is a full-time job that nobody actually has.",
  },
  {
    icon: FileQuestion,
    title: "Nobody knows where anyone is",
    body: "Half the pipeline lives in a spreadsheet, half in an inbox, and the candidate waiting on a reply lives in neither.",
  },
];

function Problem() {
  return (
    <Section tone="muted">
      <SectionHeading
        eyebrow="The problem"
        title="Hiring breaks the same way everywhere"
        subtitle="Whether you are filling a night shift, a ward rota or an engineering team, the bottleneck is the same — there is more applicant than there is hour."
      />
      <div className="mt-12 grid gap-5 md:grid-cols-3">
        {PROBLEMS.map(({ icon: Icon, title, body }) => (
          <div key={title} className="bg-white border border-gray-200 rounded-xl shadow-soft p-5">
            <div className="w-11 h-11 rounded-xl bg-coral-light flex items-center justify-center">
              <Icon size={20} className="text-coral" />
            </div>
            <h3 className="mt-4 font-semibold text-gray-800">{title}</h3>
            <p className="mt-1.5 text-sm text-gray-600 leading-relaxed">{body}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}

function Features() {
  return (
    <Section id="features">
      <SectionHeading
        eyebrow="What you get"
        title="AI at every step that actually costs you time"
        subtitle="Not a chatbot bolted onto a database. Each feature replaces a specific job somebody is currently doing by hand."
      />
      <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f) => (
          <FeatureCard key={f.id} icon={f.icon} title={f.title}>
            {f.description}
          </FeatureCard>
        ))}
      </div>
    </Section>
  );
}

function HowItWorks() {
  return (
    <Section tone="muted">
      <SectionHeading eyebrow="How it works" title="From open role to signed offer" />
      <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((step, i) => (
          <div key={step.id} className="relative bg-white border border-gray-200 rounded-xl shadow-soft p-5">
            <div className="w-9 h-9 rounded-lg bg-navy text-white flex items-center justify-center text-sm font-semibold">
              {i + 1}
            </div>
            <h3 className="mt-4 font-semibold text-gray-800">{step.title}</h3>
            <p className="mt-1.5 text-sm text-gray-600 leading-relaxed">{step.description}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}

function Industries() {
  return (
    <Section>
      <SectionHeading
        eyebrow="Every industry"
        title="It does not assume you are hiring for a desk"
        subtitle="The AI works out what matters from the role you describe. A forklift ticket, an ICU rotation and a distributed systems background are all read on their own terms."
      />
      <div className="mt-12 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {INDUSTRIES.map(({ id, icon: Icon, label, example }) => (
          <div key={id} className="flex items-start gap-3 rounded-xl border border-gray-200 bg-white p-4">
            <div className="w-9 h-9 rounded-lg bg-teal-light flex items-center justify-center shrink-0">
              <Icon size={17} className="text-teal" />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold text-gray-800">{label}</div>
              <div className="text-xs text-gray-600 mt-0.5">{example}</div>
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}

function SocialProof() {
  return (
    <Section tone="muted">
      <SectionHeading
        eyebrow="Social proof"
        title="What teams say"
        subtitle="HireFlow is in early access. The quotes below are illustrative samples, not real customers — they will be replaced with genuine reviews as they come in."
      />
      <div className="mt-10 mx-auto max-w-2xl">
        <PlaceholderNote>
          These testimonials are written examples used to lay out the page. Replace them in
          <code className="mx-1 rounded bg-gray-200 px-1 py-0.5 font-mono text-[11px]">src/data/marketing.js</code>
          and remove the <code className="rounded bg-gray-200 px-1 py-0.5 font-mono text-[11px]">isPlaceholder</code> flag
          once real reviews are collected.
        </PlaceholderNote>
      </div>
      <div className="mt-8 grid gap-5 md:grid-cols-3">
        {TESTIMONIALS.slice(0, 3).map((t) => (
          <TestimonialCard key={t.id} testimonial={t} />
        ))}
      </div>
      <div className="mt-8 text-center">
        <LinkButton to="/reviews" variant="secondary">
          Read all reviews <ArrowRight size={15} />
        </LinkButton>
      </div>
    </Section>
  );
}

function ComingSoonTeaser() {
  return (
    <Section>
      <SectionHeading
        eyebrow="On the roadmap"
        title="What we are building next"
        subtitle="The hiring flow works today. These are the pieces coming after it."
      />
      <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {COMING_SOON.slice(0, 4).map(({ id, icon: Icon, title, description }) => (
          <div key={id} className="rounded-xl border border-gray-200 bg-white p-5">
            <div className="w-11 h-11 rounded-xl bg-purple-light flex items-center justify-center">
              <Icon size={20} className="text-purple" />
            </div>
            <h3 className="mt-4 font-semibold text-gray-800 text-[15px]">{title}</h3>
            <p className="mt-1.5 text-sm text-gray-600 leading-relaxed line-clamp-3">{description}</p>
          </div>
        ))}
      </div>
      <div className="mt-8 text-center">
        <LinkButton to="/coming-soon" variant="secondary">
          See the full roadmap <ArrowRight size={15} />
        </LinkButton>
      </div>
    </Section>
  );
}

export default function Home() {
  return (
    <>
      <Hero />
      <Problem />
      <Features />
      <HowItWorks />
      <Industries />
      <SocialProof />
      <ComingSoonTeaser />
      <CTABand
        title="Start hiring with a shortlist, not a stack"
        subtitle="Create an account and rank your first set of resumes today. No card, no sales call."
        primary={{ to: "/signup", label: "Create your account" }}
        secondary={{ to: "/pricing", label: "See pricing" }}
      />
    </>
  );
}

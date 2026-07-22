import { useMemo, useState } from "react";
import { MessageSquareQuote } from "lucide-react";
import {
  Section, PageHero, CTABand, PlaceholderNote, TestimonialCard, Rating,
} from "@/components/marketing";
import { TESTIMONIALS } from "@/data/marketing";

/**
 * Fully data-driven — everything renders from the TESTIMONIALS array in
 * src/data/marketing.js, so real reviews can be dropped in without touching
 * this file. The industry filter and the average rating derive themselves.
 */

const ALL = "All industries";

function EmptyState() {
  return (
    <div className="rounded-xl border border-dashed border-gray-400 bg-gray-50 px-6 py-16 text-center">
      <div className="mx-auto w-14 h-14 rounded-2xl bg-indigo-light flex items-center justify-center">
        <MessageSquareQuote size={26} className="text-indigo" />
      </div>
      <h3 className="mt-4 font-semibold text-gray-800">No reviews yet</h3>
      <p className="mt-1.5 mx-auto max-w-sm text-sm text-gray-600 leading-relaxed">
        Once customers start sharing their experience, their reviews will appear here.
      </p>
    </div>
  );
}

export default function Reviews() {
  const [industry, setIndustry] = useState(ALL);

  const industries = useMemo(
    () => [ALL, ...Array.from(new Set(TESTIMONIALS.map((t) => t.industry).filter(Boolean)))],
    []
  );

  const visible = useMemo(
    () => (industry === ALL ? TESTIMONIALS : TESTIMONIALS.filter((t) => t.industry === industry)),
    [industry]
  );

  const average = useMemo(() => {
    const rated = TESTIMONIALS.filter((t) => typeof t.rating === "number");
    if (!rated.length) return null;
    return Math.round((rated.reduce((sum, t) => sum + t.rating, 0) / rated.length) * 10) / 10;
  }, []);

  const anyPlaceholder = TESTIMONIALS.some((t) => t.isPlaceholder);

  return (
    <>
      <PageHero
        eyebrow="Reviews"
        title="What people say about HireFlow"
        subtitle="Feedback from teams hiring across very different kinds of work — because the test of this product is whether it holds up outside one industry."
      >
        {average !== null && (
          <div className="mt-7 flex items-center gap-3">
            <Rating value={Math.round(average)} />
            <span className="text-white/70 text-sm">
              {average} average · {TESTIMONIALS.length} review{TESTIMONIALS.length === 1 ? "" : "s"}
            </span>
          </div>
        )}
      </PageHero>

      <Section tone="muted">
        {anyPlaceholder && (
          <div className="mx-auto max-w-3xl mb-10">
            <PlaceholderNote>
              Some or all of the reviews below are illustrative samples, not real customers — each one
              is individually marked. Replace them in
              <code className="mx-1 rounded bg-gray-200 px-1 py-0.5 font-mono text-[11px]">src/data/marketing.js</code>
              and drop the
              <code className="mx-1 rounded bg-gray-200 px-1 py-0.5 font-mono text-[11px]">isPlaceholder</code>
              flag as genuine reviews come in. This whole page renders from that array, so nothing
              here needs editing.
            </PlaceholderNote>
          </div>
        )}

        {industries.length > 2 && (
          <div className="flex flex-wrap justify-center gap-2 mb-10" role="group" aria-label="Filter reviews by industry">
            {industries.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => setIndustry(name)}
                className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors duration-150 ${
                  industry === name
                    ? "bg-indigo text-white shadow-soft"
                    : "bg-white text-gray-700 border border-gray-200 hover:bg-gray-50"
                }`}
                aria-pressed={industry === name}
              >
                {name}
              </button>
            ))}
          </div>
        )}

        {visible.length > 0 ? (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 items-start">
            {visible.map((t) => (
              <TestimonialCard key={t.id} testimonial={t} />
            ))}
          </div>
        ) : (
          <EmptyState />
        )}
      </Section>

      <CTABand
        title="Try it on your own hiring"
        subtitle="The fairest review is the one you write yourself. Free while we are in early access."
        primary={{ to: "/signup", label: "Create your account" }}
        secondary={{ to: "/pricing", label: "See pricing" }}
      />
    </>
  );
}

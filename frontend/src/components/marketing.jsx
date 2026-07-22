import { Link } from "react-router-dom";
import { Hexagon, Pencil, Star } from "lucide-react";

/**
 * Shared building blocks for the public marketing site.
 *
 * Deliberately reuses the app's existing tokens — navy/indigo palette, soft
 * shadows, DM Sans, the rounded-xl card treatment from components/ui.jsx — so
 * the pre-login site and the product read as one system rather than two.
 */

export const CONTAINER = "max-w-6xl mx-auto px-6 sm:px-8";

export function Logo({ tone = "dark", className = "", to = "/" }) {
  return (
    <Link to={to} className={`flex items-center gap-2 shrink-0 ${className}`}>
      <Hexagon size={22} className="text-indigo" fill="#4f6ef7" />
      <span className={`text-[17px] font-semibold tracking-tight ${tone === "light" ? "text-white" : "text-gray-800"}`}>
        HireFlow
      </span>
    </Link>
  );
}

/* Mirrors the Button variants in components/ui.jsx, but renders a router Link.
   Kept in sync by hand — if Button's classes change, change these too. */
const BTN_BASE =
  "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-150 active:translate-y-px";

const BTN_VARIANTS = {
  primary: "bg-indigo text-white hover:brightness-110 shadow-soft",
  secondary: "bg-white text-gray-700 border border-gray-200 hover:bg-gray-50",
  ghost: "text-gray-600 hover:bg-gray-100",
  onNavy: "bg-white text-navy hover:bg-gray-100 shadow-soft",
  outlineNavy: "border border-white/25 text-white hover:bg-white/10",
};

const BTN_SIZES = {
  sm: "text-sm px-3 py-2",
  md: "text-sm px-4 py-2",
  lg: "text-[15px] px-5 py-3",
};

export function LinkButton({ to, variant = "primary", size = "md", className = "", children, ...props }) {
  return (
    <Link to={to} className={`${BTN_BASE} ${BTN_VARIANTS[variant]} ${BTN_SIZES[size]} ${className}`} {...props}>
      {children}
    </Link>
  );
}

export function Section({ tone = "light", className = "", children, id }) {
  const tones = { light: "bg-white", muted: "bg-gray-50", navy: "bg-navy" };
  return (
    <section id={id} className={`${tones[tone]} py-16 sm:py-20 ${className}`}>
      <div className={CONTAINER}>{children}</div>
    </section>
  );
}

export function Eyebrow({ children, tone = "light" }) {
  const styles =
    tone === "navy"
      ? "bg-white/10 text-indigo-light"
      : "bg-indigo-light text-indigo";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wider ${styles}`}>
      {children}
    </span>
  );
}

export function SectionHeading({ eyebrow, title, subtitle, align = "center", tone = "light" }) {
  const onNavy = tone === "navy";
  return (
    <div className={align === "center" ? "text-center mx-auto max-w-2xl" : "max-w-2xl"}>
      {eyebrow && <Eyebrow tone={tone}>{eyebrow}</Eyebrow>}
      <h2 className={`mt-4 text-2xl sm:text-[32px] font-semibold tracking-tight leading-tight ${onNavy ? "text-white" : "text-gray-800"}`}>
        {title}
      </h2>
      {subtitle && (
        <p className={`mt-3.5 text-[15px] leading-relaxed ${onNavy ? "text-white/55" : "text-gray-600"}`}>
          {subtitle}
        </p>
      )}
    </div>
  );
}

export function FeatureCard({ icon: Icon, title, children }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-soft p-5 transition-shadow duration-200 hover:shadow-card">
      <div className="w-11 h-11 rounded-xl bg-indigo-light flex items-center justify-center">
        <Icon size={20} className="text-indigo" />
      </div>
      <h3 className="mt-4 font-semibold text-gray-800">{title}</h3>
      <p className="mt-1.5 text-sm text-gray-600 leading-relaxed">{children}</p>
    </div>
  );
}

/**
 * Marks invented copy as invented.
 *
 * Uses a neutral dashed treatment rather than the amber accent on purpose —
 * amber means "AI" everywhere else in this product and that convention is
 * worth protecting.
 */
export function PlaceholderNote({ children, className = "" }) {
  return (
    <div className={`flex items-start gap-2.5 rounded-lg border border-dashed border-gray-400 bg-gray-50 px-4 py-3 text-xs leading-relaxed text-gray-600 ${className}`}>
      <Pencil size={14} className="mt-0.5 shrink-0 text-gray-400" />
      <p>
        <span className="font-semibold text-gray-700">Placeholder content — </span>
        {children}
      </p>
    </div>
  );
}

export function Stat({ value, label, tone = "light" }) {
  const onNavy = tone === "navy";
  return (
    <div>
      <div className={`text-3xl font-bold ${onNavy ? "text-indigo" : "text-gray-800"}`}>{value}</div>
      <div className={`text-xs mt-1 ${onNavy ? "text-white/45" : "text-gray-600"}`}>{label}</div>
    </div>
  );
}

export function Rating({ value = 5 }) {
  return (
    <div className="flex gap-0.5" aria-label={`${value} out of 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          size={14}
          className={i <= value ? "text-amber" : "text-gray-200"}
          fill={i <= value ? "#f59e0b" : "#e5e7eb"}
        />
      ))}
    </div>
  );
}

export function TestimonialCard({ testimonial }) {
  const { quote, name, title, org, industry, rating, isPlaceholder } = testimonial;
  return (
    <figure className="flex flex-col bg-white border border-gray-200 rounded-xl shadow-soft p-5">
      <Rating value={rating} />
      <blockquote className="mt-3.5 flex-1 text-[15px] text-gray-700 leading-relaxed">“{quote}”</blockquote>
      <figcaption className="mt-5 pt-4 border-t border-gray-100">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-sm font-semibold text-gray-800 truncate">{name}</div>
            <div className="text-xs text-gray-600 truncate">{title} · {org}</div>
          </div>
          {industry && (
            <span className="shrink-0 rounded-md bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-700">
              {industry}
            </span>
          )}
        </div>
        {isPlaceholder && (
          <div className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-dashed border-gray-400 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-gray-600">
            <Pencil size={10} /> Sample — not a real customer
          </div>
        )}
      </figcaption>
    </figure>
  );
}

/** Full-bleed navy call-to-action band. Matches the auth pages' brand panel. */
export function CTABand({ title, subtitle, primary, secondary }) {
  return (
    <section className="bg-navy relative overflow-hidden">
      <div className={`${CONTAINER} py-16 sm:py-20 relative z-10 text-center`}>
        <h2 className="text-2xl sm:text-[32px] font-semibold text-white tracking-tight leading-tight">{title}</h2>
        {subtitle && <p className="mt-3.5 text-white/55 text-[15px] max-w-xl mx-auto leading-relaxed">{subtitle}</p>}
        <div className="mt-8 flex flex-wrap gap-3 justify-center">
          {primary && <LinkButton to={primary.to} variant="onNavy" size="lg">{primary.label}</LinkButton>}
          {secondary && <LinkButton to={secondary.to} variant="outlineNavy" size="lg">{secondary.label}</LinkButton>}
        </div>
      </div>
      <div className="absolute -right-24 -bottom-32 w-96 h-96 rounded-full bg-indigo/20 blur-3xl" aria-hidden="true" />
      <div className="absolute -left-20 -top-24 w-72 h-72 rounded-full bg-purple/20 blur-3xl" aria-hidden="true" />
    </section>
  );
}

/** Simple page header for the secondary marketing pages. */
export function PageHero({ eyebrow, title, subtitle, children }) {
  return (
    <section className="bg-navy relative overflow-hidden">
      <div className={`${CONTAINER} pt-16 pb-16 sm:pt-20 sm:pb-20 relative z-10`}>
        <div className="max-w-2xl">
          {eyebrow && <Eyebrow tone="navy">{eyebrow}</Eyebrow>}
          <h1 className="mt-4 text-3xl sm:text-[40px] font-semibold text-white tracking-tight leading-[1.15]">
            {title}
          </h1>
          {subtitle && <p className="mt-4 text-white/55 text-[15px] sm:text-base leading-relaxed">{subtitle}</p>}
          {children}
        </div>
      </div>
      <div className="absolute -right-24 -bottom-32 w-96 h-96 rounded-full bg-indigo/20 blur-3xl" aria-hidden="true" />
      <div className="absolute right-40 -top-20 w-56 h-56 rounded-full bg-purple/20 blur-3xl" aria-hidden="true" />
    </section>
  );
}

/** Prose wrapper for the long-form legal and about pages. */
export function Prose({ children, className = "" }) {
  return <div className={`text-[15px] text-gray-700 leading-relaxed space-y-4 ${className}`}>{children}</div>;
}

export function ProseHeading({ children, id }) {
  return (
    <h2 id={id} className="text-lg font-semibold text-gray-800 pt-6 first:pt-0 scroll-mt-24">
      {children}
    </h2>
  );
}

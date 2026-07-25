import { Mail, Phone, MapPin, Linkedin, Github, Link as LinkIcon } from "lucide-react";

/**
 * Renders a candidate's resume from stored STRUCTURED data into one consistent,
 * professional, printable layout. No rendered HTML is stored — this component is
 * the single presentation layer, so every resume looks the same regardless of
 * how the original file was formatted.
 */

function Section({ title, children }) {
  return (
    <section className="mt-5">
      <h2 className="text-[11px] font-bold uppercase tracking-wider text-gray-500 border-b border-gray-200 pb-1 mb-2.5">
        {title}
      </h2>
      {children}
    </section>
  );
}

const has = (arr) => Array.isArray(arr) && arr.length > 0;

export default function ResumeView({ data, className = "" }) {
  const d = data || {};
  const contact = d.contact || {};
  const links = d.links || {};
  const contactItems = [
    contact.email && { icon: Mail, text: contact.email },
    contact.phone && { icon: Phone, text: contact.phone },
    contact.location && { icon: MapPin, text: contact.location },
  ].filter(Boolean);
  const linkItems = [
    links.linkedin && { icon: Linkedin, label: "LinkedIn", href: links.linkedin },
    links.github && { icon: Github, label: "GitHub", href: links.github },
    links.portfolio && { icon: LinkIcon, label: "Portfolio", href: links.portfolio },
  ].filter(Boolean);

  return (
    <div className={`bg-white text-gray-800 ${className}`}>
      {/* Header */}
      <header className="border-b-2 border-gray-800 pb-4">
        <h1 className="text-2xl font-bold tracking-tight">{d.name || "Candidate"}</h1>
        {d.headline && <p className="text-indigo font-medium mt-0.5">{d.headline}</p>}
        {(contactItems.length > 0 || linkItems.length > 0) && (
          <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
            {contactItems.map(({ icon: Icon, text }) => (
              <span key={text} className="inline-flex items-center gap-1"><Icon size={12} /> {text}</span>
            ))}
            {linkItems.map(({ icon: Icon, label, href }) => (
              <a key={label} href={href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-indigo hover:underline">
                <Icon size={12} /> {label}
              </a>
            ))}
          </div>
        )}
      </header>

      {d.summary && (
        <Section title="Summary">
          <p className="text-sm leading-relaxed text-gray-700">{d.summary}</p>
        </Section>
      )}

      {has(d.experience) && (
        <Section title="Experience">
          <div className="space-y-4">
            {d.experience.map((e, i) => (
              <div key={i}>
                <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <h3 className="font-semibold text-gray-800 text-[15px]">
                    {e.title}{e.organization ? <span className="font-normal text-gray-600"> · {e.organization}</span> : null}
                  </h3>
                  {e.dates && <span className="text-xs text-gray-500 whitespace-nowrap">{e.dates}</span>}
                </div>
                {e.location && <div className="text-xs text-gray-500">{e.location}</div>}
                {has(e.highlights) && (
                  <ul className="mt-1.5 space-y-1">
                    {e.highlights.map((h, j) => (
                      <li key={j} className="text-sm text-gray-700 flex gap-2 leading-relaxed">
                        <span className="text-gray-300 mt-1.5 w-1 h-1 rounded-full bg-gray-400 shrink-0" /> {h}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {has(d.education) && (
        <Section title="Education">
          <div className="space-y-2">
            {d.education.map((e, i) => (
              <div key={i} className="flex flex-wrap items-baseline justify-between gap-x-3">
                <span className="text-sm text-gray-800">
                  <span className="font-medium">{e.qualification}</span>
                  {e.institution ? <span className="text-gray-600"> · {e.institution}</span> : null}
                </span>
                {e.dates && <span className="text-xs text-gray-500 whitespace-nowrap">{e.dates}</span>}
              </div>
            ))}
          </div>
        </Section>
      )}

      {has(d.skills) && (
        <Section title="Skills">
          <div className="flex flex-wrap gap-1.5">
            {d.skills.map((s, i) => (
              <span key={i} className="rounded-md bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">{s}</span>
            ))}
          </div>
        </Section>
      )}

      {has(d.certifications) && (
        <Section title="Certifications & Licences">
          <ul className="space-y-1">
            {d.certifications.map((c, i) => (
              <li key={i} className="text-sm text-gray-700 flex gap-2"><span className="text-gray-300">•</span> {c}</li>
            ))}
          </ul>
        </Section>
      )}

      {has(d.languages) && (
        <Section title="Languages">
          <p className="text-sm text-gray-700">{d.languages.join(" · ")}</p>
        </Section>
      )}
    </div>
  );
}

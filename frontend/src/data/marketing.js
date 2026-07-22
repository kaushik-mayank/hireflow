import {
  Sparkles, ListOrdered, MessageSquareQuote, GitCompareArrows, Mail, BarChart3,
  Database, Send, CalendarClock, Globe, Smartphone, FileCheck, Users,
  HeartPulse, HardHat, Forklift, UtensilsCrossed, ShoppingBag, Factory,
  GraduationCap, Building2, Truck, HandHeart, Wrench, CalendarRange,
} from "lucide-react";

/**
 * Content for the public marketing site.
 *
 * Everything a non-engineer might reasonably want to reword lives here rather
 * than inside the page components, so copy edits don't mean touching JSX.
 *
 * Anything with `isPlaceholder: true` is invented and must be replaced before
 * this goes in front of real prospects.
 */

// ---------------------------------------------------------------------------
// Hero
// ---------------------------------------------------------------------------

/** Cycled through in the Home hero headline. Deliberately spans very different
 *  kinds of work — this is the clearest single signal that HireFlow is not an
 *  office-jobs-only tool. Keep the mix broad when editing. */
export const HERO_ROLES = [
  "registered nurse",
  "forklift operator",
  "backend engineer",
  "line cook",
  "delivery driver",
  "retail supervisor",
  "care assistant",
  "CNC machinist",
  "primary teacher",
  "site electrician",
];

// ---------------------------------------------------------------------------
// Features (all shipped and working today)
// ---------------------------------------------------------------------------

export const FEATURES = [
  {
    id: "jd",
    icon: Sparkles,
    title: "Job description enhancement",
    description:
      "Paste a rough outline — even a few bullet points scribbled between shifts — and get back a clear, structured, inclusive posting that reads like the job it actually is.",
  },
  {
    id: "rank",
    icon: ListOrdered,
    title: "AI resume ranking",
    description:
      "Upload a stack of resumes and every one comes back scored against your posting, with the skills that matched, the ones that didn't, and anything worth a second look.",
  },
  {
    id: "questions",
    icon: MessageSquareQuote,
    title: "Screening questions, generated",
    description:
      "Tailored questions for each individual candidate, drawn from their background and your role — not a generic list you have to rewrite anyway.",
  },
  {
    id: "compare",
    icon: GitCompareArrows,
    title: "Side-by-side comparison",
    description:
      "Two strong applicants and one opening. Put them next to each other and get a straight recommendation with the reasoning spelled out.",
  },
  {
    id: "email",
    icon: Mail,
    title: "Offer and rejection emails",
    description:
      "Drafts written for the role and the person, ready to review and send. Nobody gets left waiting on a reply you never found time to write.",
  },
  {
    id: "reports",
    icon: BarChart3,
    title: "Dashboard and analytics",
    description:
      "Time-to-hire, where candidates drop out, which postings have gone quiet, and how close you are to filling every open seat.",
  },
];

// ---------------------------------------------------------------------------
// How it works
// ---------------------------------------------------------------------------

export const STEPS = [
  {
    id: "post",
    title: "Describe the role",
    description:
      "Set how many people you need and by when. Rough notes are fine — the AI turns them into a proper posting.",
  },
  {
    id: "upload",
    title: "Add your applicants",
    description:
      "Drop in resumes however they arrived. Details are read out of each one automatically, so nothing is typed twice.",
  },
  {
    id: "rank",
    title: "Let AI do the first pass",
    description:
      "Every applicant is scored against your posting, so you start with the ones worth your time instead of page one of the pile.",
  },
  {
    id: "hire",
    title: "Move people through to hired",
    description:
      "A visual pipeline from first look to signed, with screening questions and emails generated at each step.",
  },
];

// ---------------------------------------------------------------------------
// Industries
// ---------------------------------------------------------------------------

/** Used to make the universal-niche promise concrete rather than asserted. */
export const INDUSTRIES = [
  { id: "healthcare", icon: HeartPulse, label: "Healthcare", example: "Nurses, care staff, technicians" },
  { id: "trades", icon: HardHat, label: "Trades & construction", example: "Electricians, welders, site leads" },
  { id: "logistics", icon: Forklift, label: "Warehouse & logistics", example: "Pickers, forklift operators" },
  { id: "hospitality", icon: UtensilsCrossed, label: "Hospitality & food", example: "Chefs, servers, baristas" },
  { id: "retail", icon: ShoppingBag, label: "Retail", example: "Associates, shift supervisors" },
  { id: "manufacturing", icon: Factory, label: "Manufacturing", example: "Machinists, QA inspectors" },
  { id: "education", icon: GraduationCap, label: "Education", example: "Teachers, teaching assistants" },
  { id: "corporate", icon: Building2, label: "Corporate & professional", example: "Engineers, analysts, marketers" },
  { id: "transport", icon: Truck, label: "Transport & driving", example: "HGV, delivery, couriers" },
  { id: "care", icon: HandHeart, label: "Care & community", example: "Support workers, key workers" },
  { id: "field", icon: Wrench, label: "Field services", example: "Engineers, installers, fitters" },
  { id: "seasonal", icon: CalendarRange, label: "Gig & seasonal", example: "Event, agency, peak-season crews" },
];

// ---------------------------------------------------------------------------
// Testimonials
// ---------------------------------------------------------------------------

/**
 * Data-driven so real reviews can be dropped straight in.
 *
 * Shape: { id, quote, name, title, org, industry, rating (1-5), isPlaceholder }
 *
 * To publish real ones: replace the objects below and remove `isPlaceholder`.
 * Any entry still carrying `isPlaceholder: true` renders with a visible
 * "sample" marker, so nothing invented can be mistaken for a real customer.
 */
export const TESTIMONIALS = [
  {
    id: "t1",
    quote:
      "We were filling the same three ward roles over and over and losing good applicants to slow replies. Now the first pass happens the same day the resumes land.",
    name: "Sample Name",
    title: "Head of Talent",
    org: "Regional care group",
    industry: "Healthcare",
    rating: 5,
    isPlaceholder: true,
  },
  {
    id: "t2",
    quote:
      "Peak season means four hundred applications in a fortnight. Ranking them by hand was two people's entire week. It isn't any more.",
    name: "Sample Name",
    title: "Operations Manager",
    org: "Distribution centre",
    industry: "Warehouse & logistics",
    rating: 5,
    isPlaceholder: true,
  },
  {
    id: "t3",
    quote:
      "The generated screening questions actually reference the certifications the job needs. That was the part I expected to have to rewrite and didn't.",
    name: "Sample Name",
    title: "Site Manager",
    org: "Electrical contractor",
    industry: "Trades & construction",
    rating: 4,
    isPlaceholder: true,
  },
  {
    id: "t4",
    quote:
      "Every applicant hears back now, even the ones we don't take forward. That mattered more to our reputation locally than we expected.",
    name: "Sample Name",
    title: "General Manager",
    org: "Independent restaurant group",
    industry: "Hospitality & food",
    rating: 5,
    isPlaceholder: true,
  },
  {
    id: "t5",
    quote:
      "I can see which postings have gone quiet without opening five spreadsheets. That single view is most of the value for me.",
    name: "Sample Name",
    title: "People Lead",
    org: "Software company",
    industry: "Corporate & professional",
    rating: 4,
    isPlaceholder: true,
  },
  {
    id: "t6",
    quote:
      "We hire in bursts before every term. Setting the number of positions and watching it count down is exactly how we already thought about it.",
    name: "Sample Name",
    title: "Recruitment Coordinator",
    org: "Multi-academy trust",
    industry: "Education",
    rating: 5,
    isPlaceholder: true,
  },
];

// ---------------------------------------------------------------------------
// Roadmap
// ---------------------------------------------------------------------------

/**
 * Teaser content only — these are NOT built yet and the page says so plainly.
 * `status` is free text and shows as a small tag on each card.
 */
export const COMING_SOON = [
  {
    id: "resume-db",
    icon: Database,
    title: "Resume database integrations",
    status: "In design",
    description:
      "Pull candidates straight from the job boards and resume databases you already pay for, instead of exporting and re-uploading them.",
  },
  {
    id: "email-connect",
    icon: Mail,
    title: "Connect your email account",
    status: "In design",
    description:
      "Link your own mailbox so generated messages send from your address and replies land in the thread where you expect them.",
  },
  {
    id: "bulk-email",
    icon: Send,
    title: "Bulk email sending",
    status: "Planned",
    description:
      "Message an entire stage at once — every applicant not moving forward, or every shortlisted candidate — without pasting one at a time.",
  },
  {
    id: "scheduling",
    icon: CalendarClock,
    title: "Calendar interview scheduling",
    status: "Planned",
    description:
      "Share your availability, let candidates pick a slot, and have it land on your calendar. Built to handle shift patterns, not just nine-to-five.",
  },
  {
    id: "job-portals",
    icon: Globe,
    title: "Post to external job portals",
    status: "Planned",
    description:
      "Write a posting once and publish it to the boards that matter for your sector, without re-keying it into each one.",
  },
  {
    id: "sms",
    icon: Smartphone,
    title: "SMS and WhatsApp outreach",
    status: "Exploring",
    description:
      "For the many roles where candidates answer a text far faster than an email. Same drafts, different channel.",
  },
  {
    id: "compliance",
    icon: FileCheck,
    title: "Certification and document tracking",
    status: "Exploring",
    description:
      "Track the licences, tickets, DBS checks and right-to-work documents a role legally requires, with expiry dates surfaced before they lapse.",
  },
  {
    id: "teams",
    icon: Users,
    title: "Team accounts and collaboration",
    status: "Exploring",
    description:
      "Bring hiring managers into the same pipeline with their own logins, shared notes and scorecards.",
  },
];

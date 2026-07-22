import { ShieldAlert } from "lucide-react";
import { Section, PageHero, Prose, ProseHeading, PlaceholderNote } from "@/components/marketing";

/**
 * A complete, genuine privacy policy for a SaaS that stores candidate resumes
 * and personal data — NOT legal advice and NOT reviewed by a lawyer.
 *
 * Owner must confirm before publishing:
 *   - the contact addresses and legal entity name below
 *   - the sub-processor list (§7) against what is actually deployed
 *   - retention periods (§9), which are currently stated as intentions
 *   - which privacy regimes actually apply to your customers
 */

/** TODO(owner): replace all three before launch. */
const PRIVACY_EMAIL = "privacy@example.com";
const SUPPORT_EMAIL = "support@example.com";
const LEGAL_ENTITY = "HireFlow";

const LAST_UPDATED = "23 July 2026";

const SUB_PROCESSORS = [
  {
    name: "MongoDB Atlas",
    purpose: "Primary database — stores accounts, job postings, candidate records and extracted resume text.",
  },
  {
    name: "Render",
    purpose: "Application hosting and infrastructure for the website and API.",
  },
  {
    name: "Groq",
    purpose: "AI model provider. Processes job descriptions and resume text to produce rankings, screening questions, summaries and email drafts.",
  },
  {
    name: "Google Firebase",
    purpose: "Authentication — account sign-up, sign-in, email verification and password resets.",
  },
  {
    name: "Google Fonts",
    purpose: "Serves the typefaces used across the site. May receive your IP address when a page loads.",
  },
];

export default function Privacy() {
  return (
    <>
      <PageHero
        eyebrow="Legal"
        title="Privacy policy"
        subtitle={`How ${LEGAL_ENTITY} collects, uses, shares and protects personal data — both yours as a user and that of the candidates whose applications you process.`}
      />

      <Section>
        <div className="mx-auto max-w-3xl">
          <div className="rounded-xl border border-coral bg-coral-light px-5 py-4">
            <div className="flex items-start gap-3">
              <ShieldAlert size={18} className="mt-0.5 shrink-0 text-coral" />
              <div className="text-sm text-coral leading-relaxed">
                <span className="font-semibold">Requires legal review before publication.</span> This
                policy was drafted to be accurate to how HireFlow actually works, but it has not been
                reviewed by a qualified lawyer and is not legal advice. Have a solicitor or privacy
                counsel check it against the jurisdictions you operate in before you rely on it.
              </div>
            </div>
          </div>

          <div className="mt-6">
            <PlaceholderNote>
              The contact addresses, legal entity name, retention periods and sub-processor list below
              must all be confirmed against your live setup. They are marked with TODO comments in
              <code className="mx-1 rounded bg-gray-200 px-1 py-0.5 font-mono text-[11px]">src/pages/marketing/Privacy.jsx</code>.
            </PlaceholderNote>
          </div>

          <p className="mt-8 text-xs uppercase tracking-wider text-gray-600 font-semibold">
            Last updated: {LAST_UPDATED}
          </p>

          <Prose className="mt-6">
            <ProseHeading id="intro">1. Introduction</ProseHeading>
            <p>
              {LEGAL_ENTITY} (&ldquo;we&rdquo;, &ldquo;us&rdquo;) provides AI-assisted hiring software.
              This policy explains what personal data we handle, why, who we share it with, and what
              rights people have over it. It applies to our website and to the HireFlow application.
            </p>
            <p>
              Two distinct groups of people appear in this policy. <strong>Users</strong> are the
              people who hold a HireFlow account and use it to hire.{" "}
              <strong>Candidates</strong> are the people whose resumes and applications a user uploads
              into HireFlow. We handle data about both, but in different roles — see section 3.
            </p>

            <ProseHeading id="roles">2. Data we collect</ProseHeading>
            <p>
              <strong>Account data (users).</strong> Your name, email address, company or organisation
              name, and a securely hashed password. We never store your password in a readable form.
            </p>
            <p>
              <strong>Usage and technical data (users).</strong> Login timestamps, IP address and
              browser user-agent string, recorded to secure accounts and investigate suspicious
              activity. We also log which AI features are used and how often, in order to monitor
              cost and capacity.
            </p>
            <p>
              <strong>Content you create (users).</strong> Job postings, job descriptions, hiring
              targets, pipeline stages, and any notes you write about candidates.
            </p>
            <p>
              <strong>Candidate data (uploaded by users).</strong> When you upload a resume we store
              the file and extract text from it. That text routinely contains a name, email address,
              phone number, employment history, education, skills and whatever else the candidate
              chose to include. We also store the AI-generated score, summary, matched and missing
              skills, and any stage changes or notes recorded against that candidate.
            </p>
            <p>
              We do not ask for, and ask that you do not upload, special category data — such as
              health information, racial or ethnic origin, religious beliefs, trade union membership,
              biometric data, or criminal records — unless you have a lawful basis and appropriate
              safeguards for doing so.
            </p>

            <ProseHeading id="controller">3. Our role: controller and processor</ProseHeading>
            <p>
              For <strong>user account data</strong>, we act as the data controller: we decide why and
              how it is processed.
            </p>
            <p>
              For <strong>candidate data</strong>, you — the user or your organisation — are the
              controller, and we act as your processor. You decide whose resumes to upload and why. We
              process that data on your instructions in order to provide the service. This means you
              are responsible for having a lawful basis to collect and upload candidate data, for
              telling candidates that their application is being processed with AI assistance, and for
              responding to requests those candidates make about their data.
            </p>

            <ProseHeading id="use">4. How we use data</ProseHeading>
            <p>We use personal data to:</p>
            <ul className="list-disc pl-5 space-y-1.5">
              <li>create and secure your account, and authenticate you when you sign in;</li>
              <li>provide the core product — storing postings, resumes and pipeline state;</li>
              <li>
                run the AI features you trigger: ranking resumes, generating screening questions,
                comparing candidates, drafting emails and producing pipeline insights;
              </li>
              <li>produce reports and analytics within your own account;</li>
              <li>
                monitor service health, prevent abuse, and investigate security incidents;
              </li>
              <li>respond to support requests and any feedback you send us;</li>
              <li>comply with legal obligations.</li>
            </ul>

            <ProseHeading id="ai">5. AI processing — read this part</ProseHeading>
            <p>
              HireFlow&rsquo;s core features work by sending text to a third-party AI model provider.
              Specifically, <strong>job description text and extracted resume text are transmitted to
              Groq</strong> when you run ranking, screening question generation, candidate comparison,
              deep summaries, email drafting or pipeline health analysis. That text ordinarily contains
              candidate personal data.
            </p>
            <p>
              AI output is assistive only. Scores, summaries and recommendations are suggestions for a
              human to weigh, not decisions. <strong>HireFlow does not automatically reject, shortlist
              or hire anyone</strong>, and no candidate&rsquo;s outcome is determined solely by
              automated processing — a person on your team makes every decision. If your jurisdiction
              gives candidates rights concerning automated decision-making, you should nonetheless tell
              them AI assistance is used.
            </p>
            <p>
              AI models can be wrong, and can reflect biases present in their training data. You should
              review AI output rather than rely on it, and you remain responsible for the fairness and
              legality of your hiring decisions.
            </p>

            <ProseHeading id="legal-basis">6. Legal bases</ProseHeading>
            <p>
              Where UK or EU data protection law applies, we rely on: <strong>contract</strong> — to
              provide the service you signed up for; <strong>legitimate interests</strong> — to secure
              the service, prevent abuse and improve the product, balanced against your rights;{" "}
              <strong>legal obligation</strong> — where we must retain or disclose data; and{" "}
              <strong>consent</strong> — where we ask for it specifically, which you may withdraw at
              any time.
            </p>

            <ProseHeading id="sharing">7. Who we share data with</ProseHeading>
            <p>
              We do not sell personal data. We do not share it for advertising. We use the following
              service providers, each of which processes data on our behalf under contract:
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
                <thead>
                  <tr className="bg-gray-50 text-left text-xs text-gray-600">
                    <th className="py-2.5 px-3 font-semibold">Provider</th>
                    <th className="py-2.5 px-3 font-semibold">What it is used for</th>
                  </tr>
                </thead>
                <tbody>
                  {SUB_PROCESSORS.map((p) => (
                    <tr key={p.name} className="border-t border-gray-200 align-top">
                      <td className="py-2.5 px-3 font-medium text-gray-800 whitespace-nowrap">{p.name}</td>
                      <td className="py-2.5 px-3 text-gray-600">{p.purpose}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p>
              We may also disclose data where required by law, court order or a valid request from a
              public authority, and to establish or defend legal claims. If we are ever involved in a
              merger or acquisition, data may transfer to the acquiring entity; we would tell you
              before that happened.
            </p>

            <ProseHeading id="transfers">8. International transfers</ProseHeading>
            <p>
              Our providers may process data outside your country, including in the United States.
              Where data protection law requires it, such transfers are made under appropriate
              safeguards — typically standard contractual clauses or an equivalent recognised
              mechanism.
            </p>

            <ProseHeading id="retention">9. How long we keep data</ProseHeading>
            <p>
              <strong>Account data</strong> is kept while your account is active. If you close it, we
              delete or anonymise your account data within a reasonable period, except where we must
              retain something to meet a legal obligation.
            </p>
            <p>
              <strong>Candidate data</strong> is kept until you delete it. Deleting a candidate removes
              their record, their stored resume file and their stage history. Deleting a job posting
              removes the candidates attached to it. Because you are the controller of candidate data,
              you decide the retention period appropriate to your obligations — many jurisdictions
              limit how long unsuccessful applicants&rsquo; data may be kept.
            </p>
            <p>
              <strong>Security logs</strong> such as login records are kept for a limited period for
              fraud and abuse investigation.
            </p>

            <ProseHeading id="security">10. Security</ProseHeading>
            <p>
              We use access controls, encrypted connections and hashed passwords, and we restrict
              access to production data to those who need it. Authentication uses time-limited session
              tokens.
            </p>
            <p>
              No system is perfectly secure, and we cannot guarantee absolute security. If a breach
              occurs that is likely to result in a risk to people&rsquo;s rights, we will notify
              affected users and the relevant regulator as required by law.
            </p>

            <ProseHeading id="rights">11. Your rights</ProseHeading>
            <p>Depending on where you live, you may have the right to:</p>
            <ul className="list-disc pl-5 space-y-1.5">
              <li>access the personal data we hold about you;</li>
              <li>correct data that is inaccurate or incomplete;</li>
              <li>delete your data;</li>
              <li>restrict or object to certain processing;</li>
              <li>receive your data in a portable, machine-readable format;</li>
              <li>withdraw consent where processing relies on it;</li>
              <li>complain to your data protection authority.</li>
            </ul>
            <p>
              To exercise any of these, contact us at{" "}
              <a href={`mailto:${PRIVACY_EMAIL}`} className="text-indigo font-medium hover:underline">
                {PRIVACY_EMAIL}
              </a>
              . We respond within the timeframe the applicable law requires.
            </p>
            <p>
              <strong>Candidates:</strong> if you applied for a job and want your data accessed,
              corrected or deleted, please contact the organisation you applied to — they control that
              data and can act on it directly. If you contact us instead, we will pass your request to
              them and support them in fulfilling it.
            </p>

            <ProseHeading id="cookies">12. Cookies and local storage</ProseHeading>
            <p>
              We do not use advertising or third-party tracking cookies. HireFlow stores a session
              token in your browser&rsquo;s local storage to keep you signed in; clearing your browser
              storage signs you out. Our hosting provider may set strictly necessary cookies for
              security and load balancing.
            </p>

            <ProseHeading id="children">13. Children</ProseHeading>
            <p>
              HireFlow is a business tool and is not directed at children. We do not knowingly collect
              data from anyone under 16 as a user. If you believe a child has created an account,
              contact us and we will remove it.
            </p>

            <ProseHeading id="changes">14. Changes to this policy</ProseHeading>
            <p>
              We may update this policy as the product changes. The &ldquo;last updated&rdquo; date at
              the top reflects the most recent version. If a change materially affects how we handle
              personal data, we will give notice in the product or by email before it takes effect.
            </p>

            <ProseHeading id="contact">15. Contact us</ProseHeading>
            <p>
              Privacy questions, data requests and complaints:{" "}
              <a href={`mailto:${PRIVACY_EMAIL}`} className="text-indigo font-medium hover:underline">
                {PRIVACY_EMAIL}
              </a>
              .
            </p>
            <p>
              General support:{" "}
              <a href={`mailto:${SUPPORT_EMAIL}`} className="text-indigo font-medium hover:underline">
                {SUPPORT_EMAIL}
              </a>
              .
            </p>
          </Prose>

          <div className="mt-10">
            <PlaceholderNote>
              Before publishing, confirm: the legal entity name and registered address, both contact
              addresses, that the sub-processor table in section 7 matches what is actually deployed,
              and that the retention periods in section 9 reflect what you really do.
            </PlaceholderNote>
          </div>
        </div>
      </Section>
    </>
  );
}

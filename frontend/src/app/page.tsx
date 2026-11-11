import Image from "next/image";
import Link from "next/link";
import { GuestAnalyzer } from "@/features/guest/guest-analyzer";
import { ReportPreview } from "@/features/landing/report-preview";
import { Icon, type IconName } from "@/components/icon";
import { SiteFooter, SiteHeader } from "@/components/site-header";
import styles from "./landing.module.css";

const capabilities: { icon: IconName; title: string; text: string }[] = [
  {
    icon: "document",
    title: "A closer reading",
    text: "Turn your PDF or DOCX into structured experience you can inspect and correct before a review.",
  },
  {
    icon: "search",
    title: "Evidence, in context",
    text: "See the résumé passages behind a finding. Distinguish clear support from a skill that is only mentioned.",
  },
  {
    icon: "history",
    title: "Progress you can trace",
    text: "Keep versions, compare reviews, and understand what changed when you update your résumé.",
  },
];
const questions = [
  [
    "Can I try it without creating an account?",
    "Yes. Upload a PDF or DOCX for a résumé review. Add a job description only when you want a role-specific review. Guests get one review per network every 24 hours. Failed processing restores the allowance. Create an account to keep versions and compare reviews.",
  ],
  [
    "Is this an ATS score or a hiring prediction?",
    "Neither. Rolemaker compares the evidence in your résumé with a job description. It cannot verify your qualifications, reproduce an employer’s screening process, or predict an interview.",
  ],
  [
    "How is my document handled?",
    "Documents are processed on this server without sending them to an outside AI service. Guest report access expires after 24 hours; scheduled cleanup removes temporary documents. You can delete your guest report sooner.",
  ],
  [
    "What powers the analysis?",
    "When enabled, a local language model writes feedback about the experience, impact and clarity in your résumé, with quotations checked against the source. Separate document and role-matching checks remain available. Each report names the method actually used. AI feedback can be mistaken and does not predict hiring outcomes.",
  ],
  [
    "How do review credits work?",
    "Reviews are free unless credit charging is enabled. The optional Stripe sandbox checkout offers five review credits for $5 USD using test payments only. When charging is enabled, a new account review uses one credit; failed or cancelled reviews return it. There is no recurring subscription.",
  ],
];
function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className={styles.eyebrow}>
      <Icon name="grid" size={16} />
      {children}
    </p>
  );
}
export default function Landing() {
  return (
    <div className={styles.landing}>
      <SiteHeader />
      <main id="main">
        <div className={styles.hero}>
          <Image
            src="/images/resume-review.webp"
            alt=""
            fill
            priority
            sizes="100vw"
            className={styles.heroImage}
          />

          <section className={styles.heroContent} aria-labelledby="landing-title">
            <Eyebrow>Your experience. A clearer next step.</Eyebrow>
            <h1 id="landing-title">
              Bring Your Experience
              <br />
              Into Focus For
              <br />
              Your <span>Next Role</span>
            </h1>
            <p className={styles.heroLead}>
              Get a thoughtful review of your résumé, with or without a target role.
              <br className={styles.desktopBreak} /> Find the evidence. Understand the gaps. Make
              your next edit count.
            </p>
            <div className={styles.actions}>
              <a className={styles.primary} href="#analyze">
                Review my résumé <Icon name="arrowUpRight" size={18} />
              </a>
              <Link className={styles.secondary} href="/demo">
                Explore a sample <Icon name="arrow" size={18} />
              </Link>
            </div>
            <p className={styles.heroNote}>One review without an account · PDF or DOCX</p>
          </section>
        </div>
        <div className={styles.content}>
          <section className={styles.intro} aria-labelledby="intro-title">
            <div className={styles.centerHeading}>
              <Eyebrow>Built around the work you’ve done</Eyebrow>
              <h2 id="intro-title">
                A Better Review Starts With
                <br />
                <span>Your Actual Experience</span>
              </h2>
            </div>
            <ul className={styles.proofRow}>
              <li>
                <Icon name="document" />
                Evidence-linked findings
              </li>
              <li>
                <Icon name="shield" />
                Processed on this server
              </li>
              <li>
                <Icon name="history" />
                Versioned, editable source
              </li>
            </ul>
          </section>
          <section id="how-it-works" className={styles.about} aria-labelledby="about-title">
            <div>
              <Eyebrow>Make the connection clear</Eyebrow>
              <h2 id="about-title">
                Your Experience Has Value.
                <br />
                Help The Right Details <span>Stand Out.</span>
              </h2>
              <p>
                A job description gives your review a direction. Your résumé provides the evidence.
                Rolemaker helps you see where the two connect.
              </p>
              <ol className={styles.numbered}>
                <li>
                  <h3>1. Start with what you’ve done</h3>
                  <p>
                    Upload your résumé and check the extracted experience. Correct the source before
                    it becomes a finding.
                  </p>
                </li>
                <li>
                  <h3>2. Read it through the role</h3>
                  <p>
                    Add a job description. Inspect clear support, missing context, and requirements
                    that need a second look.
                  </p>
                </li>
              </ol>
              <a className={styles.textLink} href="#analyze">
                Try it with your résumé <Icon name="arrowUpRight" size={18} />
              </a>
            </div>
            <div className={styles.aboutImage}>
              <Image
                src="/images/resume-review.webp"
                alt="A professional reviewing a résumé beside a laptop"
                fill
                sizes="(max-width: 800px) 100vw, 45vw"
              />
            </div>
          </section>
          <section className={styles.features} aria-labelledby="features-title">
            <div className={styles.centerHeading}>
              <Eyebrow>From a document to a decision you can explain</Eyebrow>
              <h2 id="features-title">
                Less Guesswork.
                <br />
                <span>More Useful Context.</span>
              </h2>
            </div>
            <div className={styles.featureGrid}>
              {capabilities.map(({ icon, title, text }, i) => (
                <article key={title} className={styles.featureCard}>
                  <div className={styles.cardTop}>
                    <Icon name={icon} size={32} />
                    <span>0{i + 1}</span>
                  </div>
                  <h3>{title}</h3>
                  <p>{text}</p>
                  <Link href={i === 2 ? "/register" : "/demo"}>
                    {i === 2 ? "Keep your history" : "See it in the sample"}
                    <Icon name="arrowUpRight" size={16} />
                  </Link>
                </article>
              ))}
            </div>
          </section>
        </div>
        <section className={styles.band} aria-label="The review workflow">
          <div>
            <span>01</span>
            <p>Upload your résumé</p>
          </div>
          <div>
            <span>02</span>
            <p>Optional: add a target role</p>
          </div>
          <div>
            <span>03</span>
            <p>Review the evidence</p>
          </div>
        </section>
        <div className={styles.content}>
          <section className={styles.method} aria-labelledby="method-title">
            <Eyebrow>Understand the reading, then make the edit</Eyebrow>
            <h2 id="method-title">
              A Finding Is A Starting Point.
              <br />
              <span>You Keep The Final Say.</span>
            </h2>
            <div className={styles.methodGrid}>
              <article>
                <h3>
                  Clear <span>support</span>
                </h3>
                <p>
                  Inspect a passage that demonstrates the requirement in context. Keep the specific
                  work and outcome visible.
                </p>
              </article>
              <article>
                <h3>
                  Missing <span>context</span>
                </h3>
                <p>
                  A named skill may need an example. Explain how you used it when you have the
                  experience to support it.
                </p>
              </article>
              <article>
                <h3>
                  A closer <span>look</span>
                </h3>
                <p>
                  A missing or conflicting match needs your judgment. Review the wording without
                  inventing experience.
                </p>
              </article>
            </div>
          </section>
          <section id="report-preview" className={styles.preview} aria-labelledby="preview-title">
            <div className={styles.centerHeading}>
              <Eyebrow>Explore the experience behind each finding</Eyebrow>
              <h2 id="preview-title">
                The Role Changes.
                <br />
                <span>The Evidence Stays Visible.</span>
              </h2>
              <p>Choose a role and a requirement in this synthetic example.</p>
            </div>
            <ReportPreview />
            <Link href="/demo" className={styles.textLink}>
              Open the full sample report <Icon name="arrowUpRight" size={18} />
            </Link>
          </section>
          <section className={styles.workflow} aria-labelledby="workflow-title">
            <div
              className={styles.workflowIllustration}
              aria-label="Version history example, synthetic data"
            >
              <div className={styles.document}>
                <p>RÉSUMÉ / VERSION 02</p>
                <h3>Alex Morgan</h3>
                <span>Software engineer</span>
                <hr />
                <p className={styles.documentLine}>
                  Built billing APIs in Python, with integration tests for payment and refund flows.
                </p>
                <div className={styles.documentHighlight}>
                  <Icon name="check" size={17} />
                  Clear evidence for Python API development
                </div>
              </div>
              <div className={styles.versionNote}>
                <Icon name="history" size={20} />
                <div>
                  <strong>A clearer version</strong>
                  <p>Compare the evidence after each edit.</p>
                </div>
              </div>
            </div>
            <div>
              <Eyebrow>Keep the work connected</Eyebrow>
              <h2 id="workflow-title">
                One Role. A Thoughtful Edit.
                <br />
                <span>A Clearer Next Version.</span>
              </h2>
              <p>
                Review a suggestion, update the underlying résumé, and run the comparison again.
                Your earlier versions remain available so you can understand the change.
              </p>
              <ul className={styles.checks}>
                <li>
                  <Icon name="check" />
                  Correct the extracted résumé
                </li>
                <li>
                  <Icon name="check" />
                  Review and adjust role requirements
                </li>
                <li>
                  <Icon name="check" />
                  Compare two completed analyses
                </li>
                <li>
                  <Icon name="check" />
                  Export a report or delete your data
                </li>
              </ul>
              <Link href="/register" className={styles.primary}>
                Create your workspace <Icon name="arrowUpRight" size={18} />
              </Link>
            </div>
          </section>
          <section className={styles.analyzer} aria-label="Try the résumé analyzer">
            <div className={styles.centerHeading}>
              <Eyebrow>Start with the version you have</Eyebrow>
              <h2>
                See Your Résumé
                <br />
                <span>Through A New Role.</span>
              </h2>
            </div>
            <GuestAnalyzer headingLevel={2} />
          </section>
          <section id="pricing" className={styles.pricing} aria-labelledby="pricing-title">
            <div className={styles.centerHeading}>
              <Eyebrow>Simple access. No recurring commitment.</Eyebrow>
              <h2 id="pricing-title">
                Start With A Review.
                <br />
                <span>Keep Going When You Need To.</span>
              </h2>
            </div>
            <div className={styles.priceGrid}>
              <article>
                <p className={styles.plan}>Guest review</p>
                <h3>Free</h3>
                <p>A first look at one résumé and one role.</p>
                <ul className={styles.checks}>
                  <li>
                    <Icon name="check" />
                    One review per network every 24 hours
                  </li>
                  <li>
                    <Icon name="check" />
                    Evidence and editing suggestions
                  </li>
                  <li>
                    <Icon name="check" />
                    No account needed
                  </li>
                </ul>
                <a href="#analyze" className={styles.secondary}>
                  Try a guest review <Icon name="arrow" size={17} />
                </a>
              </article>
              <article className={styles.featuredPlan}>
                <p className={styles.plan}>Review credit pack · Stripe test mode</p>
                <h3>
                  $5 <span>USD / 5 reviews</span>
                </h3>
                <p>A one-time pack for an account workspace.</p>
                <ul className={styles.checks}>
                  <li>
                    <Icon name="check" />
                    Five additional analysis runs
                  </li>
                  <li>
                    <Icon name="check" />
                    Version history and comparisons
                  </li>
                  <li>
                    <Icon name="check" />
                    Failed or cancelled runs return a credit
                  </li>
                </ul>
                <Link href="/app/billing" className={styles.primary}>
                  Explore test checkout <Icon name="arrowUpRight" size={17} />
                </Link>
                <p className={styles.priceNote}>
                  Test payments only. Reviews stay free unless credit charging is enabled.
                </p>
              </article>
            </div>
          </section>
          <section className={styles.faq} aria-labelledby="questions-title">
            <div className={styles.centerHeading}>
              <Eyebrow>A few things worth knowing</Eyebrow>
              <h2 id="questions-title">
                Clear About The Work.
                <br />
                <span>And Its Limits.</span>
              </h2>
            </div>
            <div className={styles.faqList}>
              {questions.map(([q, a]) => (
                <details key={q}>
                  <summary>
                    {q}
                    <span className={styles.faqToggle} aria-hidden="true">
                      <Icon name="minus" size={18} />
                      <span />
                    </span>
                  </summary>
                  <p>{a}</p>
                </details>
              ))}
            </div>
          </section>
          <section className={styles.closing}>
            <div>
              <Eyebrow>Your next chapter starts with a clearer story</Eyebrow>
              <h2>
                Let Your Experience
                <br />
                <span>Speak For Itself.</span>
              </h2>
            </div>
            <a href="#analyze" className={styles.primary}>
              Review my résumé <Icon name="arrowUpRight" size={20} />
            </a>
          </section>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}

import Link from "next/link";
import { GuestAnalyzer } from "@/components/guest-analyzer";
import { Icon } from "@/components/icon";
import { SiteFooter, SiteHeader } from "@/components/site-header";

const steps = [
  {
    icon: "document" as const,
    title: "Bring your experience.",
    text: "Upload the résumé you already have. A PDF or Word document works.",
  },
  {
    icon: "briefcase" as const,
    title: "Give it a direction.",
    text: "Add the job description for a role you want to explore.",
  },
  {
    icon: "search" as const,
    title: "Find your next useful edit.",
    text: "See the evidence, spot the gaps, and decide what to clarify.",
  },
];
export default function Landing() {
  return (
    <>
      <SiteHeader />
      <main id="main" className="rolemark-home">
        <GuestAnalyzer />
        <section id="how-it-works" className="how-section" aria-labelledby="how-title">
          <div className="how-heading">
            <span className="micro-label">A LITTLE DIRECTION GOES A LONG WAY</span>
            <h2 id="how-title">
              Less second-guessing.
              <br /> <em>More moving forward.</em>
            </h2>
          </div>
          <ol className="how-steps">
            {steps.map((step, i) => (
              <li key={step.title}>
                <div className="how-step-top">
                  <span>0{i + 1}</span>
                  <Icon name={step.icon} size={21} />
                </div>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </li>
            ))}
          </ol>
        </section>
        <section className="questions-section" aria-labelledby="questions-title">
          <div>
            <span className="micro-label">GOOD TO KNOW</span>
            <h2 id="questions-title">
              A few details.
              <br /> Then you’re on your way.
            </h2>
            <Link href="/privacy">
              Read our privacy approach <Icon name="arrowUpRight" size={15} />
            </Link>
          </div>
          <div className="questions-list">
            <details>
              <summary>
                Can I try it without an account?
                <Icon name="plus" size={18} />
              </summary>
              <p>
                Yes. One résumé review is free per network every 24 hours. Create a free account for
                additional reviews and version history. Failed processing restores your allowance.
              </p>
            </details>
            <details>
              <summary>
                Where does my résumé go?
                <Icon name="plus" size={18} />
              </summary>
              <p>
                Your document is processed on this server, without an outside AI service. Guest
                report access expires after 24 hours, and scheduled cleanup removes temporary
                documents. You can delete yours sooner.
              </p>
            </details>
            <details>
              <summary>
                What does the feedback actually tell me?
                <Icon name="plus" size={18} />
              </summary>
              <p>
                It compares your résumé’s wording with the role’s requirements and shows the
                passages behind each finding. It cannot verify qualifications or predict an
                interview. The current reader uses local, deterministic rules and makes its limits
                visible.
              </p>
            </details>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

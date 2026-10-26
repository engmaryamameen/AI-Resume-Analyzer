import { SiteFooter, SiteHeader } from "@/components/site-header";
import { ButtonLink, Card } from "@/components/ui";

const steps = [
  { title: "Bring a résumé and a job", body: "Upload a PDF or Word file and paste the job description. Or skip both and use the sample documents." },
  { title: "See what each requirement rests on", body: "For every requirement you see the exact line of your résumé that backs it up, or a plain statement that nothing does." },
  { title: "Fix it honestly", body: "Suggestions point at your own words. Anything that needs new facts is a blank for you to fill in with true details." },
];

const promises = [
  ["Mentioned isn't the same as shown", "A skill sitting in a list is treated differently from a bullet that describes using it, and \"no experience with Go\" is not read as Go."],
  ["Nothing invented", "Nothing is added to your résumé. Suggestions quote what you wrote and leave blanks for you."],
  ["No mystery score", "There is no overall number. You get descriptive readings, each with how it was worked out and where it falls short."],
  ["Your data stays on this server", "Analysis runs on models stored on the same machine. No document or text is sent to an outside AI service. Delete a résumé, or your whole account, whenever you like."],
];

export default function Landing() {
  return (
    <>
      <SiteHeader />
      <main id="main">
        <section className="mx-auto max-w-6xl px-4 py-16 sm:py-24">
          <p className="text-sm font-medium uppercase tracking-wide text-accent">Résumé feedback with receipts</p>
          <h1 className="mt-3 max-w-3xl font-serif text-4xl leading-tight sm:text-6xl">
            Find out what your résumé actually proves.
          </h1>
          <p className="mt-5 max-w-prose text-lg text-muted">
            Most résumé checkers count keywords. Margin Notes looks for the evidence behind them, so you can see what's solid,
            what's only claimed, and what's missing for the job in front of you.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <ButtonLink href="/demo">Try it with sample résumés</ButtonLink>
            <ButtonLink href="/register" variant="secondary">Create an account</ButtonLink>
          </div>
          <p className="mt-3 text-sm text-muted">The demo needs no account and no upload, and stores nothing.</p>
        </section>

        <section aria-labelledby="how" className="border-y border-line bg-surface">
          <div className="mx-auto max-w-6xl px-4 py-14">
            <h2 id="how" className="font-serif text-3xl">How it works</h2>
            <ol className="mt-8 grid gap-6 md:grid-cols-3">
              {steps.map((s, i) => (
                <li key={s.title}>
                  <span className="font-serif text-4xl text-accent" aria-hidden>{i + 1}</span>
                  <h3 className="mt-2 font-medium">{s.title}</h3>
                  <p className="mt-1 text-muted">{s.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section aria-labelledby="promises" className="mx-auto max-w-6xl px-4 py-14">
          <h2 id="promises" className="font-serif text-3xl">What we won't do</h2>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {promises.map(([t, b]) => (
              <Card key={t} as="div"><h3 className="font-medium">{t}</h3><p className="mt-1 text-muted">{b}</p></Card>
            ))}
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

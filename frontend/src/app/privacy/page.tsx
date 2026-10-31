import type { Metadata } from "next";
import { SiteFooter, SiteHeader } from "@/components/site-header";

export const metadata: Metadata = { title: "Privacy" };

export default function Privacy() {
  return (
    <>
      <SiteHeader />
      <main id="main" className="mx-auto max-w-3xl px-4 py-12">
        <h1 className="font-serif text-4xl">Privacy, in plain terms</h1>
        <div className="mt-6 space-y-8 text-base leading-relaxed">
          <section aria-labelledby="where">
            <h2 id="where" className="font-serif text-2xl">
              Where your documents are processed
            </h2>
            <p className="mt-2">
              Everything happens on the server this service runs on, which is run by whoever
              operates it. Your résumé is read, analyzed and stored there. It is not sent to any
              outside AI service, and nothing is downloaded or called out to while your analysis
              runs.
            </p>
          </section>
          <section aria-labelledby="models">
            <h2 id="models" className="font-serif text-2xl">
              The models
            </h2>
            <p className="mt-2">
              When learned models are in use, they are open-weight models stored on the same server
              and run there. Each analysis lists which models were used, where they came from, their
              exact revision and licence, and whether they were published models used as they are or
              fine-tuned for this task. If the models aren&apos;t set up, a simpler rule-based
              reader is used instead, and every result says so.
            </p>
            <p className="mt-2">
              Models can be wrong. They are checked against labelled examples before being approved,
              but that doesn&apos;t make them right for every résumé.
            </p>
          </section>
          <section aria-labelledby="stored">
            <h2 id="stored" className="font-serif text-2xl">
              What is stored
            </h2>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              <li>
                The file you upload, in private storage under a random name, and the text read from
                it.
              </li>
              <li>The job descriptions you paste and the requirements taken from them.</li>
              <li>The results of your analyses.</li>
              <li>
                Your email address and a salted hash of your password, never the password itself.
              </li>
            </ul>
            <p className="mt-2">
              The operator sets the retention period and schedules retention maintenance to remove
              expired files and their derived data. You can also delete them yourself at any time.
            </p>
          </section>
          <section aria-labelledby="logs">
            <h2 id="logs" className="font-serif text-2xl">
              What logs contain
            </h2>
            <p className="mt-2">
              Operational logs record what happened (a request id, a route, a status, how long it
              took), not what your documents say. Email addresses, phone numbers and tokens are
              masked, and résumé text is never written to logs.
            </p>
          </section>
          <section aria-labelledby="delete">
            <h2 id="delete" className="font-serif text-2xl">
              Deleting things
            </h2>
            <p className="mt-2">
              You can delete any résumé or job description at any time, whatever state it is in.
              That removes the stored file, the extracted text and every analysis built on it.
              Deleting your account (it asks for your password) removes everything you have stored.
              A short anonymous record that an account was deleted is kept, with no link back to
              you.
            </p>
          </section>
          <section aria-labelledby="demo">
            <h2 id="demo" className="font-serif text-2xl">
              The demo
            </h2>
            <p className="mt-2">
              The demo uses made-up sample documents, needs no account and stores nothing.
            </p>
          </section>
          <section aria-labelledby="guest-privacy">
            <h2 id="guest-privacy" className="font-serif text-2xl">
              Guest reviews
            </h2>
            <p className="mt-2">
              One free review is available per network every 24 hours. We store a keyed hash of the
              client address to enforce this allowance, rather than the raw address. Clearing
              cookies or deleting a report does not reset it. Failed processing restores the
              allowance.
            </p>
            <p className="mt-2">
              Guest report access expires after 24 hours. Scheduled cleanup removes the documents
              and results, normally within the following hour. You can delete your guest report
              sooner from its review panel.
            </p>
          </section>
          <section aria-labelledby="cookies">
            <h2 id="cookies" className="font-serif text-2xl">
              Cookies and tracking
            </h2>
            <p className="mt-2">
              Account cookies keep you signed in and protect against forged requests. A separate
              HttpOnly guest cookie grants access to your temporary guest report. There are no
              analytics or advertising trackers.
            </p>
          </section>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}

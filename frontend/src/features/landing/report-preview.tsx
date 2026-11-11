"use client";

import { useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/icon";
import styles from "./report-preview.module.css";

const examples = {
  backend: {
    role: "Backend engineer",
    description: "Python services · PostgreSQL · Production ownership",
    findings: [
      {
        title: "Python API development",
        status: "Clear evidence",
        kind: "supported",
        requirement: "Build and maintain production APIs in Python.",
        evidence:
          "Built billing APIs in Python, with integration tests for payment and refund flows.",
        note: "The language and the work are explicit. This passage gives the requirement useful context.",
        action: "Keep the concrete description. Add the impact if you can support it.",
      },
      {
        title: "Production ownership",
        status: "Needs context",
        kind: "partial",
        requirement: "Own services from design through operation.",
        evidence: "Contributed to the billing platform and worked with the infrastructure team.",
        note: "The project is relevant, but this wording does not explain your individual responsibility.",
        action:
          "If accurate, name a design decision you owned or an operational problem you resolved.",
      },
      {
        title: "PostgreSQL optimization",
        status: "Not found",
        kind: "missing",
        requirement: "Diagnose and improve PostgreSQL query performance.",
        evidence: null,
        note: "This sample contains no passage about query optimization. That is a gap in the document, not proof of a gap in your experience.",
        action:
          "Add a specific example only if you have done this work. Otherwise, leave the gap visible.",
      },
    ],
  },
  platform: {
    role: "Platform engineer",
    description: "Deployment pipelines · Service operations · Kubernetes",
    findings: [
      {
        title: "Deployment automation",
        status: "Clear evidence",
        kind: "supported",
        requirement: "Automate build and deployment workflows.",
        evidence: "Maintained GitHub Actions workflows to test and deploy the billing service.",
        note: "The passage names the automation tool and the service it supports. It is relevant evidence for this role.",
        action:
          "Keep the specificity. If available, explain the improvement to the deployment process.",
      },
      {
        title: "Service reliability",
        status: "Needs context",
        kind: "partial",
        requirement: "Improve service reliability and respond to production incidents.",
        evidence: "Contributed to the billing platform and worked with the infrastructure team.",
        note: "Working with infrastructure is relevant context, but it does not establish incident response or reliability ownership.",
        action:
          "If accurate, describe an incident you helped resolve and the change that prevented a recurrence.",
      },
      {
        title: "Kubernetes operations",
        status: "Not found",
        kind: "missing",
        requirement: "Operate services running on Kubernetes.",
        evidence: null,
        note: "This sample does not mention Kubernetes. Deployment experience alone does not establish experience operating a cluster.",
        action:
          "Include a real example if you have one. Do not add the keyword just to improve a match.",
      },
    ],
  },
} as const;
type ExampleKey = keyof typeof examples;

export function ReportPreview() {
  const [role, setRole] = useState<ExampleKey>("backend");
  const [selected, setSelected] = useState(0);
  const example = examples[role];
  const finding = example.findings[selected] ?? example.findings[0];
  return (
    <div className={styles.preview}>
      <div className={styles.toolbar}>
        <span>
          <Icon name="document" size={16} /> A résumé, read in context
        </span>
        <span className={styles.sample}>Interactive example · synthetic data</span>
      </div>
      <div className={styles.context}>
        <div>
          <span className={styles.label}>RÉSUMÉ</span>
          <p>
            Alex Morgan <span>/ Software engineer</span>
          </p>
        </div>
        <Icon name="arrow" size={20} />
        <div className={styles.roleField}>
          <label className={styles.label} htmlFor="example-role">
            COMPARE WITH A ROLE
          </label>
          <select
            id="example-role"
            value={role}
            onChange={(event) => {
              setRole(event.target.value as ExampleKey);
              setSelected(0);
            }}
          >
            <option value="backend">Backend engineer</option>
            <option value="platform">Platform engineer</option>
          </select>
        </div>
      </div>
      <div className={styles.body}>
        <div className={styles.requirements}>
          <p className={styles.label}>WHAT THE ROLE NEEDS</p>
          <p className={styles.roleDescription}>{example.description}</p>
          <div className={styles.findings} aria-label="Sample requirements">
            {example.findings.map((item, index) => (
              <button
                key={item.title}
                type="button"
                aria-pressed={selected === index}
                aria-controls="sample-evidence"
                onClick={() => setSelected(index)}
              >
                <span className={styles.findingTitle}>
                  {item.title}
                  <Icon name="arrow" size={14} />
                </span>
                <span className={`${styles.status} ${styles[item.kind]}`}>{item.status}</span>
              </button>
            ))}
          </div>
          <p className={styles.hint}>
            Change the role. Notice how the same experience is read differently.
          </p>
        </div>
        <div id="sample-evidence" className={styles.evidence} aria-live="polite" aria-atomic="true">
          <div className={styles.evidenceHeading}>
            <span className={`${styles.status} ${styles[finding.kind]}`}>{finding.status}</span>
            <span>0{selected + 1} / 03</span>
          </div>
          <h3>{finding.title}</h3>
          <p className={styles.label}>FROM THE JOB DESCRIPTION</p>
          <p className={styles.requirement}>{finding.requirement}</p>
          <p className={styles.label}>FROM THE RÉSUMÉ</p>
          {finding.evidence ? (
            <blockquote>{finding.evidence}</blockquote>
          ) : (
            <p className={styles.noEvidence}>No supporting passage in this sample résumé.</p>
          )}
          <p className={styles.reasoning}>{finding.note}</p>
          <div className={styles.edit}>
            <span className={styles.label}>YOUR NEXT EDIT</span>
            <p>{finding.action}</p>
          </div>
        </div>
      </div>
      <div className={styles.footer}>
        <span>An editing aid, not a hiring prediction.</span>
        <Link href="/demo">
          Open the full working demo <Icon name="arrowUpRight" size={14} />
        </Link>
      </div>
    </div>
  );
}

"""Generate deterministic, annotated synthetic examples for tests and training.

Template-based data does not establish real-world accuracy. Challenge sets are held out."""

import argparse
import random
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ml.schema import (
    ExtractionRecord,
    Record,
    Requirement,
    RetrievalPassage,
    RetrievalRecord,
    VerificationRecord,
    parse_markup,
    write_jsonl,
)
from ml.split import assign
from ml.validate import normalized, record_texts

DOMAINS: dict[str, list[str]] = {
    "software": [
        "Python",
        "Java",
        "Go",
        "TypeScript",
        "React",
        "Django",
        "Spring",
        "GraphQL",
        "gRPC",
        "Redis",
    ],
    "data": [
        "SQL",
        "Spark",
        "Airflow",
        "dbt",
        "pandas",
        "scikit-learn",
        "PyTorch",
        "Snowflake",
        "Kafka",
        "Tableau",
    ],
    "devops": [
        "Kubernetes",
        "Docker",
        "Terraform",
        "Ansible",
        "Jenkins",
        "Prometheus",
        "AWS",
        "Linux",
        "Helm",
        "GitHub Actions",
    ],
    "finance": [
        "Excel",
        "Bloomberg Terminal",
        "SAP",
        "QuickBooks",
        "financial modelling",
        "IFRS",
        "Power BI",
        "VBA",
    ],
    "healthcare": [
        "Epic",
        "HL7",
        "FHIR",
        "ICD-10 coding",
        "Cerner",
        "clinical documentation",
        "HIPAA compliance",
        "triage",
    ],
    "marketing": [
        "Google Analytics",
        "SEO",
        "HubSpot",
        "Salesforce",
        "A/B Testing",
        "Mailchimp",
        "Figma",
        "Google Ads",
    ],
}
ORGS = [
    "Northwind Traders",
    "Acme Logistics",
    "Bluepeak Systems",
    "Harbor Health",
    "Lumen Retail",
    "Cobalt Labs",
    "Greenfield Bank",
    "Riverside University",
    "Summit College",
    "Alder Institute",
]
DEPARTMENTS = [
    "platform",
    "payments",
    "claims",
    "growth",
    "billing",
    "research",
    "operations",
    "support",
]
TITLES = [
    "Software Engineer",
    "Senior Engineer",
    "Data Analyst",
    "Site Reliability Engineer",
    "Marketing Manager",
    "Staff Nurse",
    "Financial Analyst",
    "Product Engineer",
    "Team Lead",
]
FIELDS = [
    "Computer Science",
    "Statistics",
    "Economics",
    "Nursing",
    "Marketing",
    "Mechanical Engineering",
    "Data Science",
]
CERTIFICATIONS = [
    "AWS Certified Solutions Architect",
    "PMP",
    "CISSP",
    "Certified Kubernetes Administrator",
    "CompTIA Security+",
    "Google Cloud Certified Professional Data Engineer",
    "Certified Scrum Master",
]
MONTHS = ["March", "June", "September", "November"]

# Requirements a passage can support without containing the requirement's words.
PARAPHRASES: dict[str, list[str]] = {
    "Kubernetes": [
        "Ran production clusters that scheduled and scaled containerised workloads across {n} nodes.",
        "Operated the container orchestration platform used by the {dept} teams.",
    ],
    "Docker": [
        "Packaged services into container images and published them to the internal registry."
    ],
    "SQL": [
        "Wrote analytical queries against the relational warehouse and tuned slow joins."
    ],
    "Terraform": [
        "Defined cloud infrastructure as code and reviewed every change before it was applied."
    ],
    "Python": [
        "Wrote the scripts and services in the interpreted language the {dept} group standardised on, mostly pytest-covered."
    ],
    "Kafka": [
        "Built event streaming pipelines that carried {n} messages a second between services."
    ],
    "Excel": [
        "Maintained the spreadsheet models the {dept} team used for monthly forecasting."
    ],
    "SEO": [
        "Improved organic search rankings by restructuring page titles, internal links and site speed."
    ],
}

EXPERIENCE_SUBJECTS: dict[str, dict[str, str]] = {
    "data engineering": {
        "supports": "Built batch and streaming pipelines that load the warehouse tables every night.",
        "mentions_only": "Sat in on data engineering stand-ups to learn how the team works.",
        "contradicts": "No data engineering experience; this is a career change from retail management.",
        "unrelated": "Managed a retail team of twelve and handled weekly scheduling.",
    },
    "people management": {
        "supports": "Managed a team of eight, ran weekly one-to-ones and handled hiring and reviews.",
        "mentions_only": "Shadowed a manager for a week to see what the role involves.",
        "contradicts": "Have never managed anyone; I prefer working as an individual contributor.",
        "unrelated": "Wrote unit tests and fixed bugs in the billing service.",
    },
    "customer support": {
        "supports": "Answered {n} customer tickets a week and escalated billing problems to the {dept} team.",
        "mentions_only": "Read through support tickets once a quarter to spot product problems.",
        "contradicts": "No customer-facing experience; all of my work has been internal tooling.",
        "unrelated": "Designed a database schema for the claims system.",
    },
    "project management": {
        "supports": "Planned and delivered a {n}-person project on schedule, tracking risks and reporting to sponsors.",
        "mentions_only": "Attended project steering meetings as a note-taker.",
        "contradicts": "Have not run a project; I have only contributed tasks to projects run by others.",
        "unrelated": "Tuned database queries and rewrote slow reports.",
    },
}

GENERIC_VAGUE = [
    "Worked on internal tooling and automation for the {dept} team.",
    "Contributed to several projects across the {dept} group and supported releases.",
    "Helped colleagues solve technical problems and documented what we learned.",
]


@dataclass(frozen=True)
class SkillPattern:
    name: str
    section: str
    template: str  # {S} is the requirement skill; {O1}, {O2} are other skills of the same domain
    role: str
    verdict: str
    others: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


PATTERNS: tuple[SkillPattern, ...] = (
    SkillPattern(
        "affirm-built",
        "experience",
        "Built and maintained {S} services for {n} internal teams.",
        "affirmed",
        "supports",
    ),
    SkillPattern(
        "affirm-migrated",
        "experience",
        "Migrated legacy workloads to {S}, cutting deployment time from {n} hours to {m} minutes.",
        "affirmed",
        "supports",
    ),
    SkillPattern(
        "affirm-designed",
        "experience",
        "Designed {S} based tooling used across the {dept} group.",
        "affirmed",
        "supports",
    ),
    SkillPattern(
        "affirm-admin",
        "experience",
        "Administered {S} in production for {n}0 users, alongside {O1}.",
        "affirmed",
        "supports",
        ("affirmed",),
    ),
    SkillPattern(
        "affirm-led",
        "experience",
        "Led the move from {O1} to {S} and trained {n} engineers on it.",
        "affirmed",
        "supports",
        ("affirmed",),
    ),
    SkillPattern(
        "mention-team",
        "experience",
        "Collaborated with the {S} team on release planning.",
        "mentioned",
        "mentions_only",
        (),
        ("mention",),
    ),
    SkillPattern(
        "mention-workshop",
        "experience",
        "Attended a workshop where {S} was demonstrated to the {dept} group.",
        "mentioned",
        "mentions_only",
        (),
        ("mention",),
    ),
    SkillPattern(
        "mention-docs",
        "experience",
        "Reviewed documentation written by engineers who use {S}.",
        "mentioned",
        "mentions_only",
        (),
        ("mention",),
    ),
    SkillPattern(
        "list-skills",
        "skills",
        "Skills: {S}, {O1}, {O2}",
        "listed",
        "mentions_only",
        ("listed", "listed"),
        ("list",),
    ),
    SkillPattern(
        "list-tools",
        "skills",
        "Tools: {O1}, {S}, {O2}",
        "listed",
        "mentions_only",
        ("listed", "listed"),
        ("list",),
    ),
    SkillPattern(
        "negate-no-exp",
        "experience",
        "No professional experience with {S}.",
        "negated",
        "contradicts",
        (),
        ("negation",),
    ),
    SkillPattern(
        "negate-not-worked",
        "experience",
        "Have not worked with {S} in a production setting.",
        "negated",
        "contradicts",
        (),
        ("negation",),
    ),
    SkillPattern(
        "negate-never",
        "experience",
        "Never used {S} beyond reading about it.",
        "negated",
        "contradicts",
        (),
        ("negation",),
    ),
    SkillPattern(
        "negate-unfamiliar",
        "experience",
        "Unfamiliar with {S}; my background is in {O1}.",
        "negated",
        "contradicts",
        ("affirmed",),
        ("negation",),
    ),
    SkillPattern(
        "hedge-learning",
        "experience",
        "Currently learning {S} through an online course.",
        "hedged",
        "mentions_only",
        (),
        ("hedge",),
    ),
    SkillPattern(
        "hedge-basic",
        "experience",
        "Basic familiarity with {S}.",
        "hedged",
        "mentions_only",
        (),
        ("hedge",),
    ),
    SkillPattern(
        "hedge-exploring",
        "experience",
        "Exploring {S} for a side project, no production use yet.",
        "hedged",
        "mentions_only",
        (),
        ("hedge",),
    ),
)


def _skill_markup(name: str, role: str) -> str:
    return f"[[{name}|SKILL|{role}]]"


def _fill(
    pattern: SkillPattern, skill: str, others: Sequence[str], rng: random.Random
) -> str:
    values = {
        "S": _skill_markup(skill, pattern.role),
        "n": str(rng.randint(3, 40)),
        "m": str(rng.randint(5, 45)),
        "dept": rng.choice(DEPARTMENTS),
    }
    for index, (name, role) in enumerate(
        zip(others, pattern.others, strict=True), start=1
    ):
        values[f"O{index}"] = _skill_markup(name, role)
    return pattern.template.format(**values)


def _header(rng: random.Random) -> str:
    year = rng.randint(2012, 2022)
    return (
        f"{rng.choice(TITLES)}, {rng.choice(ORGS)}, {year}-{year + rng.randint(1, 4)}"
    )


def _header_for(section: str, rng: random.Random) -> str | None:
    return _header(rng) if section == "experience" else None


def _skill_records(
    pattern: SkillPattern, domain: str, index: int, seed: int
) -> list[Record]:
    rng = random.Random(f"{seed}:{pattern.name}:{domain}:{index}")
    pool = DOMAINS[domain]
    skill = rng.choice(pool)
    others = rng.sample([s for s in pool if s != skill], len(pattern.others))
    text, spans = parse_markup(_fill(pattern, skill, others, rng))
    group = f"{pattern.name}:{domain}"
    header = _header_for(pattern.section, rng)
    base = {
        "group": group,
        "source": "synthetic",
        "section_kind": pattern.section,
        "entry_header": header,
    }
    tags = list(pattern.tags)
    return [
        ExtractionRecord(
            id=f"syn-x-{group}-{index}", tags=tags, text=text, spans=spans, **base
        ),
        VerificationRecord(
            id=f"syn-v-{group}-{index}",
            tags=tags,
            text=text,
            label=pattern.verdict,  # type: ignore[arg-type]
            requirement=Requirement(type="skill", value=skill),
            **base,
        ),
    ]


def _hard_negative_records(
    kind: str, domain: str, index: int, seed: int
) -> list[Record]:
    """Passages that look related but don't establish the requirement (insufficient / unrelated)."""
    rng = random.Random(f"{seed}:{kind}:{domain}:{index}")
    pool = DOMAINS[domain]
    skill = rng.choice(pool)
    group = f"{kind}:{domain}"
    dept = rng.choice(DEPARTMENTS)
    if kind == "related-tool":
        other = rng.choice([s for s in pool if s != skill])
        marked = f"Built dashboards and services using {_skill_markup(other, 'affirmed')} for the {dept} team."
        label = "insufficient"
    elif kind == "vague":
        marked = rng.choice(GENERIC_VAGUE).format(dept=dept)
        label = "insufficient"
    else:
        other_domain = rng.choice([d for d in DOMAINS if d != domain])
        other = rng.choice(DOMAINS[other_domain])
        marked = f"Built and maintained {_skill_markup(other, 'affirmed')} for the {dept} team."
        label = "unrelated"
    text, spans = parse_markup(marked)
    base = {
        "group": group,
        "source": "synthetic",
        "section_kind": "experience",
        "entry_header": _header(rng),
    }
    tags = ["hard_negative"] if label == "insufficient" else []
    return [
        ExtractionRecord(
            id=f"syn-x-{group}-{index}", tags=tags, text=text, spans=spans, **base
        ),
        VerificationRecord(
            id=f"syn-v-{group}-{index}",
            tags=tags,
            text=text,
            label=label,  # type: ignore[arg-type]
            requirement=Requirement(type="skill", value=skill),
            **base,
        ),
    ]


def _paraphrase_records(domain: str, index: int, seed: int) -> list[Record]:
    rng = random.Random(f"{seed}:paraphrase:{domain}:{index}")
    candidates = [s for s in DOMAINS[domain] if s in PARAPHRASES]
    if not candidates:
        return []
    skill = rng.choice(candidates)
    text = rng.choice(PARAPHRASES[skill]).format(
        n=rng.randint(3, 40), dept=rng.choice(DEPARTMENTS)
    )
    group = f"paraphrase:{domain}"
    base = {
        "group": group,
        "source": "synthetic",
        "section_kind": "experience",
        "entry_header": _header(rng),
    }
    return [
        VerificationRecord(
            id=f"syn-v-{group}-{index}",
            tags=["paraphrase"],
            text=text,
            label="supports",
            requirement=Requirement(type="skill", value=skill),
            **base,
        )
    ]


def _degree_records(index: int, seed: int) -> list[Record]:
    rng = random.Random(f"{seed}:degree:{index}")
    field = rng.choice(FIELDS)
    org = rng.choice(ORGS)
    year = rng.randint(2005, 2026)
    choices: list[tuple[str, str, str, tuple[str, ...]]] = [
        (
            "degree-short",
            "education",
            f"[[{rng.choice(['B.S.', 'BS', 'BSc', 'B.A.', 'BA'])}|DEGREE|affirmed]] in [[{field}|FIELD]], [[{org}|ORG]], {year}",
            (),
        ),
        (
            "degree-master",
            "education",
            f"Completed a [[{rng.choice(['Master of Science', 'Master of Arts', 'MSc', 'M.S.'])}|DEGREE|affirmed]] in [[{field}|FIELD]] at [[{org}|ORG]].",
            (),
        ),
        (
            "degree-ma-ms",
            "education",
            f"[[{rng.choice(['MA', 'MS', 'MBA'])}|DEGREE|affirmed]] in [[{field}|FIELD]], [[{org}|ORG]], {year}",
            ("degree_ambiguity",),
        ),
        (
            "degree-pursuing",
            "education",
            f"Pursuing an [[{rng.choice(['MBA', 'MS', 'MSc', 'PhD'])}|DEGREE|hedged]] at [[{org}|ORG]], expected {year + 1}.",
            ("hedge", "degree_ambiguity"),
        ),
        (
            "degree-left",
            "education",
            f"Left the [[{rng.choice(['PhD', 'MSc', 'BSc'])}|DEGREE|negated]] programme in [[{field}|FIELD]] before finishing.",
            ("negation",),
        ),
        (
            "degree-not-held",
            "education",
            f"Does not hold a [[{rng.choice(['Bachelor of Science', 'Master of Arts', 'PhD'])}|DEGREE|negated]]; self-taught in [[{field}|FIELD]].",
            ("negation",),
        ),
        (
            "distractor-state",
            "experience",
            f"Worked with clinics in Boston, MA and Portland, ME for {rng.randint(2, 9)} years.",
            ("degree_ambiguity",),
        ),
        (
            "distractor-office",
            "skills",
            f"Skills: [[MS Office|SKILL|listed]], [[{rng.choice(DOMAINS['finance'])}|SKILL|listed]]",
            ("degree_ambiguity",),
        ),
        (
            "distractor-office-sentence",
            "experience",
            f"Managed [[MS Office|SKILL|affirmed]] licences for {rng.randint(20, 400)} staff.",
            ("degree_ambiguity",),
        ),
        (
            "header",
            "experience",
            f"[[{rng.choice(TITLES)}|TITLE]], [[{org}|ORG]], {year - 3}-{year}",
            (),
        ),
    ]
    name, section, marked, tags = choices[index % len(choices)]
    text, spans = parse_markup(marked)
    return [
        ExtractionRecord(
            id=f"syn-x-{name}-{index}",
            group=f"{name}:{org}",
            source="synthetic",
            tags=list(tags),
            section_kind=section,
            entry_header=None,
            text=text,
            spans=spans,
        )
    ]


def _certification_records(index: int, seed: int) -> list[Record]:
    rng = random.Random(f"{seed}:cert:{index}")
    cert = rng.choice(CERTIFICATIONS)
    variants = [
        (
            "cert-earned",
            f"Earned the [[{cert}|CERT|affirmed]] in {rng.randint(2016, 2025)}.",
            "affirmed",
            "supports",
            (),
        ),
        (
            "cert-preparing",
            f"Preparing for the [[{cert}|CERT|hedged]]; exam booked for {rng.choice(MONTHS)}.",
            "hedged",
            "mentions_only",
            ("hedge",),
        ),
        (
            "cert-failed",
            f"Did not pass the [[{cert}|CERT|negated]] and has not retaken it.",
            "negated",
            "contradicts",
            ("negation",),
        ),
    ]
    name, marked, _, label, tags = variants[index % len(variants)]
    text, spans = parse_markup(marked)
    base = {
        "group": f"{name}:{cert}",
        "source": "synthetic",
        "section_kind": "certifications",
        "entry_header": None,
    }
    return [
        ExtractionRecord(
            id=f"syn-x-{name}-{index}", tags=list(tags), text=text, spans=spans, **base
        ),
        VerificationRecord(
            id=f"syn-v-{name}-{index}",
            tags=list(tags),
            text=text,
            label=label,  # type: ignore[arg-type]
            requirement=Requirement(type="certification", value=cert),
            **base,
        ),
    ]


def _experience_records(index: int, seed: int) -> list[Record]:
    rng = random.Random(f"{seed}:subject:{index}")
    subject = rng.choice(sorted(EXPERIENCE_SUBJECTS))
    label = ("supports", "mentions_only", "contradicts", "unrelated")[index % 4]
    text = EXPERIENCE_SUBJECTS[subject][label].format(
        n=rng.randint(3, 40), dept=rng.choice(DEPARTMENTS)
    )
    group = f"subject-{label}:{subject}"
    return [
        VerificationRecord(
            id=f"syn-v-{group}-{index}",
            group=group,
            source="synthetic",
            tags=["experience"],
            section_kind="experience",
            entry_header=_header(rng),
            text=text,
            label=label,  # type: ignore[arg-type]
            requirement=Requirement(type="experience", value=subject),
        )
    ]


def _retrieval_records(
    verifications: Sequence[VerificationRecord], seed: int, split_seed: int
) -> list[Record]:
    """Each supporting passage becomes a query. Distractors come from other groups of the same split, so a
    retrieval record never carries text from a different split."""
    rng = random.Random(f"{seed}:retrieval")
    supporting = [
        v
        for v in verifications
        if v.label == "supports" and v.requirement.type == "skill"
    ]
    out: list[Record] = []
    for record in supporting:
        split = assign(record.group, split_seed)
        others = [
            v
            for v in verifications
            if v.group != record.group
            and v.requirement.value != record.requirement.value
            and assign(v.group, split_seed) == split
        ]
        distractors = rng.sample(others, min(7, len(others)))
        passages = [RetrievalPassage(id="p0", text=record.text, relevant=True)]
        passages += [
            RetrievalPassage(id=f"p{i}", text=d.text, relevant=False)
            for i, d in enumerate(distractors, start=1)
        ]
        rng.shuffle(passages)
        out.append(
            RetrievalRecord(
                id=f"syn-r-{record.id.removeprefix('syn-v-')}",
                group=record.group,
                source="synthetic",
                tags=list(record.tags),
                query=record.requirement.value,
                passages=passages,
            )
        )
    return out


def generate(per_pattern: int, seed: int, split_seed: int) -> list[Record]:
    records: list[Record] = []
    for pattern in PATTERNS:
        for domain in DOMAINS:
            for index in range(per_pattern):
                records += _skill_records(pattern, domain, index, seed)
    for kind in ("related-tool", "vague", "other-domain"):
        for domain in DOMAINS:
            for index in range(per_pattern):
                records += _hard_negative_records(kind, domain, index, seed)
    for domain in DOMAINS:
        for index in range(per_pattern):
            records += _paraphrase_records(domain, index, seed)
    for index in range(per_pattern * 10):
        records += _degree_records(index, seed)
    for index in range(per_pattern * 3):
        records += _certification_records(index, seed)
    for index in range(per_pattern * 4):
        records += _experience_records(index, seed)
    records = _unify_groups(_dedupe(records))
    verifications = [r for r in records if isinstance(r, VerificationRecord)]
    return records + _retrieval_records(verifications, seed, split_seed)


def _unify_groups(records: Sequence[Record]) -> list[Record]:
    """Records with identical text always share a group, so they can never be split apart."""
    parent: dict[str, str] = {}

    def find(group: str) -> str:
        parent.setdefault(group, group)
        while parent[group] != group:
            parent[group] = parent[parent[group]]
            group = parent[group]
        return group

    owner: dict[str, str] = {}
    for record in records:
        for text in record_texts(record):
            key = normalized(text)
            if key in owner:
                parent[find(record.group)] = find(owner[key])
            else:
                owner[key] = record.group
                find(record.group)
    return [
        record.model_copy(
            update={"group": min(g for g in parent if find(g) == find(record.group))}
        )
        for record in records
    ]


def _dedupe(records: Sequence[Record]) -> list[Record]:
    seen: set[str] = set()
    kept: list[Record] = []
    for record in records:
        if isinstance(record, VerificationRecord):
            key = f"v|{normalized(record.text)}|{normalized(record.requirement.value)}"
        elif isinstance(record, ExtractionRecord):
            key = f"x|{normalized(record.text)}"
        else:
            key = f"r|{record.id}"
        if key not in seen:
            seen.add(key)
            kept.append(record)
    return kept


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--per-pattern", type=int, default=12)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--split-seed",
        type=int,
        default=13,
        help="must match the seed given to ml.split",
    )
    args = parser.parse_args(argv)
    records = generate(args.per_pattern, args.seed, args.split_seed)
    write_jsonl(args.out, records)
    print(f"wrote {len(records)} records to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Which chapter each topic belongs to.

The four levels the user described:

    Operating Systems   subject
    Process Management  chapter   <- this file defines these
    CPU Scheduling      topic     <- existing `topics` rows, by slug
    FCFS, SJF, ...      concepts  <- existing `concepts` rows

Held as data rather than inferred, because grouping topics into chapters is
a curriculum judgement and a wrong guess is worse than no chapter at all:
a student revising "Memory Management" who is silently shown paging *and*
pipelining learns the syllabus wrong. Every grouping here follows the
standard GATE CSE syllabus divisions.

Order within each subject is study order, and it matches the order already
established in `curriculum.py` -- chapters group runs of topics that were
already adjacent there, so the sequence is preserved rather than reshuffled.

Topic slugs must match `topics.slug` exactly. `validate()` checks that and
is run by the migration before it writes anything, so a typo fails loudly
instead of leaving a topic unmapped.
"""

#: subject slug -> ordered list of (chapter slug, chapter name, [topic slugs])
CHAPTER_MAP: dict[str, list[tuple[str, str, list[str]]]] = {

    "engineering-mathematics": [
        ("discrete-mathematics", "Discrete Mathematics", [
            "logic-predicates",
            "sets-relations",
            "combinatorics",
        ]),
        ("graph-theory", "Graph Theory", [
            "graph-theory",
        ]),
        ("linear-algebra", "Linear Algebra", [
            "linear-algebra",
        ]),
        ("calculus", "Calculus", [
            "calculus",
        ]),
        ("probability-statistics", "Probability & Statistics", [
            "probability-distributions",
        ]),
    ],

    "digital-logic": [
        ("number-systems", "Number Systems & Representation", [
            "number-systems",
        ]),
        ("boolean-algebra", "Boolean Algebra & Minimisation", [
            "boolean-kmaps",
        ]),
        ("combinational-circuits", "Combinational Circuits", [
            "combinational-circuits",
        ]),
        ("sequential-circuits", "Sequential Circuits", [
            "sequential-circuits",
        ]),
    ],

    "programming-data-structures": [
        ("programming-in-c", "Programming in C", [
            "c-programming-pointers",
            "recursion-stack",
        ]),
        ("linear-data-structures", "Linear Data Structures", [
            "stacks-queues-hashing",
        ]),
        ("trees-heaps", "Trees & Heaps", [
            "trees-bst-avl",
            "heaps-priority-queues",
        ]),
    ],

    "algorithms": [
        ("complexity-analysis", "Complexity Analysis", [
            "asymptotic-analysis",
            "recurrences",
        ]),
        ("algorithm-design", "Algorithm Design Paradigms", [
            "divide-conquer",
            "greedy-algorithms",
            "dynamic-programming",
        ]),
        ("graph-algorithms", "Graph Algorithms", [
            "shortest-paths",
        ]),
    ],

    "theory-of-computation": [
        ("regular-languages", "Regular Languages & Finite Automata", [
            "regular-languages-fa",
            "closure-properties",
        ]),
        ("context-free-languages", "Context-Free Languages", [
            "cfg-pda",
        ]),
        ("computability", "Turing Machines & Undecidability", [
            "turing-decidability",
        ]),
    ],

    "computer-organization-architecture": [
        ("instruction-set-architecture", "Instruction Set Architecture", [
            "addressing-modes",
        ]),
        ("pipelining", "Pipelining", [
            "instruction-pipelining",
        ]),
        ("memory-hierarchy", "Memory Hierarchy", [
            "cache-memory",
            "memory-hierarchy",
        ]),
        ("io-organization", "I/O Organisation", [
            "io-organization",
        ]),
    ],

    "compiler-design": [
        ("parsing", "Parsing", [
            "ll1-parsing",
            "lr-parsing",
        ]),
        ("semantic-analysis", "Syntax Directed Translation", [
            "sdt-translation",
        ]),
        ("code-generation", "Intermediate Code & Optimisation", [
            "intermediate-code-optimization",
        ]),
    ],

    "operating-systems": [
        # The user's own example: Process Management is the chapter, CPU
        # Scheduling the topic.
        ("process-management", "Process Management", [
            "process-pcb-context-switching",
            "process-threads",
            "cpu-scheduling",
            "process-synchronization",
            "deadlocks",
        ]),
        ("memory-management", "Memory Management", [
            "paging-tlb",
            "page-replacement",
        ]),
        # `miscellaneous` is a junk bucket carrying 5 concepts. Kept as its
        # own chapter rather than forced into one of the above, because
        # filing it wrongly would misrepresent what those concepts teach.
        # Flagged by the review report for reassignment.
        ("other", "Other Topics", [
            "miscellaneous",
        ]),
    ],

    "databases": [
        ("relational-model", "Relational Model & Query Languages", [
            "relational-algebra",
            "sql-queries",
        ]),
        ("database-design", "Database Design & Normalisation", [
            "normalization-fd",
        ]),
        ("transactions", "Transactions & Concurrency Control", [
            "transactions-concurrency",
        ]),
        ("file-organization", "Indexing & File Organisation", [
            "b-trees-indexing",
        ]),
    ],

    "computer-networks": [
        ("data-link-layer", "Data Link Layer", [
            "sliding-window-protocols",
        ]),
        ("network-layer", "Network Layer", [
            "ipv4-subnetting",
            "routing-algorithms",
        ]),
        ("transport-layer", "Transport Layer", [
            "tcp-congestion-control",
        ]),
        # DNS and RSA. Two different layers strictly speaking, but GATE
        # examines them together at the top of the stack, and splitting 24
        # questions across two near-empty chapters would help nobody.
        ("application-layer-security", "Application Layer & Security", [
            "app-layer-crypto",
        ]),
    ],

    "general-aptitude": [
        ("verbal-aptitude", "Verbal Aptitude", [
            "verbal-aptitude",
        ]),
        ("quantitative-aptitude", "Quantitative Aptitude", [
            "quantitative-aptitude",
        ]),
        ("reasoning", "Analytical & Spatial Reasoning", [
            "analytical-reasoning",
            "spatial-aptitude",
        ]),
    ],
}


def topic_to_chapter() -> dict[str, tuple[str, str, str, int, int]]:
    """Flatten to: topic slug -> (subject, chapter slug, name, chap seq, topic seq).

    Keyed by topic slug alone. Topic slugs are not globally unique in
    principle, but `validate_unique()` confirms they are in practice before
    the migration relies on it.
    """
    out: dict[str, tuple[str, str, str, int, int]] = {}
    for subject, chapters in CHAPTER_MAP.items():
        for chapter_seq, (chap_slug, chap_name, topics) in enumerate(chapters):
            for topic_seq, topic_slug in enumerate(topics):
                out[topic_slug] = (
                    subject, chap_slug, chap_name, chapter_seq, topic_seq,
                )
    return out


def validate_unique() -> list[str]:
    """Report any topic slug listed under more than one chapter."""
    seen: dict[str, str] = {}
    problems: list[str] = []
    for subject, chapters in CHAPTER_MAP.items():
        for chap_slug, _name, topics in chapters:
            for topic in topics:
                where = f"{subject}/{chap_slug}"
                if topic in seen:
                    problems.append(
                        f"{topic!r} listed twice: {seen[topic]} and {where}"
                    )
                seen[topic] = where
    return problems


def chapter_count() -> int:
    return sum(len(chapters) for chapters in CHAPTER_MAP.values())


def topic_count() -> int:
    return sum(
        len(topics)
        for chapters in CHAPTER_MAP.values()
        for _s, _n, topics in chapters
    )

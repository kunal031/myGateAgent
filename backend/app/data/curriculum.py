"""The order to study GATE CSE in, as the student laid it out.

This is a dependency order, not an exam-weight order. Discrete Mathematics
comes first because logic, sets, relations and graphs underpin everything
after it; Compiler Design comes last because it needs Theory of Computation
for parsing and Data Structures for symbol tables. Sorting by marks -- as
the feed did -- puts General Aptitude ahead of the maths that Algorithms
depends on, which is the wrong thing to study first however many marks it
carries.

Each subject lists its topics in teaching order. The slugs are the ones in
the database, so a topic the plan names but the syllabus does not have is
simply absent here and falls to the end of its subject.

`TRAPS` records what each topic is actually tested on. The feed does not
order by it, but generation and the assistant can use it to aim cards at
the question types that appear, rather than at whatever the textbook
happens to emphasise.
"""

#: Subjects in study order. Position is what matters, not the numbers.
SUBJECT_ORDER = [
    "engineering-mathematics",          # 1. logic, sets, combinatorics, graphs
    "programming-data-structures",      # 2. C and the structures everything uses
    "digital-logic",                    # 3. number systems upward
    "algorithms",                       # 4. needs maths and data structures
    "theory-of-computation",            # 5. needs sets and graphs
    "computer-organization-architecture",  # 6. needs digital logic
    "compiler-design",                  # 7. needs TOC and data structures
    "operating-systems",                # 8. needs COA
    "databases",                        # 9. needs sets, relations, B-trees
    "computer-networks",                # 10. largely self-contained
    "general-aptitude",                 # 11. no prerequisites; revise anytime
]

#: Topics in teaching order within each subject. A slug missing from the
#: database is ignored; a database topic missing here sorts after the
#: listed ones, so an unmapped topic is demoted rather than lost.
TOPIC_ORDER: dict[str, list[str]] = {
    "engineering-mathematics": [
        "logic-predicates",             # mathematical logic and proofs
        "sets-relations",               # sets, relations, functions, algebra
        "combinatorics",                # counting and recurrences
        "graph-theory",
        "linear-algebra",
        "calculus",
        "probability-distributions",
    ],
    "programming-data-structures": [
        "c-programming-pointers",       # C internals first
        "stacks-queues-hashing",        # linear structures
        "recursion-stack",
        "trees-bst-avl",                # non-linear structures
        "heaps-priority-queues",
    ],
    "digital-logic": [
        "number-systems",               # everything else is built on these
        "boolean-kmaps",
        "combinational-circuits",
        "sequential-circuits",
    ],
    "algorithms": [
        "asymptotic-analysis",
        "recurrences",
        "divide-conquer",
        "greedy-algorithms",
        "dynamic-programming",
        "shortest-paths",               # graph algorithms last
    ],
    "theory-of-computation": [
        "regular-languages-fa",
        "closure-properties",
        "cfg-pda",
        "turing-decidability",
    ],
    "computer-organization-architecture": [
        "addressing-modes",             # instruction set architecture first
        "instruction-pipelining",
        "cache-memory",
        "memory-hierarchy",
        "io-organization",
    ],
    "compiler-design": [
        "ll1-parsing",                  # lexical analysis then top-down
        "lr-parsing",
        "sdt-translation",
        "intermediate-code-optimization",
    ],
    "operating-systems": [
        "process-pcb-context-switching",  # processes before scheduling
        "process-threads",
        "cpu-scheduling",
        "process-synchronization",
        "deadlocks",
        "paging-tlb",                   # memory management
        "page-replacement",
        "miscellaneous",
    ],
    "databases": [
        "relational-algebra",           # the model before the language
        "sql-queries",
        "normalization-fd",
        "transactions-concurrency",
        "b-trees-indexing",
    ],
    "computer-networks": [
        "sliding-window-protocols",     # data link layer
        "ipv4-subnetting",              # network layer
        "routing-algorithms",
        "tcp-congestion-control",       # transport layer
        "app-layer-crypto",             # application layer
    ],
    "general-aptitude": [
        "verbal-aptitude",
        "quantitative-aptitude",
        "analytical-reasoning",
        "spatial-aptitude",
    ],
}

#: What each topic is actually examined on. Used to aim generated cards and
#: to let the assistant answer "what do they ask here?" -- not for ordering.
TRAPS: dict[str, list[str]] = {
    "logic-predicates": [
        "Translating English assertions into first-order logic",
        "Validity under empty vs non-empty universes",
        "Tautology vs contradiction vs satisfiable",
    ],
    "sets-relations": [
        "Counting reflexive/symmetric/asymmetric relations on n elements",
        "LUB and GLB in non-trivial Hasse diagrams",
        "Whether a lattice is distributive or complemented",
        "Order of elements in cyclic groups; Lagrange's theorem",
    ],
    "combinatorics": [
        "Distributing distinct vs identical items into bins with capacity limits",
        "Extracting coefficients from generating functions",
        "Boundary conditions in non-homogeneous recurrences",
    ],
    "graph-theory": [
        "Counting non-isomorphic trees and graphs on n vertices",
        "Planarity bounds: E <= 3V-6, and E <= 2V-4 when triangle-free",
        "Maximum matching vs minimum vertex cover in bipartite graphs",
    ],
    "linear-algebra": [
        "Unique/infinite/no solutions from rank(A) vs rank(A|b)",
        "Eigenvalues of A^-1, A^k and A+cI without the characteristic polynomial",
    ],
    "calculus": [
        "L'Hopital on 0/0, inf/inf and 1^inf forms",
    ],
    "probability-distributions": [
        "False positive and negative rates via Bayes",
        "Memoryless property of geometric and exponential distributions",
        "Expectation of a sum of indicator variables",
    ],
    "c-programming-pointers": [
        "Pre- vs post-increment and undefined behaviour",
        "*(*(arr+i)+j) vs *(arr+i)+j in multi-dimensional arrays",
        "Static variables preserved across recursive calls",
    ],
    "stacks-queues-hashing": [
        "k-dimensional array address with arbitrary starting indices",
        "Stacks from queues and queues from two stacks, with amortised cost",
        "Valid output permutations of a restricted stack",
        "Linear probing search cost after deletions",
        "Primary vs secondary clustering",
    ],
    "trees-bst-avl": [
        "Reconstruction from inorder+preorder vs preorder+postorder",
        "Valid BST deletion replacements",
    ],
    "heaps-priority-queues": [
        "Bottom-up build-heap O(n) vs repeated insertion O(n log n)",
    ],
    "number-systems": [
        "Negative decimals to IEEE 754 32-bit hex",
        "Overflow flag V = Cin XOR Cout in two's complement",
    ],
    "boolean-kmaps": [
        "Minimum 2-input NAND/NOR gates for a given function",
        "Essential prime implicants from K-maps or algebra",
        "Static and dynamic hazards",
    ],
    "combinational-circuits": [
        "A function on a single 4x1 or 8x1 MUX, with and without inverted inputs",
        "Cascading 2x4 decoders into a 4x16 using enable pins",
        "Ripple carry vs carry lookahead delay",
    ],
    "sequential-circuits": [
        "Counter sequences under combinational feedback",
        "Maximum clock frequency from setup, hold and propagation delays",
        "Modulo-N transitions and lockout states",
    ],
    "asymptotic-analysis": [
        "Ordering n^log n vs 2^sqrt(n) vs (log n)!",
    ],
    "recurrences": [
        "Master theorem gap cases where it does not apply",
    ],
    "divide-conquer": [
        "Minimum comparisons for max and min: ceil(3n/2) - 2",
        "Quicksort depth under a 99:1 split",
        "Stability and in-place constraints",
    ],
    "greedy-algorithms": [
        "Huffman tree height, codeword length, compressed size in bits",
        "Whether a greedy heuristic is optimal, or a counterexample",
    ],
    "dynamic-programming": [
        "Parenthesisations and scalar multiplications in matrix chain",
        "Reconstructing the solution path from the DP table",
        "Reducing O(n^2) states to O(n)",
    ],
    "shortest-paths": [
        "Cycle detection via DFS back edges, directed vs undirected",
        "MST uniqueness with distinct vs duplicate edge weights",
        "Dijkstra on negative edges vs negative cycles",
        "Updating shortest paths after one edge changes, in O(V+E)",
    ],
    "regular-languages-fa": [
        "Minimum DFA states for divisibility by k in base b",
        "Pumping lemma on a^n b^n, a^p for prime p, and ww^R",
    ],
    "closure-properties": [
        "Closure under Prefix, Suffix, Half and homomorphism",
    ],
    "cfg-pda": [
        "Proving ambiguity, e.g. the dangling else",
        "wcw^R is DCFL while ww^R is CFL but not DCFL",
        "CFLs are not closed under intersection or complement",
    ],
    "turing-decidability": [
        "Rice's theorem on semantic properties",
        "Membership, emptiness, finiteness and equivalence by language class",
    ],
    "addressing-modes": [
        "Opcode size and expanding opcodes in fixed-length instructions",
        "PC-relative branch targets, accounting for the PC increment",
        "Control store size: horizontal vs vertical microprogramming",
    ],
    "instruction-pipelining": [
        "Speedup with non-uniform stage delays and latch overhead",
        "Exact cycles with and without operand forwarding",
        "Stall cycles for conditional branches",
    ],
    "cache-memory": [
        "Tag array overhead including dirty, valid and LRU bits",
        "Hit/miss trace through a k-way set associative cache",
        "AMAT: simultaneous vs hierarchical access",
    ],
    "memory-hierarchy": [
        "Virtual address split across page directory, table and offset",
        "EMAT with two-level paging, TLB hit ratio and fault service time",
    ],
    "io-organization": [
        "Contiguous vs random sector read times",
        "DMA cycle stealing and CPU slowdown",
    ],
    "ll1-parsing": [
        "Token count in a C snippet, including string literals",
        "Maximal munch, e.g. a+++++b",
        "Is the grammar LL(1)?",
    ],
    "lr-parsing": [
        "LL(1) vs SLR(1) vs LALR(1) vs CLR(1) classification",
        "RR conflicts can appear when merging CLR to LALR; SR conflicts cannot",
        "Tracing shift/reduce moves",
    ],
    "sdt-translation": [
        "Synthesised vs inherited attributes, S- vs L-attributed",
        "Minimum nodes and edges in a DAG for a basic block",
    ],
    "intermediate-code-optimization": [
        "Static vs dynamic scoping output with nested calls",
        "Leader instructions and basic block partitioning",
        "Loop invariant detection and strength reduction",
    ],
    "process-pcb-context-switching": [
        "Process count from nested fork() loops",
    ],
    "process-threads": [
        "User-level vs kernel-level thread behaviour",
    ],
    "cpu-scheduling": [
        "Average waiting and turnaround time with preemption and arrivals",
        "Convoy effect in FCFS; starvation in SRTF and priority",
    ],
    "process-synchronization": [
        "Whether a protocol guarantees mutual exclusion and progress",
        "Maximum and minimum semaphore values after P/V sequences",
        "Starvation in reader-writer variants",
    ],
    "deadlocks": [
        "Minimum resources to prevent deadlock across n processes",
        "Banker's algorithm: safe sequences and immediate grants",
    ],
    "paging-tlb": [
        "Address split for multi-level paging",
        "EMAT with TLB hit ratio and page fault service",
    ],
    "page-replacement": [
        "Exact faults under FIFO vs LRU vs Optimal",
        "Belady's anomaly",
    ],
    "miscellaneous": [
        "Head movement across FCFS, SSTF, SCAN, C-SCAN, LOOK, C-LOOK",
        "Maximum file size from inode direct and indirect pointers",
    ],
    "relational-algebra": [
        "Universal queries via division vs nested negation",
        "Equivalent algebra expressions and empty results",
    ],
    "sql-queries": [
        "NULL in three-valued logic: salary > 1000 OR salary <= 1000 omits NULLs",
        "Correlated subqueries with EXISTS and NOT EXISTS",
        "Row counts after multiple left outer joins",
    ],
    "normalization-fd": [
        "Counting candidate keys for a relation and FD set",
        "Highest normal form of a schema",
        "Lossless join by matrix test or intersection key rule",
    ],
    "transactions-concurrency": [
        "Precedence graphs for conflict serialisability",
        "Recoverable vs cascadeless vs strict schedules",
        "2PL: deadlock possible, serialisability guaranteed",
    ],
    "b-trees-indexing": [
        "Max and min keys/pointers in B and B+ nodes of order p",
        "B+ tree height from block, key and pointer sizes",
        "Block accesses with and without an index",
    ],
    "sliding-window-protocols": [
        "Minimum frame size for CSMA/CD over a given cable length",
        "Sequence bits for Go-Back-N vs Selective Repeat",
        "CRC remainder for a given divisor polynomial",
    ],
    "ipv4-subnetting": [
        "Fragment offset and MF flag across MTUs",
        "Longest prefix match on a routing table",
    ],
    "routing-algorithms": [
        "Distance vector updates after a link failure",
        "Count-to-infinity and split horizon",
    ],
    "tcp-congestion-control": [
        "cwnd across rounds: timeout vs triple duplicate ACK",
        "Throughput limited by receiver buffer vs bandwidth",
        "Sequence and ACK progression in bidirectional streams",
    ],
    "app-layer-crypto": [
        "Page download time: persistent vs non-persistent HTTP",
        "DNS latency across root, TLD and authoritative servers",
    ],
}


def subject_rank(slug: str) -> int:
    """Position in the study order; unlisted subjects sort last."""
    try:
        return SUBJECT_ORDER.index(slug)
    except ValueError:
        return len(SUBJECT_ORDER)


def topic_rank(subject_slug: str, topic_slug: str) -> int:
    """Position within a subject; unlisted topics sort after listed ones."""
    order = TOPIC_ORDER.get(subject_slug, [])
    try:
        return order.index(topic_slug)
    except ValueError:
        return len(order)


def sort_topics(subject_slug: str, topics: list) -> list:
    """Put a subject's topics in teaching order.

    Anything listing topics for a human -- the syllabus tree, the quiz and
    test pickers -- should go through this. Database order is insertion
    order, which for several subjects is close to reverse teaching order:
    Digital Logic listed Boolean Algebra before Number Systems, and
    Operating Systems listed Synchronization before Processes.

    Topics are matched on `.slug`; one the curriculum does not name keeps
    its relative position at the end rather than disappearing.
    """
    return sorted(
        topics,
        key=lambda t: (topic_rank(subject_slug, t.slug), t.id),
    )


def sort_subjects(subjects: list) -> list:
    """Put subjects in study order, by `.slug`."""
    return sorted(subjects, key=lambda s: (subject_rank(s.slug), s.id))

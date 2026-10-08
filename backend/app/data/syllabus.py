# Complete official GATE CSE 2027 Syllabus Structure
# Weightage reflects average marks over 2015-2026

SYLLABUS_DATA = [
    {
        "name": "General Aptitude",
        "slug": "general-aptitude",
        "icon": "Brain",
        "weightage_marks": 15.0,
        "description": "Verbal Aptitude, Quantitative Aptitude, Analytical Aptitude, and Spatial Aptitude (15 marks guaranteed in GATE).",
        "topics": [
            {"name": "Quantitative Aptitude (Ratio, %, Work, Speed, Geometry)", "slug": "quantitative-aptitude", "importance": "Core"},
            {"name": "Analytical & Logical Reasoning (Syllogisms, Blood Relations, Sequences)", "slug": "analytical-reasoning", "importance": "Core"},
            {"name": "Spatial Aptitude (Transformation, Paper Folding, Mirror)", "slug": "spatial-aptitude", "importance": "High"},
            {"name": "Verbal Aptitude (Grammar, Vocab, Sentence Completion)", "slug": "verbal-aptitude", "importance": "Medium"}
        ]
    },
    {
        "name": "Engineering Mathematics",
        "slug": "engineering-mathematics",
        "icon": "Sigma",
        "weightage_marks": 13.0,
        "description": "Discrete Mathematics, Linear Algebra, Calculus, and Probability & Statistics.",
        "topics": [
            {"name": "Propositional & First-Order Logic", "slug": "logic-predicates", "importance": "Core"},
            {"name": "Set Theory, Relations & Equivalence Classes", "slug": "sets-relations", "importance": "Core"},
            {"name": "Combinatorics & Generating Functions", "slug": "combinatorics", "importance": "High"},
            {"name": "Graph Theory (Coloring, Matching, Trees, Planarity)", "slug": "graph-theory", "importance": "Core"},
            {"name": "Linear Algebra (Eigenvalues, Rank, System of Equations)", "slug": "linear-algebra", "importance": "Core"},
            {"name": "Calculus (Limits, Continuity, Maxima/Minima)", "slug": "calculus", "importance": "Medium"},
            {"name": "Probability & Distributions (Bayes, Conditional, Expectation)", "slug": "probability-distributions", "importance": "Core"}
        ]
    },
    {
        "name": "Digital Logic",
        "slug": "digital-logic",
        "icon": "Cpu",
        "weightage_marks": 5.0,
        "description": "Boolean algebra, Minimization, Combinational & Sequential Circuits, Number representations.",
        "topics": [
            {"name": "Boolean Algebra & K-Maps", "slug": "boolean-kmaps", "importance": "High"},
            {"name": "Combinational Circuits (Multiplexers, Decoders, Adders)", "slug": "combinational-circuits", "importance": "Core"},
            {"name": "Sequential Circuits (Flip-Flops, Counters, FSMs)", "slug": "sequential-circuits", "importance": "Core"},
            {"name": "Number Representation & Fixed/Floating Point", "slug": "number-systems", "importance": "Medium"}
        ]
    },
    {
        "name": "Computer Organization & Architecture",
        "slug": "computer-organization-architecture",
        "icon": "Layers",
        "weightage_marks": 8.0,
        "description": "Machine instructions, Addressing modes, ALU, Pipelining, Memory hierarchy, Cache, I/O.",
        "topics": [
            {"name": "Instruction Pipelining & Hazard Resolution", "slug": "instruction-pipelining", "importance": "Core"},
            {"name": "Cache Memory (Direct, Associative, Hit/Miss latency)", "slug": "cache-memory", "importance": "Core"},
            {"name": "Addressing Modes & Instruction Cycles", "slug": "addressing-modes", "importance": "High"},
            {"name": "Secondary Storage & Virtual Memory Mapping", "slug": "memory-hierarchy", "importance": "High"},
            {"name": "I/O Organization (Interrupts, DMA, Polling)", "slug": "io-organization", "importance": "Medium"}
        ]
    },
    {
        "name": "Programming & Data Structures",
        "slug": "programming-data-structures",
        "icon": "Code",
        "weightage_marks": 9.0,
        "description": "C Programming constructs, Recursion, Pointers, Arrays, Stacks, Queues, Linked Lists, Trees, Heaps.",
        "topics": [
            {"name": "C Programming, Pointers & Parameter Passing", "slug": "c-programming-pointers", "importance": "Core"},
            {"name": "Recursion & Call Stack Analysis", "slug": "recursion-stack", "importance": "Core"},
            {"name": "Binary Search Trees & AVL Trees", "slug": "trees-bst-avl", "importance": "Core"},
            {"name": "Priority Queues & Binary Heaps", "slug": "heaps-priority-queues", "importance": "High"},
            {"name": "Stacks, Queues, and Hashing", "slug": "stacks-queues-hashing", "importance": "High"}
        ]
    },
    {
        "name": "Algorithms",
        "slug": "algorithms",
        "icon": "Zap",
        "weightage_marks": 8.0,
        "description": "Asymptotic analysis, Recurrence relations, Divide & Conquer, Greedy, DP, Graph algorithms.",
        "topics": [
            {"name": "Asymptotic Notation & Time Complexity", "slug": "asymptotic-analysis", "importance": "Core"},
            {"name": "Recurrence Relations (Master Theorem, Substitution)", "slug": "recurrences", "importance": "Core"},
            {"name": "Divide and Conquer (Sorting & Order Statistics)", "slug": "divide-conquer", "importance": "High"},
            {"name": "Greedy Algorithms (MST: Prim/Kruskal, Huffman)", "slug": "greedy-algorithms", "importance": "High"},
            {"name": "Dynamic Programming (LCS, Knapsack, Matrix Chain)", "slug": "dynamic-programming", "importance": "Core"},
            {"name": "Shortest Paths (Dijkstra, Bellman-Ford, Floyd-Warshall)", "slug": "shortest-paths", "importance": "Core"}
        ]
    },
    {
        "name": "Theory of Computation",
        "slug": "theory-of-computation",
        "icon": "GitBranch",
        "weightage_marks": 8.0,
        "description": "Regular languages, Finite automata, Context-free languages, Pushdown automata, Turing machines, Decidability.",
        "topics": [
            {"name": "DFA, NFA, Regular Expressions & Pumping Lemma", "slug": "regular-languages-fa", "importance": "Core"},
            {"name": "Closure Properties of Regular & Context-Free Languages", "slug": "closure-properties", "importance": "Core"},
            {"name": "Context-Free Grammars & Pushdown Automata", "slug": "cfg-pda", "importance": "High"},
            {"name": "Turing Machines & Decidability / Undecidability (Rice Theorem)", "slug": "turing-decidability", "importance": "Core"}
        ]
    },
    {
        "name": "Compiler Design",
        "slug": "compiler-design",
        "icon": "Terminal",
        "weightage_marks": 4.0,
        "description": "Lexical analysis, Parsing (LL, LR, LALR), Syntax-directed translation, Intermediate code, Basic blocks.",
        "topics": [
            {"name": "LL(1) Parsing & First/Follow Sets", "slug": "ll1-parsing", "importance": "Core"},
            {"name": "LR Parsing (SLR, CLR, LALR) & Conflict Resolution", "slug": "lr-parsing", "importance": "Core"},
            {"name": "Syntax Directed Translation (SDT & S/L-attributed)", "slug": "sdt-translation", "importance": "High"},
            {"name": "Intermediate Code Generation & Basic Blocks", "slug": "intermediate-code-optimization", "importance": "Medium"}
        ]
    },
    {
        "name": "Operating Systems",
        "slug": "operating-systems",
        "icon": "Server",
        "weightage_marks": 9.0,
        "description": "Processes, Threads, CPU Scheduling, Synchronization, Deadlocks, Memory Management, File Systems.",
        "topics": [
            {"name": "Process Synchronization (Semaphores, Peterson's, Mutex)", "slug": "process-synchronization", "importance": "Core"},
            {"name": "CPU Scheduling Algorithms & Convoy Effect", "slug": "cpu-scheduling", "importance": "High"},
            {"name": "Deadlock Handling (Banker's Algorithm, Resource Allocation Graphs)", "slug": "deadlocks", "importance": "Core"},
            {"name": "Paging, Multi-level Paging, TLB & Inverted Page Tables", "slug": "paging-tlb", "importance": "Core"},
            {"name": "Page Replacement Algorithms (FIFO, LRU, Optimal)", "slug": "page-replacement", "importance": "High"}
        ]
    },
    {
        "name": "Databases (DBMS)",
        "slug": "databases",
        "icon": "Database",
        "weightage_marks": 7.0,
        "description": "ER Model, Relational algebra, SQL, Normalization (1NF to BCNF), Transactions & Concurrency control.",
        "topics": [
            {"name": "Functional Dependencies & Normal Forms (3NF, BCNF, Minimal Cover)", "slug": "normalization-fd", "importance": "Core"},
            {"name": "Transactions, ACID Properties, Serializability & 2PL", "slug": "transactions-concurrency", "importance": "Core"},
            {"name": "Relational Algebra & Tuple Relational Calculus", "slug": "relational-algebra", "importance": "High"},
            {"name": "SQL Queries (Subqueries, Aggregates, Joins)", "slug": "sql-queries", "importance": "High"},
            {"name": "B & B+ Trees (Index structures, Node capacities)", "slug": "b-trees-indexing", "importance": "Core"}
        ]
    },
    {
        "name": "Computer Networks",
        "slug": "computer-networks",
        "icon": "Globe",
        "weightage_marks": 8.0,
        "description": "OSI & TCP/IP layers, Framing, Error control, Flow control (Sliding Window), IP addressing, Routing, TCP/UDP.",
        "topics": [
            {"name": "IPv4 Subnetting, CIDR, Supernetting & NAT", "slug": "ipv4-subnetting", "importance": "Core"},
            {"name": "TCP Flow & Congestion Control (Slow Start, AIMD)", "slug": "tcp-congestion-control", "importance": "Core"},
            {"name": "Sliding Window Protocols (Stop-and-Wait, Go-Back-N, SR)", "slug": "sliding-window-protocols", "importance": "Core"},
            {"name": "Routing Algorithms (Distance Vector & Link State)", "slug": "routing-algorithms", "importance": "High"},
            {"name": "Application Layer Protocols (DNS, HTTP, SMTP) & Cryptography", "slug": "app-layer-crypto", "importance": "Medium"}
        ]
    }
]

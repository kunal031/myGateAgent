import json

SEED_FEED_CARDS = [
    {
        "subject_slug": "operating-systems",
        "topic_slug": "paging-tlb",
        "card_type": "TRAP",
        "title": "Page Size and Page Offset Trap",
        "content": "When page size is doubled, the number of bits required for the **Page Offset (d)** increases by 1 bit, which means the **Page Number (p)** field decreases by 1 bit!\n\n**Common Trap**: GATE often asks how the page table size changes when page size increases by factor of $2^k$. Each entry might remain same size, but the number of entries drops by factor of $2^k$, shrinking page table size dramatically!",
        "takeaway": "Page Offset bits $d = \\log_2(\\text{Page Size})$. Page Table Size = $(\\text{Number of Pages}) \\times (\\text{PTE Size})$.",
        "difficulty": "Standard",
        "base_weight": 2
    },
    {
        "subject_slug": "algorithms",
        "topic_slug": "recurrences",
        "card_type": "FORMULA",
        "title": "Master Theorem Quick Checklist",
        "content": "For $T(n) = aT(n/b) + \\Theta(n^k \\log^p n)$ where $a \\ge 1, b > 1$:\n\n1. If $\\log_b a > k \\implies T(n) = \\Theta(n^{\\log_b a})$\n2. If $\\log_b a = k$:\n   - If $p > -1 \\implies T(n) = \\Theta(n^k \\log^{p+1} n)$\n   - If $p = -1 \\implies T(n) = \\Theta(n^k \\log \\log n)$\n   - If $p < -1 \\implies T(n) = \\Theta(n^k)$\n3. If $\\log_b a < k$:\n   - If $p \\ge 0 \\implies T(n) = \\Theta(n^k \\log^p n)$",
        "takeaway": "Compare $n^{\\log_b a}$ vs $f(n)$. The larger polynomial order dictates asymptotic runtime.",
        "difficulty": "Core",
        "base_weight": 1
    },
    {
        "subject_slug": "databases",
        "topic_slug": "normalization-fd",
        "card_type": "TRAP",
        "title": "BCNF vs 3NF Dependency Preservation",
        "content": "A 3NF decomposition is **always guaranteed** to be both Lossless Join and Dependency Preserving.\n\n**GATE Trap**: A BCNF decomposition is always guaranteed to be Lossless Join, but **NOT** guaranteed to preserve all functional dependencies! For example, $R(A,B,C)$ with $AB \\to C$ and $C \\to B$. Decomposing to BCNF loses $AB \\to C$.",
        "takeaway": "Lossless is non-negotiable. 3NF always preserves FDs; BCNF might sacrifice FDs.",
        "difficulty": "Standard",
        "base_weight": 2
    },
    {
        "subject_slug": "computer-networks",
        "topic_slug": "tcp-congestion-control",
        "card_type": "CONCEPT",
        "title": "TCP Congestion Control State Machine",
        "content": "1. **Slow Start**: Congestion Window (cwnd) doubles every RTT (exponential growth) until it hits `ssthresh`.\n2. **Congestion Avoidance**: cwnd increases by 1 MSS every RTT (additive increase, AIMD).\n3. **On 3 Duplicate ACKs (Fast Retransmit/Recovery)**: `ssthresh = cwnd / 2`, cwnd set to `ssthresh + 3 MSS`.\n4. **On Timeout**: `ssthresh = cwnd / 2`, cwnd drops to **1 MSS** (back to slow start)!",
        "takeaway": "Timeout triggers full drop to 1 MSS. 3 Duplicate ACKs triggers fast recovery (cwnd halving).",
        "difficulty": "Standard",
        "base_weight": 1
    },
    {
        "subject_slug": "computer-organization-architecture",
        "topic_slug": "instruction-pipelining",
        "card_type": "FORMULA",
        "title": "Pipeline Speedup & Stall Overhead",
        "content": "For a $k$-stage pipeline executing $n$ instructions with clock cycle $\\tau$:\n\n$$\\text{Ideal Cycles} = k + (n - 1)$$\n$$\\text{With Stalls} = k + (n - 1) + \\text{Total Stall Cycles}$$\n$$\\text{Speedup } S = \\frac{n \\cdot k \\cdot \\tau_{\\text{non-pipe}}}{(k + n - 1 + \\text{Stalls}) \\cdot \\tau_{\\text{pipe}}}$$\nAs $n \\to \\infty$, ideal speedup approaches $k$.",
        "takeaway": "CPI of ideal pipeline = 1. Branch stalls and data hazards inflate effective CPI above 1.",
        "difficulty": "Core",
        "base_weight": 1
    },
    {
        "subject_slug": "theory-of-computation",
        "topic_slug": "turing-decidability",
        "card_type": "SHORTCUT",
        "title": "Rice's Theorem Instant Decision Rule",
        "content": "Rice's Theorem applies to any **non-trivial property of the language** recognized by a Turing Machine (recursively enumerable languages).\n\nIf the property is about the language $L(M)$ (semantic property) and not about the syntax/encoding of $M$, and there exists at least one TM language that satisfies it and at least one that does not, it is **UNDECIDABLE**!\n\n*Examples*: 'Is $L(M)$ empty?', 'Is $L(M)$ regular?', 'Is $L(M)$ finite?' $\\to$ All Undecidable by Rice's theorem.",
        "takeaway": "Check: 1. Is it a language property? 2. Is it non-trivial? If both YES $\\implies$ Undecidable.",
        "difficulty": "Rank Booster",
        "base_weight": 3
    }
]

SEED_QUESTIONS = [
    {
        "subject_slug": "operating-systems",
        "topic_slug": "paging-tlb",
        "question_type": "MCQ",
        "marks": 2,
        "negative_marks": 0.66,
        "content": "Consider a system with a two-level paging scheme. The page size is 4 KB. The physical memory access time is 100 ns. The TLB hit ratio is 90% and TLB search time is 10 ns. If a TLB hit occurs, only one physical memory access is needed to read the required data. If a TLB miss occurs, both page table levels must be accessed before accessing the final data frame. What is the Effective Memory Access Time (EMAT) in nanoseconds?",
        "options": json.dumps([
            {"id": "A", "text": "120 ns"},
            {"id": "B", "text": "140 ns"},
            {"id": "C", "text": "130 ns"},
            {"id": "D", "text": "110 ns"}
        ]),
        "correct_answer": "C",
        "nat_min": None,
        "nat_max": None,
        "explanation": "**Detailed Step-by-Step Breakdown:**\n\n1. **TLB Hit Case** ($h = 0.90$):\n   $$T_{\\text{hit}} = T_{\\text{TLB}} + M = 10 + 100 = 110\\text{ ns}$$\n\n2. **TLB Miss Case** ($1 - h = 0.10$):\n   On miss, we first search TLB (10 ns), then read Level-1 Page Table from memory (100 ns), then Level-2 Page Table from memory (100 ns), and finally fetch the actual data (100 ns):\n   $$T_{\\text{miss}} = T_{\\text{TLB}} + 2 \\times M + M = 10 + 200 + 100 = 310\\text{ ns}$$\n\n3. **Effective Memory Access Time (EMAT)**:\n   $$\\text{EMAT} = h \\times T_{\\text{hit}} + (1 - h) \\times T_{\\text{miss}}$$\n   $$\\text{EMAT} = (0.90 \\times 110) + (0.10 \\times 310) = 99 + 31 = 130\\text{ ns}$$\n\nCorrect Option: **C**.",
        "difficulty": "Standard GATE",
        "source": "GATE CSE Classic Variant",
        "is_pyq": True
    },
    {
        "subject_slug": "theory-of-computation",
        "topic_slug": "closure-properties",
        "question_type": "MSQ",
        "marks": 2,
        "negative_marks": 0.0,
        "content": "Which of the following statements is/are **CORRECT** regarding language families? *(Select all correct options)*",
        "options": json.dumps([
            {"id": "A", "text": "The family of Regular languages is closed under subset operation."},
            {"id": "B", "text": "The family of Context-Free Languages (CFL) is closed under intersection with regular languages."},
            {"id": "C", "text": "The family of Context-Free Languages is NOT closed under complementation."},
            {"id": "D", "text": "The family of Decidable (Recursive) languages is closed under intersection."}
        ]),
        "correct_answer": "B,C,D",
        "nat_min": None,
        "nat_max": None,
        "explanation": "**Option Analysis (Crucial for MSQs):**\n\n- **A is FALSE**: If $L = \\Sigma^*$, it is regular. But any arbitrary non-regular subset (e.g., $\{a^n b^n \\mid n \\ge 0\}$) is a subset of $\\Sigma^*$. Hence NOT closed under subset.\n- **B is TRUE**: If $L$ is CFL and $R$ is regular, $L \\cap R$ is always a CFL (proven using product construction of PDA and DFA).\n- **C is TRUE**: CFLs are closed under union, but NOT closed under intersection ($L_1 \\cap L_2$). Since $L_1 \\cap L_2 = \\overline{\\overline{L_1} \\cup \\overline{L_2}}$, if CFLs were closed under complement, they would also be closed under intersection. Hence, CFL is NOT closed under complementation.\n- **D is TRUE**: Recursive (Decidable) languages are closed under union, intersection, complementation, and concatenation.\n\nTherefore, the correct options to select are **B, C, D**.",
        "difficulty": "Rank Booster",
        "source": "GATE CSE Standard",
        "is_pyq": False
    },
    {
        "subject_slug": "computer-networks",
        "topic_slug": "ipv4-subnetting",
        "question_type": "NAT",
        "marks": 2,
        "negative_marks": 0.0,
        "content": "An organization is assigned the IPv4 address block `192.168.16.0/20`. The administrator wants to divide this block into 8 subnets of equal size. What is the total number of usable host IP addresses across all 8 subnets combined?",
        "options": None,
        "correct_answer": "4080",
        "nat_min": 4080.0,
        "nat_max": 4080.0,
        "explanation": "**Step-by-Step Calculation:**\n\n1. **Original Network**: `/20` prefix.\n   Total host bits in original block = $32 - 20 = 12$ bits.\n\n2. **Dividing into 8 Subnets**:\n   $8 = 2^3$, so we need 3 additional bits for the subnet ID.\n   New subnet prefix = $20 + 3 = /23$.\n\n3. **Host Bits per Subnet**:\n   $32 - 23 = 9$ bits.\n   Total IP addresses per subnet = $2^9 = 512$.\n\n4. **Usable Hosts per Subnet**:\n   Each subnet reserves 2 addresses (Subnet Network Address and Directed Broadcast Address):\n   $$\\text{Usable hosts per subnet} = 512 - 2 = 510$$\n\n5. **Total Usable Hosts across all 8 Subnets**:\n   $$8 \\times 510 = 4080$$\n\nAnswer: **4080**.",
        "difficulty": "Standard GATE",
        "source": "GATE CSE 2021 Numerical",
        "is_pyq": True
    },
    {
        "subject_slug": "algorithms",
        "topic_slug": "asymptotic-analysis",
        "question_type": "MCQ",
        "marks": 1,
        "negative_marks": 0.33,
        "content": "Let $f(n) = n^{\\log_2 n}$ and $g(n) = 2^{\\sqrt{n}}$. Which of the following asymptotic relations is correct?",
        "options": json.dumps([
            {"id": "A", "text": "f(n) = O(g(n))"},
            {"id": "B", "text": "g(n) = O(f(n))"},
            {"id": "C", "text": "f(n) = Theta(g(n))"},
            {"id": "D", "text": "None of the above"}
        ]),
        "correct_answer": "A",
        "nat_min": None,
        "nat_max": None,
        "explanation": "**Logarithmic Comparison Technique:**\n\nTake $\\log_2$ on both sides:\n- $\\log_2(f(n)) = \\log_2(n^{\\log_2 n}) = (\\log_2 n)^2$\n- $\\log_2(g(n)) = \\log_2(2^{\\sqrt{n}}) = \\sqrt{n} \\cdot \\log_2 2 = \\sqrt{n} = n^{0.5}$\n\nNow compare $(\\log_2 n)^2$ with $n^{0.5}$ as $n \\to \\infty$:\nAny polynomial $n^c$ (even with $c = 0.5$) strictly dominates any polylogarithmic function $(\\log n)^k$.\n\nTherefore, $\\log(f(n)) < \\log(g(n)) \\implies f(n)$ grows strictly slower than $g(n)$.\nHence, $f(n) = O(g(n))$ (in fact $o(g(n))$).\n\nCorrect Option: **A**.",
        "difficulty": "Foundational",
        "source": "GATE CSE Classic",
        "is_pyq": True
    },
    {
        "subject_slug": "engineering-mathematics",
        "topic_slug": "graph-theory",
        "question_type": "NAT",
        "marks": 1,
        "negative_marks": 0.0,
        "content": "A simple connected planar graph $G$ has 10 vertices and divides the plane into 7 regions (faces). How many edges does the graph $G$ have?",
        "options": None,
        "correct_answer": "15",
        "nat_min": 15.0,
        "nat_max": 15.0,
        "explanation": "**Euler's Planar Formula:**\n\nFor any connected planar graph with $V$ vertices, $E$ edges, and $R$ faces (regions):\n$$V - E + R = 2$$\n\nGiven:\n- $V = 10$\n- $R = 7$\n\nSubstitute values:\n$$10 - E + 7 = 2$$\n$$17 - E = 2 \\implies E = 15$$\n\nAnswer: **15**.",
        "difficulty": "Foundational",
        "source": "GATE CSE 2018 Numerical",
        "is_pyq": True
    }
]

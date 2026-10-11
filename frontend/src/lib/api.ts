const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export interface TopicItem {
  id: number;
  name: string;
  slug: string;
  importance: string;
}

export interface SubjectItem {
  id: number;
  name: string;
  slug: string;
  icon: string;
  description: string;
  weightage_marks: number;
  question_count: number;
  topics: TopicItem[];
}

export interface FeedCardItem {
  id: number;
  subject_name: string;
  subject_slug: string;
  topic_name: string;
  topic_slug: string;
  card_type: "TRAP" | "FORMULA" | "CONCEPT" | "SHORTCUT";
  title: string;
  content: string;
  takeaway: string;
  difficulty: string;
  effective_weight: number;
  is_remedial: boolean;
  recent_mistakes_in_topic: number;
  provenance?: string;
  /** knowledge_base | web | hybrid | user */
  source_type?: string;
  tags?: string[];
  concept_id?: number | null;
}

/** The fields a hand-written card is created or edited with. */
export interface UserCardInput {
  subject_slug: string;
  topic_slug: string;
  title: string;
  content: string;
  takeaway?: string;
  card_type?: string;
  mode?: string;
  difficulty?: string;
  concept_id?: number | null;
  tags?: string[];
}

export interface QuestionOption {
  id: string;
  text: string;
}

export interface QuizQuestion {
  id: number;
  subject_name: string;
  subject_slug: string;
  topic_name: string;
  topic_slug: string;
  question_type: "MCQ" | "MSQ" | "NAT";
  marks: number;
  negative_marks: number;
  content: string;
  options: QuestionOption[] | null;
  difficulty: string;
  source: string;
  is_pyq: boolean;
}

export interface SubmitPayload {
  question_id: number;
  user_answer: string;
  time_spent_seconds?: number;
  mode?: string;
}

export interface SubmitResponse {
  is_correct: boolean;
  marks_awarded: number;
  correct_answer: string;
  explanation: string;
  question_type: string;
  source: string;
}

export interface SubjectStat {
  subject_id: number;
  subject_name: string;
  subject_slug: string;
  weightage_marks: number;
  attempts: number;
  accuracy: number;
  marks_earned: number;
  unresolved_mistakes: number;
}

export interface StatsSummary {
  total_attempts: number;
  correct_attempts: number;
  accuracy: number;
  total_marks_earned: number;
  active_mistakes_count: number;
  subject_stats: SubjectStat[];
}

export interface AgentChatResponse {
  reply: string;
  source: string;
  matched_excerpts: {
    content: string;
    file_name: string;
    page_number: number;
  }[];
}

export interface AgentDocumentsResponse {
  total_documents: number;
  total_vector_chunks: number;
  documents: {
    name: string;
    relative_path: string;
    size_bytes: number;
  }[];
}

export async function fetchSyllabus(): Promise<SubjectItem[]> {
  const res = await fetch(`${API_BASE}/api/syllabus`);
  if (!res.ok) throw new Error("Failed to fetch syllabus");
  return res.json();
}

export interface FeedPage {
  items: FeedCardItem[];
  /** null means no further pages. */
  next_offset: number | null;
  total: number;
}

export interface FeedFilters {
  subjectSlug?: string;
  topicSlug?: string;
  cardType?: string;
  mode?: string;
  /** knowledge_base | web | hybrid | user */
  sourceType?: string;
  tag?: string;
}

export async function fetchFeed(
  filters: FeedFilters = {},
  offset = 0,
  limit = 18,
): Promise<FeedPage> {
  const params = new URLSearchParams();
  const add = (key: string, value?: string) => {
    if (value && value !== "all") params.append(key, value);
  };
  add("subject_slug", filters.subjectSlug);
  add("topic_slug", filters.topicSlug);
  add("card_type", filters.cardType);
  add("mode", filters.mode);
  add("source_type", filters.sourceType);
  add("tag", filters.tag);
  params.append("offset", String(offset));
  params.append("limit", String(limit));

  const res = await fetch(`${API_BASE}/api/feed?${params}`);
  if (!res.ok) throw new Error("Failed to fetch feed");
  return res.json();
}

// ---- Rotation ----

export async function markCardSeen(cardId: number): Promise<void> {
  await fetch(`${API_BASE}/api/feed/cards/${cardId}/seen`, { method: "POST" });
}

export async function markCardRecalled(
  cardId: number,
): Promise<{ recall_count: number; mastered: boolean; due_at: string | null }> {
  const res = await fetch(`${API_BASE}/api/feed/cards/${cardId}/recall`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Could not record that");
  return res.json();
}

// ---- Assistant ----

export type AssistantLanguage = "en" | "hi" | "hinglish";

export interface AssistantFeedResult {
  output: "feed";
  filters: {
    subject_slug: string | null;
    topic: string | null;
    level: string | null;
    card_type: string | null;
    query: string;
  };
  language: AssistantLanguage;
}

export interface AssistantChatResult {
  output: "chat";
  thread_id: number;
  message_id: number;
  answer: string;
  citations: string[];
  source_type: string;
  language: AssistantLanguage;
}

export type AssistantResult = AssistantFeedResult | AssistantChatResult;

export async function askAssistant(body: {
  query: string;
  thread_id?: number;
  card_id?: number;
  language?: AssistantLanguage;
}): Promise<AssistantResult> {
  const res = await fetch(`${API_BASE}/api/assistant/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? "Assistant unavailable");
  return res.json();
}

export interface AssistantMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  citations: string[];
  created_at: string | null;
}

export async function fetchThread(
  threadId: number,
): Promise<{ id: number; title: string; messages: AssistantMessage[] }> {
  const res = await fetch(`${API_BASE}/api/assistant/threads/${threadId}`);
  if (!res.ok) throw new Error("Could not load that conversation");
  return res.json();
}

export async function fetchQuiz(params: {
  subject_slug?: string;
  topic_slug?: string;
  question_type?: string;
  difficulty?: string;
  limit?: number;
}): Promise<QuizQuestion[]> {
  const qParams = new URLSearchParams();
  if (params.subject_slug && params.subject_slug !== "all") qParams.append("subject_slug", params.subject_slug);
  if (params.topic_slug && params.topic_slug !== "all") qParams.append("topic_slug", params.topic_slug);
  if (params.question_type && params.question_type !== "all") qParams.append("question_type", params.question_type);
  if (params.difficulty && params.difficulty !== "all") qParams.append("difficulty", params.difficulty);
  if (params.limit) qParams.append("limit", params.limit.toString());
  
  const res = await fetch(`${API_BASE}/api/quiz?${qParams.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch quiz questions");
  return res.json();
}

export async function submitQuizAnswer(payload: SubmitPayload): Promise<SubmitResponse> {
  const res = await fetch(`${API_BASE}/api/quiz/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to submit answer");
  return res.json();
}

export async function fetchStats(): Promise<StatsSummary> {
  const res = await fetch(`${API_BASE}/api/stats/summary`);
  if (!res.ok) throw new Error("Failed to fetch statistics");
  return res.json();
}

export async function chatWithAgent(query: string, subjectSlug?: string): Promise<AgentChatResponse> {
  // /api/agent/chat was never built; the assistant lives at /api/assistant/ask.
  // Its reply is reshaped here so callers of this function stay unchanged.
  const res = await fetch(`${API_BASE}/api/assistant/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, subject_slug: subjectSlug }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(
      `Assistant request failed (${res.status})${detail ? `: ${detail.slice(0, 200)}` : ""}`,
    );
  }
  const data = await res.json();
  return {
    reply: data.answer ?? "",
    source: data.source_type ?? "knowledge_base",
    // The assistant cites sources as strings; the panel wants excerpt
    // objects, so each citation becomes a header-only excerpt.
    matched_excerpts: (data.citations ?? []).map((c: string) => ({
      content: "",
      file_name: c,
      page_number: 0,
    })),
  };
}

export async function fetchAgentDocuments(): Promise<AgentDocumentsResponse> {
  const res = await fetch(`${API_BASE}/api/agent/documents`);
  if (!res.ok) throw new Error("Failed to fetch agent documents");
  return res.json();
}

// ---- Mock test ----

export type ExamState =
  | "not_visited"
  | "not_answered"
  | "answered"
  | "marked"
  | "answered_marked";

export interface ExamQuestion {
  position: number;
  question_id: number;
  question_type: "MCQ" | "MSQ" | "NAT";
  marks: number;
  negative_marks: number;
  content: string;
  options: QuestionOption[] | null;
  subject_name: string;
  state: ExamState;
  user_answer: string;
  time_spent_seconds: number;
}

export interface ExamSummary {
  id: number;
  name: string;
  kind?: "quiz" | "test";
  pattern: string;
  status: "in_progress" | "submitted" | "abandoned";
  total_questions: number;
  total_marks: number;
  duration_minutes: number;
  started_at: string | null;
  submitted_at: string | null;
  elapsed_seconds: number;
  remaining_seconds: number;
  score: number;
  max_score: number;
  correct_count: number;
  wrong_count: number;
  unattempted_count: number;
  accuracy: number;
  shortfall_note: string;
  questions?: ExamQuestion[];
}

export interface ExamResultRow extends ExamQuestion {
  correct_answer: string;
  is_correct: boolean | null;
  marks_obtained: number;
  has_worked_solution: boolean;
}

/** A submitted paper: same summary, but rows carry the outcome. */
export type ExamResult = Omit<ExamSummary, "questions"> & {
  questions: ExamResultRow[];
};

export interface ExamPatterns {
  presets: {
    key: string;
    name: string;
    total_questions: number;
    total_marks: number;
    duration_minutes: number;
  }[];
  subjects: {
    slug: string;
    name: string;
    weightage_marks: number;
    question_count: number;
  }[];
  total_questions_available: number;
}

export async function fetchExamPatterns(): Promise<ExamPatterns> {
  const res = await fetch(`${API_BASE}/api/exam/patterns`);
  if (!res.ok) throw new Error("Failed to load exam patterns");
  return res.json();
}

export async function startExam(body: {
  pattern: string;
  subject_slug?: string;
  subject_slugs?: string[];
  topic_slug?: string;
  question_type?: string;
  difficulty?: string;
  questions?: number;
  duration_minutes?: number;
  name?: string;
  kind?: "quiz" | "test";
}): Promise<ExamSummary> {
  const res = await fetch(`${API_BASE}/api/exam/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? "Could not start test");
  return res.json();
}

export async function fetchExam(id: number): Promise<ExamSummary> {
  const res = await fetch(`${API_BASE}/api/exam/${id}`);
  if (!res.ok) throw new Error("Failed to load test");
  return res.json();
}

export async function visitExamQuestion(id: number, position: number) {
  await fetch(`${API_BASE}/api/exam/${id}/visit/${position}`, { method: "POST" });
}

export async function saveExamAnswer(
  id: number,
  position: number,
  body: { answer?: string; marked?: boolean; time_spent_seconds?: number },
): Promise<{ position: number; state: ExamState; user_answer: string }> {
  const res = await fetch(`${API_BASE}/api/exam/${id}/answer/${position}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to save answer");
  return res.json();
}

export async function submitExam(id: number): Promise<ExamSummary> {
  const res = await fetch(`${API_BASE}/api/exam/${id}/submit`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to submit test");
  return res.json();
}

export async function fetchExamResult(id: number): Promise<ExamResult> {
  const res = await fetch(`${API_BASE}/api/exam/${id}/result`);
  if (!res.ok) throw new Error("Failed to load result");
  return res.json();
}

export async function fetchExamHistory(
  options: { limit?: number; kind?: "quiz" | "test"; subjectSlug?: string; since?: string } = {},
): Promise<ExamSummary[]> {
  const params = new URLSearchParams({ limit: String(options.limit ?? 20) });
  if (options.kind) params.set("kind", options.kind);
  if (options.subjectSlug && options.subjectSlug !== "all") {
    params.set("subject_slug", options.subjectSlug);
  }
  if (options.since) params.set("since", options.since);

  const res = await fetch(`${API_BASE}/api/exam?${params}`);
  if (!res.ok) throw new Error("Failed to load history");
  return res.json();
}


export interface SolutionResponse {
  question_id: number;
  question_type: string;
  correct_answer: string;
  solution: string;
  has_worked_solution: boolean;
  source: string;
  exam_year: number | null;
  provenance: string;
  attempts: {
    user_answer: string;
    is_correct: boolean;
    marks_obtained: number;
    time_spent_seconds: number;
    mode: string;
    attempted_at: string | null;
  }[];
}

export async function fetchSolution(questionId: number): Promise<SolutionResponse> {
  const res = await fetch(`${API_BASE}/api/quiz/${questionId}/solution`);
  if (!res.ok) throw new Error((await res.json()).detail ?? "Solution unavailable");
  return res.json();
}

export async function createUserCard(input: UserCardInput): Promise<FeedCardItem> {
  const res = await fetch(`${API_BASE}/api/feed`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? "Could not save that card");
  }
  return res.json();
}

export async function updateUserCard(
  id: number, input: UserCardInput,
): Promise<FeedCardItem> {
  const res = await fetch(`${API_BASE}/api/feed/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? "Could not update that card");
  }
  return res.json();
}

export async function deleteUserCard(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/feed/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? "Could not delete that card");
  }
}

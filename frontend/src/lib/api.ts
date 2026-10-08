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

export async function fetchFeed(subjectSlug?: string, cardType?: string): Promise<FeedCardItem[]> {
  const params = new URLSearchParams();
  if (subjectSlug && subjectSlug !== "all") params.append("subject_slug", subjectSlug);
  if (cardType && cardType !== "all") params.append("card_type", cardType);
  const res = await fetch(`${API_BASE}/api/feed?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch feed");
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
  const res = await fetch(`${API_BASE}/api/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, subject_slug: subjectSlug }),
  });
  if (!res.ok) throw new Error("Failed to chat with agent");
  return res.json();
}

export async function fetchAgentDocuments(): Promise<AgentDocumentsResponse> {
  const res = await fetch(`${API_BASE}/api/agent/documents`);
  if (!res.ok) throw new Error("Failed to fetch agent documents");
  return res.json();
}

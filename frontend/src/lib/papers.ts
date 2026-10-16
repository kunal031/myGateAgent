/** Question papers: importing a batch of questions from a URL or a PDF. */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type QuestionType = "MCQ" | "MSQ" | "NAT";

/** Where an explanation came from, in descending order of trust. */
export type SolutionSource = "book" | "web" | "ai" | "user" | "";

export const SOLUTION_SOURCE_LABELS: Record<Exclude<SolutionSource, "">, string> = {
  book: "From your books",
  web: "From the web",
  ai: "AI-written",
  user: "Yours",
};

export interface PaperOption {
  id: string;
  text: string;
}

/** A question as parsed, before it is stored. */
export interface ParsedQuestion {
  content: string;
  options: PaperOption[];
  correct_answer: string;
  question_type: QuestionType;
  marks: number;
  nat_min: number | null;
  nat_max: number | null;
  exam_year: number | null;
  source_label: string;
  /** True when the source gave no answer and the student must supply one. */
  needs_answer: boolean;
  explanation?: string;
  solution_source?: SolutionSource;
}

export interface PaperProgress {
  id: number;
  import_status: "parsing" | "preview" | "saving" | "complete" | "failed";
  import_error: string;
  progress_done: number;
  progress_total: number;
  progress_note: string;
  question_count: number;
}

export interface QuestionPaper {
  id: number;
  name: string;
  subject_id: number;
  topic_id: number;
  subject_name: string;
  topic_name: string;
  source_kind: "url" | "pdf" | "manual";
  origin_url: string;
  file_name: string;
  exam_year: number | null;
  source_label: string;
  question_count: number;
  import_status: "parsing" | "preview" | "saving" | "complete" | "failed";
  import_error: string;
  progress_done: number;
  progress_total: number;
  progress_note: string;
  created_at: string | null;
}

export interface ImportPreview {
  paper: QuestionPaper;
  questions: ParsedQuestion[];
  total: number;
  missing_answers: number;
}

/** A question already stored, as the paper detail view returns it. */
export interface StoredQuestion {
  id: number;
  content: string;
  options: PaperOption[];
  correct_answer: string;
  question_type: QuestionType;
  marks: number;
  negative_marks: number;
  explanation: string;
  solution_source: SolutionSource;
  exam_year: number | null;
  source: string;
  review_status: string;
}

async function json<T>(res: Response, fallback: string): Promise<T> {
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? fallback);
  }
  return res.json();
}

export async function fetchPapers(
  params: { subjectSlug?: string; topicSlug?: string } = {},
  signal?: AbortSignal,
): Promise<QuestionPaper[]> {
  const search = new URLSearchParams();
  if (params.subjectSlug && params.subjectSlug !== "all") {
    search.set("subject_slug", params.subjectSlug);
  }
  if (params.topicSlug && params.topicSlug !== "all") {
    search.set("topic_slug", params.topicSlug);
  }
  const res = await fetch(`${API_BASE}/api/papers?${search.toString()}`, { signal });
  const data = await json<{ items: QuestionPaper[] }>(res, "Could not load papers");
  return data.items;
}

/** Queued, not finished: poll {@link fetchPaperStatus} for progress. */
export interface QueuedImport {
  paper: QuestionPaper;
  queued: boolean;
}

export async function importPaperFromUrl(input: {
  url: string;
  subject_slug: string;
  topic_slug: string;
  name?: string;
}): Promise<QueuedImport> {
  const res = await fetch(`${API_BASE}/api/papers/import/url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return json<QueuedImport>(res, "Could not import from that link");
}

export async function importPaperFromPdf(input: {
  file: File;
  subject_slug: string;
  topic_slug: string;
  name?: string;
}): Promise<QueuedImport> {
  const form = new FormData();
  form.append("file", input.file);
  form.append("subject_slug", input.subject_slug);
  form.append("topic_slug", input.topic_slug);
  if (input.name) form.append("name", input.name);

  // No Content-Type header: the browser sets the multipart boundary.
  const res = await fetch(`${API_BASE}/api/papers/import/upload`, {
    method: "POST",
    body: form,
  });
  return json<QueuedImport>(res, "Could not import that file");
}

export async function confirmPaperImport(
  paperId: number,
  questions: ParsedQuestion[],
  generateExplanations = true,
): Promise<QueuedImport> {
  const res = await fetch(`${API_BASE}/api/papers/${paperId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ questions, generate_explanations: generateExplanations }),
  });
  return json<QueuedImport>(res, "Could not save those questions");
}

/** Light enough to poll once a second while an import runs. */
export async function fetchPaperStatus(
  paperId: number,
  signal?: AbortSignal,
): Promise<PaperProgress> {
  const res = await fetch(`${API_BASE}/api/papers/${paperId}/status`, { signal });
  return json<PaperProgress>(res, "Could not read import progress");
}

/** The parsed questions awaiting review, recoverable after a reload. */
export async function fetchPaperPreview(
  paperId: number,
  signal?: AbortSignal,
): Promise<ImportPreview> {
  const res = await fetch(`${API_BASE}/api/papers/${paperId}/preview`, { signal });
  return json<ImportPreview>(res, "Could not load what was found");
}

export async function fetchPaper(
  paperId: number,
  signal?: AbortSignal,
): Promise<{ paper: QuestionPaper; questions: StoredQuestion[] }> {
  const res = await fetch(`${API_BASE}/api/papers/${paperId}`, { signal });
  return json(res, "Could not load that paper");
}

export async function editPaperQuestion(
  questionId: number,
  patch: {
    correct_answer?: string;
    explanation?: string;
    question_type?: QuestionType;
  },
): Promise<Partial<StoredQuestion> & { id: number }> {
  const res = await fetch(`${API_BASE}/api/papers/questions/${questionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return json(res, "Could not save that change");
}

export async function deletePaper(
  paperId: number,
  deleteQuestions = false,
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/papers/${paperId}?delete_questions=${deleteQuestions}`,
    { method: "DELETE" },
  );
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? "Could not delete that paper");
  }
}

/** Create a topic, so a paper can be filed somewhere that does not exist yet. */
export async function createTopic(
  subjectSlug: string,
  name: string,
): Promise<{ id: number; name: string; slug: string; created: boolean }> {
  const res = await fetch(`${API_BASE}/api/syllabus/topics`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subject_slug: subjectSlug, name }),
  });
  return json(res, "Could not create that topic");
}

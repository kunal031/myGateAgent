/** Question papers: importing a batch of questions from a URL or a PDF. */

import { api } from "./client/web";

// This module used to read NEXT_PUBLIC_API_BASE while every other module
// read NEXT_PUBLIC_API_URL, so a deployment that set only the documented
// one left the paper importer talking to localhost. Going through the
// shared client removes the second name entirely.

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
  const data = await api.get<{ items: QuestionPaper[] }>("/api/papers", {
    query: Object.fromEntries(search), signal,
  });
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
  return api.post<QueuedImport>("/api/papers/import/url", input);
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
  // `form`, not `body`: the client leaves Content-Type unset so the
  // runtime can add the multipart boundary.
  return api.request<QueuedImport>("/api/papers/import/upload", {
    method: "POST", form,
  });
}

export async function confirmPaperImport(
  paperId: number,
  questions: ParsedQuestion[],
  generateExplanations = true,
): Promise<QueuedImport> {
  return api.post<QueuedImport>(`/api/papers/${paperId}/confirm`, {
    questions, generate_explanations: generateExplanations,
  });
}

/** Light enough to poll once a second while an import runs. */
export async function fetchPaperStatus(
  paperId: number,
  signal?: AbortSignal,
): Promise<PaperProgress> {
  return api.get<PaperProgress>(`/api/papers/${paperId}/status`, { signal });
}

/** The parsed questions awaiting review, recoverable after a reload. */
export async function fetchPaperPreview(
  paperId: number,
  signal?: AbortSignal,
): Promise<ImportPreview> {
  return api.get<ImportPreview>(`/api/papers/${paperId}/preview`, { signal });
}

export async function fetchPaper(
  paperId: number,
  signal?: AbortSignal,
): Promise<{ paper: QuestionPaper; questions: StoredQuestion[] }> {
  return api.get(`/api/papers/${paperId}`, { signal });
}

export async function editPaperQuestion(
  questionId: number,
  patch: {
    correct_answer?: string;
    explanation?: string;
    question_type?: QuestionType;
  },
): Promise<Partial<StoredQuestion> & { id: number }> {
  return api.patch(`/api/papers/questions/${questionId}`, patch);
}

export async function deletePaper(
  paperId: number,
  deleteQuestions = false,
): Promise<void> {
  // ApiError carries the server's own message, so the hand-rolled
  // detail extraction this replaced is no longer needed.
  await api.request(`/api/papers/${paperId}`, {
    method: "DELETE", query: { delete_questions: deleteQuestions },
  });
}

/** Create a topic, so a paper can be filed somewhere that does not exist yet. */
export async function createTopic(
  subjectSlug: string,
  name: string,
): Promise<{ id: number; name: string; slug: string; created: boolean }> {
  return api.post("/api/syllabus/topics", {
    subject_slug: subjectSlug, name,
  });
}

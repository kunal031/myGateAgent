"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Check, Link2, Loader2, Plus, Upload, X } from "lucide-react";

import MathText from "@/components/MathText";
import { SubjectItem } from "@/lib/api";
import {
  ImportPreview, ParsedQuestion, confirmPaperImport, createTopic,
  importPaperFromPdf, importPaperFromUrl,
} from "@/lib/papers";

interface Props {
  subjects: SubjectItem[];
  onClose: () => void;
  /** Fired once questions are stored, so the caller can refresh its lists. */
  onImported: (stored: number) => void;
}

type Step = "source" | "review" | "saving";

/**
 * Import a paper: choose where it files, fetch it, review what was found,
 * then save.
 *
 * The review step is not optional. Parsing infers answers and question
 * types, and a wrong answer stored silently is practised as if it were
 * right, surfacing weeks later as confusion. Anything the source did not
 * answer is flagged and blocks saving until it is filled in.
 */
export default function PaperImporter({ subjects, onClose, onImported }: Props) {
  const [step, setStep] = useState<Step>("source");

  const [subjectSlug, setSubjectSlug] = useState("");
  const [topicSlug, setTopicSlug] = useState("");
  const [newTopic, setNewTopic] = useState("");
  const [addingTopic, setAddingTopic] = useState(false);

  const [mode, setMode] = useState<"url" | "pdf">("url");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");

  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [questions, setQuestions] = useState<ParsedQuestion[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Topics come from the syllabus payload and grow when one is added here.
  const [extraTopics, setExtraTopics] = useState<
    Record<string, { slug: string; name: string }[]>
  >({});

  const topics = useMemo(() => {
    const base = subjects.find((s) => s.slug === subjectSlug)?.topics ?? [];
    return [...base, ...(extraTopics[subjectSlug] ?? [])];
  }, [subjects, subjectSlug, extraTopics]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, []);

  const addTopic = useCallback(async () => {
    const label = newTopic.trim();
    if (!label || !subjectSlug) return;
    setAddingTopic(true);
    setError("");
    try {
      const created = await createTopic(subjectSlug, label);
      setExtraTopics((prev) => ({
        ...prev,
        [subjectSlug]: [
          ...(prev[subjectSlug] ?? []),
          { slug: created.slug, name: created.name },
        ],
      }));
      setTopicSlug(created.slug);
      setNewTopic("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create that topic");
    } finally {
      setAddingTopic(false);
    }
  }, [newTopic, subjectSlug]);

  const canFetch = Boolean(
    subjectSlug && topicSlug && (mode === "url" ? url.trim() : file) && !busy,
  );

  const runImport = async () => {
    if (!canFetch) return;
    setBusy(true);
    setError("");
    try {
      const result = mode === "url"
        ? await importPaperFromUrl({
            url: url.trim(), subject_slug: subjectSlug,
            topic_slug: topicSlug, name: name.trim() || undefined,
          })
        : await importPaperFromPdf({
            file: file!, subject_slug: subjectSlug,
            topic_slug: topicSlug, name: name.trim() || undefined,
          });
      setPreview(result);
      setQuestions(result.questions);
      setStep("review");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not import that");
    } finally {
      setBusy(false);
    }
  };

  const setAnswer = (index: number, answer: string) => {
    setQuestions((prev) =>
      prev.map((q, i) =>
        i === index
          ? { ...q, correct_answer: answer, needs_answer: !answer.trim() }
          : q,
      ),
    );
  };

  const unanswered = questions.filter((q) => !q.correct_answer.trim()).length;

  const save = async () => {
    if (!preview || unanswered > 0) return;
    setStep("saving");
    setError("");
    try {
      const result = await confirmPaperImport(preview.paper.id, questions, true);
      onImported(result.stored);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save those questions");
      setStep("review");
    }
  };

  const field = {
    background: "var(--surface-sunk)",
    border: "var(--line-width) solid var(--line)",
    color: "var(--ink)",
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4"
      style={{ background: "rgba(0,0,0,0.45)" }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Import a question paper"
        className="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-[var(--radius-lg)] sm:max-h-[88vh] sm:rounded-[var(--radius-lg)]"
        style={{
          background: "var(--surface)",
          border: "var(--line-width) solid var(--line)",
          boxShadow: "var(--shadow)",
        }}
      >
        <header
          className="flex shrink-0 items-center justify-between gap-2 px-4 py-3"
          style={{ borderBottom: "var(--line-width) solid var(--line)" }}
        >
          <div>
            <h2 className="text-sm font-extrabold" style={{ color: "var(--ink)" }}>
              {step === "review" ? "Review what was found" : "Import a question paper"}
            </h2>
            {preview && step !== "source" && (
              <p className="text-[11px] font-semibold" style={{ color: "var(--ink-faint)" }}>
                {preview.paper.subject_name} → {preview.paper.topic_name}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius-pill)]"
            style={field}
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
          {step === "source" && (
            <>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-1 block text-[10px] font-extrabold uppercase tracking-wider"
                        style={{ color: "var(--ink-faint)" }}>Subject</span>
                  <select
                    value={subjectSlug}
                    onChange={(e) => { setSubjectSlug(e.target.value); setTopicSlug(""); }}
                    className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm"
                    style={field}
                  >
                    <option value="">Choose…</option>
                    {subjects.map((s) => (
                      <option key={s.slug} value={s.slug}>{s.name}</option>
                    ))}
                  </select>
                </label>

                <label className="block">
                  <span className="mb-1 block text-[10px] font-extrabold uppercase tracking-wider"
                        style={{ color: "var(--ink-faint)" }}>Topic</span>
                  <select
                    value={topicSlug}
                    onChange={(e) => setTopicSlug(e.target.value)}
                    disabled={!subjectSlug}
                    className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm disabled:opacity-50"
                    style={field}
                  >
                    <option value="">{subjectSlug ? "Choose…" : "Pick a subject first"}</option>
                    {topics.map((t) => (
                      <option key={t.slug} value={t.slug}>{t.name}</option>
                    ))}
                  </select>
                </label>
              </div>

              {subjectSlug && (
                <div className="flex items-end gap-2">
                  <label className="min-w-0 flex-1">
                    <span className="mb-1 block text-[10px] font-extrabold uppercase tracking-wider"
                          style={{ color: "var(--ink-faint)" }}>
                      Or add a topic this subject does not have yet
                    </span>
                    <input
                      value={newTopic}
                      onChange={(e) => setNewTopic(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); void addTopic(); } }}
                      placeholder="e.g. Process, PCB & Context Switching"
                      className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm outline-none"
                      style={field}
                    />
                  </label>
                  <button
                    type="button"
                    onClick={addTopic}
                    disabled={!newTopic.trim() || addingTopic}
                    className="flex min-h-11 shrink-0 items-center gap-1 rounded-[var(--radius-pill)] px-3 text-[12px] font-bold disabled:opacity-40"
                    style={{ background: "var(--accent)", color: "var(--ink)",
                             border: "var(--line-width) solid var(--line)" }}
                  >
                    {addingTopic ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                 : <Plus className="h-3.5 w-3.5" />}
                    Add
                  </button>
                </div>
              )}

              <div className="flex gap-2 pt-1">
                {(["url", "pdf"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setMode(m)}
                    className="flex min-h-10 items-center gap-1.5 rounded-[var(--radius-pill)] px-3 text-[11px] font-bold"
                    style={{
                      background: mode === m ? "var(--accent)" : "var(--surface)",
                      border: "var(--line-width) solid var(--line)",
                      color: "var(--ink)",
                    }}
                  >
                    {m === "url" ? <Link2 className="h-3.5 w-3.5" />
                                 : <Upload className="h-3.5 w-3.5" />}
                    {m === "url" ? "From a link" : "From a PDF"}
                  </button>
                ))}
              </div>

              {mode === "url" ? (
                <label className="block">
                  <span className="mb-1 block text-[10px] font-extrabold uppercase tracking-wider"
                        style={{ color: "var(--ink-faint)" }}>Link</span>
                  <input
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://…"
                    className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm outline-none"
                    style={field}
                  />
                </label>
              ) : (
                <label className="block">
                  <span className="mb-1 block text-[10px] font-extrabold uppercase tracking-wider"
                        style={{ color: "var(--ink-faint)" }}>PDF</span>
                  <input
                    type="file"
                    accept="application/pdf"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    className="min-h-11 w-full rounded-[var(--radius)] px-3 py-2 text-sm"
                    style={field}
                  />
                </label>
              )}

              <label className="block">
                <span className="mb-1 block text-[10px] font-extrabold uppercase tracking-wider"
                      style={{ color: "var(--ink-faint)" }}>Name — optional</span>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Taken from the page if left empty"
                  className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm outline-none"
                  style={field}
                />
              </label>
            </>
          )}

          {step !== "source" && preview && (
            <>
              <div className="flex flex-wrap items-center gap-2 text-[11px] font-bold">
                <span className="rounded-[var(--radius-pill)] px-2 py-1"
                      style={{ background: "var(--surface-sunk)", color: "var(--ink)",
                               border: "var(--line-width) solid var(--line)" }}>
                  {questions.length} questions
                </span>
                {unanswered > 0 && (
                  <span className="flex items-center gap-1 rounded-[var(--radius-pill)] px-2 py-1"
                        style={{ background: "var(--warning)", color: "var(--ink)",
                                 border: "var(--line-width) solid var(--line)" }}>
                    <AlertTriangle className="h-3 w-3" />
                    {unanswered} need an answer
                  </span>
                )}
              </div>

              {questions.map((q, i) => (
                <article
                  key={i}
                  className="rounded-[var(--radius)] px-3 py-2.5"
                  style={{
                    background: q.correct_answer ? "var(--surface-muted)" : "var(--surface-sunk)",
                    border: "var(--line-width) solid "
                      + (q.correct_answer ? "var(--line)" : "var(--warning)"),
                  }}
                >
                  <div className="mb-1 flex flex-wrap items-center gap-2 text-[10px] font-extrabold"
                       style={{ color: "var(--ink-faint)" }}>
                    <span>#{i + 1}</span>
                    <span className="rounded-[var(--radius-pill)] px-1.5 py-0.5"
                          style={{ background: "var(--surface)",
                                   border: "var(--line-width) solid var(--line)" }}>
                      {q.question_type} · {q.marks}M
                    </span>
                    {q.source_label && <span>{q.source_label}</span>}
                  </div>

                  <div className="overflow-x-auto text-[13px] leading-relaxed"
                       style={{ color: "var(--ink)" }}>
                    <MathText text={q.content} />
                  </div>

                  {q.options.length > 0 && (
                    <ul className="mt-1.5 space-y-0.5">
                      {q.options.map((o) => (
                        <li key={o.id} className="text-[12px]"
                            style={{ color: "var(--ink-soft)" }}>
                          <strong>{o.id}.</strong> {o.text}
                        </li>
                      ))}
                    </ul>
                  )}

                  <label className="mt-2 flex items-center gap-2">
                    <span className="text-[10px] font-extrabold uppercase tracking-wider"
                          style={{ color: "var(--ink-faint)" }}>Answer</span>
                    <input
                      value={q.correct_answer}
                      onChange={(e) => setAnswer(i, e.target.value)}
                      placeholder={q.question_type === "NAT" ? "e.g. 21" : "e.g. A or A,C"}
                      className="min-h-9 w-32 rounded-[var(--radius)] px-2 text-[12px] font-bold outline-none"
                      style={field}
                    />
                  </label>
                </article>
              ))}
            </>
          )}

          {error && (
            <p className="rounded-[var(--radius)] px-3 py-2 text-[12px] font-semibold"
               style={{ background: "var(--danger)", color: "var(--ink)",
                        border: "var(--line-width) solid var(--line)" }}>
              {error}
            </p>
          )}
        </div>

        <footer
          className="flex shrink-0 items-center justify-between gap-2 px-4 py-3"
          style={{ borderTop: "var(--line-width) solid var(--line)" }}
        >
          <p className="text-[10px] font-semibold" style={{ color: "var(--ink-faint)" }}>
            {step === "source"
              ? "Nothing is saved until you review what was found."
              : "Solutions are written after saving, and cited to their source."}
          </p>

          {step === "source" ? (
            <button
              type="button"
              onClick={runImport}
              disabled={!canFetch}
              className="flex min-h-11 items-center gap-1.5 rounded-[var(--radius-pill)] px-4 text-[12px] font-bold disabled:opacity-40"
              style={{ background: "var(--accent)", color: "var(--ink)",
                       border: "var(--line-width) solid var(--line)" }}
            >
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
              {busy ? "Reading…" : "Find questions"}
            </button>
          ) : (
            <button
              type="button"
              onClick={save}
              disabled={unanswered > 0 || step === "saving"}
              className="flex min-h-11 items-center gap-1.5 rounded-[var(--radius-pill)] px-4 text-[12px] font-bold disabled:opacity-40"
              style={{ background: "var(--success)", color: "var(--ink)",
                       border: "var(--line-width) solid var(--line)" }}
            >
              {step === "saving"
                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                : <Check className="h-3.5 w-3.5" />}
              {step === "saving"
                ? "Saving and writing solutions…"
                : `Save ${questions.length} questions`}
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}

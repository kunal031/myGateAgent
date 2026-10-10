"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Plus, X } from "lucide-react";

import {
  FeedCardItem, SubjectItem, UserCardInput, createUserCard, updateUserCard,
} from "@/lib/api";

type CardType = FeedCardItem["card_type"];

const CARD_TYPES: CardType[] = ["CONCEPT", "FORMULA", "TRAP", "SHORTCUT"];
const MODES = [
  { value: "BASIC", label: "Basic" },
  { value: "ADVANCED", label: "Advanced" },
  { value: "REVISION", label: "Revision" },
];

interface Props {
  subjects: SubjectItem[];
  /** Pass a card to edit it; omit to write a new one. */
  card?: FeedCardItem | null;
  onClose: () => void;
  onSaved: (card: FeedCardItem) => void;
}

/**
 * Write or edit a card by hand.
 *
 * Subject and topic are required because the card has to land somewhere the
 * feed can file it. Everything else is optional: a card written in a hurry
 * during revision should cost one title and one paragraph.
 */
export default function CardComposer({ subjects, card = null, onClose, onSaved }: Props) {
  const editing = card !== null;

  const [subjectSlug, setSubjectSlug] = useState(card?.subject_slug ?? "");
  const [topicSlug, setTopicSlug] = useState(card?.topic_slug ?? "");
  const [title, setTitle] = useState(card?.title ?? "");
  const [content, setContent] = useState(card?.content ?? "");
  const [takeaway, setTakeaway] = useState(card?.takeaway ?? "");
  const [cardType, setCardType] = useState<CardType>(card?.card_type ?? "CONCEPT");
  const [mode, setMode] = useState("ADVANCED");
  const [tags, setTags] = useState<string[]>(card?.tags ?? []);
  const [tagDraft, setTagDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const titleRef = useRef<HTMLInputElement>(null);

  const topics = useMemo(
    () => subjects.find((s) => s.slug === subjectSlug)?.topics ?? [],
    [subjects, subjectSlug],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    titleRef.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, []);

  const addTag = useCallback(() => {
    const next = tagDraft.replace(",", " ").trim();
    if (!next) return;
    setTags((prev) =>
      prev.some((t) => t.toLowerCase() === next.toLowerCase())
        ? prev
        : [...prev, next].slice(0, 12),
    );
    setTagDraft("");
  }, [tagDraft]);

  const onTagKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    // Enter and comma both commit a tag; Enter must not submit the form.
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag();
    } else if (e.key === "Backspace" && !tagDraft) {
      setTags((prev) => prev.slice(0, -1));
    }
  };

  const canSave = Boolean(
    subjectSlug && topicSlug && title.trim() && content.trim() && !saving,
  );

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSave) return;

    // A tag still being typed when Save is pressed should not be lost.
    const pending = tagDraft.replace(",", " ").trim();
    const finalTags = pending && !tags.some((t) => t.toLowerCase() === pending.toLowerCase())
      ? [...tags, pending]
      : tags;

    const input: UserCardInput = {
      subject_slug: subjectSlug,
      topic_slug: topicSlug,
      title: title.trim(),
      content: content.trim(),
      takeaway: takeaway.trim(),
      card_type: cardType,
      mode,
      tags: finalTags,
    };

    setSaving(true);
    setError("");
    try {
      const saved = editing
        ? await updateUserCard(card!.id, input)
        : await createUserCard(input);
      onSaved(saved);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save that card");
    } finally {
      setSaving(false);
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
      <form
        onSubmit={save}
        role="dialog"
        aria-modal="true"
        aria-label={editing ? "Edit your card" : "Write a card"}
        className="flex max-h-[92vh] w-full max-w-xl flex-col overflow-hidden rounded-t-[var(--radius-lg)] sm:max-h-[88vh] sm:rounded-[var(--radius-lg)]"
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
          <h2 className="text-sm font-extrabold" style={{ color: "var(--ink)" }}>
            {editing ? "Edit your card" : "Write a card"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius-pill)]"
            style={{ ...field, background: "var(--surface-sunk)" }}
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-[10px] font-extrabold uppercase tracking-wider"
                    style={{ color: "var(--ink-faint)" }}>
                Subject
              </span>
              <select
                value={subjectSlug}
                onChange={(e) => {
                  // A topic from the previous subject must not survive the
                  // switch, or the card is filed under a topic that does
                  // not belong to it.
                  setSubjectSlug(e.target.value);
                  setTopicSlug("");
                }}
                className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm"
                style={field}
                required
              >
                <option value="">Choose…</option>
                {subjects.map((s) => (
                  <option key={s.slug} value={s.slug}>{s.name}</option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="mb-1 block text-[10px] font-extrabold uppercase tracking-wider"
                    style={{ color: "var(--ink-faint)" }}>
                Topic
              </span>
              <select
                value={topicSlug}
                onChange={(e) => setTopicSlug(e.target.value)}
                disabled={!subjectSlug}
                className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm disabled:opacity-50"
                style={field}
                required
              >
                <option value="">{subjectSlug ? "Choose…" : "Pick a subject first"}</option>
                {topics.map((t) => (
                  <option key={t.slug} value={t.slug}>{t.name}</option>
                ))}
              </select>
            </label>
          </div>

          <label className="block">
            <span className="mb-1 block text-[10px] font-extrabold uppercase tracking-wider"
                  style={{ color: "var(--ink-faint)" }}>
              Title
            </span>
            <input
              ref={titleRef}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
              placeholder="What is this card about?"
              className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm outline-none"
              style={field}
              required
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-[10px] font-extrabold uppercase tracking-wider"
                  style={{ color: "var(--ink-faint)" }}>
              Content — LaTeX with $…$ works
            </span>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={5}
              placeholder="The explanation, formula, or trap worth remembering."
              className="w-full resize-y rounded-[var(--radius)] px-3 py-2 text-sm outline-none"
              style={field}
              required
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-[10px] font-extrabold uppercase tracking-wider"
                  style={{ color: "var(--ink-faint)" }}>
              Takeaway — optional, the one line to recall
            </span>
            <input
              value={takeaway}
              onChange={(e) => setTakeaway(e.target.value)}
              placeholder="Defaults to the title if left empty."
              className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm outline-none"
              style={field}
            />
          </label>

          <div className="grid grid-cols-2 gap-2">
            <label className="block">
              <span className="mb-1 block text-[10px] font-extrabold uppercase tracking-wider"
                    style={{ color: "var(--ink-faint)" }}>
                Type
              </span>
              <select
                value={cardType}
                onChange={(e) => setCardType(e.target.value as CardType)}
                className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm"
                style={field}
              >
                {CARD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </label>

            <label className="block">
              <span className="mb-1 block text-[10px] font-extrabold uppercase tracking-wider"
                    style={{ color: "var(--ink-faint)" }}>
                Mode
              </span>
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value)}
                className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm"
                style={field}
              >
                {MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </label>
          </div>

          <div>
            <span className="mb-1 block text-[10px] font-extrabold uppercase tracking-wider"
                  style={{ color: "var(--ink-faint)" }}>
              Tags — chapter, related concept, anything to find it by
            </span>
            <div className="flex flex-wrap items-center gap-1.5">
              {tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 rounded-[var(--radius-pill)] px-2 py-1 text-[11px] font-bold"
                  style={{
                    background: "var(--accent)",
                    border: "var(--line-width) solid var(--line)",
                    color: "var(--ink)",
                  }}
                >
                  {tag}
                  <button
                    type="button"
                    onClick={() => setTags((prev) => prev.filter((t) => t !== tag))}
                    aria-label={`Remove tag ${tag}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
              <input
                value={tagDraft}
                onChange={(e) => setTagDraft(e.target.value)}
                onKeyDown={onTagKey}
                onBlur={addTag}
                placeholder={tags.length ? "Add another…" : "Type and press Enter"}
                aria-label="Add a tag"
                className="min-h-9 min-w-[9rem] flex-1 rounded-[var(--radius-pill)] px-3 text-[12px] outline-none"
                style={field}
              />
            </div>
          </div>

          {error && (
            <p className="rounded-[var(--radius)] px-3 py-2 text-[12px] font-semibold"
               style={{
                 background: "var(--danger)",
                 color: "var(--ink)",
                 border: "var(--line-width) solid var(--line)",
               }}>
              {error}
            </p>
          )}
        </div>

        <footer
          className="flex shrink-0 items-center justify-end gap-2 px-4 py-3"
          style={{ borderTop: "var(--line-width) solid var(--line)" }}
        >
          <button
            type="button"
            onClick={onClose}
            className="min-h-11 rounded-[var(--radius-pill)] px-4 text-[12px] font-bold"
            style={{ ...field, background: "var(--surface)" }}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!canSave}
            className="flex min-h-11 items-center gap-1.5 rounded-[var(--radius-pill)] px-4 text-[12px] font-bold disabled:opacity-40"
            style={{
              background: "var(--accent)",
              border: "var(--line-width) solid var(--line)",
              color: "var(--ink)",
            }}
          >
            {saving
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <Plus className="h-3.5 w-3.5" />}
            {editing ? "Save changes" : "Add card"}
          </button>
        </footer>
      </form>
    </div>
  );
}

"use client";

import React from "react";
import Link from "next/link";
import {
  AlertTriangle, ArrowRight, Binary, Check, Lightbulb,
  MessageCircleQuestion, Pencil, Trash2, UserPen, Zap, type LucideIcon,
} from "lucide-react";

import ConceptPopover from "./ConceptPopover";
import MathText from "@/components/MathText";
import { FeedCardItem } from "@/lib/api";
import { variantFor } from "./card-variants";
import ActionHint from "./ActionHint";

const TYPE_META: Record<string, { label: string; icon: LucideIcon }> = {
  TRAP: { label: "TRAP", icon: AlertTriangle },
  FORMULA: { label: "FORMULA", icon: Binary },
  CONCEPT: { label: "CORE", icon: Lightbulb },
  SHORTCUT: { label: "SHORTCUT", icon: Zap },
};

interface Props {
  card: FeedCardItem;
  /** Records a single-card recall. Currently unused: the "Got it" button
   *  that called it is disabled, so nothing invokes this. Kept on the
   *  interface (and optional) so re-enabling the button is a one-line
   *  change rather than re-threading the prop from the feed page. */
  onMastered?: (id: number) => void;
  /** Opens the assistant with this card already in context. */
  onExplain: (card: FeedCardItem) => void;
  /** Mark the whole concept, not just this card. */
  onMarkConcept?: (conceptId: number, action: "learn" | "revise") => void;
  /** Only passed for cards the student wrote; generated ones are fixed. */
  onEdit?: (card: FeedCardItem) => void;
  onDelete?: (card: FeedCardItem) => void;
  /** True while the card plays its exit animation before removal. */
  leaving?: boolean;
}

export default function FeedCard({
  card, onExplain, onMarkConcept, onEdit, onDelete,
  leaving = false,
}: Props) {
  const meta = TYPE_META[card.card_type] ?? TYPE_META.CONCEPT;
  const Icon = meta.icon;
  const v = variantFor(card);
  const mine = card.source_type === "user";

  return (
    <article
      // break-inside-avoid keeps a card whole inside a CSS column.
      className="mb-4 break-inside-avoid overflow-hidden transition-all duration-300"
      style={{
        background: v.surface,
        border: "var(--line-width) solid var(--line)",
        borderRadius: v.radius,
        boxShadow: v.shadow,
        opacity: leaving ? 0 : 1,
        transform: leaving ? "scale(0.94)" : "scale(1)",
      }}
    >
      <div
        className="flex flex-wrap items-center gap-2 px-4 py-2.5"
        style={{
          background: v.bandedHeader ? v.accent : "transparent",
          borderBottom: v.bandedHeader
            ? "var(--line-width) solid var(--line)"
            : "none",
        }}
      >
        <span
          className="inline-flex items-center gap-1 rounded-[var(--radius-pill)] px-2 py-0.5 text-[10px] font-extrabold tracking-wider"
          style={{
            background: v.bandedHeader ? "var(--surface)" : v.accent,
            color: "var(--ink)",
            border: "var(--line-width) solid var(--line)",
          }}
        >
          <Icon className="h-3 w-3" />
          {meta.label}
        </span>

        {mine && (
          <span
            className="inline-flex items-center gap-1 rounded-[var(--radius-pill)] px-2 py-0.5 text-[10px] font-extrabold tracking-wider"
            style={{
              background: "var(--surface)",
              color: "var(--ink)",
              border: "var(--line-width) solid var(--line)",
            }}
            title="You wrote this card"
          >
            <UserPen className="h-3 w-3" />
            MINE
          </span>
        )}

        {card.is_remedial && (
          <span
            className="rounded-[var(--radius-pill)] px-2 py-0.5 text-[10px] font-extrabold"
            style={{
              background: "var(--danger)",
              color: "var(--ink)",
              border: "var(--line-width) solid var(--line)",
            }}
          >
            {card.recent_mistakes_in_topic}× MISSED
          </span>
        )}
      </div>

      <div className="px-4 pt-3">
        <p className="truncate text-[12px] font-semibold" style={{ color: "var(--ink-faint)" }}>
          {card.subject_name}
        </p>
        <ConceptPopover cardId={card.id}>
          <h3
            className="mt-1 break-words text-[18px] font-bold leading-snug"
            style={{ color: "var(--ink)" }}
          >
            {card.title}
          </h3>
        </ConceptPopover>
      </div>

      <div className="min-w-0 px-4 py-2.5">
        <div
          className="overflow-x-auto text-[15px] leading-relaxed"
          style={{ color: "var(--ink-soft)" }}
        >
          <MathText text={card.content} />
        </div>
      </div>

      <div className="px-4 pb-3">
        <div
          className="overflow-x-auto rounded-[var(--radius)] px-3 py-2"
          style={{ background: v.accent, border: "var(--line-width) solid var(--line)" }}
        >
          <div className="text-[14.5px] font-semibold" style={{ color: "var(--ink)" }}>
            <MathText text={card.takeaway} />
          </div>
        </div>
      </div>

      {card.tags && card.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 px-4 pb-3">
          {card.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-[var(--radius-pill)] px-2 py-0.5 text-[10px] font-bold"
              style={{
                background: "var(--surface-sunk)",
                color: "var(--ink-soft)",
                border: "var(--line-width) solid var(--line)",
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      <div
        className="flex items-stretch"
        style={{ borderTop: "var(--line-width) solid var(--line)" }}
      >
        {/* Wording says what each one changes, because the difference
            between them is not guessable: "Got it" was about this card,
            L and R are about the whole concept behind it.

            "Got it" is deliberately inert. It is kept visible rather than
            removed because it is the only control that writes
            CardView.recall_count, which is what starts the 1/3/7/21/60-day
            spacing ladder -- dropping the button outright would silently
            leave the feed's 25% review slot permanently empty and report
            every retention figure as zero. Disabled rather than deleted so
            the footer keeps its three-way split and the mechanic can be
            turned back on by restoring onClick.

            aria-disabled, not `disabled`: a `disabled` button is removed
            from the accessibility tree and stops announcing its label, so
            a screen-reader user gets an unexplained gap where a control
            used to be. This way it is announced and explained. pointer
            events are dropped so the hint cannot imply it still acts. */}
        <ActionHint grow
          label="Marking single cards is off — use L to mark the whole concept learned, or R once you have revised it">
          <button
            type="button"
            aria-disabled="true"
            tabIndex={-1}
            title="Marking single cards is off — use L or R instead"
            className="pointer-events-none flex min-h-11 flex-1 cursor-default items-center justify-center gap-1.5 text-[13px] font-bold transition-colors"
            style={{ color: "var(--ink-soft)", opacity: 0.55 }}
            aria-label={`Marking ${card.title} on its own is turned off; use L or R to mark the concept`}
          >
            <Check className="h-3.5 w-3.5" />
            Got it
          </button>
        </ActionHint>

        {/* Now the only controls that record progress, since "Got it" is
            inert. Widened from w-11 to a shared flex slot: at 44px beside
            two full-width buttons they read as an afterthought, which is
            the wrong weight for the only thing that moves a concept
            forward. */}
        {card.concept_id != null && onMarkConcept && (
          <>
            <ActionHint label="Learned — mark the whole concept known, without going through its other cards">
              <button
                type="button"
                onClick={() => onMarkConcept(card.concept_id as number, "learn")}
                title="Learned — mark the whole concept known"
                aria-label={`Mark the concept behind ${card.title} as learned`}
                className="flex min-h-11 w-14 items-center justify-center text-[13px] font-extrabold"
                style={{
                  color: "var(--ink)",
                  borderLeft: "var(--line-width) solid var(--line)",
                }}
              >
                L
              </button>
            </ActionHint>
            <ActionHint label="Revised — you have been back over this concept; counts towards your revision streak">
              <button
                type="button"
                onClick={() => onMarkConcept(card.concept_id as number, "revise")}
                title="Revised — you have been back over this concept"
                aria-label={`Mark the concept behind ${card.title} as revised`}
                className="flex min-h-11 w-14 items-center justify-center text-[13px] font-extrabold"
                style={{
                  color: "var(--ink)",
                  borderLeft: "var(--line-width) solid var(--line)",
                }}
              >
                R
              </button>
            </ActionHint>
          </>
        )}

        <ActionHint grow
          label="Ask the AI about this card — a deeper explanation, or anything you want to follow up. Changes no progress.">
          <button
            type="button"
            onClick={() => onExplain(card)}
            title="Ask the AI about this card"
            aria-label={`Explain ${card.title}`}
            className="flex min-h-11 flex-1 items-center justify-center gap-1.5 text-[13px] font-bold"
            style={{
              color: "var(--ink)",
              borderLeft: "var(--line-width) solid var(--line)",
            }}
          >
            <MessageCircleQuestion className="h-3.5 w-3.5" />
            Explain
          </button>
        </ActionHint>

        {mine && onEdit && onDelete ? (
          <>
            <button
              type="button"
              onClick={() => onEdit(card)}
              aria-label={`Edit ${card.title}`}
              className="flex min-h-11 flex-1 items-center justify-center gap-1.5 text-[13px] font-bold"
              style={{
                color: "var(--ink)",
                borderLeft: "var(--line-width) solid var(--line)",
              }}
            >
              <Pencil className="h-3.5 w-3.5" />
              Edit
            </button>
            <button
              type="button"
              onClick={() => onDelete(card)}
              aria-label={`Delete ${card.title}`}
              className="flex min-h-11 w-12 shrink-0 items-center justify-center"
              style={{
                color: "var(--ink)",
                borderLeft: "var(--line-width) solid var(--line)",
              }}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </>
        ) : (
          <Link
            href={`/quiz?subject=${card.subject_slug}&topic=${card.topic_slug}`}
            className="flex min-h-11 flex-1 items-center justify-center gap-1 text-[13px] font-bold"
            style={{
              color: "var(--ink)",
              borderLeft: "var(--line-width) solid var(--line)",
            }}
          >
            Drill
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        )}
      </div>
    </article>
  );
}

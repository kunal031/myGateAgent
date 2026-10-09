"use client";

import React from "react";
import Link from "next/link";
import {
  AlertTriangle, ArrowRight, Binary, Check, Lightbulb,
  MessageCircleQuestion, Zap, type LucideIcon,
} from "lucide-react";

import MathText from "@/components/MathText";
import { FeedCardItem } from "@/lib/api";
import { variantFor } from "./card-variants";

const TYPE_META: Record<string, { label: string; icon: LucideIcon }> = {
  TRAP: { label: "TRAP", icon: AlertTriangle },
  FORMULA: { label: "FORMULA", icon: Binary },
  CONCEPT: { label: "CORE", icon: Lightbulb },
  SHORTCUT: { label: "SHORTCUT", icon: Zap },
};

interface Props {
  card: FeedCardItem;
  onMastered: (id: number) => void;
  /** Opens the assistant with this card already in context. */
  onExplain: (card: FeedCardItem) => void;
  /** True while the card plays its exit animation before removal. */
  leaving?: boolean;
}

export default function FeedCard({
  card, onMastered, onExplain, leaving = false,
}: Props) {
  const meta = TYPE_META[card.card_type] ?? TYPE_META.CONCEPT;
  const Icon = meta.icon;
  const v = variantFor(card);

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
        <h3
          className="mt-1 break-words text-[18px] font-bold leading-snug"
          style={{ color: "var(--ink)" }}
        >
          {card.title}
        </h3>
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

      <div
        className="flex items-stretch"
        style={{ borderTop: "var(--line-width) solid var(--line)" }}
      >
        <button
          type="button"
          onClick={() => onMastered(card.id)}
          className="flex min-h-11 flex-1 items-center justify-center gap-1.5 text-[13px] font-bold transition-colors"
          style={{ color: "var(--ink)" }}
          aria-label={`Mark ${card.title} as read`}
        >
          <Check className="h-3.5 w-3.5" />
          Got it
        </button>

        <button
          type="button"
          onClick={() => onExplain(card)}
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
      </div>
    </article>
  );
}

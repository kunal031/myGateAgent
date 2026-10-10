"use client";

import React, { useEffect, useRef, useState } from "react";
import { ChevronRight, Loader2 } from "lucide-react";

import {
  CardMetadata, TAG_ROLE_LABELS, fetchCardMetadata,
} from "@/lib/tags";

/** Delay before a hover counts as intent, so crossing a grid is free. */
const HOVER_DELAY_MS = 220;

interface Props {
  cardId: number;
  children: React.ReactNode;
}

/**
 * Shows a card's structural ancestry and its typed tags on hover.
 *
 * The request is deferred and abortable: moving a pointer across a masonry
 * grid passes over many cards, and firing on each would issue a burst of
 * requests whose answers arrive out of order. Nothing is fetched until the
 * pointer settles, and leaving cancels whatever is in flight.
 *
 * Metadata is cached per card for the life of the component, since the
 * ancestry and tags do not change while the feed is open.
 */
export default function ConceptPopover({ cardId, children }: Props) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<CardMetadata | null>(null);
  const [loading, setLoading] = useState(false);

  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const controller = useRef<AbortController | null>(null);
  const cache = useRef<Map<number, CardMetadata>>(new Map());

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
    controller.current?.abort();
  }, []);

  const begin = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      setOpen(true);

      const cached = cache.current.get(cardId);
      if (cached) { setData(cached); return; }

      controller.current?.abort();
      const ctrl = new AbortController();
      controller.current = ctrl;

      setLoading(true);
      try {
        const meta = await fetchCardMetadata(cardId, ctrl.signal);
        cache.current.set(cardId, meta);
        setData(meta);
      } catch {
        // An aborted or failed lookup simply shows nothing; the card
        // itself is unaffected.
      } finally {
        if (!ctrl.signal.aborted) setLoading(false);
      }
    }, HOVER_DELAY_MS);
  };

  const end = () => {
    if (timer.current) clearTimeout(timer.current);
    controller.current?.abort();
    setOpen(false);
  };

  return (
    <span
      className="relative inline-block"
      onMouseEnter={begin}
      onMouseLeave={end}
      onFocus={begin}
      onBlur={end}
    >
      {children}

      {open && (
        <span
          role="tooltip"
          className="absolute left-0 top-full z-40 mt-1 block w-[min(21rem,80vw)] rounded-[var(--radius)] p-3 text-left"
          style={{
            background: "var(--surface)",
            border: "var(--line-width) solid var(--line)",
            boxShadow: "var(--shadow)",
          }}
        >
          {loading && !data && (
            <span className="flex items-center gap-2 text-[11px] font-semibold"
                  style={{ color: "var(--ink-faint)" }}>
              <Loader2 className="h-3 w-3 animate-spin" />
              Loading…
            </span>
          )}

          {data && (
            <>
              {/* The strict tree: one path, rendered as a breadcrumb. */}
              <span className="mb-2 flex flex-wrap items-center gap-1 text-[11px] font-bold"
                    style={{ color: "var(--ink-soft)" }}>
                <span>{data.ancestry.subject.name}</span>
                <ChevronRight className="h-3 w-3 shrink-0" />
                <span>{data.ancestry.chapter.name}</span>
              </span>

              {/* The graph: tags grouped by what kind of thing they name. */}
              {data.tags.length === 0 ? (
                <span className="block text-[11px]" style={{ color: "var(--ink-faint)" }}>
                  No concept tags yet.
                </span>
              ) : (
                data.tags.map((group) => (
                  <span key={group.type} className="mb-2 block last:mb-0">
                    <span className="mb-1 block text-[9px] font-extrabold uppercase tracking-wider"
                          style={{ color: "var(--ink-faint)" }}>
                      {group.label}
                    </span>
                    <span className="flex flex-wrap gap-1">
                      {group.items.map((tag) => (
                        <span
                          key={tag.id}
                          title={tag.note || undefined}
                          className="inline-flex items-center gap-1 rounded-[var(--radius-pill)] px-2 py-0.5 text-[10px] font-bold"
                          style={{
                            background: tag.role === "primary"
                              ? "var(--accent)" : "var(--surface-sunk)",
                            border: "var(--line-width) solid var(--line)",
                            color: "var(--ink)",
                          }}
                        >
                          {tag.name}
                          {tag.role !== "primary" && (
                            <span style={{ color: "var(--ink-faint)" }}>
                              {TAG_ROLE_LABELS[tag.role]}
                            </span>
                          )}
                        </span>
                      ))}
                    </span>
                  </span>
                ))
              )}

              {data.provenance && (
                <span className="mt-2 block truncate text-[10px] font-semibold"
                      style={{ color: "var(--ink-faint)" }}>
                  {data.provenance}
                </span>
              )}
            </>
          )}
        </span>
      )}
    </span>
  );
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { FeedCardItem, fetchFeed } from "@/lib/api";

export const PAGE_SIZE = 18; // within the 15-20 per batch target

interface State {
  cards: FeedCardItem[];
  loading: boolean;      // first page
  loadingMore: boolean;  // subsequent pages
  error: string | null;
  total: number;
  hasMore: boolean;
}

/**
 * Paged feed loader.
 *
 * Filters reset the list; scrolling appends. A request token guards against
 * out-of-order responses, so a slow page for old filters cannot append to a
 * newer list, and ids are de-duplicated because ranking can shift between
 * requests when a mistake is recorded mid-session.
 */
export function useInfiniteFeed(subjectSlug: string, cardType: string) {
  const [state, setState] = useState<State>({
    cards: [], loading: true, loadingMore: false,
    error: null, total: 0, hasMore: true,
  });

  const offsetRef = useRef(0);
  const requestRef = useRef(0);
  const inFlight = useRef(false);

  const load = useCallback(
    async (reset: boolean) => {
      if (inFlight.current) return;
      inFlight.current = true;

      const token = ++requestRef.current;
      const offset = reset ? 0 : offsetRef.current;

      setState((prev) => ({
        ...prev,
        loading: reset,
        loadingMore: !reset,
        error: null,
      }));

      try {
        const page = await fetchFeed(subjectSlug, cardType, offset, PAGE_SIZE);
        if (token !== requestRef.current) return; // superseded

        offsetRef.current = page.next_offset ?? offset + page.items.length;
        setState((prev) => {
          const base = reset ? [] : prev.cards;
          const seen = new Set(base.map((c) => c.id));
          const merged = [...base, ...page.items.filter((c) => !seen.has(c.id))];
          return {
            cards: merged,
            loading: false,
            loadingMore: false,
            error: null,
            total: page.total,
            hasMore: page.next_offset !== null,
          };
        });
      } catch {
        if (token !== requestRef.current) return;
        setState((prev) => ({
          ...prev,
          loading: false,
          loadingMore: false,
          error: "Could not load the feed. Is the backend running?",
        }));
      } finally {
        inFlight.current = false;
      }
    },
    [subjectSlug, cardType],
  );

  useEffect(() => {
    offsetRef.current = 0;
    void load(true);
  }, [load]);

  const loadMore = useCallback(() => {
    if (state.hasMore && !state.loadingMore && !state.loading) void load(false);
  }, [load, state.hasMore, state.loadingMore, state.loading]);

  return { ...state, loadMore, refresh: () => load(true) };
}

/** Fires `onHit` when the sentinel scrolls into view. */
export function useScrollSentinel(
  onHit: () => void,
  enabled: boolean,
): (node: HTMLElement | null) => void {
  const observer = useRef<IntersectionObserver | null>(null);

  return useCallback(
    (node: HTMLElement | null) => {
      observer.current?.disconnect();
      if (!node || !enabled) return;
      observer.current = new IntersectionObserver(
        (entries) => {
          if (entries[0]?.isIntersecting) onHit();
        },
        // Start loading before the sentinel is visible, so the next batch is
        // usually ready by the time the user reaches it.
        { rootMargin: "600px 0px" },
      );
      observer.current.observe(node);
    },
    [enabled, onHit],
  );
}

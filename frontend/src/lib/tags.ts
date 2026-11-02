/**
 * The concept graph: typed tags laid over the syllabus tree.
 *
 * Two shapes, deliberately kept apart. `CardAncestry` is the strict tree --
 * exactly one path per card, always present. `TagGroup[]` is the graph --
 * many tags, typed, crossing subjects. A popover renders the first as a
 * breadcrumb and the second as a grouped list, and conflating them in one
 * array would lose the guarantee that ancestry is singular.
 */

import { api } from "./client/web";

/** Closed vocabulary; mirrors TagType in the backend. */
export type TagTypeValue =
  | "data_structure"
  | "algorithm"
  | "theorem"
  | "paradigm"
  | "system_mechanism"
  | "formula"
  | "problem_pattern"
  | "concept";

/** How a card relates to a tag, in hover display order. */
export type TagRole = "primary" | "uses" | "related" | "contrasts";

export const TAG_TYPE_LABELS: Record<TagTypeValue, string> = {
  data_structure: "Data Structure",
  algorithm: "Algorithm",
  theorem: "Theorem",
  paradigm: "Paradigm",
  system_mechanism: "System Mechanism",
  formula: "Formula",
  problem_pattern: "Problem Pattern",
  concept: "Concept",
};

export const TAG_ROLE_LABELS: Record<TagRole, string> = {
  primary: "about",
  uses: "uses",
  related: "related",
  contrasts: "vs",
};

/** One tag as it appears on a card, with the per-edge context. */
export interface TaggedConcept {
  id: number;
  name: string;
  slug: string;
  /** Why this tag is on this card. Differs per card, hence per edge. */
  role: TagRole;
  note: string;
  /** "user" or "auto" -- an inferred tag is marked as such. */
  added_by: string;
  /** How many cards share it; drives "N other cards" in the popover. */
  usage_count: number;
}

/** Tags of one type, which is how the popover reads them. */
export interface TagGroup {
  type: TagTypeValue;
  label: string;
  items: TaggedConcept[];
}

export interface TaxonomyNode {
  id: number;
  name: string;
  slug: string;
}

/** The strict tree: one path, always present. */
export interface CardAncestry {
  subject: TaxonomyNode;
  chapter: TaxonomyNode;
  concept_id: number | null;
  /** Pre-joined "Subject → Chapter", so the UI does not rebuild it. */
  path: string;
}

/** Everything a hover popover needs, from one request. */
export interface CardMetadata {
  card_id: number;
  title: string;
  ancestry: CardAncestry;
  source_type: string;
  provenance: string;
  tags: TagGroup[];
  tag_count: number;
}

export interface RelatedCard {
  id: number;
  title: string;
  subject_name: string;
  shared_tags: number;
  source_type: string;
}

/** A tag in the vocabulary, for autocomplete and browsing. */
export interface TagVocabularyItem {
  id: number;
  name: string;
  slug: string;
  type: TagTypeValue;
  label: string;
  usage_count: number;
}

/** What a client sends to set a card's tags. */
export interface TagInput {
  name: string;
  type?: TagTypeValue;
  role?: TagRole;
  note?: string;
}

/**
 * Ancestry and tags for one card.
 *
 * Takes an AbortSignal because this fires on mouse-over: moving across a
 * grid starts a request per card, and without cancellation the last one to
 * land wins rather than the one still hovered.
 */
export async function fetchCardMetadata(
  cardId: number,
  signal?: AbortSignal,
): Promise<CardMetadata> {
  return api.get<CardMetadata>(`/api/feed/${cardId}/metadata`, { signal });
}

export async function fetchRelatedCards(
  cardId: number,
  limit = 8,
  signal?: AbortSignal,
): Promise<RelatedCard[]> {
  const data = await api.get<{ items: RelatedCard[] }>(
    `/api/feed/${cardId}/related`, { query: { limit }, signal },
  );
  return data.items;
}

export async function setCardTags(
  cardId: number,
  tags: TagInput[],
): Promise<CardMetadata> {
  return api.put<CardMetadata>(`/api/feed/${cardId}/tags`, tags);
}

export async function browseTags(
  params: { type?: TagTypeValue | "all"; q?: string; limit?: number } = {},
  signal?: AbortSignal,
): Promise<{ items: TagVocabularyItem[]; types: { value: TagTypeValue; label: string }[] }> {
  const search = new URLSearchParams();
  if (params.type && params.type !== "all") search.set("tag_type", params.type);
  if (params.q) search.set("q", params.q);
  if (params.limit) search.set("limit", String(params.limit));

  return api.get(`/api/feed/tags/browse`, {
    query: Object.fromEntries(search), signal,
  });
}

/** Flatten groups back to one list, for a compact inline display. */
export function flattenTags(groups: TagGroup[]): TaggedConcept[] {
  return groups.flatMap((group) => group.items);
}

/**
 * Per-card visual variation.
 *
 * A wall of identical cards is hard to scan, so each card picks an accent,
 * a corner treatment and a header style. The choice is derived from the card
 * id, which keeps it stable across re-renders and pagination -- a random
 * pick would reshuffle every time the list changed.
 */

export interface CardVariant {
  /** Background for the card body. */
  surface: string;
  /** Accent block behind the type badge and takeaway. */
  accent: string;
  /** Corner radius mix, so cards are not all identical rounded rectangles. */
  radius: string;
  /** Tinted header band, used on roughly half the cards. */
  bandedHeader: boolean;
  /** Offset shadow depth. */
  shadow: string;
}

const ACCENTS = [
  "var(--concept)",
  "var(--shortcut)",
  "var(--formula)",
  "var(--warning)",
  "var(--danger)",
];

const RADII = [
  "var(--radius-lg)",
  "var(--radius)",
  "calc(var(--radius-lg) + 6px) var(--radius) var(--radius-lg) var(--radius)",
  "var(--radius) calc(var(--radius-lg) + 6px) var(--radius) var(--radius-lg)",
];

/** Type keeps its semantic colour; everything else varies. */
const TYPE_ACCENT: Record<string, string> = {
  TRAP: "var(--danger)",
  FORMULA: "var(--formula)",
  CONCEPT: "var(--concept)",
  SHORTCUT: "var(--shortcut)",
};

export function variantFor(card: { id: number; card_type: string }): CardVariant {
  const seed = card.id;
  return {
    surface: seed % 5 === 0 ? "var(--surface-muted)" : "var(--surface)",
    accent: TYPE_ACCENT[card.card_type] ?? ACCENTS[seed % ACCENTS.length],
    radius: RADII[seed % RADII.length],
    bandedHeader: seed % 2 === 0,
    shadow: seed % 3 === 0 ? "var(--shadow)" : "var(--shadow-sm)",
  };
}

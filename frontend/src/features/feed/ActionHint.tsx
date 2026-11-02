"use client";

import React, { useEffect, useRef, useState } from "react";

/**
 * A label that explains what an action button does.
 *
 * The native `title` attribute is not enough here: it waits a second or
 * more before appearing, cannot be styled, and does nothing at all on a
 * touch screen -- which is where "L" and "R" are least self-explanatory,
 * since there is no hover to discover them with.
 *
 * So this shows on hover and on focus for keyboard users, and on a long
 * press for touch. `title` is still passed through underneath as a
 * fallback for anything that bypasses this, such as a screen reader
 * reading the raw element.
 */

/** Long enough not to fire on an ordinary tap, short enough to feel
 *  deliberate. Matches the platform convention for a press-and-hold. */
const LONG_PRESS_MS = 400;

export default function ActionHint({
  label, children, align = "center", grow = false,
}: {
  /** What the button does, in a few words. */
  label: string;
  children: React.ReactNode;
  align?: "center" | "right";
  /** True when the wrapped button was a flex child sharing the row's
   *  width. The wrapper becomes the flex child, so without this the
   *  button collapses to its content and the row stops splitting evenly. */
  grow?: boolean;
}) {
  const [shown, setShown] = useState(false);
  const timer = useRef<number | null>(null);

  // A press that becomes a scroll should not leave the hint stuck open,
  // and an unmount mid-press must not fire the timer afterwards.
  useEffect(() => () => {
    if (timer.current !== null) window.clearTimeout(timer.current);
  }, []);

  const startPress = () => {
    timer.current = window.setTimeout(() => setShown(true), LONG_PRESS_MS);
  };
  const endPress = () => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
    setShown(false);
  };

  return (
    <span
      className={`relative flex ${grow ? "flex-1" : ""}`}
      onMouseEnter={() => setShown(true)}
      onMouseLeave={() => setShown(false)}
      onFocus={() => setShown(true)}
      onBlur={() => setShown(false)}
      onTouchStart={startPress}
      onTouchEnd={endPress}
      onTouchCancel={endPress}
    >
      {children}

      {shown && (
        <span
          role="tooltip"
          className="pointer-events-none absolute bottom-full z-40 mb-1.5 w-max max-w-[220px] rounded-[var(--radius)] px-2 py-1 text-[11px] font-semibold leading-snug"
          style={{
            // Anchored above: these buttons sit at the foot of a card, so
            // a hint below would be clipped by the next card.
            background: "var(--ink)",
            color: "var(--surface)",
            border: "var(--line-width) solid var(--line)",
            boxShadow: "var(--shadow-sm)",
            ...(align === "right"
              ? { right: 0 }
              : { left: "50%", transform: "translateX(-50%)" }),
          }}
        >
          {label}
        </span>
      )}
    </span>
  );
}

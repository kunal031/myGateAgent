"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Hides a sticky header while scrolling down, reveals it on scroll up.
 *
 * Reads scroll position inside requestAnimationFrame so the handler does not
 * force layout on every scroll event. A threshold avoids flapping on the
 * small jitters that trackpads and momentum scrolling produce.
 */
export function useHideOnScroll(threshold = 8): boolean {
  const [hidden, setHidden] = useState(false);
  const lastY = useRef(0);
  const ticking = useRef(false);

  useEffect(() => {
    lastY.current = window.scrollY;

    const onScroll = () => {
      if (ticking.current) return;
      ticking.current = true;

      requestAnimationFrame(() => {
        const y = window.scrollY;
        const delta = y - lastY.current;

        if (Math.abs(delta) > threshold) {
          // Never hide at the very top, or the header would vanish on a
          // bounce scroll with nothing to scroll back up to.
          setHidden(delta > 0 && y > 64);
          lastY.current = y;
        }
        ticking.current = false;
      });
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [threshold]);

  return hidden;
}

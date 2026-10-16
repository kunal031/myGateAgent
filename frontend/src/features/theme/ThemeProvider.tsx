"use client";

import React, {
  createContext, useCallback, useContext, useSyncExternalStore,
} from "react";

export const THEMES = ["synapse", "light", "dark"] as const;
export type Theme = (typeof THEMES)[number];

export const THEME_LABELS: Record<Theme, string> = {
  synapse: "Original",
  light: "Light",
  dark: "Dark",
};

const STORAGE_KEY = "gatemaster-theme";
const DEFAULT_THEME: Theme = "synapse";

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

function readThemeAttribute(): Theme {
  const current = document.documentElement.getAttribute("data-theme");
  return current && THEMES.includes(current as Theme)
    ? (current as Theme)
    : DEFAULT_THEME;
}

/** Re-read the attribute whenever anything changes it. */
function subscribeToThemeAttribute(onChange: () => void): () => void {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });
  return () => observer.disconnect();
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: DEFAULT_THEME,
  setTheme: () => {},
});

export const useTheme = () => useContext(ThemeContext);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // The data-theme attribute is the single source of truth: the inline
  // script in layout.tsx sets it before paint, so there is no flash and no
  // React state to keep in sync. Subscribing to it rather than mirroring it
  // avoids both a hydration mismatch and a post-hydration state update.
  const theme = useSyncExternalStore(
    subscribeToThemeAttribute,
    readThemeAttribute,
    () => DEFAULT_THEME,
  );

  const setTheme = useCallback((next: Theme) => {
    // The MutationObserver above picks this up and re-renders consumers.
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Private mode or blocked storage: the theme still applies for this
      // session, it just will not be remembered.
    }
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

/** Runs before first paint to prevent a flash of the wrong theme. */
export const THEME_INIT_SCRIPT = `
(function() {
  try {
    var t = localStorage.getItem(${JSON.stringify(STORAGE_KEY)});
    if (t !== "synapse" && t !== "light" && t !== "dark") t = ${JSON.stringify(DEFAULT_THEME)};
    document.documentElement.setAttribute("data-theme", t);
  } catch (e) {
    document.documentElement.setAttribute("data-theme", ${JSON.stringify(DEFAULT_THEME)});
  }
})();
`.trim();

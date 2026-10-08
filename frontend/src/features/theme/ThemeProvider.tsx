"use client";

import React, { createContext, useCallback, useContext, useState } from "react";

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

const ThemeContext = createContext<ThemeContextValue>({
  theme: DEFAULT_THEME,
  setTheme: () => {},
});

export const useTheme = () => useContext(ThemeContext);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // The inline script in layout.tsx has already written the stored theme to
  // <html> before paint, so the initialiser just reads it back. Doing this
  // lazily (rather than in an effect) avoids a second render and keeps state
  // in step with the DOM from the first frame.
  const [theme, setThemeState] = useState<Theme>(() => {
    if (typeof document === "undefined") return DEFAULT_THEME;
    const current = document.documentElement.getAttribute("data-theme");
    return current && THEMES.includes(current as Theme)
      ? (current as Theme)
      : DEFAULT_THEME;
  });

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
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

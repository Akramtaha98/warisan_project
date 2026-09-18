export const THEME_STORAGE_KEY = "warisan.theme.v1";

export function normalizeTheme(value) {
  return value === "dark" || value === "light" ? value : null;
}

export function resolveTheme(options = {}) {
  try {
    const storage = options.storage ?? globalThis.localStorage;
    const saved = normalizeTheme(storage?.getItem(THEME_STORAGE_KEY));
    if (saved) return saved;
  } catch {
    // Storage can be unavailable in private or restricted browser contexts.
  }

  try {
    const matchMedia = options.matchMedia ?? globalThis.matchMedia;
    return matchMedia?.("(prefers-color-scheme: dark)")?.matches ? "dark" : "light";
  } catch {
    return "light";
  }
}

export function saveTheme(theme, storage) {
  const nextTheme = normalizeTheme(theme);
  if (!nextTheme) return false;
  try {
    storage ??= globalThis.localStorage;
    storage?.setItem(THEME_STORAGE_KEY, nextTheme);
    return true;
  } catch {
    return false;
  }
}

export function applyTheme(theme, root = globalThis.document?.documentElement) {
  const nextTheme = normalizeTheme(theme) || "light";
  if (root?.dataset) root.dataset.theme = nextTheme;
  return nextTheme;
}

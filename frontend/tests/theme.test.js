import test from "node:test";
import assert from "node:assert/strict";
import { applyTheme, resolveTheme, saveTheme, THEME_STORAGE_KEY } from "../src/lib/theme.js";

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) { return values.get(key) ?? null; },
    setItem(key, value) { values.set(key, value); },
  };
}

test("saved theme overrides the system preference", () => {
  const storage = memoryStorage({ [THEME_STORAGE_KEY]: "dark" });
  assert.equal(resolveTheme({ storage, matchMedia: () => ({ matches: false }) }), "dark");
});

test("system preference is used when no saved theme exists", () => {
  assert.equal(resolveTheme({ storage: memoryStorage(), matchMedia: () => ({ matches: true }) }), "dark");
  assert.equal(resolveTheme({ storage: memoryStorage(), matchMedia: () => ({ matches: false }) }), "light");
});

test("theme saves and applies to the document root", () => {
  const storage = memoryStorage();
  const root = { dataset: {} };
  assert.equal(saveTheme("dark", storage), true);
  assert.equal(storage.getItem(THEME_STORAGE_KEY), "dark");
  assert.equal(applyTheme("dark", root), "dark");
  assert.equal(root.dataset.theme, "dark");
});

test("restricted storage and invalid values fail safely", () => {
  const blocked = {
    getItem() { throw new Error("blocked"); },
    setItem() { throw new Error("blocked"); },
  };
  assert.equal(resolveTheme({ storage: blocked, matchMedia: () => ({ matches: false }) }), "light");
  assert.equal(saveTheme("dark", blocked), false);
  assert.equal(saveTheme("sepia", memoryStorage()), false);
});

# Gates: fixed composer, themes, and responsive layouts

OWNS: frontend/**, GATES.md

Scope: keep the question composer visible without page scrolling, add a persistent accessible light/dark theme, and deliver polished desktop, tablet, and mobile layouts

- [x] G0: this completion ledger states outcome-focused checks that can fail
  CHECK: node /Users/akramtaha/.agents/skills/unlazy/scripts/gate-lint.mjs GATES.md
  EXPECT: LINT OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/akramtaha/Work/Project/Warisan/warisan_project; path=bae1e0311ed6/26 entries; EXPECT=matched; output-sha256=54ffa428490a436ff6f51299fab7f49f5c5bf1843fe7f0866e40f8a4e4739ed3; output-bytes=386

- [x] G1: theme preference resolves, saves, restores, and applies safely
  CHECK: node --test frontend/tests/theme.test.js && printf 'theme-preference-verified\n'
  EXPECT: theme-preference-verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/akramtaha/Work/Project/Warisan/warisan_project; path=bae1e0311ed6/26 entries; EXPECT=matched; output-sha256=ed7fa3b3bec4299851670186e12695693e278cdb4fa380de33f8de6a1d8281b8; output-bytes=801

- [x] G2: the complete frontend regression suite passes and the production bundle builds
  CHECK: npm --prefix frontend run verify && printf 'responsive-theme-build-verified\n'
  EXPECT: responsive-theme-build-verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/akramtaha/Work/Project/Warisan/warisan_project; path=bae1e0311ed6/26 entries; EXPECT=matched; output-sha256=f36dafa702b7693bb1a1c2e1a139998bcf6abb896a7325ec1b085092139d2721; output-bytes=2919

- [x] G3: the composer remains visible in the initial viewport on desktop, tablet, and mobile while the welcome area scrolls independently when necessary
  EVIDENCE: 2026-09-18 — browser measurements at 1440x900, 820x1180, 390x844, and 360x640 showed body scroll height equal to viewport height and composer bottom equal to viewport height; compact welcome content scrolled only inside the conversation region

- [x] G4: light and dark modes are visually legible, switch accessibly, and persist after reload on the deployed website
  EVIDENCE: 2026-09-18 — visually reviewed desktop and mobile in both themes; verified accessible Gunakan mod gelap/cerah control and confirmed the selected light theme remained active after reloading production

- [x] G5: the production homepage and health endpoint respond successfully after deployment
  EVIDENCE: 2026-09-18 — latest deployment dpl_A42CKK9Z7tzqcAEoCQq3zWvpdgak reached READY; production homepage returned HTTP 200 and /api/health returned status=ready, database_ready=true, model_ready=true

# Gates: 100-QA Malay evaluation and adaptive Qwen3 reasoning

OWNS: app/sample_data/**, api/**, frontend/**, README.md, GATES.md

Scope: provide exactly 100 structured Malay QA examples, ground Qwen3 answers in retrieved examples, use deeper reasoning for hard questions, and verify the real deployed Qwen3 path

- [x] G0: this completion ledger states outcome-focused checks that can fail
  CHECK: node /Users/akramtaha/.agents/skills/unlazy/scripts/gate-lint.mjs GATES.md
  EXPECT: LINT OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/akramtaha/Work/Project/Warisan/warisan_project; path=bae1e0311ed6/26 entries; EXPECT=matched; output-sha256=2a9f46cb4190f162b4b53b57c3bfacb7d4400cb2a2ec0f330316ce3d8821faed; output-bytes=772

- [x] G1: the Malay evaluation fixture contains exactly 100 unique complete QA records with broad categories and hard examples
  CHECK: node --test api/tests/retrieval.test.js && printf 'qa-dataset-verified\n'
  EXPECT: qa-dataset-verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/akramtaha/Work/Project/Warisan/warisan_project; path=bae1e0311ed6/26 entries; EXPECT=matched; output-sha256=fef36c860b7811b54a039e46fb4daf6c16a4e7fdb35ba90fe9b79343cb30db88; output-bytes=670

- [x] G2: adaptive routing selects deep reasoning and larger context for hard questions while keeping direct questions concise
  CHECK: node --test api/tests/chat.test.js && printf 'adaptive-qwen-reasoning-verified\n'
  EXPECT: adaptive-qwen-reasoning-verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/akramtaha/Work/Project/Warisan/warisan_project; path=bae1e0311ed6/26 entries; EXPECT=matched; output-sha256=a5e5e3c4d27bb051d4109d6f9ced707494dcfd4e8a9131f5c19739e4fb813690; output-bytes=1337

- [x] G3: the complete project regression suite and production build pass
  CHECK: npm run verify && printf 'qwen-evaluation-build-verified\n'
  EXPECT: qwen-evaluation-build-verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/akramtaha/Work/Project/Warisan/warisan_project; path=bae1e0311ed6/26 entries; EXPECT=matched; output-sha256=750d3bb34cad365556d0b122e7543355c42b600ee31aeb0ef1e2cfac1f185cc2; output-bytes=5333

- [ ] G4: the deployed API returns a grounded answer from the real Qwen3 provider and reports thinking mode for a hard Malay question
  EVIDENCE: real direct case passed on `qwen/qwen3.8-27b:free` with score 87 and four sources. The hard case correctly reached the deployed `/think` route but OpenRouter returned HTTP 429; its live catalogue exposes no other active free Qwen model on 2026-09-19, so this gate remains honestly unmet until the free quota/capacity resets or another authorized provider is configured.

- [x] G5: the live interface reports the 100-record evaluation dataset and remains usable on desktop and mobile
  EVIDENCE: visual production checks at desktop and 390x844 mobile showed `100 QA Bahasa Melayu sintetik`, ready status, visible suggestion cards, and the composer without horizontal overflow.

- [x] G6: the verified implementation is deployed to Vercel and synchronized to GitHub main
  EVIDENCE: Vercel deployment `dpl_FfPCei7eRBMDrpUp3k2yPS2RSVab` is live and implementation commit `f770ef7` was pushed to `origin/main`.

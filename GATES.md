# Gates: 100-QA Malay evaluation and adaptive Qwen3 reasoning

OWNS: app/sample_data/**, api/**, frontend/**, README.md, GATES.md

Scope: provide exactly 100 structured Malay QA examples, ground Qwen3 answers in retrieved examples, use deeper reasoning for hard questions, and verify the real deployed Qwen3 path

- [x] G0: this completion ledger states outcome-focused checks that can fail
  CHECK: node /Users/akramtaha/.agents/skills/unlazy/scripts/gate-lint.mjs GATES.md
  EXPECT: LINT OK
  EVIDENCE: gate-lint returned `LINT OK (5 warning(s))`; warnings are the expected manual-evidence gates and numeric dataset requirements.

- [x] G1: the Malay evaluation fixture contains exactly 100 unique complete QA records with broad categories and hard examples
  CHECK: node --test api/tests/retrieval.test.js && printf 'qa-dataset-verified\n'
  EXPECT: qa-dataset-verified
  EVIDENCE: retrieval fixture test passed with exactly 100 unique records, 38 categories, and 15 hard examples.

- [x] G2: adaptive routing selects deep reasoning and larger context for hard questions while keeping direct questions concise
  CHECK: node --test api/tests/chat.test.js && printf 'adaptive-qwen-reasoning-verified\n'
  EXPECT: adaptive-qwen-reasoning-verified
  EVIDENCE: all 11 API tests passed, including `/think`, native medium reasoning, six references, empty-answer retry, and `/no_think` direct routing.

- [x] G3: the complete project regression suite and production build pass
  CHECK: npm run verify && printf 'qwen-evaluation-build-verified\n'
  EXPECT: qwen-evaluation-build-verified
  EVIDENCE: `./smoke-test.sh` passed: 13 frontend tests, 11 serverless API tests, 22 Python tests, 3 deployment checks, and a production Vite build.

- [ ] G4: the deployed API returns a grounded answer from the real Qwen3 provider and reports thinking mode for a hard Malay question
  EVIDENCE: real direct case passed on `qwen/qwen3.8-27b:free` with score 87 and four sources. The hard case correctly reached the deployed `/think` route but OpenRouter returned HTTP 429; its live catalogue exposes no other active free Qwen model on 2026-09-19, so this gate remains honestly unmet until the free quota/capacity resets or another authorized provider is configured.

- [x] G5: the live interface reports the 100-record evaluation dataset and remains usable on desktop and mobile
  EVIDENCE: visual production checks at desktop and 390x844 mobile showed `100 QA Bahasa Melayu sintetik`, ready status, visible suggestion cards, and the composer without horizontal overflow.

- [ ] G6: the verified implementation is deployed to Vercel and synchronized to GitHub main
  EVIDENCE: Vercel deployment `dpl_FfPCei7eRBMDrpUp3k2yPS2RSVab` is live; GitHub push is pending.

# Gates: DBP chatbot reasoning and answer quality

OWNS: app/scripts/**, app/ui/app.py, tests/**, .env.example, .gitignore, deploy.sh, docker-compose.yml, Dockerfile, README.md, README_DEPLOY.md, GATES.md

Scope: improve retrieval, grounded reasoning, resource reuse, and Qwen3 deployment defaults without weakening DBP-source grounding

- [x] G1: retrieval configuration expands medium-confidence searches and returns up to six grounded chunks
  CHECK: python3 -m unittest tests.test_rag_quality.RetrievalPolicyTests -v && printf 'retrieval-policy-passed\n'
  EXPECT: retrieval-policy-passed
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/akramtaha/Work/Project/Warisan/warisan_project; path=3d428eb9bff2/23 entries; EXPECT=matched; output-sha256=0fd21dfd37144b1efb9c765b22498f70c332f4d655b58e741ee129d322bb7b12; output-bytes=586

- [x] G2: HyDE follows the actual Malay query and expensive RAG resources are cached
  CHECK: python3 -m unittest tests.test_rag_quality.HydeAndResourceTests -v && printf 'hyde-resource-passed\n'
  EXPECT: hyde-resource-passed
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/akramtaha/Work/Project/Warisan/warisan_project; path=3d428eb9bff2/23 entries; EXPECT=matched; output-sha256=3447b5eb9f73fb8f90f9d0b91aee59aecae7d06dc85b6566148cab922003fc93; output-bytes=468

- [x] G3: generation routes complex questions through private thinking and does not reject supported answers through brittle keyword guards
  CHECK: python3 -m unittest tests.test_generation_quality -v && printf 'generation-quality-passed\n'
  EXPECT: generation-quality-passed
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/akramtaha/Work/Project/Warisan/warisan_project; path=3d428eb9bff2/23 entries; EXPECT=matched; output-sha256=8fc937a82893ac410c74b4adf485088e96ce0f35e9fe71bde6ea65d4192e3495; output-bytes=851

- [x] G4: source compiles and Qwen3 deployment defaults are consistent across configuration and documentation
  CHECK: python3 -m compileall -q app tests && bash -n deploy.sh && python3 -m unittest discover -s tests -v && printf 'full-quality-suite-passed\n'
  EXPECT: full-quality-suite-passed
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/akramtaha/Work/Project/Warisan/warisan_project; path=3d428eb9bff2/23 entries; EXPECT=matched; output-sha256=852dd0a7c9581f85c739e8bc403ada3300aab287c980a70990e54a6382e203c3; output-bytes=1955

# Gates: modern React chatbot experience

OWNS: frontend/**, app/api/**, app/ui/**, .streamlit/**, tests/**, .dockerignore, .env.example, .gitignore, Dockerfile, deploy.sh, requirements.txt, smoke-test.sh, README.md, README_DEPLOY.md, GATES.md

Scope: replace the Streamlit interface with a responsive React chatbot backed by a tested FastAPI contract and the existing grounded Qwen3 pipeline

- [x] G1: the React application tests and produces a deployable production bundle
  CHECK: npm --prefix frontend run verify && printf 'react-bundle-verified\n'
  EXPECT: react-bundle-verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/akramtaha/Work/Project/Warisan/warisan_project; path=3d428eb9bff2/23 entries; EXPECT=matched; output-sha256=43e51bbb364a827e85f490184800da9e76c095824a8b300ec0e4b4e6765ab1ad; output-bytes=1254

- [x] G2: the HTTP API validates questions, returns reasoning metadata, and records feedback safely
  CHECK: python3 -m unittest tests.test_api_contract -v && printf 'api-contract-verified\n'
  EXPECT: api-contract-verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/akramtaha/Work/Project/Warisan/warisan_project; path=3d428eb9bff2/23 entries; EXPECT=matched; output-sha256=715ff24593cfd6f4ae0f0ad625ec4903c761279197617127b912696211a092b8; output-bytes=787

- [x] G3: the project smoke test covers Python, React, deployment configuration, and reasoning regressions
  CHECK: ./smoke-test.sh && printf 'full-stack-smoke-verified\n'
  EXPECT: full-stack-smoke-verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/akramtaha/Work/Project/Warisan/warisan_project; path=3d428eb9bff2/23 entries; EXPECT=matched; output-sha256=af747d59905c90d37f36a88cd8ede021f4149d1418db8107f4303ffbf3ddbf4c; output-bytes=4851

- [x] G4: container and documentation consistently describe FastAPI serving the built React interface
  CHECK: python3 -m unittest tests.test_deployment_config -v && printf 'react-deployment-verified\n'
  EXPECT: react-deployment-verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/akramtaha/Work/Project/Warisan/warisan_project; path=3d428eb9bff2/23 entries; EXPECT=matched; output-sha256=7f55f189d8d64206e40b400633656ed87a741d2e2047ac84395593b8328c1e94; output-bytes=660

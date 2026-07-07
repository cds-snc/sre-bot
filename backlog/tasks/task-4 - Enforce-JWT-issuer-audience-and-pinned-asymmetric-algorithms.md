---
id: TASK-4
title: 'Enforce JWT issuer, audience, and pinned asymmetric algorithms'
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - security
  - phase-0
milestone: m-0
dependencies: []
references:
  - decisions/security.md
priority: high
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/security.md (Authentication). Today app/infrastructure/security/jwt.py:116-122 passes audience=cfg.get("audience") (None when unconfigured, so PyJWT skips the aud check), never passes issuer= to decode, and takes algorithms from config (algorithms=cfg.get("algorithms", ["RS256"])) with no asymmetric-only pinning, leaving an HS256-confusion path (SEC-3, OWASP API2:2023).

Steps in app/infrastructure/security/jwt.py:
1. Require an audience in every issuer config; a config entry without an audience fails boot (validation at settings load).
2. Pass issuer= to jwt.decode and match it to the issuer whose JWKS verified the token.
3. Pin algorithms to the asymmetric set configured per issuer (e.g. RS256/ES256); reject any HS* algorithm regardless of config; never read the algorithm from the token.
4. Validate exp always; validate nbf when present.
5. Keep JWKS fail-degraded semantics: a missing/unreachable issuer 401s its tokens; the app still serves.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Boot fails when an issuer config lacks an audience (test exists)
- [ ] #2 decode() receives issuer= and audience=; a token with wrong iss or aud is rejected (tests exist)
- [ ] #3 An HS256-signed token is rejected even if HS256 appears in configuration (test exists)
- [ ] #4 A token with valid signature but expired exp, or future nbf, is rejected
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass, including the four cases above
- [ ] #2 PR references SEC-3 and decisions/security.md
<!-- DOD:END -->

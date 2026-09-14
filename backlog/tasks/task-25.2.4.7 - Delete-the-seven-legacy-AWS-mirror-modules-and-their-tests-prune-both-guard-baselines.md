---
id: TASK-25.2.4.7
title: >-
  Delete the seven legacy AWS mirror modules and their tests; prune both guard
  baselines
status: To Do
assignee: []
created_date: '2026-09-14 17:39'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.4.3
  - TASK-25.2.4.4
  - TASK-25.2.4.5
  - TASK-25.2.4.6
references:
  - app/integrations/aws/organizations.py
  - app/integrations/aws/sso_admin.py
  - app/integrations/aws/config.py
  - app/integrations/aws/cost_explorer.py
  - app/integrations/aws/guard_duty.py
  - app/integrations/aws/security_hub.py
  - app/integrations/aws/lambdas.py
  - app/bin/baselines/vendor_package_contract.txt
  - app/bin/baselines/sdk_typing_antipatterns.txt
parent_task_id: TASK-25.2.4
priority: high
ordinal: 206000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-25.2.4, mirrors TASK-25.2.3.2.4's precedent (deletion bundled as one subtask after all callers migrate). Delete integrations/aws/{organizations,sso_admin,config,cost_explorer,guard_duty,security_hub,lambdas}.py and tests/integrations/aws/{test_organizations.py,test_sso_admin.py,test_legacy_config.py,test_cost_explorer.py,test_guard_duty.py,test_security_hub.py,test_lambas.py} (note the legacy Lambda test file is misspelled 'test_lambas.py' on disk). Re-grep app/ for 'execute_aws_api_call|handle_aws_api_errors' and for each of the seven module names first, to confirm zero remaining callers/imports outside the deleted files (TASK-25.2.4.3 through .4.6 must all be Done first). Prune the seven modules' entries from bin/baselines/vendor_package_contract.txt (currently lines 8,9,11,12,13,15,18) and bin/baselines/sdk_typing_antipatterns.txt (currently lines 7,8,10,11,12,13,15). This is a pure mechanical deletion PR (no behaviour change, no adapter code) -- kept as one slice despite ~16 files touched because every file is either a straight deletion or a baseline-line removal, matching the file-count gate's config/manifest-only exception and the TASK-25.2.3.2.4 precedent for an equivalent-shaped bundled deletion.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/aws/{organizations,sso_admin,config,cost_explorer,guard_duty,security_hub,lambdas}.py and their seven listed legacy test files no longer exist
- [ ] #2 bin/baselines/vendor_package_contract.txt and bin/baselines/sdk_typing_antipatterns.txt carry no entries for the seven deleted modules
- [ ] #3 A repo-wide grep for execute_aws_api_call, handle_aws_api_errors and each of the seven module names (outside app/integrations/aws/client.py's own definitions) returns zero hits in production code
<!-- AC:END -->

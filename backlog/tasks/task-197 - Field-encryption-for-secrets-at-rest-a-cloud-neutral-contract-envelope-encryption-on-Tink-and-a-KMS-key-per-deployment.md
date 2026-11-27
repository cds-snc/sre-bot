---
id: TASK-197
title: >-
  Field encryption for secrets at rest: a cloud-neutral contract, envelope
  encryption on Tink, and a KMS key per deployment
status: To Do
assignee: []
created_date: '2026-11-27T16:46:00Z'
labels:
  - security
  - infrastructure
  - portability
milestone: m-4
dependencies: []
references:
  - decisions/security.md
  - decisions/organisation-content.md
  - decisions/cloud-portability.md
  - decisions/webhooks.md
priority: high
ordinal: 556000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Coordinator of TASK-197.1 and TASK-197.2. Created at TASK-37.2.2 planning (2026-11-27, human-approved Q3a). organisation-content.md requires a managed record holding a non-public value to encrypt it at the application level (a KMS key with the record's identity as encryption context), and security.md applies that to webhook secrets. No task built the service: the TASK-37.2.2 scope held a webhooks-only KMS helper with no consumer, and webhooks.md section 9 deferred the library to TASK-47. It is platform infrastructure, built ahead of its consumers (TASK-47 webhook secrets, TASK-37.8 managed content).

Direction (human-approved): a cloud-neutral contract in contracts/ (seal and open with an encryption context; opaque, versioned sealed bytes naming their key), an in-memory fake and conformance suite (cloud-portability.md contract 4), and an infrastructure/ implementation on Google Tink's KMS envelope AEAD (a per-value AES-256-GCM data key with the context as associated data, wrapped by a key-encryption key named by a key URI in the configuration files: aws-kms://, gcp-kms://, hcvault://). Azure Key Vault needs one wrap/unwrap client when a move is chosen; consumers, the contract and the stored format do not change. Rejected for portability: the AWS Encryption SDK (AWS KMS keyrings only) and the AWS Database Encryption SDK (wraps the DynamoDB client, bypassing the records contract). Sources: OWASP Cryptographic Storage and Key Management cheat sheets; AWS Well-Architected SEC08-BP01; Tink key management and Python setup.

Rows: 22.12a (197.1) and 22.12b (197.2), single PRs from origin/main, before 22.13 (TASK-47).
<!-- SECTION:DESCRIPTION:END -->

# Rescue-Net Desktop, Android, and iOS App Design

Updated: 2026-06-11

## Main Decision

Build one application core and package it into three targets:

- Desktop
- Android
- iOS

This should not become three separate applications with three separate codebases. Rescue-Net needs consistent offline behavior, sync, permissions, and conflict resolution across all field devices. A shared app core reduces bugs and makes maintenance realistic.

## Recommended Architecture

Use a shared offline-first web app core, then package it for each platform.

Suggested layers:

- `app-core`: domain models, API client, sync queue, conflict resolver, role rules, validation
- `ui-web`: responsive Rescue-Net screens following the mock-up layouts
- `storage`: local database adapter for browser/mobile/desktop
- `sync`: pull, push, retry, conflict detection, manual review
- `platform`: desktop/mobile wrappers, notifications, camera/file access, secure storage

Packaging direction:

- Desktop: lightweight desktop shell or installable PWA first
- Android: native wrapper around the same app core
- iOS: native wrapper around the same app core

## Offline-First Design

Each client should work even when network is unstable.

Local data should include:

- active disaster profile
- assigned posko/organization scope
- local draft records
- pending sync queue
- last pulled server snapshot
- conflict queue
- role/session state
- evidence upload metadata

Minimum local-first modules for field app:

- Posko daily status
- Logistic needs
- Stock movement
- Aid receiving
- Volunteer assignment
- Kitchen production
- Medical supply use, without exposing sensitive patient detail to unauthorized roles
- Shelter occupancy and needs
- Search & Found limited forms
- Evidence capture queue

## Sync And Conflict Model

Every mutable object should eventually have:

- `id`
- `disaster_event_id`
- `version`
- `updated_at`
- `updated_by_user_id`
- `deleted_at`
- `sync_status`
- `last_server_version`

Conflict policies:

- `server_wins` for official verification and command decisions
- `client_retry` for transient network/API failures
- `merge_if_non_conflicting` for independent field updates
- `manual_review` for stock, medical, missing person, evidence, and distribution conflicts

Sync events should be triggered by:

- app open
- app becomes visible
- device reconnects
- manual Sync Now
- before logout
- after critical local submission

Avoid continuous aggressive polling.

## UI Layout Direction

Desktop:

- Keep sidebar navigation and dense dashboard panels.
- Use War Room as the command center pattern.
- Show map/status/critical queues in the first viewport.
- Use tables and compact cards for operators.

Android / iOS:

- Use a compact home module launcher.
- Use bottom navigation for the most common field flows.
- Keep forms short and task-based.
- Save drafts automatically.
- Make Sync status always visible.
- Keep evidence capture one tap away.

Visual identity:

- Do not change colors in the current completion phase.
- First align layout, spacing, hierarchy, responsive behavior, and module flow with the mock-ups.
- Reserve red/orange/yellow for severity and alerts.

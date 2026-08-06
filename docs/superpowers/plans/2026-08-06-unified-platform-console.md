# Unified Platform Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Merge the new dark Agent console, the existing infrastructure console, and Prompt Center into one PlatformLayout while preserving existing URLs and business functionality.

**Architecture:** Use `route.meta.platform` to select one shared `PlatformLayout` for all management pages. Keep business pages on `DefaultLayout`. Mark legacy pages with `platformLegacy` so they render inside a light compatibility surface within the shared dark shell. Redirect the old `/infra` overview to `/platform`, while preserving all detailed `/infra/*` and `/prompt-center/*` URLs.

## Plan

- [x] Add shared PlatformLayout navigation for overview, runtime, Prompt, model, logs, health, and configuration areas.
- [x] Move legacy infrastructure routes to PlatformLayout without rewriting their page logic.
- [x] Move all Prompt Center routes to PlatformLayout without changing Prompt API calls or version workflow.
- [x] Preserve old URLs and redirect `/infra` to `/platform`.
- [ ] Add real Session, Agent, Team, Skill, Tool, and MCP pages as follow-up platform slices.
- [ ] Connect the unified overview and Prompt displays to real platform APIs.

## Validation

- Legacy `/infra/*` pages render inside the same shell.
- Prompt list/detail/editor/test/compare/release/metrics routes render inside the same shell.
- `/infra` redirects to `/platform`.
- Business routes such as `/operation` remain on the existing business layout.
- Existing Prompt Center data flow remains unchanged.

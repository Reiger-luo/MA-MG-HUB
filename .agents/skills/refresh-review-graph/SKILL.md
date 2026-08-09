---
name: refresh-review-graph
description: Refresh and verify the MA-MG-HUB code-review graph after user-approved code changes are pushed or deployed. Use whenever Codex is asked to push, deploy, publish, ship, or take approved website changes online, and after review fixes are pushed. Do not treat invocation as push authorization, and do not run for review-only work or data/docs-only changes.
---

# Refresh Review Graph

Close the review loop after an authorized push by rebuilding the local CRG graph, rechecking impact, and reporting evidence.

## Workflow

1. Before the authorized push, capture the current upstream commit:

   ```bash
   prePushHead=$(git rev-parse '@{upstream}')
   ```

2. Complete the requested validation, commit, push, and deployment steps. Never infer push or deployment permission from this skill.
3. Only after the push succeeds, run:

   ```bash
   bash .agents/skills/refresh-review-graph/scripts/refreshGraphAfterPush.sh --base "$prePushHead"
   ```

4. The script performs a full build at the pushed commit, then analyzes the pushed range. If the MCP server is available, rerun `detect_changes_tool` and `get_review_context_tool` against the same base to confirm affected flows and test gaps.
5. Report the pushed SHA, Graph status, changed nodes or skip reason, impact summary, test gaps, and the post-push GitHub workflow status when available.

## Safety and completion rules

- Require explicit user authorization for the push or deployment itself.
- Require the local `HEAD` to equal its upstream commit before refreshing.
- Stop if graph-covered paths contain uncommitted changes; do not mix unpushed source into the post-push graph.
- Treat `scripts/**`, `assets/*.js`, `worker/**`, and `tests/**` as graph-covered paths. For data, HTML, CSS, or documentation-only pushes, report that CRG was not applicable instead of claiming a refresh.
- Do not start a watcher, daemon, or Git hook.
- A Graph refresh failure does not undo a successful push. Report the failure and recovery command precisely; do not claim the deployment failed unless its own verification failed.
- Do not call the task complete after a graph-covered push until the local refresh has succeeded or the failure has been explicitly disclosed.

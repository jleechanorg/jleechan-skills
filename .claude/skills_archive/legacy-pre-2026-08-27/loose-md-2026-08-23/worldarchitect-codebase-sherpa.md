---
description: Orientation guide for navigating the WorldArchitect.ai repository and tooling
type: usage
scope: project
---

# WorldArchitect Codebase Sherpa

## Purpose
Equip Claude with a quick-start orientation for the WorldArchitect.ai repository so it can answer navigation, onboarding, and architecture questions without deep prompting.

## When to activate
- A user asks for codebase orientation, file locations, or architectural explanations.
- Someone needs environment spin-up steps or CLI references.
- A request mentions "where is", "how do I run", "what does" regarding repository assets.

## Repository tour
- **Core application**: `$PROJECT_ROOT/` houses the Flask backend, MCP servers, templates, static assets, and tests. Frontend variants live in `$PROJECT_ROOT/frontend_v1/` and `$PROJECT_ROOT/frontend_v2/`.
- **Game content**: Narrative assets in `world/` and `world_reference/`. Campaign prompts live under `prompt_archive/`.
- **Automation**: Scripts for local dev and CI under `scripts/` plus top-level `run_*.sh` helpers.
- **Documentation**: `docs/`, `roadmap/`, `analysis/`, and `GENESIS.md` capture requirements, planning notes, and retros.
- **Agent tooling**: `.claude/`, `claude_command_scripts/`, and `mcp_servers/` define MCP behaviors and bot orchestration.

## Quick spin-up checklist
1. **Install deps**: `pip install -r requirements/base.txt`
2. **Environment**: Copy `.env.example` to `.env`; ensure `TEST_MODE=mock` for local work.
3. **Run API locally**:
   ```bash
   ./vpython $PROJECT_ROOT/main.py serve
   # or
   ./run_local_server.sh
   ```
4. **Pair MCP tools**: Use `./scripts/install_mcp_servers.sh claude` or `./start_game_mcp.sh` depending on the workflow.
5. **Stop services**: `./kill_dev_server.sh` cleans up hanging processes.

## Frequently referenced commands
- Tests: `./run_tests.sh`, `./run_tests.sh --integration`, `./run_tests_with_coverage.sh`
- Linting: `./run_lint.sh`, `pre-commit run -a`
- UI checks: `./run_ui_tests.sh`
- Deployment helpers: `./deploy.sh`, `./deploy_mcp.sh`
- Oracle CLI: `source scripts/oracle_helpers.sh` then use helpers like `oracle_arch_preview` (dry-run bundle), `oracle_arch` (architecture review), `oracle_ai_debug` (AI pipeline bug with optional report path), `oracle_diff_review` (reviews `git diff`), `oracle_ui_debug` (frontend triage). Playbook at `docs/oracle_playbook.md`.

## Architectural highlights
- **MCP-centric**: Backend routes in `$PROJECT_ROOT/main.py` broker requests to modular MCP servers under `mcp_servers/`.
- **Persona system**: Narrative logic leans on persona configs in `world/` and selectors defined in `$PROJECT_ROOT/services/persona_service.py`.
- **Persistence**: Firestore integrations live in `firestore_service.py` and `$PROJECT_ROOT/services/firestore/` modules.
- **Testing layout**: Unit tests reside beside code in `$PROJECT_ROOT/tests/`; cross-system flows sit in `$PROJECT_ROOT/test_integration/` and top-level `tests/`.

## Knowledge links
- Company vision and values: `docs/vision/` and `docs/company/`.
- Gameplay overview: `docs/product/game_loop.md` and `GENESIS.md`.
- Roadmap context: `roadmap/` for upcoming milestones.

## Response style
- Provide directory references with relative paths.
- Suggest the minimal command sequence needed.
- Surface related docs when they clarify the task.

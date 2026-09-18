# Prior art: git-branch-based cross-machine session mirroring (SSH + tmux)

Research for the `linux-mirror`/`mac-mirror` skills (`.claude/skills/linux-mirror/SKILL.md`, `.claude/skills/mac-mirror/SKILL.md`), which push the current branch, SSH to a remote host (LAN → Tailscale-IP → Slack-gateway fallback tiers), check out the branch remotely, and attach/create a tmux session.

## 1. VS Code Remote Tunnels

Official docs: https://code.visualstudio.com/docs/remote/tunnels

Different model entirely: instead of moving *state* between two independent filesystems, Remote Tunnels keeps one canonical copy of the workspace running on a single remote machine and lets various *clients* attach to it via a `code tunnel` CLI process + the VS Code Server, authenticated end-to-end over an SSH-secured tunnel (AES-256-CTR). The remote is only reachable while the tunnel process (or VS Code itself) stays running there — there is no "hand off and resume on a different physical copy" concept; it's remote-editing-in-place, not mirroring. This confirms the mirror tool's design choice (git push + remote checkout) is solving a different problem than Microsoft's tool: true multi-machine handoff where either machine can be the working copy, not a thin client to one fixed server.

## 2. tmux-resurrect / tmux-continuum

Official repos: https://github.com/tmux-plugins/tmux-resurrect, https://github.com/tmux-plugins/tmux-continuum

Both plugins persist/restore tmux state **across restarts of the same machine** (resurrect: manual save/restore of panes/windows/programs; continuum: autosave every 15 min + autorestore on tmux start). Neither plugin, per their own READMEs, syncs a session *between different machines* — restoration reads from a local save file. No cross-machine transfer mechanism exists in either project. This validates that the mirror skill's tmux usage (`tmux new-session`/`has-session` on the remote, driven fresh from git state rather than a saved tmux payload) is the right layering: git carries the durable state across machines, tmux is only a local-to-each-host attach point, and there's no existing plugin that would have done the cross-machine part instead.

## 3. mosh (mobile shell)

Official site/README: https://mosh.org/, https://github.com/mobile-shell/mosh, USENIX paper: https://www.usenix.org/system/files/conference/atc12/atc12-final32.pdf

Mosh's State Synchronization Protocol (SSP) runs over UDP; the **client** may roam (change IP/port) and the server updates its send-target to whatever source IP sent the latest authenticated, highest-sequence-numbered heartbeat/packet — but explicitly, per the original paper, **the server is not permitted to roam**. That asymmetry is the relevant finding: Mosh solves "my client device moves across networks while the remote server stays put," which is a different problem from the mirror tool's "the workload itself relocates to a different physical server." Mosh's roaming has no bearing on the Tailscale-IP fallback design (that's about reaching a stationary remote host from an off-LAN client, which is exactly the problem Tailscale — not Mosh — is built for). No prior-art gap here; Mosh is simply orthogonal.

## 4. git worktree

Official docs: https://git-scm.com/docs/git-worktree

`git worktree` is explicitly a **single repository with shared metadata** feature: a linked worktree shares the same `.git` directory as the main worktree and cannot exist independently on another machine. The docs describe no cross-machine or cross-clone synchronization pattern — for that you still need `git clone` + `fetch`/`push` per machine, which is precisely what the mirror skill does (`git clone`-if-absent, then `fetch`/`checkout`/`pull --ff-only`). There is no documented git-native "worktree across machines" pattern to have used instead; `push` + remote `clone`/`checkout` is the standard mechanism for this, confirming the tool's approach rather than suggesting a superior alternative.

## 5. Tailscale (regular SSH over the tailnet, plus its own Tailscale SSH feature and exit nodes)

Official docs: https://tailscale.com/kb/1193/tailscale-ssh, https://tailscale.com/docs/features/exit-nodes

Tailscale ships an actual feature called "Tailscale SSH" (`tailscale up --ssh` + tailnet ACL policy, authenticating over WireGuard node identity with no separate SSH key exchange) — that is a *different* thing from what the mirror tool's Tier 2 uses: a normal OpenSSH connection (standard `ssh -i <key> user@<tailscale-ip>`) that merely routes over the tailnet's private network, using an ordinary SSH keypair exactly as it would over the LAN. Calling Tier 2 "Tailscale SSH" would misname it as the special feature; it's SSH over Tailscale, nothing more. Exit nodes are a further distinct, unrelated feature (routing *all* traffic through a peer device, e.g. for compliance) and are not part of a "follow me" access pattern — Tailscale's own docs flag this as a common confusion (adding an exit node only permits SSH *to* it, not routing through it). No official "follow me across networks to resume a session" feature/pattern is documented; the tool's Tier 1→Tier 2 (LAN alias → explicit Tailscale-IP + `-i` SSH) is a reasonable, docs-consistent use of the primitives Tailscale actually ships (note also confirmed in the skill's own text: a bare `~/.ssh/config` alias does **not** auto-fail-over to a Tailscale IP — Tailscale doesn't rewrite existing SSH config, so the skill's explicit two-tier logic is necessary, not redundant).

## 6. `echo | tr` trailing-newline corruption — is this a known gotcha?

No single primary source documents this *exact* `tr -c` composition, but it's a direct, well-documented consequence of two independently-cited facts:
- `echo`'s trailing-newline/flag behavior is explicitly **implementation-defined** under POSIX/IEEE Std 1003.1-2001, not guaranteed identical across shells (cited in historical GNU `echo` man page discussion: https://chuck.stanford.edu/planetccrma/man/man1/echo.1.html).
- GitLab's own engineering practice independently reached the same fix for the same reason: "POSIX: 'echo' flags are undefined... use printf which always works" (https://gitlab.com/gitlab-org/gitlab/-/merge_requests/100013).

`tr -c 'allowed-chars' '-'` translates *any* character outside the allowed set — including `echo`'s trailing `\n` — into the replacement character, so a trailing newline silently becomes a literal `-` at the end of the string. `printf '%s' "$string"` emits no implicit newline and has fully POSIX-defined behavior, which is the fix already applied in the skill (see the `printf ... | tr -c 'a-zA-Z0-9_-' '-'` line and its inline comment in both SKILL.md files). This is a known, citable class of bug (echo-vs-printf portability), even though no source names this specific `tr` composition verbatim — worth keeping the code comment since it's non-obvious to a future reader.

## Bottom line

No primary source describes an existing tool that does exactly what this mirror skill does (git-branch-based, bidirectional, tmux-resuming session handoff across two independent physical machines, with a LAN→Tailscale→messaging-gateway fallback ladder). The closest adjacent tools solve different problems: VS Code Tunnels keeps one canonical remote copy instead of mirroring; tmux-resurrect/continuum persist state only within one machine's restarts; mosh solves client-roams-not-server; git worktree is single-filesystem only. The design is a reasonable, docs-consistent composition of existing primitives (git push/clone/fetch, tmux session management, SSH over Tailscale, printf-over-echo) rather than a reinvention of something that already exists off-the-shelf.

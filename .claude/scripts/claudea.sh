# Source this file from your shell startup file.
# Native safe mode preserves authentication and admin policy while disabling
# user/project customizations. History remains in the normal Claude profile.
unalias claudea claudeac 2>/dev/null || true
claudea() {
  command claude --safe-mode --dangerously-skip-permissions \
    --model claude-fable-5-2 "$@"
}
claudeac() { claudea --continue "$@"; }

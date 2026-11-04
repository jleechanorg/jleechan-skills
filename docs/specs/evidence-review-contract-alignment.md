# Evidence review contract alignment

- **Outcome:** Evidence reviewers audit claims and provenance through current
  `/er`, `/es` and repository owners, without becoming source writers or a
  duplicate full-code review lane.
- **Non-goals:** No application behavior, provider calls, new schema/framework,
  reviewer quorum, merge authority, installer behavior or unrelated review-access
  policy changes. No local installation or PR publication by this source task.
- **Acceptance:** The agent is a read-only dispatcher; both overlay forms resolve
  through instructions/catalog; aggregate or sibling hashes cover all substantive
  and claim-map artifacts; missing coverage/mismatch fails integrity. Canonical
  producer formats map explicitly without losing raw proof. Evidence-only review
  inspects diff-derived claims/source/media without demanding unrelated full-code
  packets. Coordinator asks explicitly prohibit mutations and posting. All actual
  acceptance failures and service/auth/provider/BQ/visual gates remain binding.
- **User story:** An evidence producer can submit its complete frozen canonical
  bundle once; an independent reviewer returns scoped findings without rewriting
  the bundle, changing branches, or requiring invented sidecars/stdout output.
- **Proof plan:** Review the focused diff and independent behavioral scenarios:
  complete aggregate versus siblings; uncovered raw file; mismatched digest;
  flat versus directory overlay; structured command receipt versus duplicate
  stdout; missing live/visual proof; observed forbidden state; evidence-only versus
  separately requested code approval; coordinator mutation attempt. Run existing
  installer/portability checks. No new test files.
- **Mock exemption:** Policy Markdown has no rendered UI or runtime/provider path.
  Static scenario review and existing installer checks establish bounded policy
  consistency only, not sustained live-agent compliance.
- **Risk:** Incorrect scoping could weaken proof or overburden review. Preserve
  owner-required raw artifacts, independence, strict withholding, user authority
  and all acceptance gates; isolate this change from other open review-policy PRs.

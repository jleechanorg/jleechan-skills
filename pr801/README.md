# PR 801 dashboard evidence

Source head: `9ffb51e0c1e5e82808c9a00781ef8f00e4ac5bf5`; comparison base: `1d02eaedf1ae5bb074cd650c151cd9231a7166e3`.

## Layers and limits

`good`, `small`, and `missing` are synthetic exporter fixtures. They support controlled numeric and missing-data checks; they are not live integration proof. Both versions serve identical inputs using real local HTTP and Chrome. Final synthetic comparisons are the 1360px desktop and 390x1400px mobile images. Original 390x900 captures are retained but crop lower tiles.

`real` replays 219 unchanged PR records from a previously collected public jleechanorg/jleechan-skills snapshot. See real-projection.json for original hash, timestamps, selection and removed cross-repository summaries. The snapshot is stale and visibly labeled; no fresh collector execution or current production metrics are claimed. The real desktop viewport is 1440x900 and mobile 375x812. Mobile viewport screenshots crop below the first new tile; the additional `after-real-375-tiles.png` element capture shows all four tiles at the same viewport width.

## Results

Capture result JSON records timestamps, HTTP response hashes, rendered labels/values/coverage, console errors and document width. All requested asset responses are HTTP200 and match bytes on disk. No console/page errors or horizontal overflow were observed. Raw before/after app source is pinned to the indicated commits. The real input replay proves display against existing exported records; synthetic exporter fixtures plus committed regression tests cover Python export behavior. This does not establish that a fresh full collector pipeline currently runs successfully.

Synthetic good expected values: one-shot 2 of5 (40%), steers median/p90 1/5, duration60min/2.0h, reached6of7. Each metric includes unknown1. Synthetic n2 and missing scenarios suppress estimates as Not enough data. Cached real input displays duration38min/27.6h (n135,unknown6), reached141of158 (unknown61), and suppresses estimates for only two observed human-steering records.

Capture drivers are public portable derivatives: only the machine-specific Playwright module path was changed to PLAYWRIGHT_MODULE or installed playwright. fixture-generator.py uses REPO_ROOT and ARTIFACT_ROOT environment variables instead of private machine paths. Raw result driver hashes refer to original drivers; manifest records both original and public hashes. The original private drivers remain retained. Run node capture.cjs, node capture-mobile.cjs and node capture-real.cjs with Playwright and Chrome installed. Fixture regeneration also needs the repository Python test dependencies at the head commit.

These captures are author evidence; independent review is recorded separately in the PR.

const test = require("node:test");
const assert = require("node:assert/strict");
const S = require("./stats.js");

const DAY = 86400e3;
const T0 = Date.parse("2026-11-01T00:00:00Z");
const iso = (ms) => new Date(ms).toISOString().replace(".000Z", "Z");
const range = { startMs: T0, endMs: T0 + 14 * DAY };

function pr(n, o = {}) {
  const created = o.createdMs ?? T0 + DAY;
  const merged = o.state === "OPEN" || o.state === "CLOSED" ? null : (o.mergedMs ?? created + (o.elapsed ?? 3600) * 1000);
  return {
    id: `acme/${o.repo || "app"}#${n}`, repo: `acme/${o.repo || "app"}`, number: n, title: o.title || `PR ${n}`,
    state: o.state || "MERGED", created: iso(created), merged: merged ? iso(merged) : null,
    closed: o.state === "CLOSED" ? iso(created + 1000) : merged ? iso(merged) : null,
    elapsed_s: o.elapsed ?? 3600, usage: o.tokens === undefined ? null : { total: o.tokens },
    cost: o.cost === undefined ? null : { known_subtotal_usd: o.cost, full_scenario_usd: o.full ?? null },
    human: o.human === undefined ? null : { verified_messages: o.human }, active_s: o.active ?? null, branch: o.branch || null,
  };
}

test("nearest-rank quantiles match the collector's method", () => {
  const v = Array.from({ length: 10 }, (_, i) => (i + 1) * 10); // 10..100
  assert.equal(S.quantile(v, 0.5), 50);
  assert.equal(S.quantile(v, 0.9), 90);
  assert.equal(S.quantile(v, 0.99), 100);
  assert.equal(S.quantile([7], 0.99), 7);
  assert.equal(S.quantile([], 0.5), null);
  // an even count takes the lower middle value, never an interpolated one
  assert.equal(S.quantile([1, 2, 3, 4], 0.5), 2);
});

test("summaries exclude missing values instead of counting them as zero", () => {
  const s = S.summarize([100, null, undefined, NaN, 300]);
  assert.deepEqual([s.n, s.mean, s.p50, s.sum], [2, 200, 100, 400]);
  assert.deepEqual(S.summarize([null]), { n: 0, mean: null, p50: null, p90: null, p99: null, sum: null });
});

test("an unsorted input does not change the percentiles", () => {
  assert.equal(S.summarize([90, 10, 50, 30, 70]).p50, 50);
});

test("aggregate reports coverage counts beside each figure", () => {
  const rows = [pr(1, { elapsed: 100, tokens: 500, cost: 1.5 }), pr(2, { elapsed: 300 }), pr(3, { state: "OPEN", elapsed: 9999, human: 4 })];
  const a = S.aggregate(rows, range);
  assert.deepEqual([a.total, a.merged, a.open], [3, 2, 1]);
  assert.deepEqual([a.elapsed.n, a.elapsed.p50, a.elapsed.mean], [2, 100, 200]); // the open PR's running time is not a merge time
  assert.deepEqual([a.usageN, a.usage.sum, a.costKnownN, a.costFullN], [1, 500, 1, 0]);
  assert.deepEqual([a.humanN, a.human.sum, a.activeN, a.active.p50], [1, 4, 0, null]);
});

test("filters narrow rows by repository, state, attribution, search and period", () => {
  const rows = [
    pr(1, { repo: "app", tokens: 5, title: "Fix login" }), pr(2, { repo: "web", human: 2, branch: "feat/cart" }),
    pr(3, { repo: "web", state: "OPEN" }), pr(4, { createdMs: T0 - 30 * DAY, mergedMs: T0 - 20 * DAY }),
    pr(5, { createdMs: T0 - 30 * DAY, state: "OPEN" }),
  ];
  const ids = (f) => S.filterPrs(rows, { ...range, ...f }).map((p) => p.number);
  assert.deepEqual(ids({}), [1, 2, 3, 5]); // #4 ended before the period; #5 is still open so it overlaps
  assert.deepEqual(ids({ repos: { "acme/web": true } }), [2, 3]);
  assert.deepEqual(ids({ state: "OPEN" }), [3, 5]);
  assert.deepEqual(ids({ attribution: "usage" }), [1]);
  assert.deepEqual(ids({ attribution: "human" }), [2]);
  assert.deepEqual(ids({ attribution: "none" }), [3, 5]);
  assert.deepEqual(ids({ search: "LOGIN" }), [1]);
  assert.deepEqual(ids({ search: "feat/cart" }), [2]);
});

test("merged-in-period uses the merge time with a half-open window", () => {
  const atStart = pr(1, { createdMs: T0 - DAY, mergedMs: T0 });
  const atEnd = pr(2, { createdMs: T0 + DAY, mergedMs: range.endMs });
  assert.equal(S.mergedIn(atStart, range.startMs, range.endMs), true);
  assert.equal(S.mergedIn(atEnd, range.startMs, range.endMs), false);
});

test("daily merges keep empty days and split by repository", () => {
  const rows = [pr(1, { repo: "app", mergedMs: T0 + 3600e3 }), pr(2, { repo: "web", mergedMs: T0 + 7200e3 }), pr(3, { repo: "app", mergedMs: T0 + 2 * DAY + 5 })];
  const days = S.dailyMerges(rows, { startMs: T0, endMs: T0 + 3 * DAY }, ["acme/app", "acme/web"], "UTC");
  assert.deepEqual(days.map((d) => [d.day, d.counts, d.total]), [["2026-11-01", [1, 1], 2], ["2026-11-02", [0, 0], 0], ["2026-11-03", [1, 0], 1]]);
});

test("the display time zone moves a merge to the correct local day", () => {
  const rows = [pr(1, { mergedMs: Date.parse("2026-11-02T03:00:00Z") })];
  const f = { startMs: T0, endMs: T0 + 3 * DAY };
  const day = (tz) => S.dailyMerges(rows, f, ["acme/app"], tz).find((d) => d.total).day;
  assert.equal(day("UTC"), "2026-11-02");
  assert.equal(day("America/Los_Angeles"), "2026-11-01");
});

test("histogram buckets are half-open and skip missing values", () => {
  const bins = S.histogram([10, 3599, 3600, null, 8 * 86400], S.ELAPSED_EDGES, S.ELAPSED_LABELS);
  assert.deepEqual(bins.map((b) => b.n), [2, 1, 0, 0, 0, 0, 1]);
});

test("durations and counts format without inventing precision", () => {
  assert.equal(S.formatDuration(null), null);
  assert.equal(S.formatDuration(45), "45 s");
  assert.equal(S.formatDuration(7191), "2.0 h");
  assert.equal(S.formatDuration(3 * 86400), "3.0 d");
  assert.equal(S.compact(null), null);
  assert.equal(S.compact(16655524), "16.7M");
});

test("CSV escapes quotes, newlines and spreadsheet formulas, and leaves unknowns blank", () => {
  const out = S.csv([{ a: '=HYPERLINK("x")', b: null }, { a: "line\nbreak, comma", b: 0 }], [
    { header: "a", value: (r) => r.a }, { header: "b", value: (r) => r.b },
  ]);
  assert.equal(out, 'a,b\n"\'=HYPERLINK(""x"")",\n"line\nbreak, comma",0\n');
});

test("count axes label every gridline with a distinct whole number", () => {
  for (const peak of [0, 1, 2, 3, 4, 5, 7, 12, 37, 180, 950]) {
    const ticks = S.countTicks(peak);
    assert.equal(ticks[0], 0);
    assert.ok(ticks[ticks.length - 1] >= peak, `top tick covers ${peak}`);
    assert.ok(ticks.every(Number.isInteger), `integer ticks for ${peak}: ${ticks}`);
    assert.equal(new Set(ticks).size, ticks.length, `distinct ticks for ${peak}: ${ticks}`);
  }
  assert.deepEqual(S.countTicks(1), [0, 1]);
  assert.deepEqual(S.countTicks(3), [0, 1, 2, 3, 4, 5]);
});

test("only web links are linkable", () => {
  assert.equal(S.webUrl("https://github.com/acme/app/pull/7"), "https://github.com/acme/app/pull/7");
  for (const bad of ["javascript:alert(1)", " JavaScript:alert(1)", "data:text/html,x", "", null, 7]) {
    assert.equal(S.webUrl(bad), null, String(bad));
  }
});

test("csv keeps negative numbers numeric and still guards formula text", () => {
  const cols = [{ header: "v", value: (r) => r.v }];
  assert.equal(S.csv([{ v: -5 }, { v: "-cmd" }, { v: "=SUM(A1)" }], cols), "v\n-5\n'-cmd\n'=SUM(A1)\n");
});

test("a comparison window keeps every filter except the period", () => {
  const small = { ...pr(1), size: { additions: 10, deletions: 5, files: 1 } };
  const large = { ...pr(2), size: { additions: 900, deletions: 400, files: 30 } };
  const stillOpen = { ...pr(3, { state: "OPEN" }), size: { additions: 3, deletions: 0, files: 1 } };
  const rows = [small, large, stillOpen];
  const base = { ...range, repos: { "acme/app": true }, state: "all", attribution: "all", size: "xs", search: "" };
  const win = [iso(T0), iso(T0 + 7 * DAY)];
  const f = S.windowFilter(base, win, null);
  assert.deepEqual([f.startMs, f.endMs], [T0, T0 + 7 * DAY]);
  assert.deepEqual(S.filterPrs(rows, f).map((p) => p.number), [1, 3]);
  assert.equal(S.aggregate(S.filterPrs(rows, f), f).merged, 1); // the 1,300-line merge is outside "Under 50 lines"
  const openOnly = S.windowFilter({ ...base, size: "all", state: "OPEN" }, win, null);
  assert.equal(S.aggregate(S.filterPrs(rows, openOnly), openOnly).merged, 0);
  assert.deepEqual(S.windowFilter(base, win, "acme/web").repos, { "acme/web": true });
});

test("a snapshot without a status is shown as unknown, not fresh", () => {
  assert.deepEqual(S.statusChip("FRESH"), { tone: "good", label: "Fresh", stale: false });
  assert.deepEqual(S.statusChip("STALE"), { tone: "warn", label: "Stale", stale: true });
  assert.deepEqual(S.statusChip("FAILED"), { tone: "warn", label: "Status: FAILED", stale: true });
  assert.deepEqual(S.statusChip(null), { tone: "warn", label: "Status unknown", stale: false });
  assert.deepEqual(S.statusChip(undefined), { tone: "warn", label: "Status unknown", stale: false });
});

test("episode counts are unknown, not zero, when no episode was observed", () => {
  const none = S.aggregate([pr(1)], range);
  assert.equal(none.episodeTotal, 0);
  assert.deepEqual(S.episodeCounts(none), { good: null, bad: null, mixed: null, unknown: null });
  const some = S.aggregate([{ ...pr(1), human: { verified_messages: 1, episodes: { good: 2, bad: 0, mixed: 0, unknown: 1 } } }], range);
  assert.deepEqual(S.episodeCounts(some), { good: 2, bad: 0, mixed: 0, unknown: 1 });
});

test("daily merges include the last calendar day when the window ends just after midnight", () => {
  const f = { startMs: Date.parse("2026-11-01T00:30:00Z"), endMs: Date.parse("2026-11-02T00:30:00Z") };
  const late = { ...pr(1), merged: "2026-11-02T00:10:00Z" };
  for (const tz of ["UTC", "America/Los_Angeles"]) {
    const days = S.dailyMerges([late], f, ["acme/app"], tz);
    assert.equal(days.reduce((a, d) => a + d.total, 0), S.aggregate([late], f).merged, tz);
  }
  assert.deepEqual(S.dailyMerges([late], f, ["acme/app"], "UTC").map((d) => d.day), ["2026-11-01", "2026-11-02"]);
});

test("CSV quotes a carriage return", () => {
  assert.equal(S.csv([{ v: "first\rsecond" }], [{ header: "v", value: (r) => r.v }]), 'v\n"first\rsecond"\n');
});

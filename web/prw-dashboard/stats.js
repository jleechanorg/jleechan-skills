/* Pure data logic for the PRW dashboard. No DOM. Loaded by the page and by tests. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.PRWStats = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /** Nearest-rank (type 1) quantile, matching DuckDB quantile_disc. Null when empty. */
  function quantile(sortedValues, p) {
    var n = sortedValues.length;
    if (!n) return null;
    var rank = Math.ceil(p * n);
    return sortedValues[Math.min(n, Math.max(1, rank)) - 1];
  }

  /** Mean, p50, p90, p99 over finite numbers only. Missing values are excluded, never zero. */
  function summarize(values) {
    var valid = values.filter(function (v) { return typeof v === "number" && isFinite(v); });
    valid.sort(function (a, b) { return a - b; });
    var n = valid.length;
    if (!n) return { n: 0, mean: null, p50: null, p90: null, p99: null, sum: null };
    var sum = valid.reduce(function (a, b) { return a + b; }, 0);
    return {
      n: n, sum: sum, mean: sum / n,
      p50: quantile(valid, 0.5), p90: quantile(valid, 0.9), p99: quantile(valid, 0.99),
    };
  }

  function ms(iso) { return iso ? Date.parse(iso) : null; }

  /** End of a PR's life inside the snapshot: merge, close, or still open (null). */
  function endMs(pr) { return ms(pr.merged) || ms(pr.closed); }

  /** A PR is in range when its lifetime overlaps [start, end). Open PRs run to the cutoff. */
  function inRange(pr, startMs, endRangeMs) {
    var created = ms(pr.created);
    if (created === null || created >= endRangeMs) return false;
    var end = endMs(pr);
    return end === null || end >= startMs;
  }

  function mergedIn(pr, startMs, endRangeMs) {
    var merged = ms(pr.merged);
    return pr.state === "MERGED" && merged !== null && merged >= startMs && merged < endRangeMs;
  }

  function matches(pr, f) {
    if (f.repos && !f.repos[pr.repo]) return false;
    if (f.state && f.state !== "all" && pr.state !== f.state) return false;
    if (f.attribution === "usage" && !pr.usage) return false;
    if (f.attribution === "human" && !(pr.human && pr.human.verified_messages)) return false;
    if (f.attribution === "none" && (pr.usage || (pr.human && pr.human.verified_messages))) return false;
    if (f.size && f.size !== "all" && sizeBand(pr) !== f.size) return false;
    if (f.search) {
      var hay = (pr.title || "") + " " + pr.id + " " + (pr.branch || "");
      if (hay.toLowerCase().indexOf(f.search.toLowerCase()) === -1) return false;
    }
    return inRange(pr, f.startMs, f.endMs);
  }

  /** Size band by lines changed. Null when size was not observed. */
  function sizeBand(pr) {
    if (!pr.size) return null;
    var lines = pr.size.additions + pr.size.deletions;
    return lines < 50 ? "xs" : lines < 200 ? "s" : lines < 1000 ? "m" : "l";
  }

  function filterPrs(prs, f) { return prs.filter(function (pr) { return matches(pr, f); }); }

  /** The current filter moved to a comparison window: only the period (and optionally the repository) changes. */
  function windowFilter(base, win, repo) {
    var f = {};
    for (var k in base) f[k] = base[k];
    f.startMs = Date.parse(win[0]); f.endMs = Date.parse(win[1]);
    if (repo) { f.repos = {}; f.repos[repo] = true; }
    return f;
  }

  /** Header chip for the snapshot status. A missing status is unknown, never fresh. */
  function statusChip(status) {
    if (status === "FRESH") return { tone: "good", label: "Fresh", stale: false };
    if (!status) return { tone: "warn", label: "Status unknown", stale: false };
    return { tone: "warn", label: status === "STALE" ? "Stale" : "Status: " + status, stale: true };
  }

  /** Episode counts for export: null (unknown) when no episode was observed in the selection. */
  function episodeCounts(agg) {
    var out = {};
    ["good", "bad", "mixed", "unknown"].forEach(function (k) { out[k] = agg.episodeTotal ? agg.episodes[k] : null; });
    return out;
  }

  /** Aggregate the filtered rows. Every figure carries its own observed n. */
  function aggregate(rows, f) {
    var merged = rows.filter(function (pr) { return mergedIn(pr, f.startMs, f.endMs); });
    var withUsage = rows.filter(function (pr) { return pr.usage && typeof pr.usage.total === "number"; });
    var withCost = rows.filter(function (pr) { return pr.cost && typeof pr.cost.known_subtotal_usd === "number"; });
    var fullyPriced = rows.filter(function (pr) { return pr.cost && typeof pr.cost.full_scenario_usd === "number"; });
    var withHuman = rows.filter(function (pr) { return pr.human && pr.human.verified_messages > 0; });
    var withActive = rows.filter(function (pr) { return typeof pr.active_s === "number"; });
    var withIdle = rows.filter(function (pr) { return typeof pr.eligible_idle_s === "number"; });
    var episodes = { good: 0, bad: 0, mixed: 0, unknown: 0 }, episodePrN = 0;
    rows.forEach(function (pr) {
      var e = pr.human && pr.human.episodes, any = false;
      if (!e) return;
      Object.keys(episodes).forEach(function (k) { if (typeof e[k] === "number" && e[k] > 0) { episodes[k] += e[k]; any = true; } });
      if (any) episodePrN += 1;
    });
    var handoffs = {};
    rows.forEach(function (pr) {
      for (var k in pr.handoffs || {}) (handoffs[k] = handoffs[k] || []).push(pr.handoffs[k]);
    });
    for (var key in handoffs) handoffs[key] = summarize(handoffs[key]);
    return {
      idle: summarize(withIdle.map(function (pr) { return pr.eligible_idle_s; })),
      idleN: withIdle.length,
      episodes: episodes,
      episodeTotal: episodes.good + episodes.bad + episodes.mixed + episodes.unknown,
      episodePrN: episodePrN,
      handoffs: handoffs,
      handoffPrN: rows.filter(function (pr) { return pr.handoffs; }).length,
      total: rows.length,
      merged: merged.length,
      open: rows.filter(function (pr) { return pr.state === "OPEN"; }).length,
      closed: rows.filter(function (pr) { return pr.state === "CLOSED"; }).length,
      elapsed: summarize(merged.map(function (pr) { return pr.elapsed_s; })),
      usage: summarize(withUsage.map(function (pr) { return pr.usage.total; })),
      usageN: withUsage.length,
      costKnown: summarize(withCost.map(function (pr) { return pr.cost.known_subtotal_usd; })),
      costKnownN: withCost.length,
      costFull: summarize(fullyPriced.map(function (pr) { return pr.cost.full_scenario_usd; })),
      costFullN: fullyPriced.length,
      human: summarize(withHuman.map(function (pr) { return pr.human.verified_messages; })),
      humanN: withHuman.length,
      active: summarize(withActive.map(function (pr) { return pr.active_s; })),
      activeN: withActive.length,
    };
  }

  var MIN_TILE_N = 3;

  /**
   * Headline "one-shot" figures over the given rows. Reached final = a final-stage entry (or label) was
   * recorded; started = any stage evidence. Steers = verified follow-up human messages; an unknown steer
   * count or an unusable start-to-final interval is excluded and counted as unknown, never zero.
   * Below MIN_TILE_N observations a tile reports ok:false and no figure.
   */
  function oneShot(rows) {
    var started = rows.filter(function (pr) { return pr.flow; });
    var reached = started.filter(function (pr) { return pr.flow.reached_final; });
    var steerRows = reached.filter(function (pr) { return pr.human && typeof pr.human.followup === "number"; });
    var steers = steerRows.map(function (pr) { return pr.human.followup; });
    var minutes = [];
    reached.forEach(function (pr) {
      var a = ms(pr.flow.started_at), b = ms(pr.flow.final_at);
      if (a !== null && b !== null && b >= a) minutes.push((b - a) / 60e3);
    });
    var s = summarize(steers), m = summarize(minutes);
    var ones = steers.filter(function (v) { return v === 0; }).length;
    var steerOk = s.n >= MIN_TILE_N, minOk = m.n >= MIN_TILE_N;
    return {
      rate: { ok: steerOk, n: s.n, ones: ones, pct: steerOk ? (100 * ones) / s.n : null, unknown: reached.length - s.n },
      steers: { ok: steerOk, n: s.n, p50: steerOk ? s.p50 : null, p90: steerOk ? s.p90 : null, unknown: reached.length - s.n },
      minutes: { ok: minOk, n: m.n, p50: minOk ? m.p50 : null, p90: minOk ? m.p90 : null, unknown: reached.length - m.n },
      counts: { ok: started.length >= MIN_TILE_N, started: started.length, reached: reached.length, unknown: rows.length - started.length },
    };
  }

  /** Calendar-day key in UTC or a fixed-offset zone label resolved by the caller. */
  function dayKey(msValue, timeZone) {
    var parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: timeZone, year: "numeric", month: "2-digit", day: "2-digit",
    }).format(new Date(msValue));
    return parts;
  }

  /** Merges per day per repository. Days with no merges are present with zeros. */
  function dailyMerges(rows, f, repos, timeZone) {
    var days = [], index = {};
    function addDay(t) {
      var key = dayKey(t, timeZone);
      if (!(key in index)) { index[key] = days.length; days.push({ day: key, counts: repos.map(function () { return 0; }), total: 0 }); }
    }
    for (var t = f.startMs; t < f.endMs; t += 3600e3) addDay(t);
    // Hourly steps can stop short of the window's last calendar day when it holds under an hour of the window.
    if (f.endMs > f.startMs) addDay(f.endMs - 1);
    rows.forEach(function (pr) {
      if (!mergedIn(pr, f.startMs, f.endMs)) return;
      var slot = index[dayKey(ms(pr.merged), timeZone)], r = repos.indexOf(pr.repo);
      if (slot === undefined || r === -1) return;
      days[slot].counts[r] += 1; days[slot].total += 1;
    });
    return days;
  }

  function histogram(values, edges, labels) {
    var bins = labels.map(function (label) { return { label: label, n: 0 }; });
    values.forEach(function (v) {
      if (typeof v !== "number" || !isFinite(v)) return;
      var i = 0;
      while (i < edges.length && v >= edges[i]) i += 1;
      bins[i].n += 1;
    });
    return bins;
  }

  var HOUR = 3600, DAY = 86400;
  var ELAPSED_EDGES = [HOUR, 4 * HOUR, 12 * HOUR, DAY, 3 * DAY, 7 * DAY];
  var ELAPSED_LABELS = ["< 1 h", "1–4 h", "4–12 h", "12–24 h", "1–3 d", "3–7 d", "> 7 d"];
  var TOKEN_EDGES = [1e6, 5e6, 2e7, 1e8];
  var TOKEN_LABELS = ["< 1M", "1–5M", "5–20M", "20–100M", "> 100M"];

  function formatDuration(seconds) {
    if (seconds === null || seconds === undefined) return null;
    if (seconds < 90) return Math.round(seconds) + " s";
    if (seconds < 90 * 60) return Math.round(seconds / 60) + " min";
    if (seconds < 48 * HOUR) return (seconds / HOUR).toFixed(1) + " h";
    return (seconds / DAY).toFixed(1) + " d";
  }

  function compact(n) {
    if (n === null || n === undefined) return null;
    var abs = Math.abs(n);
    if (abs >= 1e9) return (n / 1e9).toFixed(abs >= 1e10 ? 1 : 2) + "B";
    if (abs >= 1e6) return (n / 1e6).toFixed(abs >= 1e7 ? 1 : 2) + "M";
    if (abs >= 1e4) return (n / 1e3).toFixed(1) + "K";
    return Math.round(n).toLocaleString("en-US");
  }

  /** Whole-number gridline values from 0 up to a rounded top (1, 2 or 5 x 10^k) covering the peak count. */
  function countTicks(peak) {
    var top = 1;
    if (peak > 0) {
      var mag = Math.pow(10, Math.floor(Math.log10(peak))), n = peak / mag;
      top = (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * mag;
    }
    var steps = top <= 5 ? top : top % 4 === 0 ? 4 : 5;
    var ticks = [];
    for (var i = 0; i <= steps; i++) ticks.push((top * i) / steps);
    return ticks;
  }

  /** The URL when it is an http(s) link, else null; snapshot values never become script links. */
  function webUrl(value) {
    return typeof value === "string" && /^https?:\/\//i.test(value) ? value : null;
  }

  function csv(rows, columns) {
    function cell(v) {
      if (v === null || v === undefined) return "";
      var s = String(v);
      if (typeof v !== "number" && /^[=+\-@\t\r]/.test(s)) s = "'" + s; // spreadsheet formula guard
      return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    }
    return [columns.map(function (c) { return cell(c.header); }).join(",")]
      .concat(rows.map(function (r) { return columns.map(function (c) { return cell(c.value(r)); }).join(","); }))
      .join("\n") + "\n";
  }

  return {
    quantile: quantile, summarize: summarize, filterPrs: filterPrs, aggregate: aggregate,
    windowFilter: windowFilter, oneShot: oneShot, MIN_TILE_N: MIN_TILE_N, statusChip: statusChip, episodeCounts: episodeCounts,
    mergedIn: mergedIn, inRange: inRange, sizeBand: sizeBand, dailyMerges: dailyMerges, histogram: histogram,
    ELAPSED_EDGES: ELAPSED_EDGES, ELAPSED_LABELS: ELAPSED_LABELS,
    TOKEN_EDGES: TOKEN_EDGES, TOKEN_LABELS: TOKEN_LABELS,
    formatDuration: formatDuration, compact: compact, csv: csv, countTicks: countTicks, webUrl: webUrl,
  };
});

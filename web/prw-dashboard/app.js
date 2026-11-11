/* PRW dashboard page. Reads dashboard.json and renders everything from one filtered slice. */
(function () {
  "use strict";
  var S = window.PRWStats;
  // ?data=<file>.json selects another snapshot in the same directory (used for fixtures). No paths or URLs.
  var requested = new URLSearchParams(location.search).get("data");
  var DATA_URL = requested && /^[A-Za-z0-9._-]+\.json$/.test(requested) ? requested : "dashboard.json";
  var PAGE = 50;
  var SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];
  var SVGNS = "http://www.w3.org/2000/svg";
  var $ = function (id) { return document.getElementById(id); };

  var data = null;
  var state = { range: "14d", repos: {}, st: "all", attr: "all", size: "all", search: "", tz: "UTC", sort: "end", dir: -1, page: 0 };

  // ---------- small DOM helpers (text is always set as text, never as HTML) ----------
  function h(tag, attrs, kids) {
    var el = document.createElement(tag);
    apply(el, attrs); append(el, kids);
    return el;
  }
  function s(tag, attrs, kids) {
    var el = document.createElementNS(SVGNS, tag);
    for (var k in attrs || {}) if (attrs[k] !== null && attrs[k] !== undefined) el.setAttribute(k, attrs[k]);
    append(el, kids);
    return el;
  }
  function apply(el, attrs) {
    for (var k in attrs || {}) {
      var v = attrs[k];
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k.slice(0, 2) === "on") el.addEventListener(k.slice(2), v);
      else if (k === "style") el.style.cssText = v;
      else el.setAttribute(k, v === true ? "" : v);
    }
  }
  function append(el, kids) {
    if (kids === null || kids === undefined) return;
    (Array.isArray(kids) ? kids : [kids]).forEach(function (kid) {
      if (kid === null || kid === undefined || kid === false) return;
      el.appendChild(typeof kid === "object" ? kid : document.createTextNode(String(kid)));
    });
  }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }
  function shortRepo(repo) { return repo ? repo.split("/").pop() : ""; }
  function repoColor(repo) { var i = data.repositories.indexOf(repo); return i >= 0 && i < SERIES.length ? SERIES[i] : "var(--text-muted)"; }
  function swatch(color) { return h("span", { class: "swatch", style: "background:" + color }); }
  function na(text) { return h("span", { class: "na", text: text || "Unavailable" }); }
  function pct(n, d) { return d ? Math.round((100 * n) / d) + "%" : "–"; }
  function usd(v) { return v === null || v === undefined ? null : "$" + (v >= 1000 ? S.compact(v) : v.toFixed(2)); }

  function fmtTime(iso, withTime) {
    if (!iso) return null;
    var opts = { timeZone: state.tz, year: "numeric", month: "short", day: "numeric" };
    if (withTime !== false) { opts.hour = "2-digit"; opts.minute = "2-digit"; opts.hour12 = false; }
    return new Intl.DateTimeFormat("en-US", opts).format(new Date(iso)) + (withTime !== false ? (state.tz === "UTC" ? " UTC" : " PT") : "");
  }

  // ---------- tooltip ----------
  var tip = null;
  function showTip(evt, nodes) {
    tip = tip || $("tip");
    clear(tip); append(tip, nodes); tip.hidden = false;
    var x = evt.clientX, y = evt.clientY;
    if (x === undefined || (x === 0 && y === 0)) { var r = evt.target.getBoundingClientRect(); x = r.left + r.width / 2; y = r.top; }
    var w = tip.offsetWidth, hh = tip.offsetHeight;
    tip.style.left = Math.max(6, Math.min(window.innerWidth - w - 6, x + 12)) + "px";
    tip.style.top = Math.max(6, y - hh - 10) + "px";
  }
  function hideTip() { if (tip) tip.hidden = true; }
  function hover(el, build) {
    el.addEventListener("mousemove", function (e) { showTip(e, build()); });
    el.addEventListener("mouseleave", hideTip);
    el.addEventListener("focus", function (e) { showTip(e, build()); });
    el.addEventListener("blur", hideTip);
  }

  // ---------- filters ----------
  function bounds() {
    var end = Date.parse(data.window_end || data.data_through), start = Date.parse(data.window_start);
    var w1 = data.windows && data.windows.w1, w2 = data.windows && data.windows.w2;
    if (state.range === "w1" && w1) return { startMs: Date.parse(w1[0]), endMs: Date.parse(w1[1]) };
    if (state.range === "w2" && w2) return { startMs: Date.parse(w2[0]), endMs: Date.parse(w2[1]) };
    return { startMs: start, endMs: end };
  }
  function currentFilter() {
    var b = bounds();
    return { startMs: b.startMs, endMs: b.endMs, repos: state.repos, state: state.st, attribution: state.attr, size: state.size, search: state.search.trim() };
  }

  function buildFilters() {
    var box = $("f-repos");
    data.repositories.forEach(function (repo) {
      state.repos[repo] = true;
      var input = h("input", { type: "checkbox", checked: true, onchange: function () { state.repos[repo] = input.checked; state.page = 0; render(); } });
      input.dataset.repo = repo;
      box.appendChild(h("label", { class: "repo" }, [input, swatch(repoColor(repo)), shortRepo(repo)]));
    });
    function bind(id, key, evt) {
      $(id).addEventListener(evt || "change", function () { state[key] = $(id).value; state.page = 0; render(); });
    }
    bind("f-size", "size"); bind("f-range", "range"); bind("f-state", "st"); bind("f-attr", "attr"); bind("f-tz", "tz"); bind("f-search", "search", "input");
    $("f-reset").addEventListener("click", function () {
      state.range = "14d"; state.st = "all"; state.attr = "all"; state.size = "all"; state.search = ""; state.page = 0;
      $("f-size").value = "all"; $("f-range").value = "14d"; $("f-state").value = "all"; $("f-attr").value = "all"; $("f-search").value = "";
      Array.prototype.forEach.call(box.querySelectorAll("input"), function (i) { i.checked = true; state.repos[i.dataset.repo] = true; });
      render();
    });
    var sized = data.prs.some(function (pr) { return pr.size; });
    var sizeSel = $("f-size");
    if (!sized) sizeSel.title = "Additions, deletions and changed files were not collected in this snapshot.";
    else {
      clear(sizeSel); sizeSel.disabled = false;
      [["all", "All sizes"], ["xs", "Under 50 lines"], ["s", "50–199 lines"], ["m", "200–999 lines"], ["l", "1,000+ lines"]].forEach(function (o) {
        sizeSel.appendChild(h("option", { value: o[0], text: o[1] }));
      });
    }
  }

  // ---------- header ----------
  function renderHeader() {
    var chip = S.statusChip(data.status), stale = chip.stale;
    var ribbon = clear($("ribbon"));
    append(ribbon, [
      h("span", { class: "chip " + chip.tone }, [h("i"), chip.label]),
      h("span", null, ["Data through ", h("b", { text: fmtTime(data.data_through) || "unknown" })]),
      h("span", null, ["Generated ", h("b", { text: fmtTime(data.generated_at) || "unknown" })]),
    ]);
    var sources = data.sources || {};
    var names = Object.keys(sources), complete = names.filter(function (n) { return sources[n] && sources[n].status === "COMPLETE"; }).length;
    ribbon.appendChild(h("span", { class: "chip " + (names.length && complete === names.length ? "good" : "warn") },
      [h("i"), "Sources " + complete + "/" + names.length + " complete"]));
    $("scope-line").textContent = data.prs.length.toLocaleString("en-US") + " pull requests in this snapshot across " + data.repositories.length +
      " repositories, " + fmtTime(data.window_start, false) + " to " + fmtTime(data.window_end || data.data_through, false) + ".";
    var banner = $("banner");
    if (data.fixture) {
      banner.hidden = false;
      banner.textContent = "Synthetic fixture: " + data.fixture + " These are not real measurements.";
    } else if (stale) {
      banner.hidden = false;
      banner.textContent = "This snapshot is marked " + data.status + ". Figures reflect data through " + (fmtTime(data.data_through) || "an unknown time") + ", not the present.";
    } else banner.hidden = true;
  }

  // ---------- cards ----------
  function tile(o) {
    var el = h("article", { class: "card tile" }, [
      h("div", { class: "label", text: o.label }),
      h("div", { class: "value" + (o.value === null ? " na" : ""), text: o.value === null ? (o.naText || "Unavailable") : o.value }),
      h("div", { class: "detail" }, o.detail || ""),
    ]);
    if (o.covN !== undefined) {
      var ratio = o.covD ? o.covN / o.covD : 0;
      el.appendChild(h("div", { class: "cov" }, [
        o.covLabel + ": " + o.covN.toLocaleString("en-US") + " of " + o.covD.toLocaleString("en-US") + " (" + pct(o.covN, o.covD) + ")",
        h("div", { class: "meter" + (ratio ? "" : " empty"), role: "img", "aria-label": pct(o.covN, o.covD) + " coverage" },
          h("span", { style: "width:" + Math.max(ratio ? 2 : 0, ratio * 100) + "%" })),
      ]));
    }
    return el;
  }
  function dist(sum, fmt) {
    return "mean " + fmt(sum.mean) + " · p90 " + fmt(sum.p90) + " · p99 " + fmt(sum.p99);
  }
  function renderOneShot(rows) {
    var t = S.oneShot(rows), box = clear($("oneshot"));
    var min = S.MIN_TILE_N, na = "Not enough data";
    function sample(x, noun) {
      return "n = " + x.n.toLocaleString("en-US") + " " + noun + " · unknown: " + x.unknown.toLocaleString("en-US");
    }
    function minutes(v) { return v < 90 ? Math.round(v) + " min" : S.formatDuration(v * 60); }
    append(box, [
      tile({ label: "One-shot rate (0 human steers)", value: t.rate.ok ? t.rate.ones + " of " + t.rate.n + " · " + t.rate.pct.toFixed(0) + "%" : null, naText: na,
        detail: sample(t.rate, "reached final") + (t.rate.ok ? "" : " (needs " + min + "+)") }),
      tile({ label: "Human steers per PR, median / p90", value: t.steers.ok ? t.steers.p50 + " / " + t.steers.p90 : null, naText: na,
        detail: sample(t.steers, "reached final") + (t.steers.ok ? "" : " (needs " + min + "+)") }),
      tile({ label: "Start to final stage, median / p90", value: t.minutes.ok ? minutes(t.minutes.p50) + " / " + minutes(t.minutes.p90) : null, naText: na,
        detail: sample(t.minutes, "reached final") + (t.minutes.ok ? "" : " (needs " + min + "+)") }),
      tile({ label: "Reached final stage vs started", value: t.counts.ok ? t.counts.reached.toLocaleString("en-US") + " of " + t.counts.started.toLocaleString("en-US") : null, naText: na,
        detail: "n = " + t.counts.started.toLocaleString("en-US") + " started" + (t.counts.ok ? "" : " (needs " + min + "+)") }),
    ]);
    box.style.marginBottom = "12px";
  }
  function renderCards(rows, agg) {
    var box = clear($("cards")), N = agg.total;
    append(box, [
      tile({ label: "Merged pull requests", value: agg.merged.toLocaleString("en-US"),
        detail: agg.open.toLocaleString("en-US") + " open · " + agg.closed.toLocaleString("en-US") + " closed unmerged",
        covLabel: "Merged in period", covN: agg.merged, covD: N }),
      tile({ label: "Open-to-merge time, median", value: agg.elapsed.n ? S.formatDuration(agg.elapsed.p50) : null, naText: "No merges in selection",
        detail: agg.elapsed.n ? dist(agg.elapsed, S.formatDuration) : "",
        covLabel: "Merged PRs measured", covN: agg.elapsed.n, covD: agg.merged }),
      tile({ label: "Tokens attributed to PRs", value: agg.usageN ? S.compact(agg.usage.sum) : null,
        detail: agg.usageN ? "per PR: median " + S.compact(agg.usage.p50) + " · p90 " + S.compact(agg.usage.p90) + " · p99 " + S.compact(agg.usage.p99) : "No usage is tied to these PRs",
        covLabel: rows.some(function (r) { return r.usage && r.usage.basis !== "source_branch"; }) ? "PRs with usage tied to them" : "PRs with usage (branch match, low confidence)", covN: agg.usageN, covD: N }),
      (function () {
        var complete = agg.costKnownN > 0 && agg.costFullN === agg.costKnownN;
        return tile({ label: complete ? "List-price estimate" : "List-price estimate, known part",
          value: !agg.costKnownN ? null : complete ? usd(agg.costFull.sum) : "≥ " + usd(agg.costKnown.sum),
          detail: !agg.costKnownN ? "No priced usage for these PRs" : complete
            ? "per PR: median " + usd(agg.costFull.p50) + " · p90 " + usd(agg.costFull.p90) + " · p99 " + usd(agg.costFull.p99) + ". Not invoiced spend."
            : "Lower bound: some token types have no published rate. Not invoiced spend.",
          covLabel: "PRs fully priced", covN: agg.costFullN, covD: N });
      })(),
      tile({ label: "Verified human steering messages", value: agg.humanN ? agg.human.sum.toLocaleString("en-US") : null,
        detail: agg.humanN ? "per PR: median " + agg.human.p50 + " · p90 " + agg.human.p90 + " · p99 " + agg.human.p99 : "No verified steering is tied to these PRs",
        covLabel: "PRs with verified steering", covN: agg.humanN, covD: N }),
      tile({ label: "Observed active time", value: agg.activeN ? S.formatDuration(agg.active.p50) : null, naText: "Not measured",
        detail: agg.activeN ? dist(agg.active, S.formatDuration) : "No timed operation telemetry for these PRs",
        covLabel: "PRs with active-time telemetry", covN: agg.activeN, covD: N }),
      tile({ label: "Eligible unattended time, median", value: agg.idleN ? S.formatDuration(agg.idle.p50) : null, naText: "Not measured",
        detail: agg.idleN ? dist(agg.idle, S.formatDuration) : "No evidenced ready-and-authorized waiting intervals",
        covLabel: "PRs with evidenced intervals", covN: agg.idleN, covD: N }),
      tile({ label: "Steering episodes", value: agg.episodeTotal ? agg.episodeTotal.toLocaleString("en-US") : null, naText: "None rated or recorded",
        detail: agg.episodeTotal ? agg.episodes.good + " good · " + agg.episodes.bad + " bad · " + agg.episodes.mixed + " mixed · " + agg.episodes.unknown + " unknown" : "No steering episodes are tied to these PRs",
        covLabel: "PRs with episodes", covN: agg.episodePrN, covD: N }),
    ]);
  }

  // ---------- chart plumbing ----------
  function chartHead(title, sub) {
    return h("div", { class: "head" }, h("div", null, [h("h2", { text: title }), h("p", { class: "sub", text: sub })]));
  }
  function tableView(headers, rows) {
    var t = h("table", { class: "mini" }, [
      h("thead", null, h("tr", null, headers.map(function (x, i) { return h("th", { class: i ? "num" : "", text: x }); }))),
      h("tbody", null, rows.map(function (r) { return h("tr", null, r.map(function (c, i) { return h("td", { class: i ? "num" : "", text: c }); })); })),
    ]);
    return h("details", { class: "tv" }, [h("summary", { text: "Show as table" }), h("div", { class: "table-wrap", style: "display:block" }, t)]);
  }
  /** Column bar with a 4px rounded data end and a square baseline end. */
  function column(x, yTop, w, hgt, roundTop, fill) {
    var r = roundTop ? Math.min(4, hgt, w / 2) : 0, yB = yTop + hgt;
    var d = "M" + x + "," + yB + "V" + (yTop + r) + "Q" + x + "," + yTop + " " + (x + r) + "," + yTop +
      "H" + (x + w - r) + "Q" + (x + w) + "," + yTop + " " + (x + w) + "," + (yTop + r) + "V" + yB + "Z";
    return s("path", { d: d, fill: fill });
  }
  function yAxis(svg, ticks, x0, x1, y0, y1) {
    var top = ticks[ticks.length - 1];
    ticks.forEach(function (v, i) {
      var y = y1 - ((y1 - y0) * v) / top;
      svg.appendChild(s("line", { x1: x0, x2: x1, y1: y, y2: y, class: i ? "gridline" : "baseline" }));
      svg.appendChild(s("text", { x: x0 - 6, y: y + 3.5, "text-anchor": "end" }, String(v)));
    });
  }

  // ---------- chart: merges per day ----------
  function renderDaily(rows, f) {
    var el = clear($("c-daily"));
    var repos = data.repositories.filter(function (r) { return state.repos[r]; });
    var days = S.dailyMerges(rows, f, repos, state.tz);
    var total = days.reduce(function (a, d) { return a + d.total; }, 0);
    el.appendChild(chartHead("Merges per day", total.toLocaleString("en-US") + " merged in the selection, by merge day (" + (state.tz === "UTC" ? "UTC" : "Pacific") + ")"));
    if (!total) { el.appendChild(h("div", { class: "empty-note", text: "No merges match these filters." })); return; }
    var W = 520, H = 220, x0 = 36, x1 = W - 6, y0 = 10, y1 = H - 26;
    var ticks = S.countTicks(Math.max.apply(null, days.map(function (d) { return d.total; }))), max = ticks[ticks.length - 1];
    var svg = s("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Stacked columns of merged pull requests per day by repository" });
    yAxis(svg, ticks, x0, x1, y0, y1);
    var band = (x1 - x0) / days.length, bw = Math.min(24, band - 4);
    var labelEvery = Math.ceil(days.length / 8);
    days.forEach(function (d, i) {
      var x = x0 + band * i + (band - bw) / 2, y = y1;
      var last = -1;
      d.counts.forEach(function (c, r) { if (c) last = r; });
      d.counts.forEach(function (c, r) {
        if (!c) return;
        var hh = ((y1 - y0) * c) / max, gap = y < y1 ? 2 : 0;
        if (hh - gap > 0.5) svg.appendChild(column(x, y - hh, bw, hh - gap, r === last, repoColor(repos[r])));
        y -= hh;
      });
      if (i % labelEvery === 0) svg.appendChild(s("text", { x: x + bw / 2, y: H - 8, "text-anchor": "middle" }, d.day.slice(5)));
      var hit = s("rect", { class: "hit", x: x0 + band * i, y: y0, width: band, height: y1 - y0, tabindex: 0,
        "aria-label": d.day + ": " + d.total + " merged" });
      hover(hit, function () {
        return [h("b", { text: d.day + " · " + d.total + " merged" })].concat(repos.map(function (r, k) {
          return h("div", { class: "k" }, [swatch(repoColor(r)), shortRepo(r) + ": " + d.counts[k]]);
        }));
      });
      svg.appendChild(hit);
    });
    el.appendChild(svg);
    if (repos.length > 1) el.appendChild(h("div", { class: "legend" }, repos.map(function (r) { return h("span", null, [swatch(repoColor(r)), shortRepo(r)]); })));
    el.appendChild(tableView(["Day"].concat(repos.map(shortRepo), ["Total"]),
      days.map(function (d) { return [d.day].concat(d.counts, [d.total]); })));
  }

  // ---------- chart: single-series histogram ----------
  function renderHistogram(id, title, sub, bins, unitLabel, emptyText) {
    var el = clear($(id));
    el.appendChild(chartHead(title, sub));
    var total = bins.reduce(function (a, b) { return a + b.n; }, 0);
    if (!total) { el.appendChild(h("div", { class: "empty-note", text: emptyText })); return; }
    var W = 520, H = 220, x0 = 36, x1 = W - 6, y0 = 18, y1 = H - 26;
    var ticks = S.countTicks(Math.max.apply(null, bins.map(function (b) { return b.n; }))), max = ticks[ticks.length - 1];
    var svg = s("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": title });
    yAxis(svg, ticks, x0, x1, y0, y1);
    var band = (x1 - x0) / bins.length, bw = Math.min(24, band - 8);
    bins.forEach(function (b, i) {
      var x = x0 + band * i + (band - bw) / 2, hh = ((y1 - y0) * b.n) / max;
      if (b.n) svg.appendChild(column(x, y1 - hh, bw, hh, true, SERIES[0]));
      svg.appendChild(s("text", { x: x + bw / 2, y: H - 8, "text-anchor": "middle" }, b.label));
      if (b.n) svg.appendChild(s("text", { class: "val", x: x + bw / 2, y: y1 - hh - 5, "text-anchor": "middle" }, String(b.n)));
      var hit = s("rect", { class: "hit", x: x0 + band * i, y: y0, width: band, height: y1 - y0, tabindex: 0,
        "aria-label": b.label + ": " + b.n + " " + unitLabel });
      hover(hit, function () { return [h("b", { text: b.label }), h("div", { text: b.n + " " + unitLabel + " (" + pct(b.n, total) + ")" })]; });
      svg.appendChild(hit);
    });
    el.appendChild(svg);
    el.appendChild(tableView(["Bucket", "PRs", "Share"], bins.map(function (b) { return [b.label, b.n, pct(b.n, total)]; })));
  }

  // ---------- week over week (a table is the right form: few values, exact comparison) ----------
  function renderWow() {
    var el = clear($("c-wow"));
    var w1 = data.windows && data.windows.w1, w2 = data.windows && data.windows.w2;
    el.appendChild(chartHead("Preceding 7 days vs recent 7 days", "Merged PRs and open-to-merge time. Follows every filter except the period."));
    if (!w1 || !w2) { el.appendChild(h("div", { class: "empty-note", text: "Comparison windows are not in this snapshot." })); return; }
    var base = currentFilter();
    function slice(win, repo) {
      var f = S.windowFilter(base, win, repo);
      return S.aggregate(S.filterPrs(data.prs, f), f);
    }
    var names = data.repositories.filter(function (r) { return state.repos[r]; });
    var lines = names.map(function (r) { return { label: shortRepo(r), color: repoColor(r), a: slice(w1, r), b: slice(w2, r) }; });
    if (names.length > 1) lines.push({ label: "Selected repositories", color: null, a: slice(w1, null), b: slice(w2, null) });
    function pair(a, b, fmt) {
      if (a === null && b === null) return na("No merges");
      return (a === null ? "–" : fmt(a)) + " → " + (b === null ? "–" : fmt(b));
    }
    var num = function (v) { return v.toLocaleString("en-US"); };
    var t = h("table", { class: "mini", style: "margin-top:10px" }, [
      h("thead", null, h("tr", null, ["Repository", "Merged", "Median", "p90", "p99"].map(function (x, i) { return h("th", { class: i ? "num" : "", text: x }); }))),
      h("tbody", null, lines.map(function (l) {
        return h("tr", null, [
          h("td", null, h("span", { class: "pr-id", style: "font-size:13px;color:var(--text-primary)" }, [l.color ? swatch(l.color) : null, l.label])),
          h("td", { class: "num" }, pair(l.a.merged, l.b.merged, num)),
          h("td", { class: "num" }, pair(l.a.elapsed.p50, l.b.elapsed.p50, S.formatDuration)),
          h("td", { class: "num" }, pair(l.a.elapsed.p90, l.b.elapsed.p90, S.formatDuration)),
          h("td", { class: "num" }, pair(l.a.elapsed.p99, l.b.elapsed.p99, S.formatDuration)),
        ]);
      })),
    ]);
    el.appendChild(h("div", { class: "table-wrap", style: "display:block" }, t));
    el.appendChild(h("p", { class: "sub", text: "Preceding: " + fmtTime(w1[0], false) + " to " + fmtTime(w1[1], false) + ". Recent: " + fmtTime(w2[0], false) + " to " + fmtTime(w2[1], false) +
      ". A change between weeks is a description, not evidence of cause." }));
  }

  // ---------- horizontal ranked bars (one series, one colour) ----------
  function renderBars(id, title, sub, items, fmt, emptyText, dims) {
    var el = clear($(id));
    el.appendChild(chartHead(title, sub));
    var usable = items.filter(function (i) { return typeof i.value === "number"; });
    if (!usable.length) { el.appendChild(h("div", { class: "empty-note", text: emptyText })); return; }
    dims = dims || {};
    var W = dims.W || 520, rowH = 28, labelW = dims.labelW || 170, valueW = dims.valueW || 150, x0 = labelW, x1 = W - valueW;
    var max = Math.max.apply(null, usable.map(function (i) { return i.value; })) || 1;
    var svg = s("svg", { viewBox: "0 0 " + W + " " + (items.length * rowH + 4), role: "img", "aria-label": title });
    svg.appendChild(s("line", { x1: x0, x2: x0, y1: 0, y2: items.length * rowH, class: "baseline" }));
    items.forEach(function (it, i) {
      var y = i * rowH + 8, known = typeof it.value === "number";
      svg.appendChild(s("text", { class: "val", x: x0 - 8, y: y + 10, "text-anchor": "end" }, it.label));
      if (known) {
        var w = Math.max(2, ((x1 - x0) * it.value) / max), r = Math.min(4, w);
        svg.appendChild(s("path", { fill: SERIES[0], d: "M" + x0 + "," + y + "H" + (x0 + w - r) + "Q" + (x0 + w) + "," + y + " " + (x0 + w) + "," + (y + r) +
          "V" + (y + 12 - r) + "Q" + (x0 + w) + "," + (y + 12) + " " + (x0 + w - r) + "," + (y + 12) + "H" + x0 + "Z" }));
        svg.appendChild(s("text", { class: "val", x: x0 + w + 6, y: y + 10 }, fmt(it.value) + (it.note ? "  " + it.note : "")));
      } else svg.appendChild(s("text", { x: x0 + 6, y: y + 10 }, "Unavailable"));
      var hit = s("rect", { class: "hit", x: 0, y: i * rowH, width: W, height: rowH, tabindex: 0, "aria-label": it.label + ": " + (known ? fmt(it.value) : "unavailable") });
      hover(hit, function () { return [h("b", { text: it.label }), h("div", { text: known ? fmt(it.value) : "Unavailable" }), it.tip ? h("div", { text: it.tip }) : null]; });
      svg.appendChild(hit);
    });
    el.appendChild(svg);
  }

  function renderHandoffs(agg) {
    var items = (data.handoff_transitions || []).map(function (t) {
      var sm = agg.handoffs[t.key];
      return { label: t.label.replace(" to ", " → "), value: sm ? sm.p50 : null,
        note: sm ? "· mean " + S.formatDuration(sm.mean) + " · p90 " + S.formatDuration(sm.p90) + " · p99 " + S.formatDuration(sm.p99) + " · n=" + sm.n : "",
        tip: sm ? sm.n + " PRs with both ends recorded" : "No PR in the selection has both ends recorded" };
    });
    renderBars("c-handoffs", "Handoff delay, median", agg.handoffPrN + " of " + agg.total + " PRs have a recorded transition. Delay between steps is not by itself avoidable waiting.",
      items, S.formatDuration, "No handoff timestamps are recorded for PRs in this selection.", { labelW: 250, valueW: 250, W: 760 });
  }
  function renderEpisodes(agg) {
    var e = agg.episodes, has = agg.episodeTotal > 0;
    renderBars("c-episodes", "Steering episodes by reviewed quality", agg.episodePrN + " of " + agg.total + " PRs have episodes. Unknown means not yet rated, not neutral.",
      [["Good", e.good], ["Bad", e.bad], ["Mixed", e.mixed], ["Unknown", e.unknown]].map(function (x) { return { label: x[0], value: has ? x[1] : null }; }),
      function (v) { return v.toLocaleString("en-US"); }, "No steering episodes are tied to PRs in this selection.");
  }

  function renderSnapshotLevel() {
    var stages = (data.stage_dwell || []).map(function (st) {
      var p50 = typeof st.p50_h === "number" ? st.p50_h : null;
      return { label: String(st.stage || "").replace(/^stage:/, ""), value: p50,
        note: "· p90 " + (typeof st.p90_h === "number" ? S.formatDuration(st.p90_h * 3600) : "–") + " · n=" + st.n,
        tip: st.n + " of " + st.total_n + " merged PRs have this stage observed" };
    });
    renderBars("c-stage", "Stage dwell, median", "Recent-7-day merged cohort. Only PRs where the stage label was observed.",
      stages, function (v) { return S.formatDuration(v * 3600); }, "Stage dwell was not collected.");

    var hc = data.human_coverage || {};
    var classes = [
      ["assigned_verified_messages", "Verified, tied to one PR"],
      ["branch_only_messages", "Branch match only"],
      ["multi_pr_unassigned_messages", "Unassigned: several PRs"],
      ["ambiguous_branch_messages", "Ambiguous branch"],
      ["global_scope_unassigned_messages", "Unassigned: no PR scope"],
      ["no_single_pr_unassigned_messages", "Unassigned: no single PR"],
    ].map(function (c) { return { label: c[1], value: typeof hc[c[0]] === "number" ? hc[c[0]] : null }; });
    renderBars("c-human", "Human-input candidates by attribution", "Message counts. Only the first row is counted as steering on a PR.",
      classes, function (v) { return v.toLocaleString("en-US"); }, "Human-input attribution was not collected.");

    var box = clear($("snapshot-facts"));
    var facts = h("div", { class: "facts" });
    var u = data.usage_totals || {}, tb = u.tokens_by_bucket || {}, qc = data.query_coverage || {};
    function fact(title, rows, note) {
      return h("div", null, [h("h3", { text: title }),
        h("table", { class: "mini" }, h("tbody", null, rows.map(function (r) { return h("tr", null, [h("td", { text: r[0] }), h("td", { class: "num" }, r[1] === null ? na() : r[1])]); }))),
        note ? h("p", { class: "sub", text: note }) : null]);
    }
    var c = function (v) { return typeof v === "number" ? S.compact(v) : null; };
    facts.appendChild(fact("All observed usage, 14 days", [
      ["Requests", c(u.event_count)], ["Uncached input tokens", c(tb.input_uncached)], ["Cache-read tokens", c(tb.cache_read)],
      ["Output tokens", c(tb.output)], ["Requests with a full price", c(u.priced_event_count)],
      ["Known list-price total", u.known_cost_usd !== undefined && u.known_cost_usd !== null ? usd(Number(u.known_cost_usd)) : null],
    ], (u.label || "Public list-price equivalent") + ". " + (u.scope || "")));
    facts.appendChild(fact("How much usage is tied to a PR", [
      ["Usage requests in snapshot", c(qc.canonical_event_n)], ["Naming a PR directly", c(qc.validated_direct_attribution_event_n)],
      ["Not bound to any PR", c(qc.unbound_event_n)],
    ], "Unbound usage is real work that cannot yet be assigned to a pull request. It is not spread across PRs."));
    var hand = (data.handoffs || []).map(function (x) {
      return [x.name, x.status === "UNKNOWN" || x.observed_n === 0 ? null : (x.observed_n + " observed")];
    });
    if (hand.length) facts.appendChild(fact("Handoff delays", hand, "Unavailable rows have no handoff receipts collected yet."));
    box.appendChild(facts);
  }

  // ---------- coverage panel ----------
  function renderGaps(rows) {
    var el = clear($("gaps"));
    el.appendChild(h("h2", { text: "What this data can and cannot tell you" }));
    el.appendChild(h("p", { class: "sub", text: "Coverage for the current selection. A measure with no coverage is shown as unavailable everywhere on this page, never as zero." }));
    var N = rows.length;
    var counts = {
      usage: rows.filter(function (r) { return r.usage; }).length,
      cost: rows.filter(function (r) { return r.cost && typeof r.cost.full_scenario_usd === "number"; }).length,
      human: rows.filter(function (r) { return r.human && r.human.verified_messages; }).length,
      active: rows.filter(function (r) { return typeof r.active_s === "number"; }).length,
      idle: rows.filter(function (r) { return typeof r.eligible_idle_s === "number"; }).length,
      size: rows.filter(function (r) { return r.size; }).length,
      handoffs: rows.filter(function (r) { return r.handoffs; }).length,
      episodes: rows.filter(function (r) { return r.human && r.human.episodes && ((r.human.episodes.good || 0) + (r.human.episodes.bad || 0) + (r.human.episodes.mixed || 0)) > 0; }).length,
    };
    var list = h("div", { class: "gap-list" });
    (data.gaps || []).forEach(function (g) {
      var n = g.key in counts ? counts[g.key] : g.observed_n, d = g.key in counts ? N : g.total_n, ratio = d ? n / d : 0;
      list.appendChild(h("div", { class: "gap" }, [
        h("div", { class: "row" }, [h("b", { text: g.label }), h("span", { text: n.toLocaleString("en-US") + " of " + d.toLocaleString("en-US") + " (" + (ratio > 0 && ratio < 0.01 ? "<1%" : pct(n, d)) + ")" })]),
        h("div", { class: "meter" + (ratio ? "" : " empty") }, h("span", { style: "width:" + Math.max(ratio ? 1 : 0, ratio * 100) + "%" })),
        h("p", { text: g.detail }),
      ]));
    });
    el.appendChild(list);
  }

  // ---------- table ----------
  function endOf(pr) { return pr.merged || pr.closed || null; }
  var COLS = [
    { key: "id", label: "Pull request", get: function (p) { return p.repo + "#" + String(p.number).padStart(7, "0"); } },
    { key: "state", label: "State", get: function (p) { return p.state; } },
    { key: "created", label: "Opened", get: function (p) { return p.created; } },
    { key: "end", label: "Merged / closed", get: function (p) { return endOf(p); } },
    { key: "elapsed", label: "Elapsed", num: true, get: function (p) { return p.elapsed_s; } },
    { key: "tokens", label: "Tokens", num: true, get: function (p) { return p.usage ? p.usage.total : null; } },
    { key: "cost", label: "List price", num: true, get: function (p) { return p.cost ? p.cost.known_subtotal_usd : null; } },
    { key: "human", label: "Steering msgs", num: true, get: function (p) { return p.human ? p.human.verified_messages : null; } },
    { key: "idle", label: "Unattended", num: true, get: function (p) { return p.eligible_idle_s; } },
    { key: "size", label: "Lines", num: true, get: function (p) { return p.size ? p.size.additions + p.size.deletions : null; } },
  ];
  function sortRows(rows) {
    var col = COLS.filter(function (c) { return c.key === state.sort; })[0] || COLS[3];
    return rows.slice().sort(function (a, b) {
      var x = col.get(a), y = col.get(b);
      if (x === null || x === undefined) return y === null || y === undefined ? 0 : 1; // unknowns last, either direction
      if (y === null || y === undefined) return -1;
      return (x < y ? -1 : x > y ? 1 : 0) * state.dir;
    });
  }
  function stateChip(pr) {
    var cls = pr.state === "MERGED" ? "good" : pr.state === "OPEN" ? "" : "bad";
    var label = pr.state === "MERGED" ? "Merged" : pr.state === "OPEN" ? (pr.draft ? "Open, draft" : "Open") : "Closed";
    return h("span", { class: "chip " + cls }, [h("i"), label]);
  }
  function elapsedText(pr) {
    var d = S.formatDuration(pr.elapsed_s);
    if (d === null) return null;
    return pr.elapsed_basis === "SNAPSHOT_AT_RIGHT_CENSORED" ? d + " so far" : d;
  }
  function renderTable(rows) {
    var sorted = sortRows(rows), pages = Math.max(1, Math.ceil(sorted.length / PAGE));
    state.page = Math.min(state.page, pages - 1);
    var slice = sorted.slice(state.page * PAGE, state.page * PAGE + PAGE);
    $("table-count").textContent = sorted.length.toLocaleString("en-US") + " of " + data.prs.length.toLocaleString("en-US") + " pull requests match. Select a row for detail.";
    var thead = clear($("pr-table").querySelector("thead"));
    thead.appendChild(h("tr", null, COLS.map(function (c) {
      var active = state.sort === c.key;
      return h("th", { class: c.num ? "num" : "", "aria-sort": active ? (state.dir > 0 ? "ascending" : "descending") : "none" },
        h("button", { type: "button", onclick: function () { state.dir = active ? -state.dir : (c.num || c.key === "end" || c.key === "created" ? -1 : 1); state.sort = c.key; state.page = 0; render(); } },
          c.label + (active ? (state.dir > 0 ? " ▲" : " ▼") : "")));
    })));
    var tbody = clear($("pr-table").querySelector("tbody")), list = clear($("pr-list"));
    if (!slice.length) {
      tbody.appendChild(h("tr", null, h("td", { colspan: COLS.length, class: "na", text: "No pull requests match these filters." })));
      list.appendChild(h("li", { class: "na-text", text: "No pull requests match these filters." }));
    }
    slice.forEach(function (pr) {
      var open = function () { openPanel(pr); };
      var cell = function (v, fmt) { return h("td", { class: "num" }, v === null || v === undefined ? na("–") : fmt(v)); };
      tbody.appendChild(h("tr", { tabindex: 0, onclick: open, onkeydown: function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } } }, [
        h("td", { class: "title" }, [h("span", { class: "pr-id" }, [swatch(repoColor(pr.repo)), shortRepo(pr.repo) + " #" + pr.number]),
          h("span", { class: "pr-title", title: pr.title || "", text: pr.title || "(no title)" })]),
        h("td", null, stateChip(pr)),
        h("td", { text: fmtTime(pr.created, false) || "–" }),
        h("td", null, endOf(pr) ? fmtTime(endOf(pr), false) : na("–")),
        h("td", { class: "num" }, elapsedText(pr) || na("–")),
        cell(pr.usage ? pr.usage.total : null, S.compact),
        cell(pr.cost ? (pr.cost.full_scenario_usd !== null ? pr.cost.full_scenario_usd : pr.cost.known_subtotal_usd) : null,
          function (v) { return (pr.cost.full_scenario_usd !== null ? "" : "≥ ") + usd(v); }),
        cell(pr.human ? pr.human.verified_messages : null, function (v) { return v.toLocaleString("en-US"); }),
        cell(pr.eligible_idle_s, S.formatDuration),
        cell(pr.size ? pr.size.additions + pr.size.deletions : null, function (v) { return v.toLocaleString("en-US"); }),
      ]));
      list.appendChild(h("li", { tabindex: 0, onclick: open, onkeydown: function (e) { if (e.key === "Enter") open(); } }, [
        h("div", { class: "pr-id" }, [swatch(repoColor(pr.repo)), shortRepo(pr.repo) + " #" + pr.number]),
        h("div", { class: "t", text: pr.title || "(no title)" }),
        h("div", { class: "m" }, [stateChip(pr), h("span", { text: elapsedText(pr) || "elapsed unknown" }),
          h("span", { text: pr.usage && typeof pr.usage.total === "number" ? S.compact(pr.usage.total) + " tokens" : "tokens unavailable" })]),
      ]));
    });
    var pager = clear($("pager"));
    append(pager, [
      h("button", { type: "button", class: "ghost", disabled: state.page === 0, onclick: function () { state.page -= 1; render(); }, text: "Previous" }),
      h("span", { text: "Page " + (state.page + 1) + " of " + pages }),
      h("button", { type: "button", class: "ghost", disabled: state.page >= pages - 1, onclick: function () { state.page += 1; render(); }, text: "Next" }),
    ]);
  }

  // ---------- drilldown ----------
  var lastFocus = null;
  function openPanel(pr) {
    lastFocus = document.activeElement;
    var p = clear($("panel"));
    function dl(pairs) {
      var el = h("dl");
      pairs.forEach(function (x) { el.appendChild(h("dt", { text: x[0] })); el.appendChild(h("dd", null, x[1] === null || x[1] === undefined ? na() : x[1])); });
      return el;
    }
    var n = function (v) { return typeof v === "number" ? v.toLocaleString("en-US") : null; };
    var basis = { MERGED_AT: "Opened to merged", CLOSED_AT: "Opened to closed without merge", SNAPSHOT_AT_RIGHT_CENSORED: "Opened to the data cutoff; still open, so the final value will be longer" };
    append(p, [
      h("button", { type: "button", class: "ghost close", "aria-label": "Close detail", onclick: closePanel, text: "Close" }),
      h("div", { class: "pr-id" }, [swatch(repoColor(pr.repo)), pr.repo + " #" + pr.number]),
      h("h2", { text: pr.title || "(no title)" }),
      h("p", { class: "sub" }, [stateChip(pr), " ", S.webUrl(pr.url) && h("a", { href: S.webUrl(pr.url), target: "_blank", rel: "noopener noreferrer", text: "Open on GitHub" })]),
      h("section", null, [h("h3", { text: "Timeline" }), dl([
        ["Opened", fmtTime(pr.created)], ["Merged", pr.merged ? fmtTime(pr.merged) : (pr.state === "MERGED" ? null : "Not merged")],
        ["Closed", pr.closed ? fmtTime(pr.closed) : (pr.state === "OPEN" ? "Still open" : null)],
        ["Elapsed", elapsedText(pr)], ["Measured as", basis[pr.elapsed_basis] || pr.elapsed_basis], ["Stage label", pr.stage ? pr.stage.replace(/^stage:/, "") : "None observed"],
        ["Branch", pr.branch],
      ])]),
      h("section", null, [h("h3", { text: "Token usage" }), pr.usage ? dl([
        ["Total", n(pr.usage.total)], ["Uncached input", n(pr.usage.uncached_input)], ["Cache read", n(pr.usage.cache_read)], ["Output", n(pr.usage.output)],
        ["Requests", n(pr.usage.requests)], ["Tied to this PR by", pr.usage.basis === "direct" ? "Requests naming the PR" : pr.usage.basis === "session_binding" ? "Session recorded as working on this PR" : "Session branch matching this PR's branch"],
        ["Confidence", pr.usage.confidence],
      ]) : h("p", { class: "note", text: "Unavailable. No usage could be tied to this PR (" + (pr.branch_usage_status || pr.usage_status || "no attribution") + "). This is not zero usage." }),
        pr.usage && pr.usage.basis === "source_branch" ? h("p", { class: "note", text: "Branch matching credits every session on the branch to this PR, so long-lived or reused branches can overstate it." }) : null]),
      h("section", null, [h("h3", { text: "List-price estimate" }), pr.cost ? dl([
        ["Known part", pr.cost.known_subtotal_usd === null ? null : "≥ " + usd(pr.cost.known_subtotal_usd)],
        ["Full estimate", pr.cost.full_scenario_usd === null ? null : usd(pr.cost.full_scenario_usd)],
        ["Requests priced in full", pr.cost.fully_priced_event_n + " of " + pr.cost.event_n], ["Models", pr.cost.models.join(", ") || null],
        ["Rate card", pr.cost.catalog_version], ["Status", pr.cost.statuses.join(", ")],
      ]) : h("p", { class: "note", text: "Unavailable (" + (pr.cost_status || "no priced usage") + ")." }),
        h("p", { class: "note", text: "Public list prices applied to observed tokens. Not subscription spend, an invoice, or quota used." })]),
      h("section", null, [h("h3", { text: "Human steering" }), pr.human ? dl([
        ["Verified messages", n(pr.human.verified_messages)], ["Initial requests", n(pr.human.initial)], ["Follow-ups", n(pr.human.followup)],
        ["Branch-only candidates", n(pr.human.branch_candidates)],
        ["Episodes", pr.human.episodes && ["good", "bad", "mixed", "unknown"].some(function (k) { return pr.human.episodes[k]; })
          ? ["good", "bad", "mixed", "unknown"].map(function (k) { return (pr.human.episodes[k] || 0) + " " + k; }).join(" · ") : "None recorded"],
        ["Coverage", pr.human.coverage_status], ["Confidence", pr.human.confidence],
      ]) : h("p", { class: "note", text: "Unavailable. No human input could be tied to this PR. This is not the same as no steering." })]),
      h("section", null, [h("h3", { text: "Handoffs" }), pr.handoffs ? dl((data.handoff_transitions || []).map(function (t) {
        return [t.label, typeof pr.handoffs[t.key] === "number" ? S.formatDuration(pr.handoffs[t.key]) : null];
      })) : h("p", { class: "note", text: "Unavailable. No workflow transition has both ends recorded for this PR." })]),
      h("section", null, [h("h3", { text: "Time and size" }), dl([
        ["Active time", pr.active_s === null ? null : S.formatDuration(pr.active_s)],
        ["Agent effort", pr.agent_effort_s === null ? null : S.formatDuration(pr.agent_effort_s)],
        ["Eligible idle", pr.eligible_idle_s === null ? null : S.formatDuration(pr.eligible_idle_s)],
        ["Size", pr.size ? "+" + pr.size.additions + " / −" + pr.size.deletions + " in " + pr.size.files + " files" : null],
      ]), h("p", { class: "note", text: "Elapsed time minus active time is a residual, not wasted time." })]),
    ]);
    $("panel").hidden = false; $("scrim").hidden = false; $("panel").focus();
  }
  function closePanel() {
    $("panel").hidden = true; $("scrim").hidden = true;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  // ---------- downloads ----------
  function download(name, text) {
    var url = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
    var a = h("a", { href: url, download: name });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }
  function rowsCsv(rows) {
    return S.csv(sortRows(rows), [
      { header: "repository", value: function (p) { return p.repo; } }, { header: "number", value: function (p) { return p.number; } },
      { header: "title", value: function (p) { return p.title; } }, { header: "state", value: function (p) { return p.state; } },
      { header: "created_utc", value: function (p) { return p.created; } }, { header: "merged_utc", value: function (p) { return p.merged; } },
      { header: "closed_utc", value: function (p) { return p.closed; } }, { header: "elapsed_seconds", value: function (p) { return p.elapsed_s; } },
      { header: "elapsed_basis", value: function (p) { return p.elapsed_basis; } },
      { header: "tokens_total", value: function (p) { return p.usage ? p.usage.total : null; } },
      { header: "tokens_basis", value: function (p) { return p.usage ? p.usage.basis : null; } },
      { header: "list_price_known_usd", value: function (p) { return p.cost ? p.cost.known_subtotal_usd : null; } },
      { header: "list_price_full_usd", value: function (p) { return p.cost ? p.cost.full_scenario_usd : null; } },
      { header: "verified_steering_messages", value: function (p) { return p.human ? p.human.verified_messages : null; } },
      { header: "active_seconds", value: function (p) { return p.active_s; } },
      { header: "eligible_unattended_seconds", value: function (p) { return p.eligible_idle_s; } },
      { header: "lines_changed", value: function (p) { return p.size ? p.size.additions + p.size.deletions : null; } },
      { header: "url", value: function (p) { return p.url; } },
    ]);
  }
  function aggCsv(agg) {
    var ep = S.episodeCounts(agg);
    var lines = [
      ["pull_requests_in_selection", agg.total, agg.total, ""], ["merged", agg.merged, agg.total, ""],
      ["open_to_merge_seconds_mean", agg.elapsed.mean, agg.elapsed.n, "nearest-rank"], ["open_to_merge_seconds_p50", agg.elapsed.p50, agg.elapsed.n, "nearest-rank"],
      ["open_to_merge_seconds_p90", agg.elapsed.p90, agg.elapsed.n, "nearest-rank"], ["open_to_merge_seconds_p99", agg.elapsed.p99, agg.elapsed.n, "nearest-rank"],
      ["tokens_attributed_sum", agg.usage.sum, agg.usageN, "per-PR basis in row export"], ["tokens_per_pr_p50", agg.usage.p50, agg.usageN, ""],
      ["tokens_per_pr_p90", agg.usage.p90, agg.usageN, ""], ["tokens_per_pr_p99", agg.usage.p99, agg.usageN, ""],
      ["list_price_known_usd_sum", agg.costKnown.sum, agg.costKnownN, "lower bound; not invoiced spend"], ["prs_fully_priced", agg.costFullN, agg.total, ""],
      ["verified_steering_messages_sum", agg.human.sum, agg.humanN, ""], ["active_seconds_p50", agg.active.p50, agg.activeN, ""],
      ["eligible_unattended_seconds_mean", agg.idle.mean, agg.idleN, ""], ["eligible_unattended_seconds_p50", agg.idle.p50, agg.idleN, ""],
      ["eligible_unattended_seconds_p90", agg.idle.p90, agg.idleN, ""], ["eligible_unattended_seconds_p99", agg.idle.p99, agg.idleN, ""],
      ["steering_episodes_good", ep.good, agg.episodePrN, ""], ["steering_episodes_bad", ep.bad, agg.episodePrN, ""],
      ["steering_episodes_mixed", ep.mixed, agg.episodePrN, ""], ["steering_episodes_unknown", ep.unknown, agg.episodePrN, ""],
    ].concat((data.handoff_transitions || []).reduce(function (out, t) {
      var sm = agg.handoffs[t.key];
      return out.concat(["mean", "p50", "p90", "p99"].map(function (k) { return ["handoff_" + t.key + "_seconds_" + k, sm ? sm[k] : null, sm ? sm.n : 0, ""]; }));
    }, []));
    return S.csv(lines, [
      { header: "measure", value: function (l) { return l[0]; } }, { header: "value", value: function (l) { return l[1]; } },
      { header: "observed_n", value: function (l) { return l[2]; } }, { header: "note", value: function (l) { return l[3]; } },
    ]);
  }

  // ---------- render ----------
  var current = { rows: [], agg: null };
  function render() {
    var f = currentFilter(), rows = S.filterPrs(data.prs, f), agg = S.aggregate(rows, f);
    current = { rows: rows, agg: agg };
    renderHeader();
    renderOneShot(rows);
    renderCards(rows, agg);
    renderDaily(rows, f);
    var merged = rows.filter(function (pr) { return S.mergedIn(pr, f.startMs, f.endMs); });
    renderHistogram("c-elapsed", "Open-to-merge time", agg.elapsed.n ? "Merged PRs in the selection (n=" + agg.elapsed.n + "). Median " + S.formatDuration(agg.elapsed.p50) + ", p90 " + S.formatDuration(agg.elapsed.p90) + "." : "Merged PRs in the selection",
      S.histogram(merged.map(function (pr) { return pr.elapsed_s; }), S.ELAPSED_EDGES, S.ELAPSED_LABELS), "merged PRs", "No merges match these filters.");
    renderWow();
    renderHistogram("c-tokens", "Tokens per PR", "Only the " + agg.usageN + " of " + agg.total + " PRs with usage tied to them. The rest are unavailable, not zero.",
      S.histogram(rows.map(function (pr) { return pr.usage ? pr.usage.total : null; }), S.TOKEN_EDGES, S.TOKEN_LABELS), "PRs", "No usage is tied to PRs in this selection.");
    renderHandoffs(agg);
    renderEpisodes(agg);
    renderGaps(rows);
    renderTable(rows);
  }

  function fail(message) {
    var banner = $("banner");
    banner.hidden = false; banner.className = "banner error";
    banner.textContent = message;
    $("scope-line").textContent = "Snapshot unavailable.";
  }

  function start(payload) {
    if (!payload || payload.schema_version !== 1 || !Array.isArray(payload.prs)) {
      fail("The data file is not a version 1 dashboard snapshot, so nothing is shown.");
      return;
    }
    data = payload;
    buildFilters();
    renderSnapshotLevel();
    $("foot").textContent = "Snapshot schema " + data.schema_version + " · collector " + (data.code_version || "unknown version") +
      " · percentiles: " + (data.quantile_method || "nearest rank") + ", computed from the PR rows on this page.";
    $("dl-rows").addEventListener("click", function () { download("prw-pull-requests.csv", rowsCsv(current.rows)); });
    $("dl-agg").addEventListener("click", function () { download("prw-summary.csv", aggCsv(current.agg)); });
    $("scrim").addEventListener("click", closePanel);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !$("panel").hidden) closePanel(); });
    $("content").hidden = false;
    render();
  }

  fetch(DATA_URL, { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(start)
    .catch(function (err) { fail("Could not load " + DATA_URL + " (" + err.message + "). Nothing is shown rather than stale or partial figures."); });
})();

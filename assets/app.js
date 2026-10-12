/* AI Stack Intelligence — client behavior
   Zero dependencies. Data is injected by the build as window.__ASI_DATA__.
   Mounts: [data-lb-table] (leaderboard), [data-calc] (calculator), form[data-newsletter]. */
(function () {
  "use strict";

  var D = window.__ASI_DATA__ || {};
  var SERIES = ["#7c8cf8", "#5eead4", "#f0abfc", "#fbbf24", "#4ade80", "#f87171", "#67e8f9", "#fb923c"];

  function fmtMoney(v, dec) {
    if (dec === undefined) dec = v >= 100 ? 0 : 2;
    return "$" + v.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  }
  function fmtInt(v) { return v.toLocaleString("en-US"); }
  function esc(s) {
    var M = { "\x26": "\x26amp;", "<": "\x26lt;", ">": "\x26gt;", '"': "\x26quot;", "'": "\x26#39;" };
    return String(s).replace(/[&<>"']/g, function (c) { return M[c]; });
  }

  /* ================= LEADERBOARD ================= */
  function initLeaderboard() {
    var host = document.querySelector("[data-lb-table]");
    if (!host || !D.leaderboard) return;
    var models = D.leaderboard.models.slice();
    var state = { key: "rank", dir: 1, q: "", org: "all", license: "all" };

    var orgs = Array.from(new Set(models.map(function (m) { return m.org; }))).sort();
    var orgSel = host.querySelector("[data-lb-org]");
    if (orgSel) {
      orgs.forEach(function (o) {
        var opt = document.createElement("option");
        opt.value = o; opt.textContent = o;
        orgSel.appendChild(opt);
      });
    }

    var isOpen = function (lic) { return lic && lic !== "Proprietary"; };

    function rows() {
      var out = models.filter(function (m) {
        var q = state.q.toLowerCase();
        if (q && (m.model + " " + m.org).toLowerCase().indexOf(q) === -1) return false;
        if (state.org !== "all" && m.org !== state.org) return false;
        var lic = (m.extra && m.extra.license) || "";
        if (state.license === "open" && !isOpen(lic)) return false;
        if (state.license === "proprietary" && isOpen(lic)) return false;
        return true;
      });
      var k = state.key, d = state.dir;
      out.sort(function (a, b) {
        var av = k === "votes" ? ((a.extra && a.extra.votes) || 0) : a[k];
        var bv = k === "votes" ? ((b.extra && b.extra.votes) || 0) : b[k];
        if (typeof av === "string") return d * av.localeCompare(bv);
        return d * (av - bv);
      });
      return out;
    }

    function render() {
      var list = rows();
      var tbody = host.querySelector("tbody");
      var count = host.querySelector("[data-lb-count]");
      if (count) count.textContent = list.length + " of " + models.length + " models";
      var minElo = 1300, maxElo = 1470;
      var elos = models.map(function (m) { return m.elo; });
      minElo = Math.min.apply(null, elos) - 10;
      maxElo = Math.max.apply(null, elos) + 2;
      tbody.innerHTML = list.map(function (m) {
        var votes = (m.extra && m.extra.votes) || 0;
        var lic = (m.extra && m.extra.license) || "—";
        var pct = Math.max(4, Math.round(((m.elo - minElo) / (maxElo - minElo)) * 100));
        return "<tr>" +
          '<td class="rank-cell">' + m.rank + "</td>" +
          '<td><span class="model-name">' + esc(m.model) + "</span></td>" +
          "<td>" + '<span class="org-tag">' + esc(m.org) + "</span></td>" +
          '<td><div class="bar-cell"><div class="bar" style="width:' + pct + '%"></div><span class="elo-chip">' + fmtInt(m.elo) + "</span></div></td>" +
          '<td class="num text-mid">' + fmtInt(votes) + "</td>" +
          '<td><span class="' + (isOpen(lic) ? "license-open" : "license-prop") + '">' + esc(lic) + "</span></td>" +
          "</tr>";
      }).join("");
      host.querySelectorAll("th.sortable").forEach(function (th) {
        var on = th.getAttribute("data-key") === state.key;
        th.querySelector(".arrow").textContent = on ? (state.dir === 1 ? "▲" : "▼") : "";
        th.classList.toggle("sorted", on);
      });
    }

    host.querySelectorAll("th.sortable").forEach(function (th) {
      th.addEventListener("click", function () {
        var k = th.getAttribute("data-key");
        if (state.key === k) state.dir = -state.dir;
        else { state.key = k; state.dir = (k === "rank") ? 1 : -1; }
        render();
      });
    });
    var search = host.querySelector("[data-lb-search]");
    if (search) search.addEventListener("input", function () { state.q = search.value; render(); });
    if (orgSel) orgSel.addEventListener("change", function () { state.org = orgSel.value; render(); });
    host.querySelectorAll("[data-lb-license]").forEach(function (chip) {
      chip.addEventListener("click", function () {
        state.license = chip.getAttribute("data-lb-license");
        host.querySelectorAll("[data-lb-license]").forEach(function (c) { c.classList.toggle("on", c === chip); });
        render();
      });
    });
    render();
  }

  /* ================= CALCULATOR ================= */
  function initCalc() {
    var host = document.querySelector("[data-calc]");
    if (!host || !D.prices) return;
    var prices = D.prices.models;
    var byModel = {};
    prices.forEach(function (p) { byModel[p.model] = p; });

    var PRESETS = {
      chat:   { label: "Chatbot / copilot", req: 40000, i: 3000, o: 800 },
      coding: { label: "Coding agent",     req: 2000,  i: 15000, o: 4000 },
      rag:    { label: "RAG pipeline",      req: 30000, i: 8000, o: 1200 },
      batch:  { label: "Batch summarization", req: 5000, i: 20000, o: 3000 }
    };
    var DEFAULT_PICKS = (D.defaults && D.defaults.length) ? D.defaults.slice() : ["gpt-4o", "claude-sonnet-4", "gemini-2.5-pro", "gpt-4.1-mini", "deepseek-chat"];

    var els = {
      presets: host.querySelector("[data-calc-presets]"),
      list: host.querySelector("[data-calc-models]"),
      i: host.querySelector("[data-calc-i]"),
      o: host.querySelector("[data-calc-o]"),
      r: host.querySelector("[data-calc-r]"),
      table: host.querySelector("[data-calc-table] tbody"),
      chart: host.querySelector("[data-calc-chart]"),
      cheapest: host.querySelector("[data-calc-cheapest]"),
      priciest: host.querySelector("[data-calc-priciest]"),
      spread: host.querySelector("[data-calc-spread]"),
      shareUrl: host.querySelector("[data-calc-url]"),
      copyBtn: host.querySelector("[data-calc-copy]"),
      totalTok: host.querySelector("[data-calc-tokens]")
    };

    var picked = [];

    function buildChecklist() {
      els.list.innerHTML = prices.map(function (p, idx) {
        return '<label class="check-item" data-model="' + esc(p.model) + '">' +
          '<input type="checkbox" value="' + esc(p.model) + '">' +
          '<span class="check-box">✓</span>' +
          "<span>" + esc(p.model) + ' <span class="text-low">· ' + esc(p.provider) + "</span></span>" +
          "</label>";
      }).join("");
      els.list.querySelectorAll(".check-item").forEach(function (item) {
        item.addEventListener("click", function (e) {
          e.preventDefault();
          var m = item.getAttribute("data-model");
          var i = picked.indexOf(m);
          if (i >= 0) picked.splice(i, 1); else picked.push(m);
          if (picked.length > 8) picked.shift();
          syncChecks(); update();
        });
      });
    }
    function syncChecks() {
      els.list.querySelectorAll(".check-item").forEach(function (item) {
        var on = picked.indexOf(item.getAttribute("data-model")) >= 0;
        item.classList.toggle("on", on);
        item.querySelector("input").checked = on;
      });
    }

    function readInputs() {
      return {
        i: Math.max(1, parseInt(els.i.value, 10) || 0),
        o: Math.max(1, parseInt(els.o.value, 10) || 0),
        r: Math.max(1, parseInt(els.r.value, 10) || 0)
      };
    }

    function cost(p, u) {
      return u.r * ((u.i / 1e6) * p.input_per_1m_usd + (u.o / 1e6) * p.output_per_1m_usd);
    }

    function update(pushUrl) {
      var u = readInputs();
      var rows = picked.map(function (m) { return byModel[m]; }).filter(Boolean);
      if (!rows.length) {
        els.table.innerHTML = '<tr><td colspan="6" class="text-low" style="text-align:center;padding:32px 0">Select at least one model on the left.</td></tr>';
        els.chart.innerHTML = "";
        els.cheapest.textContent = "—"; els.priciest.textContent = "—"; els.spread.textContent = "—";
        if (els.totalTok) els.totalTok.textContent = "—";
      } else {
        var costs = rows.map(function (p) { return { p: p, c: cost(p, u) }; });
        costs.sort(function (a, b) { return a.c - b.c; });
        var min = costs[0].c, max = costs[costs.length - 1].c;

        els.table.innerHTML = costs.map(function (row, idx) {
          var p = row.p;
          var badge = idx === 0 && costs.length > 1 ? '<span class="cheapest-badge">CHEAPEST</span>' : "";
          return "<tr>" +
            '<td><span class="model-name">' + esc(p.model) + "</span>" + badge + "</td>" +
            "<td>" + '<span class="org-tag">' + esc(p.provider) + "</span></td>" +
            '<td class="num">' + fmtMoney(p.input_per_1m_usd) + "</td>" +
            '<td class="num">' + fmtMoney(p.output_per_1m_usd) + "</td>" +
            '<td class="num" style="color:var(--text-hi);font-weight:600">' + fmtMoney(row.c) + "/mo</td>" +
            '<td class="num text-mid">' + fmtMoney(row.c * 12) + "/yr</td>" +
            "</tr>";
        }).join("");

        var maxC = max || 1;
        els.chart.innerHTML = costs.map(function (row, idx) {
          var w = Math.max(1.5, (row.c / maxC) * 100);
          return '<div class="chart-row">' +
            '<div class="label">' + esc(row.p.model) + "</div>" +
            '<div class="track"><div class="fill" style="width:' + w + "%;background:" + SERIES[idx % SERIES.length] + '"></div></div>' +
            '<div class="val">' + fmtMoney(row.c) + "</div>" +
            "</div>";
        }).join("");

        els.cheapest.textContent = fmtMoney(min) + "/mo";
        els.priciest.textContent = fmtMoney(max) + "/mo";
        els.spread.textContent = min > 0 ? (max / min).toFixed(1) + "×" : "—";
        if (els.totalTok) els.totalTok.textContent = fmtInt(u.r * (u.i + u.o));

        if (pushUrl !== false) writeUrl(u);
      }
    }

    function writeUrl(u) {
      var params = new URLSearchParams();
      params.set("m", picked.join(","));
      params.set("i", u.i); params.set("o", u.o); params.set("r", u.r);
      var qs = params.toString();
      var base = location.pathname;
      var url = base + "?" + qs;
      els.shareUrl.textContent = url;
      try { window.history.replaceState(null, "", url); } catch (e) {}
    }

    function readUrl() {
      var params = new URLSearchParams(location.search);
      if (!params.get("m") && !params.get("r")) return null;
      var m = (params.get("m") || "").split(",").filter(function (x) { return byModel[x]; });
      return {
        m: m.length ? m : DEFAULT_PICKS,
        i: parseInt(params.get("i"), 10) || PRESETS.chat.i,
        o: parseInt(params.get("o"), 10) || PRESETS.chat.o,
        r: parseInt(params.get("r"), 10) || PRESETS.chat.r
      };
    }

    // presets
    if (els.presets) {
      els.presets.innerHTML = Object.keys(PRESETS).map(function (k) {
        return '<button type="button" class="chip" data-preset="' + k + '">' + esc(PRESETS[k].label) + "</button>";
      }).join("");
      els.presets.querySelectorAll("[data-preset]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var pr = PRESETS[btn.getAttribute("data-preset")];
          els.i.value = pr.i; els.o.value = pr.o; els.r.value = pr.r;
          els.presets.querySelectorAll(".chip").forEach(function (c) { c.classList.toggle("on", c === btn); });
          update();
        });
      });
      els.presets.querySelector('[data-preset="chat"]').classList.add("on");
    }

    [els.i, els.o, els.r].forEach(function (inp) {
      if (inp) inp.addEventListener("input", function () {
        els.presets.querySelectorAll(".chip").forEach(function (c) { c.classList.remove("on"); });
        update();
      });
    });

    if (els.copyBtn) {
      els.copyBtn.addEventListener("click", function () {
        var url = location.origin === "null" || !location.origin
          ? els.shareUrl.textContent
          : location.origin + els.shareUrl.textContent;
        var done = function () {
          els.copyBtn.textContent = "Copied ✓";
          els.copyBtn.classList.add("copy-ok");
          setTimeout(function () { els.copyBtn.textContent = "Copy link"; els.copyBtn.classList.remove("copy-ok"); }, 1600);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(url).then(done, done);
        } else {
          var ta = document.createElement("textarea");
          ta.value = url; document.body.appendChild(ta); ta.select();
          try { document.execCommand("copy"); } catch (e) {}
          document.body.removeChild(ta); done();
        }
      });
    }

    buildChecklist();
    var fromUrl = readUrl();
    if (fromUrl) {
      picked = fromUrl.m;
      els.i.value = fromUrl.i; els.o.value = fromUrl.o; els.r.value = fromUrl.r;
      els.presets.querySelectorAll(".chip").forEach(function (c) { c.classList.remove("on"); });
    } else {
      picked = DEFAULT_PICKS.slice();
      els.i.value = PRESETS.chat.i; els.o.value = PRESETS.chat.o; els.r.value = PRESETS.chat.r;
    }
    syncChecks();
    update(false);
    if (fromUrl) writeUrl(readInputs()); else writeUrl(readInputs());
  }

  /* ================= NEWSLETTER ================= */
  function initNewsletter() {
    document.querySelectorAll("form[data-newsletter]").forEach(function (form) {
      form.addEventListener("submit", function (e) {
        if (form.getAttribute("data-newsletter") === "live") return; // real beehiiv embed: let it post
        e.preventDefault();
        var email = form.querySelector("input[type=email]");
        var note = form.parentElement.querySelector(".form-note");
        if (!email || !email.value || email.value.indexOf("@") < 1) {
          if (note) note.textContent = "Please enter a valid email address.";
          return;
        }
        if (note) note.textContent = "You're on the list — check your inbox to confirm. (Demo mode: beehiiv embed lands before public launch.)";
        email.value = "";
      });
    });
  }

  /* ================= boot ================= */
  function boot() {
    initLeaderboard();
    initCalc();
    initNewsletter();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();

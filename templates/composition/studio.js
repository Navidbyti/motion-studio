/* Motion Studio runtime helpers for HyperFrames compositions.
 *
 * Reads window.TIMING (timing.js, from beatmap.json), window.DATA (data.js,
 * from data/bindings.json) and window.REFRAME (reframe.js, from
 * footage/reframe.json). Never hard-code a hit time, a number or a crop;
 * ask Studio so QA can prove it.
 *
 * In a scene sub-composition (compositions/<scene>.html) times are local:
 *   const S = Studio.forScene("s1");
 *   S.hit(tl, "s1.title", "#s1-title", {scale: .86, opacity: 0}, {scale: 1, opacity: 1, ease: "expo.out"});
 *     -> starts `anticipation` frames early and lands exactly on the event's impact frame
 *   S.after(tl, "s1.title", "#s1-title", {scale: 1.02}, 0.4)   follow-through from the impact
 *   S.drift(tl, "s1.hold", "#s1-stack", {scale: 1.02})         keeps a hold alive until its `until`
 *   S.counter(tl, "#s1-n", "co2_2025", {from: 300, start: "s1.count", impact: "s1.count_land"})
 *   S.at("s1.title") / S.start(id) / S.until(id)                local seconds
 * On the host timeline (index.html) use Studio.host (global times), e.g.
 *   Studio.host.reframe(tl, "v02", "#v02")
 * Studio.fmt("key") returns a bound value's exact display string.
 * Deterministic only: no clocks, no randomness, no network.
 */
(function () {
  "use strict";
  var T = window.TIMING || { fps: 30, events: {}, scenes: {}, media: {} };
  var D = window.DATA || { values: {}, series: {} };
  var R = window.REFRAME || {};
  var hits = (window.__studioHits = window.__studioHits || []);
  var used = (window.__studioValues = window.__studioValues || []);
  var touched = (window.__studioEvents = window.__studioEvents || []);
  var fps = T.fps || 30;

  function need(map, id, what) {
    if (!map || !(id in map)) throw new Error("Motion Studio: unknown " + what + " '" + id + "' (check beatmap / bindings / reframe)");
    return map[id];
  }
  function value(key) { used.push(key); return need(D.values, key, "value"); }

  function api(sceneId, offset) {
    function ev(id) {
      var e = need(T.events, id, "event");
      touched.push(id);
      if (sceneId && e.scene && e.scene !== sceneId) throw new Error("Motion Studio: event '" + id + "' belongs to scene " + e.scene + ", not " + sceneId);
      return e;
    }
    function local(t) { return Math.max(0, t - offset); }
    return {
      scene: sceneId,
      offset: offset,
      event: ev,
      at: function (id) { return local(ev(id).impact); },
      start: function (id) { return local(ev(id).start); },
      until: function (id) { var e = ev(id); return e.until == null ? null : local(e.until); },

      /* Lands the motion ON the impact frame. When there is no room for anticipation (the hit is on the
         scene's first frame, or anticipation is 0) it becomes an on-the-cut hit: the from-state shows on the
         impact frame and settles over `settle` seconds (default 8 frames). */
      hit: function (tl, id, target, fromVars, toVars) {
        var e = ev(id);
        var vars = Object.assign({}, toVars || {});
        var settle = vars.settle != null ? vars.settle : 8 / fps;
        delete vars.settle;
        var i = local(e.impact);
        var onCut = (e.start < offset - 1e-6) || (e.impact - e.start < 1 / fps - 1e-6);
        var s = onCut ? i : local(e.start);
        var dur = onCut ? settle : i - s;
        vars.duration = dur;
        if (fromVars) tl.fromTo(target, fromVars, vars, s); else tl.to(target, vars, s);
        tl.addLabel(id, i);
        hits.push({ id: id, scene: sceneId, mode: onCut ? "cut" : "land", start: offset + s, impact: e.impact, end: offset + s + dur, target: String(target) });
        return tl;
      },
      after: function (tl, id, target, vars, duration) {
        tl.to(target, Object.assign({}, vars, { duration: duration }), local(ev(id).impact));
        return tl;
      },
      drift: function (tl, id, target, vars) {
        var e = ev(id);
        var end = e.until != null ? e.until : e.impact + 1;
        tl.to(target, Object.assign({ ease: "sine.inOut" }, vars, { duration: Math.max(1 / fps, end - e.impact) }), local(e.impact));
        return tl;
      },
      counter: function (tl, target, key, opts) {
        opts = opts || {};
        var v = value(key);
        var el = typeof target === "string" ? document.querySelector(target) : target;
        if (!el) throw new Error("Motion Studio: counter target missing: " + target);
        el.setAttribute("data-value", key);
        var decimals = v.decimals != null ? v.decimals : 0;
        var end = Number(v.value), from = opts.from != null ? Number(opts.from) : 0;
        var land = ev(opts.impact || opts.start);
        var s = local(opts.start ? ev(opts.start).start : land.start), i = local(land.impact);
        var fmt = new Intl.NumberFormat(v.locale || "en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals, useGrouping: !!v.grouping });
        var prefix = v.prefix || "", suffix = v.suffix || "";
        var state = { n: from };
        el.textContent = prefix + fmt.format(from).replace("-", "−") + suffix;
        tl.to(state, {
          n: end, duration: Math.max(1 / fps, i - s), ease: opts.ease || "power2.out",
          onUpdate: function () { el.textContent = prefix + fmt.format(state.n).replace("-", "−") + suffix; }
        }, s);
        tl.call(function () { el.textContent = v.display; }, null, i);
        hits.push({ id: opts.impact || opts.start, scene: sceneId, start: offset + s, impact: land.impact, end: offset + i, target: String(target), counter: key });
        return tl;
      },
      reframe: function (tl, mediaId, target) {
        var r = need(R, mediaId, "reframe");
        var m = need(T.media, mediaId, "media");
        var el = typeof target === "string" ? document.querySelector(target) : target;
        var W = r.canvas.w;
        el.style.position = "absolute"; el.style.left = "0px"; el.style.top = "0px";
        el.style.width = r.source.w + "px"; el.style.height = r.source.h + "px"; el.style.maxWidth = "none";
        function pose(k) { var sc = W / k.w; return { x: -k.x * sc, y: -k.y * sc, scale: sc, transformOrigin: "0 0" }; }
        var keys = r.keys, t0 = local(m.start);
        tl.set(el, pose(keys[0]), t0);
        for (var n = 1; n < keys.length; n++) {
          var a = t0 + keys[n - 1].t, b = t0 + keys[n].t;
          tl.to(el, Object.assign({ duration: Math.max(1 / fps, b - a), ease: keys[n].ease || "sine.inOut" }, pose(keys[n])), a);
        }
        return tl;
      }
    };
  }

  window.Studio = {
    fps: fps,
    timing: T,
    data: D,
    host: api(null, 0),
    forScene: function (id) { var s = need(T.scenes, id, "scene"); return api(id, s.start); },
    value: value,
    fmt: function (key) { return value(key).display; },
    series: function (name) { return need(D.series, name, "series"); }
  };
})();

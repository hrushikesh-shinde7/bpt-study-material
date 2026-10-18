/* BPTh exam notes — shared behaviour. Everything degrades gracefully without JS. */
(function () {
  "use strict";

  var store = {
    get: function (k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { window.localStorage.setItem(k, v); } catch (e) { /* storage blocked: keep working */ } }
  };
  var root = document.documentElement;

  /* ---- theme: follows the phone's setting until the reader picks one ---- */
  var saved = store.get("notes-theme");
  if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);
  function currentTheme() {
    var t = root.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function paintThemeButton(btn) {
    var dark = currentTheme() === "dark";
    btn.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
    btn.querySelector("span").textContent = dark ? "Light" : "Dark";
  }
  document.querySelectorAll(".js-theme").forEach(function (btn) {
    paintThemeButton(btn);
    btn.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      store.set("notes-theme", next);
      paintThemeButton(btn);
    });
  });

  /* ---- contents drawer (phone) ---- */
  var tocBtn = document.querySelector(".js-toc-btn");
  var toc = document.getElementById("toc");
  function closeToc() {
    document.body.classList.remove("toc-open");
    if (tocBtn) tocBtn.setAttribute("aria-expanded", "false");
  }
  if (tocBtn && toc) {
    tocBtn.addEventListener("click", function () {
      var open = document.body.classList.toggle("toc-open");
      tocBtn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    toc.addEventListener("click", function (e) { if (e.target.closest("a")) closeToc(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeToc(); });
  }

  /* ---- highlight the section being read ---- */
  var tocLinks = toc ? Array.prototype.slice.call(toc.querySelectorAll('a[href^="#"]')) : [];
  if (tocLinks.length && "IntersectionObserver" in window) {
    var byId = {};
    tocLinks.forEach(function (a) { byId[a.getAttribute("href").slice(1)] = a; });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting && byId[en.target.id]) {
          tocLinks.forEach(function (a) { a.classList.remove("is-current"); });
          byId[en.target.id].classList.add("is-current");
        }
      });
    }, { rootMargin: "-20% 0px -70% 0px" });
    Object.keys(byId).forEach(function (id) { var el = document.getElementById(id); if (el) io.observe(el); });
  }

  /* ---- ECG trace in the top bar draws as you read ---- */
  var trace = document.querySelector(".trace path");
  if (trace) {
    var len = trace.getTotalLength();
    trace.style.strokeDasharray = len;
    var onScroll = function () {
      var max = document.documentElement.scrollHeight - window.innerHeight;
      var f = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0;
      trace.style.strokeDashoffset = String(len * (1 - f));
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
  }

  /* ---- diagrams: switch between study view and 2-minute exam sketch ---- */
  document.querySelectorAll(".js-sketch").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var fig = btn.closest(".fig");
      var on = fig.classList.toggle("is-sketch");
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.textContent = on ? "Show study view" : "Show exam sketch";
    });
  });

  /* ---- revision tracker: remembered on this phone only ---- */
  document.querySelectorAll(".js-track").forEach(function (box) {
    var key = "notes-track:" + location.pathname + ":" + box.value;
    box.checked = store.get(key) === "1";
    box.addEventListener("change", function () { store.set(key, box.checked ? "1" : "0"); });
  });

  /* ---- printing: open every answer so nothing is lost on paper ---- */
  window.addEventListener("beforeprint", function () {
    document.querySelectorAll("details").forEach(function (d) { d.setAttribute("data-was-open", d.open ? "1" : "0"); d.open = true; });
  });
  window.addEventListener("afterprint", function () {
    document.querySelectorAll("details").forEach(function (d) { d.open = d.getAttribute("data-was-open") === "1"; });
  });
})();

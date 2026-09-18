/* ADP reference docs — sidebar filter, mobile nav, theme toggle, get-the-docs. */
(function () {
  "use strict";

  var THEME_KEY = "adp-docs-theme";

  /*
    The repository address lives here and nowhere else. Both page families load this
    file — the 30 generated pages from build_html.py and the 15 hand-written ones under
    works-process/ — so injecting the control here is what keeps them from drifting apart.
    Baking the URL into the markup instead would mean 45 copies to age separately.
  */
  var REPO = "https://github.com/TyHen88/adp-docs";
  var ZIP = REPO + "/archive/refs/heads/main.zip";
  var CLONE = "git clone " + REPO + ".git";

  function readTheme() {
    try { return localStorage.getItem(THEME_KEY); } catch (e) { return null; }
  }
  function writeTheme(value) {
    try { localStorage.setItem(THEME_KEY, value); } catch (e) { /* private mode */ }
  }

  var stored = readTheme();
  if (stored === "dark" || stored === "light") {
    document.documentElement.setAttribute("data-theme", stored);
  }

  /*
    Opened from disk (file://) there is no secure context, so navigator.clipboard is
    absent — and this folder is meant to be read straight off disk. Do not drop the
    execCommand branch; it is the only one that runs in that case.
  */
  function legacyCopy(text) {
    var box = document.createElement("textarea");
    box.value = text;
    box.setAttribute("readonly", "");
    box.style.position = "fixed";
    box.style.top = "-1000px";
    document.body.appendChild(box);
    box.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(box);
    return ok;
  }

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(
        function () { return true; },
        function () { return legacyCopy(text); });
    }
    return Promise.resolve(legacyCopy(text));
  }

  function mountGetDocs() {
    var bar = document.querySelector(".topbar");
    if (!bar || bar.querySelector(".getdocs")) { return; }

    var wrap = document.createElement("div");
    wrap.className = "getdocs";
    wrap.innerHTML =
      '<button class="topbar__btn getdocs__trigger" type="button" data-getdocs-trigger' +
      ' aria-expanded="false" aria-haspopup="dialog">' +
      '<span class="getdocs__wide">Get the docs</span>' +
      '<span class="getdocs__narrow">Get</span>' +
      '</button>' +
      '<div class="getdocs__panel" data-getdocs-panel role="dialog" aria-label="Get the docs" hidden>' +
      '<p class="getdocs__lead">Every page, the Markdown sources and the screenshots &mdash; one file. ' +
      'Unpack it and open <code>index.html</code>; it reads offline, no server needed.</p>' +
      '<a class="getdocs__zip" href="' + ZIP + '">Download ZIP</a>' +
      '<p class="getdocs__or">or clone the repository</p>' +
      '<div class="getdocs__cmd">' +
      '<code data-getdocs-clone>' + CLONE + '</code>' +
      '<button class="getdocs__copy" type="button" data-getdocs-copy>Copy</button>' +
      '</div>' +
      '<a class="getdocs__repo" href="' + REPO + '">View on GitHub</a>' +
      '</div>';

    /* Sits to the left of the theme toggle, which every page's topbar ends with. */
    bar.insertBefore(wrap, bar.querySelector("[data-theme-toggle]"));

    var trigger = wrap.querySelector("[data-getdocs-trigger]");
    var panel = wrap.querySelector("[data-getdocs-panel]");

    function close() {
      panel.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
    }

    trigger.addEventListener("click", function (event) {
      event.stopPropagation();
      panel.hidden = !panel.hidden;
      trigger.setAttribute("aria-expanded", String(!panel.hidden));
    });

    /* Clicks inside the panel are left alone — copying and the two links live there. */
    document.addEventListener("click", function (event) {
      if (!panel.hidden && !wrap.contains(event.target)) { close(); }
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !panel.hidden) { close(); trigger.focus(); }
    });

    var copy = wrap.querySelector("[data-getdocs-copy]");
    var revert;
    copy.addEventListener("click", function () {
      copyText(wrap.querySelector("[data-getdocs-clone]").textContent).then(function (ok) {
        copy.textContent = ok ? "Copied" : "Select it";
        clearTimeout(revert);
        revert = setTimeout(function () { copy.textContent = "Copy"; }, 1600);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var toggle = document.querySelector("[data-theme-toggle]");
    if (toggle) {
      toggle.addEventListener("click", function () {
        var dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        var current = document.documentElement.getAttribute("data-theme") || (dark ? "dark" : "light");
        var next = current === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        writeTheme(next);
      });
    }

    var navToggle = document.querySelector("[data-nav-toggle]");
    var sidebar = document.querySelector(".sidebar");
    if (navToggle && sidebar) {
      navToggle.addEventListener("click", function () {
        var open = sidebar.classList.toggle("is-open");
        navToggle.setAttribute("aria-expanded", String(open));
      });
    }

    var search = document.querySelector("[data-nav-search]");
    if (search && sidebar) {
      search.addEventListener("input", function () {
        var q = search.value.trim().toLowerCase();
        sidebar.querySelectorAll(".sidebar__list li").forEach(function (li) {
          var hit = !q || li.textContent.toLowerCase().indexOf(q) !== -1;
          li.classList.toggle("is-hidden", !hit);
        });
        sidebar.querySelectorAll(".sidebar__group").forEach(function (group) {
          var any = group.querySelector(".sidebar__list li:not(.is-hidden)");
          group.style.display = any ? "" : "none";
        });
      });
    }

    mountGetDocs();
  });
})();

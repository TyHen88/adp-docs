/* ADP reference docs — sidebar filter, mobile nav, theme toggle. */
(function () {
  "use strict";

  var THEME_KEY = "adp-docs-theme";

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
  });
})();

/**
 * Theme bootstrap.
 *
 * Loaded synchronously in <head> so the stored preference is applied before
 * the first paint (no flash of the wrong theme). It has to be an external file
 * rather than an inline <script> because our Content-Security-Policy allows
 * scripts from 'self' only, with no unsafe-inline and no nonces.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'cyqr:theme';
  var root = document.documentElement;

  function readStored() {
    try {
      var value = window.localStorage.getItem(STORAGE_KEY);
      return value === 'light' || value === 'dark' ? value : null;
    } catch (err) {
      return null; // storage blocked (private mode, hardened browser)
    }
  }

  function writeStored(value) {
    try {
      window.localStorage.setItem(STORAGE_KEY, value);
    } catch (err) {
      /* preference simply will not persist; the toggle still works */
    }
  }

  function systemTheme() {
    return window.matchMedia &&
      window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function activeTheme() {
    return root.getAttribute('data-theme') || systemTheme();
  }

  function paintBrowserChrome(theme) {
    var color = theme === 'dark' ? '#0b0d10' : '#ffffff';
    var metas = document.querySelectorAll('meta[name="theme-color"]');
    for (var i = 0; i < metas.length; i++) {
      metas[i].setAttribute('content', color);
    }
  }

  function apply(theme) {
    root.setAttribute('data-theme', theme);
    paintBrowserChrome(theme);
  }

  // --- before first paint -------------------------------------------------
  var stored = readStored();
  if (stored) {
    root.setAttribute('data-theme', stored);
  }

  // --- wire up the toggle once the DOM exists -----------------------------
  function init() {
    if (stored) {
      paintBrowserChrome(stored);
    }

    var button = document.getElementById('theme-toggle');
    if (!button) return;

    function sync() {
      var isDark = activeTheme() === 'dark';
      button.setAttribute('aria-pressed', String(isDark));
      button.setAttribute(
        'title',
        isDark ? 'Switch to light theme' : 'Switch to dark theme'
      );
    }

    button.addEventListener('click', function () {
      var next = activeTheme() === 'dark' ? 'light' : 'dark';
      apply(next);
      writeStored(next);
      sync();
    });

    // Follow the OS while the visitor has not made an explicit choice.
    if (window.matchMedia) {
      var query = window.matchMedia('(prefers-color-scheme: dark)');
      var onChange = function () {
        if (!readStored()) sync();
      };
      if (query.addEventListener) query.addEventListener('change', onChange);
      else if (query.addListener) query.addListener(onChange);
    }

    sync();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

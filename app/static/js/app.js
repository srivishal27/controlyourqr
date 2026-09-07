/**
 * ControlYourQR — client-side QR code generator.
 *
 * Everything below runs in the visitor's browser. There is deliberately no
 * fetch(), XMLHttpRequest, WebSocket or sendBeacon anywhere in this file, and
 * the site's Content-Security-Policy (connect-src 'none') means the browser
 * would refuse one even if it were added by accident.
 *
 * Encoder: node-qrcode (MIT), bundled from source into js/vendor/qrcode.min.js
 * and served from this origin. No CDN is contacted.
 */
(function () {
  'use strict';

  if (typeof QRCode === 'undefined') {
    console.error('QR encoder failed to load.');
    return;
  }

  var STORAGE_KEY = 'cyqr:options';
  var RENDER_DEBOUNCE_MS = 140;
  var PREVIEW_PX = 560;

  var DEFAULTS = {
    ecc: 'M',
    size: 1024,
    margin: 4,
    fg: '#000000',
    bg: '#ffffff'
  };

  var ECC_PERCENT = { L: '7%', M: '15%', Q: '25%', H: '30%' };

  // ---------------------------------------------------------------------- //
  // Element lookup
  // ---------------------------------------------------------------------- //
  var $ = function (id) { return document.getElementById(id); };

  var el = {
    tablist: document.querySelector('.tablist'),
    tabs: Array.prototype.slice.call(document.querySelectorAll('[role="tab"]')),
    panels: Array.prototype.slice.call(document.querySelectorAll('[role="tabpanel"]')),
    fields: Array.prototype.slice.call(document.querySelectorAll('[data-field]')),

    eccButtons: Array.prototype.slice.call(document.querySelectorAll('[data-ecc]')),
    size: $('opt-size'),
    sizeValue: $('size-value'),
    margin: $('opt-margin'),
    marginValue: $('margin-value'),
    fg: $('opt-fg'),
    fgHex: $('opt-fg-hex'),
    bg: $('opt-bg'),
    bgHex: $('opt-bg-hex'),
    reset: $('btn-reset'),

    stage: $('qr-stage'),
    canvas: $('qr-canvas'),
    error: $('qr-error'),
    warn: $('qr-warn'),
    meta: $('qr-meta'),
    metaVersion: $('meta-version'),
    metaModules: $('meta-modules'),
    metaEcc: $('meta-ecc'),
    metaExport: $('meta-export'),

    btnPng: $('btn-png'),
    btnSvg: $('btn-svg'),
    btnCopy: $('btn-copy'),

    urlHint: document.querySelector('#fields-url .hint')
  };

  var state = {
    type: 'url',
    ecc: DEFAULTS.ecc,
    size: DEFAULTS.size,
    margin: DEFAULTS.margin,
    fg: DEFAULTS.fg,
    bg: DEFAULTS.bg
  };

  // Result of the most recent successful render, used by the download buttons.
  var current = null; // { payload, scale, modules, version, exportPx }

  // ---------------------------------------------------------------------- //
  // Payload builders
  //
  // Each returns the exact string written into the QR symbol. The formats are
  // the de-facto conventions understood by iOS/Android camera apps.
  // ---------------------------------------------------------------------- //

  var HAS_SCHEME = /^[a-z][a-z0-9+.-]*:/i;
  var LOOKS_LIKE_DOMAIN = /^[\w-]+(\.[\w-]+)+(\/|\?|#|$)/;

  function val(id) {
    var node = $(id);
    return node ? node.value.trim() : '';
  }

  function checked(id) {
    var node = $(id);
    return !!(node && node.checked);
  }

  /** Escape the reserved characters of the WIFI:/MECARD-style grammar. */
  function escapeWifi(value) {
    return value.replace(/([\;,:"])/g, '\\$1');
  }

  /** Escape the reserved characters of a vCard property value (RFC 6350). */
  function escapeVcard(value) {
    return value
      .replace(/\\/g, '\\\\')
      .replace(/\n/g, '\\n')
      .replace(/,/g, '\\,')
      .replace(/;/g, '\\;');
  }

  function buildUrl() {
    var raw = val('in-url');
    if (!raw) return '';
    // A bare "example.com" scans as plain text on most readers, so promote it
    // to https:// — and say so, rather than changing the input silently.
    if (!HAS_SCHEME.test(raw) && LOOKS_LIKE_DOMAIN.test(raw)) {
      return 'https://' + raw;
    }
    return raw;
  }

  function buildWifi() {
    var ssid = val('in-wifi-ssid');
    if (!ssid) return '';

    var encryption = val('in-wifi-enc') || 'WPA';
    var password = val('in-wifi-pass');
    var parts = ['WIFI:', 'T:' + encryption + ';', 'S:' + escapeWifi(ssid) + ';'];

    if (encryption !== 'nopass' && password) {
      parts.push('P:' + escapeWifi(password) + ';');
    }
    if (checked('in-wifi-hidden')) {
      parts.push('H:true;');
    }
    return parts.join('') + ';';
  }

  function buildEmail() {
    var to = val('in-email-to');
    var subject = val('in-email-subject');
    var body = val('in-email-body');
    if (!to && !subject && !body) return '';

    var query = [];
    if (subject) query.push('subject=' + encodeURIComponent(subject));
    if (body) query.push('body=' + encodeURIComponent(body));

    return 'mailto:' + to + (query.length ? '?' + query.join('&') : '');
  }

  function buildSms() {
    var number = val('in-sms-number').replace(/[^\d+*#]/g, '');
    var body = val('in-sms-body');
    if (!number) return '';
    // SMSTO is the format with the widest reader support.
    return body ? 'SMSTO:' + number + ':' + body : 'SMSTO:' + number;
  }

  function buildTel() {
    var number = val('in-tel').replace(/[^\d+*#]/g, '');
    return number ? 'tel:' + number : '';
  }

  function buildVcard() {
    var first = val('in-vc-first');
    var last = val('in-vc-last');
    var org = val('in-vc-org');
    var title = val('in-vc-title');
    var phone = val('in-vc-phone');
    var email = val('in-vc-email');
    var url = val('in-vc-url');
    var note = val('in-vc-note');

    if (!(first || last || org || phone || email)) return '';

    var lines = ['BEGIN:VCARD', 'VERSION:3.0'];
    lines.push('N:' + escapeVcard(last) + ';' + escapeVcard(first) + ';;;');

    var display = (first + ' ' + last).trim();
    if (display) lines.push('FN:' + escapeVcard(display));
    if (org) lines.push('ORG:' + escapeVcard(org));
    if (title) lines.push('TITLE:' + escapeVcard(title));
    if (phone) lines.push('TEL;TYPE=CELL:' + escapeVcard(phone));
    if (email) lines.push('EMAIL;TYPE=INTERNET:' + escapeVcard(email));
    if (url) lines.push('URL:' + escapeVcard(url));
    if (note) lines.push('NOTE:' + escapeVcard(note));

    lines.push('END:VCARD');
    return lines.join('\n');
  }

  function buildGeo() {
    var lat = val('in-geo-lat');
    var lng = val('in-geo-lng');
    if (!lat || !lng) return '';
    if (!isFinite(Number(lat)) || !isFinite(Number(lng))) return '';
    return 'geo:' + Number(lat) + ',' + Number(lng);
  }

  var BUILDERS = {
    url: buildUrl,
    text: function () { var node = $('in-text'); return node ? node.value : ''; },
    wifi: buildWifi,
    email: buildEmail,
    sms: buildSms,
    tel: buildTel,
    vcard: buildVcard,
    geo: buildGeo
  };

  // ---------------------------------------------------------------------- //
  // Colour helpers — a QR code that does not scan is worse than no QR code.
  // ---------------------------------------------------------------------- //

  var HEX_RE = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i;

  function normaliseHex(value) {
    var hex = String(value).trim().toLowerCase();
    if (hex.charAt(0) !== '#') hex = '#' + hex;
    if (!HEX_RE.test(hex)) return null;
    if (hex.length === 4) {
      hex = '#' + hex[1] + hex[1] + hex[2] + hex[2] + hex[3] + hex[3];
    }
    return hex;
  }

  function relativeLuminance(hex) {
    var channels = [
      parseInt(hex.substr(1, 2), 16),
      parseInt(hex.substr(3, 2), 16),
      parseInt(hex.substr(5, 2), 16)
    ].map(function (value) {
      var c = value / 255;
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
  }

  function contrastRatio(a, b) {
    var la = relativeLuminance(a);
    var lb = relativeLuminance(b);
    var lighter = Math.max(la, lb);
    var darker = Math.min(la, lb);
    return (lighter + 0.05) / (darker + 0.05);
  }

  /** Return a scanning-reliability warning for the current settings, or ''. */
  function scanWarning() {
    var notes = [];
    var ratio = contrastRatio(state.fg, state.bg);

    if (relativeLuminance(state.fg) > relativeLuminance(state.bg)) {
      notes.push(
        'the pattern is lighter than its background — many readers will not ' +
        'decode an inverted code'
      );
    } else if (ratio < 4) {
      notes.push('contrast is only ' + ratio.toFixed(1) + ':1, which is low for reliable scanning');
    }

    if (state.margin < 4) {
      notes.push('a quiet zone below 4 modules can break scanning in print');
    }

    if (!notes.length) return '';
    return 'Heads up: ' + notes.join('; ') + '.';
  }

  // ---------------------------------------------------------------------- //
  // Rendering
  // ---------------------------------------------------------------------- //

  function qrOptions(extra) {
    var options = {
      errorCorrectionLevel: state.ecc,
      margin: state.margin,
      color: { dark: state.fg, light: state.bg }
    };
    for (var key in extra) {
      if (Object.prototype.hasOwnProperty.call(extra, key)) options[key] = extra[key];
    }
    return options;
  }

  function setStage(nextState) {
    el.stage.setAttribute('data-state', nextState);
    var ready = nextState === 'ready';
    el.btnPng.disabled = !ready;
    el.btnSvg.disabled = !ready;
    el.btnCopy.disabled = !ready;
    el.meta.hidden = !ready;
  }

  function showError(message) {
    current = null;
    el.error.textContent = message;
    el.error.hidden = false;
    el.warn.hidden = true;
    setStage('error');
  }

  function clearOutput() {
    current = null;
    el.error.hidden = true;
    el.warn.hidden = true;
    setStage('empty');
  }

  function render() {
    var payload = (BUILDERS[state.type] || BUILDERS.text)();

    updateUrlHint(payload);

    if (!payload) {
      clearOutput();
      return;
    }

    var symbol;
    try {
      symbol = QRCode.create(payload, { errorCorrectionLevel: state.ecc });
    } catch (err) {
      showError(
        'That content is too long for a single QR code at correction level ' +
        state.ecc + '. Shorten it, or drop to a lower correction level.'
      );
      return;
    }

    var modules = symbol.modules.size + state.margin * 2;
    // Integer module scaling only: fractional scaling produces uneven modules
    // and unreliable scans.
    var scale = Math.max(1, Math.round(state.size / modules));
    var exportPx = modules * scale;

    try {
      QRCode.toCanvas(el.canvas, payload, qrOptions({ width: PREVIEW_PX }));
    } catch (err) {
      showError('Could not draw the QR code in this browser.');
      return;
    }

    current = {
      payload: payload,
      scale: scale,
      modules: modules,
      version: symbol.version,
      exportPx: exportPx
    };

    el.error.hidden = true;
    el.metaVersion.textContent = String(symbol.version);
    el.metaModules.textContent = symbol.modules.size + '×' + symbol.modules.size;
    el.metaEcc.textContent = state.ecc + ' · ' + ECC_PERCENT[state.ecc];
    el.metaExport.textContent = exportPx + ' px';

    var warning = scanWarning();
    el.warn.textContent = warning;
    el.warn.hidden = !warning;

    el.canvas.setAttribute(
      'aria-label',
      'QR code, version ' + symbol.version + ', ' +
      symbol.modules.size + ' by ' + symbol.modules.size + ' modules'
    );

    setStage('ready');
  }

  function updateUrlHint(payload) {
    if (!el.urlHint || state.type !== 'url') return;
    var raw = val('in-url');
    if (raw && payload && payload !== raw && payload.indexOf('https://') === 0) {
      el.urlHint.textContent =
        'Encoding as ' + payload + ' — add http:// explicitly if you need it.';
    } else {
      el.urlHint.textContent =
        'The address is written into the code itself. No shortener, no tracking hop.';
    }
  }

  var renderTimer = null;
  function scheduleRender() {
    if (renderTimer) clearTimeout(renderTimer);
    renderTimer = setTimeout(render, RENDER_DEBOUNCE_MS);
  }

  // ---------------------------------------------------------------------- //
  // Downloads — built from a Blob in memory; nothing is uploaded.
  // ---------------------------------------------------------------------- //

  function timestamp() {
    var now = new Date();
    var pad = function (n) { return String(n).padStart(2, '0'); };
    return (
      now.getFullYear() + pad(now.getMonth() + 1) + pad(now.getDate()) + '-' +
      pad(now.getHours()) + pad(now.getMinutes()) + pad(now.getSeconds())
    );
  }

  function saveBlob(blob, filename) {
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    // Give the browser a moment to start the download before revoking.
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function flash(button, message) {
    var original = button.dataset.label || button.textContent;
    button.dataset.label = original;
    button.textContent = message;
    setTimeout(function () { button.textContent = original; }, 1600);
  }

  /** Draw the current code at export resolution onto a detached canvas. */
  function exportCanvas() {
    var canvas = document.createElement('canvas');
    QRCode.toCanvas(canvas, current.payload, qrOptions({ scale: current.scale }));
    return canvas;
  }

  function downloadPng() {
    if (!current) return;
    var canvas = exportCanvas();
    canvas.toBlob(function (blob) {
      if (!blob) {
        flash(el.btnPng, 'Export failed');
        return;
      }
      saveBlob(blob, 'qr-' + state.type + '-' + timestamp() + '.png');
    }, 'image/png');
  }

  function downloadSvg() {
    if (!current) return;
    QRCode.toString(
      current.payload,
      qrOptions({ type: 'svg', width: current.exportPx }),
      function (err, svg) {
        if (err) {
          flash(el.btnSvg, 'Export failed');
          return;
        }
        var blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
        saveBlob(blob, 'qr-' + state.type + '-' + timestamp() + '.svg');
      }
    );
  }

  function copyImage() {
    if (!current) return;
    if (!navigator.clipboard || typeof window.ClipboardItem === 'undefined') {
      flash(el.btnCopy, 'Not supported');
      return;
    }
    exportCanvas().toBlob(function (blob) {
      if (!blob) {
        flash(el.btnCopy, 'Copy failed');
        return;
      }
      var item = new window.ClipboardItem({ 'image/png': blob });
      navigator.clipboard.write([item]).then(
        function () { flash(el.btnCopy, 'Copied'); },
        function () { flash(el.btnCopy, 'Copy failed'); }
      );
    }, 'image/png');
  }

  // ---------------------------------------------------------------------- //
  // Option persistence — appearance settings only.
  //
  // The content of your codes is never written to storage, deliberately: a
  // shared or seized machine should not be able to reveal what you encoded.
  // ---------------------------------------------------------------------- //

  function saveOptions() {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
        ecc: state.ecc,
        size: state.size,
        margin: state.margin,
        fg: state.fg,
        bg: state.bg
      }));
    } catch (err) { /* non-fatal */ }
  }

  function loadOptions() {
    var stored;
    try {
      stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '{}');
    } catch (err) {
      return;
    }
    if (!stored || typeof stored !== 'object') return;

    if (ECC_PERCENT[stored.ecc]) state.ecc = stored.ecc;
    if (typeof stored.size === 'number' && stored.size >= 256 && stored.size <= 2048) {
      state.size = stored.size;
    }
    if (typeof stored.margin === 'number' && stored.margin >= 0 && stored.margin <= 10) {
      state.margin = stored.margin;
    }
    var fg = normaliseHex(stored.fg || '');
    var bg = normaliseHex(stored.bg || '');
    if (fg) state.fg = fg;
    if (bg) state.bg = bg;
  }

  function syncOptionControls() {
    el.eccButtons.forEach(function (button) {
      button.setAttribute('aria-checked', String(button.dataset.ecc === state.ecc));
    });
    el.size.value = state.size;
    el.sizeValue.textContent = state.size + ' px';
    el.margin.value = state.margin;
    el.marginValue.textContent = state.margin + (state.margin === 1 ? ' module' : ' modules');
    el.fg.value = state.fg;
    el.fgHex.value = state.fg;
    el.bg.value = state.bg;
    el.bgHex.value = state.bg;
  }

  // ---------------------------------------------------------------------- //
  // Wiring
  // ---------------------------------------------------------------------- //

  function selectTab(tab, focus) {
    el.tabs.forEach(function (candidate) {
      var selected = candidate === tab;
      candidate.setAttribute('aria-selected', String(selected));
      candidate.tabIndex = selected ? 0 : -1;
    });
    el.panels.forEach(function (panel) {
      panel.hidden = panel.id !== tab.getAttribute('aria-controls');
    });

    state.type = tab.dataset.type;
    if (focus) tab.focus();

    var panel = document.getElementById(tab.getAttribute('aria-controls'));
    var firstInput = panel && panel.querySelector('input, textarea, select');
    if (firstInput && focus) firstInput.focus();

    render();
  }

  function initTabs() {
    el.tabs.forEach(function (tab) {
      tab.addEventListener('click', function () { selectTab(tab, false); });
    });

    el.tablist.addEventListener('keydown', function (event) {
      var index = el.tabs.indexOf(document.activeElement);
      if (index === -1) return;

      var next = null;
      if (event.key === 'ArrowRight') next = el.tabs[(index + 1) % el.tabs.length];
      else if (event.key === 'ArrowLeft') next = el.tabs[(index - 1 + el.tabs.length) % el.tabs.length];
      else if (event.key === 'Home') next = el.tabs[0];
      else if (event.key === 'End') next = el.tabs[el.tabs.length - 1];

      if (next) {
        event.preventDefault();
        selectTab(next, true);
      }
    });
  }

  function initFields() {
    el.fields.forEach(function (field) {
      var eventName = field.type === 'checkbox' || field.tagName === 'SELECT' ? 'change' : 'input';
      field.addEventListener(eventName, scheduleRender);
    });
  }

  function initOptions() {
    el.eccButtons.forEach(function (button) {
      button.addEventListener('click', function () {
        state.ecc = button.dataset.ecc;
        syncOptionControls();
        saveOptions();
        render();
      });
    });

    el.size.addEventListener('input', function () {
      state.size = Number(el.size.value);
      el.sizeValue.textContent = state.size + ' px';
      saveOptions();
      scheduleRender();
    });

    el.margin.addEventListener('input', function () {
      state.margin = Number(el.margin.value);
      el.marginValue.textContent =
        state.margin + (state.margin === 1 ? ' module' : ' modules');
      saveOptions();
      scheduleRender();
    });

    bindColour(el.fg, el.fgHex, 'fg');
    bindColour(el.bg, el.bgHex, 'bg');

    el.reset.addEventListener('click', function () {
      state.ecc = DEFAULTS.ecc;
      state.size = DEFAULTS.size;
      state.margin = DEFAULTS.margin;
      state.fg = DEFAULTS.fg;
      state.bg = DEFAULTS.bg;
      syncOptionControls();
      saveOptions();
      render();
    });
  }

  function bindColour(picker, hexInput, key) {
    picker.addEventListener('input', function () {
      state[key] = picker.value.toLowerCase();
      hexInput.value = state[key];
      saveOptions();
      scheduleRender();
    });

    hexInput.addEventListener('input', function () {
      var hex = normaliseHex(hexInput.value);
      if (!hex) return; // wait until it parses; do not fight the typist
      state[key] = hex;
      picker.value = hex;
      saveOptions();
      scheduleRender();
    });

    hexInput.addEventListener('blur', function () {
      hexInput.value = state[key]; // discard a half-typed value
    });
  }

  function initActions() {
    el.btnPng.addEventListener('click', downloadPng);
    el.btnSvg.addEventListener('click', downloadSvg);
    el.btnCopy.addEventListener('click', copyImage);
  }

  function init() {
    loadOptions();
    syncOptionControls();
    initTabs();
    initFields();
    initOptions();
    initActions();
    setStage('empty');
    render();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

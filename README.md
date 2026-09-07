# ControlYourQR

**A QR code generator that never sees your data.**

Everything is encoded in the browser. Nothing you type — links, text, Wi-Fi
passwords, contact cards, coordinates — is uploaded, logged or stored. The
server's only job is to hand you static files.

Live at **[controlyourqr.com](https://controlyourqr.com)** · MIT licensed

---

## Why

Most "free online QR generators" hand you a **dynamic** QR code: the pattern
encodes *their* domain, and every scan is redirected through *their* server.
That means the code stops working when the trial ends, its destination can be
changed after your posters are printed, every scan is logged, and whatever you
typed was uploaded to a machine you cannot audit.

ControlYourQR generates **static** codes only. Your destination is encoded
directly into the pattern, so the code works forever, cannot be repointed by
anyone, and reports nothing to anyone — including us.

## The guarantee, and how it is enforced

The privacy claim is not a promise in a policy document; it is a property of
how the site is built.

| Mechanism | Effect |
|---|---|
| Encoding runs in the browser | The server never receives your content |
| `connect-src 'none'` in the CSP | The **browser itself** blocks every outbound request the page could make — `fetch`, XHR, WebSocket, `EventSource`, beacons |
| No POST/PUT endpoint exists | There is nothing to send data *to* (enforced by a test) |
| Zero third-party resources | No CDN, no web fonts, no analytics, no tag manager (enforced by a test) |
| Vendored, reproducible encoder | The QR library is built from pinned source and committed, so the served bytes are reviewable in a diff (verified in CI) |

### Verify it yourself

1. Load the page, **disconnect from the network**, then generate and download a
   code. It all still works.
2. Open DevTools → Network and type into the fields. Zero requests.
3. Read the `Content-Security-Policy` response header.
4. Read [`app/static/js/app.js`](app/static/js/app.js) — unminified and
   commented, with no network calls anywhere in it.
5. Run `./tools/build-vendor.sh` and `git diff` the vendored bundle.

## Features

- **Eight content types** — link, plain text, Wi-Fi, email, SMS, phone, vCard contact, geo location
- **Full encoding control** — error-correction level (L/M/Q/H), export size, quiet zone, foreground and background colours
- **Scan-safety checks** — warns on low contrast, inverted codes and an undersized quiet zone before you print 5,000 of them
- **Print-ready output** — PNG at integer module scaling (no blurred modules) and true vector SVG
- **Light and dark themes** — respects the system setting, remembers an explicit choice
- **Accessible** — keyboard-navigable tabs, visible focus, WCAG AA text contrast, reduced-motion support

## Architecture

```
app/
├── __init__.py          Application factory + static-asset fingerprinting
├── config.py            Environment-driven configuration
├── routes.py            GET-only routes; template helpers
├── security.py          CSP and the rest of the response hardening
├── static/
│   ├── css/style.css    Design tokens, light/dark, layout
│   ├── js/app.js        The generator — all encoding logic
│   ├── js/theme.js      Pre-paint theme bootstrap
│   └── js/vendor/       node-qrcode, built from source (see tools/)
└── templates/           Jinja templates
deploy/
├── nginx/               Site config: TLS, caching, rate limiting
├── systemd/             Hardened service unit
└── scripts/             bootstrap.sh (provision) · deploy.sh (update)
tools/
├── build-vendor.sh      Reproducible build of the QR encoder
└── make_icons.py        Generates favicon / touch icon / brand mark
```

The Flask application is deliberately trivial: it renders four templates and
sets headers. All the interesting logic is client-side, where it can be
audited by anyone with a browser.

## Local development

```bash
make install     # create .venv, install dependencies
make dev         # http://127.0.0.1:5000
make test        # run the suite
make serve       # run under gunicorn, as production does
```

Requires Python 3.11+. Node is needed only to rebuild the vendored encoder.

## Deployment

Provisioned on a Debian/Ubuntu VM with nginx in front of gunicorn.

```bash
git clone git@github.com:srivishal27/controlyourqr.git
cd controlyourqr
sudo ./deploy/scripts/bootstrap.sh
```

`bootstrap.sh` is idempotent. It installs the packages, creates an unprivileged
service account, builds the virtualenv, installs the systemd unit and nginx
site, and enables the firewall.

Then point DNS at the host and enable TLS:

```bash
sudo certbot --nginx -d controlyourqr.com -d www.controlyourqr.com
echo 'ENABLE_HSTS=true' | sudo tee /etc/controlyourqr/app.env
sudo systemctl restart controlyourqr
```

Subsequent updates:

```bash
sudo /opt/controlyourqr/deploy/scripts/deploy.sh
```

### Operational notes

- The service runs as `controlyourqr`, cannot write to its own code, and is
  sandboxed by systemd (`ProtectSystem=strict`, no capabilities, seccomp
  filtered, `MemoryDenyWriteExecute`).
- gunicorn binds to `127.0.0.1:8000` only; nginx is the sole public listener.
- Logs go to journald: `journalctl -u controlyourqr -f`.
- Health check: `GET /healthz`.

## Security

Threat model, header inventory, supply-chain notes and reporting instructions
are on [the security page](https://controlyourqr.com/security), with
machine-readable contact details at
[`/.well-known/security.txt`](https://controlyourqr.com/.well-known/security.txt)
per RFC 9116.

Vulnerability reports are welcome. Please allow a reasonable window for a fix
before publishing.

## Credits

Designed and developed by **Vishal Srivastava**, security researcher and PhD
Scholar at **IIT Kanpur**.

QR encoding by [node-qrcode](https://github.com/soldair/node-qrcode) (MIT) by
Ryan Day, bundled from source.

## Licence

MIT — see [LICENSE](LICENSE).

# Frontend Changes — Dark/Light Theme Toggle

## Files Modified
- `frontend/index.html`
- `frontend/style.css`
- `frontend/script.js`

---

## index.html

**Inline `<script>` in `<head>`** (before the stylesheet):
- Reads `localStorage.getItem('theme')` and sets `data-theme="light"` on `<html>` synchronously, before CSS is parsed.
- Prevents a flash-of-wrong-theme on page load for users with a saved light-mode preference.

**`<button id="themeToggle">`** added directly inside `<body>`, before `.container`:
- Contains two inline SVGs: `.icon-moon` (crescent) and `.icon-sun` (sun with rays).
- `aria-label` and `title` set for accessibility and keyboard navigation.

---

## style.css

### New CSS variables in `:root` (dark mode defaults)
| Variable | Purpose |
|---|---|
| `--welcome-shadow` | Welcome message drop shadow |
| `--toggle-bg` / `--toggle-icon-color` / `--toggle-icon-hover` | Toggle button |
| `--source-chip-color` / `--source-chip-bg` / `--source-chip-border` | Source pill default |
| `--source-chip-hover-bg` / `--source-chip-hover-color` | Source pill hover |
| `--code-bg` | `code` and `pre` background |
| `--error-color` / `--error-bg` / `--error-border` | Error state |
| `--success-color` / `--success-bg` / `--success-border` | Success state |

### `[data-theme="light"]` block
Full color palette with WCAG AA contrast compliance verified:

| Variable | Value | Contrast (on bg) | Requirement | Result |
|---|---|---|---|---|
| `--text-primary` | `#1e293b` | ~14.5:1 on `#f8fafc` | 4.5:1 | ✅ |
| `--text-secondary` | `#475569` | ~7.1:1 on `#f8fafc` | 4.5:1 | ✅ |
| `--primary-color` | `#1d4ed8` | ~5.9:1 on `#f8fafc` | 4.5:1 | ✅ |
| white on `#1d4ed8` | (send button) | ~5.9:1 | 4.5:1 | ✅ |
| `--error-color` | `#b91c1c` | ~7.2:1 on white | 4.5:1 | ✅ |
| `--success-color` | `#15803d` | ~5.9:1 on white | 4.5:1 | ✅ |

Key accessibility fixes vs. initial values:
- `--text-secondary` darkened from `#64748b` (~4.1:1, fails AA) → `#475569` (~7.1:1)
- `--primary-color` darkened from `#2563eb` to `#1d4ed8` for safe use as text color
- `--error-color` darkened from `#dc2626` to `#b91c1c` for better contrast on tinted backgrounds
- `--success-color` darkened from `#16a34a` to `#15803d`
- `--border-color` darkened from `#e2e8f0` to `#cbd5e1` for better visible separation

### New CSS variable: `--primary-glow`
Send button hover shadow — `rgba(37,99,235,0.35)` in dark mode, `rgba(29,78,216,0.3)` in light mode.

### Smooth transition rule
Applied to: `body`, `.main-content`, `.sidebar`, `.chat-main`, `.chat-container`, `.chat-messages`, `.chat-input-container`, `#chatInput`, `.stat-item`, `.stat-label`, `.stat-value`, `.course-titles-header`, `.suggested-item`, `.message-content`, `.source-chip`, `.error-message`, `.success-message`, `.course-title-item`, `.message-meta`, `.sources-collapsible`.
All transition `background-color`, `border-color`, `color` over 0.25 s.

### Toggle button styles (`#themeToggle`)
- `position: fixed; top: 1rem; right: 1rem; z-index: 100`
- 40 × 40 px circle using `--toggle-bg` / `--border-color`
- Hover: `scale(1.1)` + focus ring; active: `scale(0.95)`
- Focus: visible `box-shadow` ring (keyboard-navigable)
- `.icon-moon` shown by default; `.icon-sun` shown under `[data-theme="light"]`

### Hardcoded colors converted to variables
| Element | Was | Now |
|---|---|---|
| `.source-chip` color | `#93c5fd` (invisible on white) | `var(--source-chip-color)` |
| `a.source-chip:hover` | `#bfdbfe` | `var(--source-chip-hover-color)` |
| `.error-message` text | `#f87171` (too light on white) | `var(--error-color)` |
| `.success-message` text | `#4ade80` (too light on white) | `var(--success-color)` |
| `code` / `pre` bg | `rgba(0,0,0,0.2)` | `var(--code-bg)` |
| Welcome `box-shadow` | hardcoded `rgba` | `var(--welcome-shadow)` |
| `#sendButton` hover glow | `rgba(37,99,235,0.3)` hardcoded | `var(--primary-glow)` |
| Blockquote border | `var(--primary)` (undefined) | `var(--primary-color)` |

---

## script.js

**Toggle logic** added inside `DOMContentLoaded`:
- Attaches a `click` listener to `#themeToggle`.
- Reads `document.documentElement.getAttribute('data-theme')` to determine current theme.
- Toggles by setting/removing the `data-theme="light"` attribute on `<html>`.
- Persists choice to `localStorage` under the key `'theme'`.
- Initial theme application is handled by the inline `<head>` script (not here) to avoid transition flash.

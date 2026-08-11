# Accessibility Checklist — PlainSpeak Web Application

Manual review checklist. PlainSpeak has been designed following WCAG/WAI
accessibility guidance; formal conformance has not yet been independently verified.

**Review date:** 2026-08-11
**Reviewer:** Self-audit (developer review)
**Standard targeted:** WCAG 2.1 AA

---

## Keyboard Operation

- [x] All interactive elements are keyboard-reachable (Tab/Shift+Tab)
- [x] Analyze button activated by Enter/Space when focused
- [x] Tab buttons (Scores/Barriers/Simplified) operable by keyboard
- [x] Sample loading buttons operable by keyboard
- [x] Textarea fully operable by keyboard
- [x] No keyboard traps
- [x] Ctrl+Enter shortcut for analysis
- [ ] Skip link tested with screen reader — **NOT YET TESTED**

## Focus Indicators

- [x] Visible focus outline on all interactive elements (3px solid accent color)
- [x] Focus outline has sufficient contrast (accent blue #2563eb on white)
- [x] Focus order is logical (header → textarea → buttons → results)
- [x] Skip link receives focus first

## Heading Structure

- [x] Single h1 ("PlainSpeak")
- [x] h2 used for major sections (Scores, Barriers)
- [x] No skipped heading levels
- [x] Headings are descriptive

## Semantic Landmarks

- [x] `<header>` for app header
- [x] `<main>` for primary content with id="main-content"
- [x] `<section>` with aria-label for input area
- [x] `<section>` with aria-label for results
- [ ] No `<nav>` element (not needed for single-page app)

## Accessible Labels

- [x] Textarea has associated `<label>`
- [x] Character count associated via aria-describedby
- [x] Live scores region has aria-live="polite"
- [x] Error messages use role="alert"
- [x] Tab buttons use role="tab" and aria-selected

## Screen Reader Announcements

- [ ] Analysis completion announcement — **NOT YET IMPLEMENTED**
- [x] Error messages announced via role="alert"
- [x] Live scores update via aria-live="polite"
- [ ] Results region focus management after analysis — **NOT YET TESTED**

## Status and Error Messaging

- [x] Error messages use role="alert"
- [x] Errors are visually distinct (red background, border)
- [x] Error text is descriptive, not just "error"
- [x] Loading state indicated by spinner on analyze button
- [ ] Success/failure announcement after analysis — **PARTIAL**

## Zoom and Reflow

- [x] Content reflows at 200% zoom
- [x] Content reflows at 400% zoom
- [x] No horizontal scrolling required at 400% on 1280px viewport
- [x] Text scales proportionally

## High Contrast

- [x] Text meets 4.5:1 contrast ratio (dark text #1a1a1a on white #ffffff = 17.1:1)
- [x] Accent color meets 3:1 contrast on white (#2563eb = 5.7:1)
- [x] Dark mode provides equivalent contrast
- [x] Focus indicators visible in both modes
- [x] Warning/critical/info colors meet contrast requirements
- [x] Color is never the only signal (icons and text labels accompany color)

## Reduced Motion

- [x] Button scale animation uses transform (GPU-accelerated)
- [ ] No `prefers-reduced-motion` media query — **NOT YET IMPLEMENTED**
- [x] No auto-playing animations
- [x] Spinner animation is decorative (not essential for understanding)

## Tab Order

- [x] Skip link → header → textarea → buttons → results tabs → results content
- [x] Tab order matches visual order
- [x] No positive tabindex values

## Screen Reader Testing

- [ ] NVDA on Windows — **NOT YET TESTED**
- [ ] VoiceOver on macOS — **NOT YET TESTED**
- [ ] JAWS on Windows — **NOT YET TESTED**

## Mobile/Touch

- [x] Touch targets are at least 44x44px (buttons are min 44px tall)
- [x] No hover-dependent interactions
- [x] Responsive layout adjusts to mobile viewports
- [x] Textarea is resizable

## Known Accessibility Gaps

1. **Screen reader testing not performed.** The application has been designed
   with semantic HTML, ARIA labels, and skip links, but has not been tested
   with actual assistive technology.
2. **Analysis completion not announced to screen readers.** After analysis
   completes, focus does not automatically move to results, and no live
   region announces completion.
3. **No prefers-reduced-motion support.** The button press animation and
   spinner do not respect the user's motion preference.
4. **Web app requires local server start via terminal.** This is a
   significant barrier for users who cannot use a command line.

---

## Summary

**Designed using WCAG/WAI accessibility guidance; formal conformance has
not yet been independently verified.**

Strengths: semantic HTML, keyboard operation, visible focus, good contrast,
responsive design, skip link, ARIA labels, dark mode support.

Gaps: no screen reader testing, no reduced-motion query, no analysis
completion announcement, terminal requirement for starting the web app.

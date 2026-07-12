# One Invoice Intelligence

A polished, cinematic front-end for **UPS Invoice Intelligence** — a hub for four
specialized AI agents that **explain, resolve, simulate and prevent** logistics
billing charges. It pairs a warm UPS-inspired light theme (deep brown + gold)
with looping video, glassy cards, fluid page transitions and a production-style
chat workspace for each agent.

> This is a **front-end demo**. Agent replies are canned/simulated locally —
> there is no backend. See [Wiring up a backend](#wiring-up-a-backend).

## Tech stack

- **React 18 + Vite** — fast dev server and build
- **React Router v6** — landing page + per-agent routes
- **Tailwind CSS** — design system, custom UPS palette, keyframe animations
- **Framer Motion** — entrance, hover and page transitions
- **GSAP + Lenis** — smooth scrolling synced to `ScrollTrigger`
- **React Three Fiber + Drei + Postprocessing** — WebGL scene components are
  included (`src/components/canvas/`) but are **not currently mounted** by any
  page (kept for reference / optional re-enable)

## Getting started

> Requires **Node.js 18+** and npm. Install Node from https://nodejs.org if the
> commands below aren't recognized.

```bash
npm install
npm run dev      # dev server at http://localhost:5173 (opens automatically)
npm run build    # production build → dist/
npm run preview  # preview the production build
```

## What's in the app

### Landing page (`/`)
- **Hero** — a full-width looping cinematic video (`public/hero.mp4`). It tries
  to play once with sound, then mutes; browsers that block unmuted autoplay fall
  back to muted playback and unmute on the first user interaction.
- **Agents section** — four responsive, cursor-tilting agent cards. Clicking a
  card fires a cinematic "morph & zoom" overlay that expands from the card,
  navigates, then dissolves into the agent's workspace.

### Agent workspace (`/agent/:slug`)
- Full-screen, app-like chat environment with a subtle looping logistics
  background (per-agent video with an animated gradient fallback).
- **ChatPanel** — persistent sidebar (new chat, conversation history, agent
  switcher), a large conversation area with typing indicator, suggested prompts
  and agent-flavored canned responses.
- The **Prevent Agent** additionally shows a searchable "Invoices with issues"
  side panel; tapping an invoice sends it into the conversation for review.

## The four agents

Defined centrally in [src/data/agents.js](src/data/agents.js):

| Agent | Role | Purpose |
| --- | --- | --- |
| **Explain** | Billing Analyst | Breaks down every invoice charge and shows how it was calculated |
| **Resolve** | Dispute Specialist | Validates shipment/contract/rate-card data and recommends dispute resolutions |
| **Simulate** | Pricing Analyst | "What-if" cost analysis — recalculates and compares shipping scenarios |
| **Prevent** | Risk & Compliance | Flags billing anomalies and dispute risks before invoices are issued |

Each agent entry carries its `name`, `role`, `tagline`, `description`, accent
color, `greeting`, input `placeholder`, `stats`, suggested `prompts` (and, for
Prevent, a list of flagged `issues`).

## Project structure

```
index.html                  Fonts, meta, #root mount
vite.config.js              Vite + React plugin, manual chunks
tailwind.config.js          UPS palette, fonts, keyframes/animations
postcss.config.js           Tailwind + autoprefixer

src/
  main.jsx                  App bootstrap wrapped in <BrowserRouter>
  App.jsx                   Shell: loader, navbar, routes, transitions, smooth scroll
  index.css                 Global design system (theme, cursor, utilities)

  data/agents.js            Single source of truth for the 4 agents + platform stats

  hooks/
    useMousePosition.js     Normalized mouse position for parallax
    useSmoothScroll.js      Lenis + GSAP ScrollTrigger integration (exposes window.__lenis)

  pages/
    Home.jsx                Hero + AgentsSection + footer
    AgentPage.jsx           VideoBackground + ChatPanel for :slug (redirects if unknown)

  components/
    sections/
      Hero.jsx              Looping hero video + "Explore Agents" CTA
      AgentsSection.jsx     Scroll-revealed heading + grid of agent cards
      AgentCard.jsx         3D tilt, cursor glow, launch transition
      VideoBackground.jsx   Per-agent looping video with animated gradient fallback
      Intro.jsx             Scroll-linked storytelling section (not mounted)
      Dashboard.jsx         Stats dashboard (not mounted)
    chat/
      ChatPanel.jsx         Full chat workspace (sidebar, history, input, issues panel)
      Message.jsx           Single chat bubble
      TypingIndicator.jsx   Animated "typing…" dots
      SuggestedPrompts.jsx  Clickable starter prompts
    ui/
      Navbar.jsx            Top navigation (hidden on agent pages)
      Loader.jsx            Simulated boot / loading screen
      Cursor.jsx            Custom cursor
      MagneticButton.jsx    Pointer-attracted button
      TransitionProvider.jsx  "Morph & zoom" transition context (useTransition/launch)
      AgentIcon.jsx         Per-agent SVG icons
      UpsLogo.jsx           UPS shield logo
    canvas/                 WebGL scene (Scene, ParticleField, LightBeams,
                            FloatingGlass, LogisticsNetwork, Effects) —
                            present but not imported by any page

public/
  hero.mp4                  Landing hero video (add your own)
  videos/{slug}.mp4         Optional per-agent background videos
```

## User journey

```
Hero video → "Explore Agents" (smooth scroll) → Agent cards →
click a card → morph/zoom transition → Agent chat workspace
```

- Smooth scrolling is powered by Lenis, wired into GSAP's ticker so
  `ScrollTrigger` stays in sync. Programmatic scrolls use `window.__lenis`.
- The card-to-page transition is provided by `TransitionProvider`: a card calls
  `launch(to, origin, color)`, an overlay expands from the card's center,
  navigation happens mid-expansion, then the overlay dissolves.

## Customization

- **Agents:** edit [src/data/agents.js](src/data/agents.js) — name, role,
  tagline, description, accent color, greeting, placeholder, stats and prompts.
- **Hero video:** replace `public/hero.mp4`.
- **Agent background videos:** drop `public/videos/{slug}.mp4` (falls back to an
  animated gradient when absent). See [public/videos/README.md](public/videos/README.md).
- **Theme:** adjust the UPS palette, fonts, shadows and keyframes in
  [tailwind.config.js](tailwind.config.js) and global styles in
  [src/index.css](src/index.css).

## Wiring up a backend

Agent responses are simulated in [src/components/chat/ChatPanel.jsx](src/components/chat/ChatPanel.jsx)
via a `CANNED` map keyed by agent slug. To connect a real API, replace the
`respondTo()` logic that picks a canned reply with an async call to your
service, then append the returned message to the active session.

## Build & performance notes

- `vite.config.js` splits `framer-motion` + `gsap` into a separate `motion`
  chunk to keep the main bundle lean.
- UI/text paints immediately; heavy WebGL is intentionally not mounted.
- Smooth scroll and custom cursor are designed to degrade gracefully on touch /
  reduced-motion contexts.
```

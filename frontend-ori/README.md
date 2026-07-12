# AI Agent Hub

A futuristic, cinematic single-page experience and entry point for four
specialized AI agents. Built to feel like a next-generation AI operating system:
dark glassmorphism, soft neon accents, an interactive WebGL environment, smooth
scroll-based storytelling and fluid page transitions.

## Tech stack

- **React 18 + Vite** — fast, modern build
- **Tailwind CSS** — design system & utilities
- **React Three Fiber + Drei + Postprocessing** — WebGL scene (particles,
  floating glass, light beams, bloom, depth-of-field)
- **GSAP + Lenis** — smooth scrolling synced to ScrollTrigger
- **Framer Motion** — entrance/hover/page transitions
- **React Router** — home + per-agent routes

## Getting started

> Requires **Node.js 18+** and npm. Install Node from https://nodejs.org if the
> commands below aren't recognized.

```bash
npm install
npm run dev      # start dev server at http://localhost:5173
npm run build    # production build → dist/
npm run preview  # preview the production build
```

## Project structure

```
src/
  main.jsx                 App bootstrap + Router
  App.jsx                  Shell: loader, cursor, navbar, routes, transitions
  index.css                Design system (glass, neon, gradients, cursor)
  data/agents.js           Single source of truth for the 4 agents
  hooks/
    useMousePosition.js    Normalized mouse for parallax
    useSmoothScroll.js     Lenis + GSAP ScrollTrigger integration
  components/
    canvas/                WebGL scene
      Scene.jsx            Canvas + camera rig (scroll/mouse driven)
      ParticleField.jsx    Shader particle field
      FloatingGlass.jsx    Transmission glass panels
      LightBeams.jsx       Animated volumetric beams
      Effects.jsx          Bloom / DoF / grain / vignette (quality-aware)
    sections/              Home page sections
      Hero.jsx             Full-screen animated headline
      Intro.jsx            Scroll-linked storytelling
      AgentsSection.jsx    Grid of agent cards
      AgentCard.jsx        3D tilt + glow + launch transition
      VideoBackground.jsx  Looping video w/ animated fallback
    chat/                  Agent chat UI
      ChatPanel.jsx        Message flow, typing, prompts, input
      Message.jsx / TypingIndicator.jsx / SuggestedPrompts.jsx
    ui/
      Navbar.jsx  Cursor.jsx  Loader.jsx  MagneticButton.jsx
      AgentIcon.jsx  TransitionProvider.jsx
  pages/
    Home.jsx               Scene + Hero + Intro + Agents
    AgentPage.jsx          Immersive per-agent environment + chat
```

## Storytelling scroll journey

`Hero → 3D camera dolly → System intro → Floating agent cards → Selection →
cinematic morph transition → Agent environment`

The camera in `Scene.jsx` eases along a path driven by normalized scroll
progress and mouse parallax. Clicking an agent triggers a radial "morph & zoom"
overlay (`TransitionProvider`) that expands from the card, navigates, then
dissolves into the agent's page.

## Customization

- **Agents:** edit `src/data/agents.js` (name, role, description, accent color,
  greeting, suggested prompts).
- **Videos:** add `public/videos/{slug}.mp4` — see that folder's README.
- **Chat backend:** replace the canned `respond()` logic in
  `components/chat/ChatPanel.jsx` with a real API call.
- **Theme:** tweak colors, glows and gradients in `tailwind.config.js` and
  `src/index.css`.

## Performance

- WebGL scene is lazy-loaded so text/UI paint instantly.
- `PerformanceMonitor` + `AdaptiveDpr` drop to a lighter effect stack on weaker
  GPUs; particle count scales with quality.
- Additive shaders instead of heavy geometry; no external 3D models.
- Custom cursor and smooth scroll disable gracefully on touch / reduced-motion.
```

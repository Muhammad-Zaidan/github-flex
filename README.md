# GitHub Flex

Flex your GitHub progress. Enter any username and get an aesthetic, shareable stats card — sized for Instagram/TikTok Stories (9:16) and feed posts (4:5).

**What's on the card**

- Rank (C → S+) with a score out of 100 and a fun title (*Streak Demon*, *Star Collector*, …)
- Core stats: contributions, stars, followers, repos, forks
- Contribution heatmap for the last year, longest & current streak
- Top languages and top repos
- 4 color themes: Aurora, Ember, Mint, Mono

**Sharing**

- **Download PNG** — 1080×1920 (Story) or 1080×1350 (Post)
- **Share** — native share sheet on mobile (sends the image), clipboard on desktop
- **𝕏 Post** and **Copy link** — links are shareable: `?u=<username>&f=story&t=aurora`

## Develop

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # outputs to dist/
```

Stack: React 18 + Vite, `html-to-image` for PNG export, self-hosted Inter & JetBrains Mono.

## Data sources

- GitHub REST API (public, no token — limited to 60 requests/hour per visitor IP; each lookup uses 2–4)
- Contribution calendar from [github-contributions-api](https://github.com/grubersjoe/github-contributions-api)

## Deploy

Pushing to `main` deploys to GitHub Pages via `.github/workflows/deploy.yml`.
One-time setup: **Settings → Pages → Build and deployment → Source: GitHub Actions**.

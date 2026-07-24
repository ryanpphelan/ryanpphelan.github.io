# ryanphelan.com

The personal site of Ryan Phelan — The Strongbow Group LLC.
Static, multi-page, hand-built. No framework, no build step. It just deploys.

## Pages
- `index.html` — Home (the animated "flip" hero, the Clarity Gap, the method, the three offers)
- `approach.html` — The Approach (Clarity Gap + Go-to-Market Alignment, with the custom diagrams)
- `services.html` — Ways to Work Together (The Clarity Sprint, Fractional CMO, Hands-On Execution)
- `about.html` — About
- `contact.html` — Contact (OnceHub booking + email)
- `404.html` — Not-found page
- `styles.css` — all styling · `script.js` — hero flip + mobile nav
- `diagram-alignment.svg`, `diagram-gap.svg` — the custom graphics
- `CNAME` — custom domain (ryanphelan.com) · `.nojekyll` — tells Pages to serve files as-is

## Preview locally
Open `index.html` in a browser, or run a tiny server so relative paths behave:
```
cd ryanphelan-site
python3 -m http.server 8080
# then visit http://localhost:8080
```

## Go live on GitHub Pages (ryanphelan.com)
1. Create a new **empty** repo on GitHub (e.g. `ryanphelan-site`). Don't add a README — this repo already has one.
2. From this folder, push it up:
   ```
   git remote add origin https://github.com/<your-username>/ryanphelan-site.git
   git branch -M main
   git push -u origin main
   ```
3. On GitHub: **Settings → Pages → Build and deployment → Source: “Deploy from a branch”**, branch `main`, folder `/ (root)`. Save.
4. **Settings → Pages → Custom domain**: enter `ryanphelan.com` and save. (The `CNAME` file is already in the repo.)
5. At your domain registrar, point DNS at GitHub Pages:
   - **Apex `ryanphelan.com`** — four `A` records:
     `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
     (and, if you want IPv6, the matching `AAAA` records from GitHub's docs).
   - **`www`** — a `CNAME` record pointing to `<your-username>.github.io`.
   > These are GitHub's published Pages IPs; confirm they're current at
   > docs.github.com → Pages → “Managing a custom domain” before you rely on them.
6. Back in **Settings → Pages**, tick **Enforce HTTPS** once the certificate finishes provisioning (can take a little while after DNS resolves).

That's it — the site is live.

## The booking calendar (OnceHub)
`contact.html` embeds `https://oncehub.com/ryanphelan` in an iframe, and the **Open the calendar** button opens it in a new tab as a guaranteed fallback. If OnceHub blocks the inline frame, grab your official embed code from
**OnceHub → your booking page → Share & embed → Website embed** and paste it where the comment marks it in `contact.html`. To add the intake questions (what's going on / company / stage), set those as custom fields on the OnceHub booking page.

## Editing later
Everything is plain HTML/CSS. To change copy, edit the `.html` file and commit — Pages redeploys on push. The nav, footer, and fonts are duplicated in each page's markup (no template engine), so a global change means the same small edit in each file.

## The hero flip
The headline cycles the subject — customers → your salespeople → your board → your analysts — and settles on **the market**, then stops. It respects `prefers-reduced-motion` (users who ask for less motion get the static sentence), and the real sentence is in the HTML for SEO. Edit the word list at the top of `script.js`.

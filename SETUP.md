# Setup checklist — Jarvis-J-Jacob

Everything in this repo already has your username, name, LinkedIn, and Codeforces
links filled in, and the accent color is purple (`#a855f7`) throughout. Here's
what's left, in order.

## 0. The magic repo

Create a GitHub repo named **exactly** `Jarvis-J-Jacob` (must match your username
character-for-character). Public. Tick "Add a README" so it's not empty.

## 1. Your photo (private step — you run this locally)

You said you'd rather choose the photo yourself, so this repo doesn't include one.
Locally:

```bash
pip install pillow
python scripts/dotify.py your-photo.jpg -o assets/portrait --cols 100 --equalize --detail 0.5 --color --reveal
```

Tips from the guide, still true here:
- `--reveal` makes the dots fade in row by row when the page loads. Drop it for a
  static portrait.
- `--equalize` is not optional — without it faces collapse into one flat blob.
- Cut yourself out of the background first (any background remover) and save as a
  transparent PNG. The script treats the alpha channel as a subject mask, so only
  you get measured and drawn — no background noise.
- `--cols 100` is a good balance (~300KB). Go to 130 only if you don't mind a
  larger file.
- Open `preview.html` in a browser to check dark and light before you commit
  anything.

## 2. Fill in your real content

- **`assets/skills.json`** — the values I put in are placeholders (student-level
  guesses). Rate yourself honestly, 0–100.
- **`assets/projects.json`** — replace `PROJECT_ONE` through `PROJECT_FOUR` with
  four of your actual repo names, and write a one-line pitch for each (not a
  commit-message description — a pitch).
- **`README.md`** — search for `#your-latest-project` and the two placeholder
  bullets under "who's writing this" and write your actual currently-building project and
  fun fact. Also update the four `PROJECT_*` references in the table and card
  links to match whatever you put in `projects.json`.

## 3. One GitHub setting (this is where it usually breaks)

**Let Actions write to your repo:**
Repo → Settings → Actions → General → Workflow permissions → **Read and write
permissions** → Save.

That's the only required setting. Every chart is drawn from GitHub's own API
using the automatic `GITHUB_TOKEN`, so no personal access token is needed.

<sub>Optional: if you ever want private-repo contributions counted too, make a
classic token with `repo` + `read:user` scope and add it as a repo secret named
`METRICS_TOKEN`. The workflows pick it up automatically if it exists.</sub>

## 4. Push and light the fuse

```bash
git init && git branch -M main
git add -A
git commit -m "profile readme"
git remote add origin https://github.com/Jarvis-J-Jacob/Jarvis-J-Jacob.git
git push -u origin main
```

Then: Actions tab → enable workflows on the banner. Both workflows (`snake` and
`charts-and-cards`) run themselves on this first push — no manual dispatch
needed. First runs take a couple of minutes; after that they run on every push
to `main` and on their schedules.

## Checklist

- [ ] Repo named exactly `Jarvis-J-Jacob`, public
- [ ] Portrait generated privately and committed to `assets/`
- [ ] `assets/skills.json` filled with real self-ratings
- [ ] `assets/projects.json` filled with 4 real repos
- [ ] README placeholders (`PROJECT_*`, currently-building, fun fact) replaced
- [ ] Workflow permissions → Read and write
- [ ] Pushed to `main`
- [ ] Both workflows green in the Actions tab (they auto-run on the push)
- [ ] Profile checked in both dark mode and light mode (Settings → Appearance)
- [ ] Profile checked on your phone

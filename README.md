# cave-viewer

A cave survey in 3D beneath the LiDAR ground and satellite imagery, in the
browser: routes through the cave, its drawn survey as a 2D plan, passage
walls, AR on an iPhone or iPad, and it works offline once opened. One
viewer and its Python build tools, configured per cave repo, rather than a
copy of the viewer in each.

```bash
python -m caveviewer build caves.json --out site/
```

A cave repo holds its data and a config (`caves.json`); cave-viewer turns
them into a static site, one page per cave (and a landing page for
several), ready for GitHub Pages.

It needs Python 3.10+ with numpy and Pillow; for a Therion survey, Therion,
Survex (`cavern`) and Subversion; for a Therion drawing or the preview
pictures, Chrome (set `CHROMIUM` to it, if it isn't in the usual place on
a Mac).

## The steps

`python -m caveviewer build <config> --out <site>` runs them all, in order;
`--steps model,drawn` runs some, and cave ids after the config build only
those caves.

1. **survey**: each cave's centreline and names, in the work folder
   (`<work>/<cave>/`, `build/` by default). A Therion survey is checked out
   with Subversion (if the config gives a URL; `--no-fetch` skips the
   update) and built with Therion: its centreline (`cave.3d`), its plan
   (`plan.svg`) and the same as GIS layers (`esri/`), whose labels become
   place names. A Survex survey is a `.3d` already in the repo. Either way
   it writes `names.json`: the entrances, the places by station, and the
   config's ways, trips, codes, avoid, alone and sumps.
2. **model**: each cave's 3D view in `<site>/<path>/`: `scene.json`,
   `terrain.bin`, `index.html` (the viewer with the cave's name, area and
   credits in it), the manifest, icons, three.js and the font, and the
   service worker (`sw.js`, with caches of its own per cave).
3. **drawn**: the drawn survey for the 2D plan, as tiles in
   `<site>/<path>/drawn/`.
4. **index**: the landing page `<site>/index.html`, for a repo of several
   caves.

`python -m caveviewer check <config>` reads the config and says what it
would build; `python -m caveviewer fit <config>` fits a scanned drawing to
the survey (below).

## The inputs, chosen by the config

| what | `type` | |
|---|---|---|
| centreline | `survex` | a Survex `.3d` file (v3 to v8) |
| | `therion` | a Therion project, built to a `.3d` (and a plan and GIS layers) |
| names | — | the config's own (and a `names.file` to start from), plus Therion's GIS labels for a Therion survey |
| terrain | `ea` | the Environment Agency's 1 m LiDAR composite DTM (England), by WCS |
| | `wales` | the Welsh Government's 1 m LiDAR DTM 2020-22, by its WFS tile catalogue |
| | `flat` | no LiDAR: level ground just above the cave (for tests, or elsewhere) |
| drawn survey | `therion-svg` | the plan Therion draws, placed by its grid labels, with a title block |
| | `scan` | a scanned drawing, fitted to the survey (`python -m caveviewer fit`) |
| | `none` | |
| walls | `walls.lox` | a Therion `.lox` with the passage walls |

And the page's features, all on unless the config turns them off:
`features: {"routes", "drawn", "walls", "ar", "offline"}`.

Every key is in [`caveviewer/schema.json`](caveviewer/schema.json) (a JSON
Schema, with a description for each). Paths are relative to the config's
folder.

## Adding a cave repo

1. Make the repo: the survey data (or where to check it out from), a
   `caves.json`, a `requirements.txt` and a `.gitignore`:

   ```
   # requirements.txt: cave-viewer, pinned to a tag
   cave-viewer @ git+https://github.com/CaveSurveying/cave-viewer@v0.4.0
   ```

   ```
   # .gitignore: what's built (and any data that isn't to be published)
   /build/
   /site/
   /lidar/
   ```

2. Write `caves.json`. One cave, from a Survex file, in Wales:

   ```json
   {
     "caves": [{
       "id": "example",
       "name": "Example Cave",
       "area": "Somewhere in Wales",
       "path": "3d",
       "credit": "Example Cave survey, &copy; its surveyors",
       "survey": {"type": "survex", "file": "data/example.3d"},
       "names": {"file": "data/names.json"},
       "terrain": {"type": "wales", "step": 4},
       "drawn": {"type": "scan", "image": "local/drawn.png", "fit": "local/drawn-georef.json",
                 "credit": "Drawn survey © its surveyors"}
     }]
   }
   ```

   Several caves from one Therion dataset share their settings through
   `defaults`, each cave adding its own (the Cheddar repo's `caves.json` is
   a full example):

   ```json
   {
     "site": {"title": "Mendip caves in 3D", "lede": "…", "footer": "… {credits}."},
     "defaults": {
       "grid": {"offset": [300000, 100000]},
       "survey": {"type": "therion", "svn": "http://www.cave-registry.org.uk/svn/CheddarCatchment", "checkout": "registry"},
       "terrain": {"type": "ea"},
       "drawn": {"type": "therion-svg"}
     },
     "caves": [
       {"id": "gb", "name": "GB Cave", "survey": {"dir": "GB", "source": "GB.th", "svx": ["GB.svx"]},
        "ways": [["GB Entrance", "Gorge", "Ladder Dig"]]}
     ]
   }
   ```

   `grid.offset` puts the survey on the full National Grid: Therion's
   export on the ST square is `[300000, 100000]`; a `.3d` already on the
   full grid is `[0, 0]` (the default).

3. Install and build:

   ```bash
   python3 -m venv .venv && . .venv/bin/activate
   pip install -r requirements.txt
   python -m caveviewer build caves.json --out site/
   python -m http.server -d site     # then open http://localhost:8000
   ```

   (Working on cave-viewer itself alongside: `pip install -e ../cave-viewer`
   instead.)

4. To publish it on GitHub Pages, call the reusable workflow from the
   cave repo (Settings → Pages → Source: GitHub Actions):

   ```yaml
   # .github/workflows/pages.yml
   on: { push: { branches: [main] }, workflow_dispatch: {} }
   permissions: { contents: read, pages: write, id-token: write }
   jobs:
     site:
       uses: CaveSurveying/cave-viewer/.github/workflows/build.yml@v0.4.0
       with:
         config: caves.json
         apt-packages: therion survex subversion   # for a Therion survey
   ```

   Only publish what the data's licence allows: whatever is in the repo,
   or is fetched by the build, ends up in the site.

### Private drawings

A `scan` drawn survey is built only where its `image` is there: keep a
private drawing out of git (in a gitignored `local/`, say) and a build
elsewhere, GitHub Actions included, leaves the drawn survey out. A local
build that has it makes it into `site/`, so don't publish that build.

### Fitting a scanned drawing

```bash
python -m caveviewer fit caves.json [cave]
```

finds the entrance triangles on the drawing (red), matches them to the
survey's entrances, then moves, turns and scales the drawing so the most
stations sit on its passages, for the whole cave and then each 250 m
square. It writes the cave's `drawn.fit`.

## Versions

Cave repos pin cave-viewer to a tag in `requirements.txt`, so a change to
the viewer reaches a cave when its repo moves the pin. To release: bump
`__version__` in `caveviewer/__init__.py`, commit, and tag it `v<version>`.

## Developing

```bash
pip install -e .
python -m unittest discover -s tests -v
```

The test builds `tests/fixture`, a made-up cave from a Survex file
(`tests/fixture/data/tiny.svx`, built to `tiny.3d` with `cavern`), on
flat ground, so nothing is fetched.

The viewer is `caveviewer/viewer/viewer.html`; `{{NAME}}`, `{{AREA}}`,
`{{ID}}`, `{{CREDIT}}`, `{{DATA}}`, `{{DATA_HTML}}`, `{{GROUND_CREDIT}}`
and `{{DRAWN_CREDIT}}` in it are filled in per cave, and the page reads the
features turned off from `scene.json`'s `features`.

## Licence and credits

cave-viewer is free software under the GNU General Public License,
version 3 ([LICENSE](LICENSE)), as are the cave repos it came from. Its
AR and VR on Android and headsets (WebXR) is Rich Smith's, from
[richsmith/draenen](https://github.com/richsmith/draenen).

three.js (MIT) and the Inter font (SIL Open Font Licence) are in
`caveviewer/viewer/vendor/`, with their own licences. A cave's survey data
keeps its own licence: cave-viewer only builds the site from it. Ground:
Environment Agency and Welsh Government LiDAR, OGL v3. Imagery: Esri.

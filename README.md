# A1886 GEP Dataset Checker

Static browser version of `jb_A1886_GUItool_check_GEP_dataset_v07.py`.

Current browser title: `A1886 GEP Dataset Checker V12 2026.06.24`.

## Use Locally

Open `index.html` in a browser, then choose one source:

- `1 Local file`: select one or more `.csv` / `.log` files from this PC, then pick one from the list to show the curve
- `2 GitHub file`: defaults to `to people80cm.csv` and shows the curve directly
- `3 Dropbox link`: loads the default Dropbox CSV link, or paste a Dropbox direct CSV/LOG link into the textbox and wait for the curve to load automatically

Recommended Dropbox operation:

1. Click `3 Dropbox link`.
2. Check that the Dropbox filename appears in the file list.
3. If using another Dropbox file, paste its shared link into the textbox.
4. Wait for the curve to load automatically.
5. If the browser blocks direct Dropbox reads, the app tries alternate Dropbox raw URLs and a CORS proxy fallback.
6. If all remote reads fail, download the file and use `1 Local file`.

The page supports:

- compact one-screen desktop layout for controls and curve
- LOG JSON-per-line parsing with `fn`, `r0`, optional `r1`, optional `r2`
- CSV parsing with `fn` and `r0_raw`/`r0`
- `r0` raw and `r0_deglitch` plot
- optional `r1` and `r2` overlays
- frame tick, start frame, window size, median, spike, and jump controls
- click a point to inspect it
- mouse wheel zoom around the selected point
- default deglitch values: median win `9`, spike TH `0.065 m`, jump TH `0.253 m`
- optional rule01 post-process: when enabled, if `r0{k+1} >= rule_base_range_TH`, replace it with `r0{k}` and mark the affected point green
- `Algorithm` button opens `A1886_GEP_algorithm_summary_v01.md`

## Deploy to GitHub Pages

1. Create a new GitHub repo.
2. Commit this folder to the repo.
3. In GitHub, open `Settings` -> `Pages`.
4. Set source to `Deploy from a branch`.
5. Select branch `main` and folder `/root`.
6. The worldwide URL will be:

   `https://YOUR-GITHUB-USERNAME.github.io/YOUR-REPO-NAME/`

## Notes

When `index.html` is opened directly with `file://`, the sample file dropdown may be blocked by browser file security. The upload control still works. On GitHub Pages, the included sample dropdown works if the dataset files are committed with `index.html`.

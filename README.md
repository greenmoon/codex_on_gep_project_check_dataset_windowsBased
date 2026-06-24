# A1886 GEP Dataset Checker

Static browser version of `jb_A1886_GUItool_check_GEP_dataset_v07.py`.

Current browser title: `A1886 GEP Dataset Checker V03 2026.06.24`.

## Use Locally

Open `index.html` in a browser, then choose one source:

- `1 Local file`: select one or more `.csv` / `.log` files from this PC, then pick one from the list to show the curve
- `2 GitHub file`: list committed dataset files from `files.json`, then pick one from the list to show the curve
- `3 Dropbox link`: paste a Dropbox `files.json` manifest link or one direct shared CSV/LOG link per line, list files, then pick one from the list to show the curve

The page supports:

- LOG JSON-per-line parsing with `fn`, `r0`, optional `r1`, optional `r2`
- CSV parsing with `fn` and `r0_raw`/`r0`
- `r0` raw and `r0_deglitch` plot
- optional `r1` and `r2` overlays
- frame tick, start frame, window size, median, spike, and jump controls
- click a point to inspect it
- mouse wheel zoom around the selected point

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

"""
replace_images.py

How it works:
- Builds a lookup of images found in website_image (recursively).
- For each file inside each subfolder of assets/images, it tries:
  1) exact filename match (case-insensitive)
  2) stem match (filename without extension, normalized)
  3) fuzzy match of stems (difflib)
  4) partial containment match (stem contains or is contained by)
- If a match is found, it backs up the original target (into assets/images/_backup_TIMESTAMP/...),
  then copies the source image over the target.
- Prints a summary with counts and lists.
"""

import os, shutil, re, difflib, datetime

# ========== CONFIG ==========
WEBSITE_FOLDER = r"R:\lenslytics-html-files\website_image"
ASSETS_IMAGES = r"R:\lenslytics-html-files\assets\images"

# Safety flags:
DRY_RUN = False       # True = only show what WOULD be done. False = actually copy.
MAKE_BACKUP = True    # backups go to assets/images/_backup_TIMESTAMP/
FUZZY_CUTOFF = 0.78   # increase for stricter fuzzy matching (0.0-1.0)
# ============================

IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.ico')

def normalize_stem(s: str) -> str:
    """Normalize a filename stem for comparison."""
    s = s.lower().strip()
    s = re.sub(r'[_\s]+', '-', s)           # unify underscores/spaces -> hyphen
    s = re.sub(r'[^a-z0-9\-]', '', s)       # keep letters, digits, hyphen
    s = re.sub(r'-{2,}', '-', s)            # collapse repeated hyphens
    return s

# 1) gather website_image files (recursively)
website_files = []
for root, _, files in os.walk(WEBSITE_FOLDER):
    for f in files:
        if f.lower().endswith(IMAGE_EXTS):
            website_files.append(os.path.join(root, f))

if not website_files:
    raise SystemExit(f"No image files found under {WEBSITE_FOLDER!r} (check path).")

# build lookup maps
by_fullname = {}   # key: basename.lower() -> fullpath (first seen)
by_stem = {}       # key: normalized stem -> list of fullpaths

for path in website_files:
    basename = os.path.basename(path)
    by_fullname.setdefault(basename.lower(), path)
    stem = os.path.splitext(basename)[0]
    norm = normalize_stem(stem)
    by_stem.setdefault(norm, []).append(path)

# 2) iterate over subfolders inside assets/images (only one level)
replacements = []
unmatched = []

backup_root = None
if MAKE_BACKUP:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = os.path.join(ASSETS_IMAGES, f"_backup_{ts}")

for sub in sorted(os.listdir(ASSETS_IMAGES)):
    subpath = os.path.join(ASSETS_IMAGES, sub)
    if not os.path.isdir(subpath):
        continue
    # iterate files directly inside this subfolder
    for fname in sorted(os.listdir(subpath)):
        target_path = os.path.join(subpath, fname)
        if not os.path.isfile(target_path):
            continue
        if not fname.lower().endswith(IMAGE_EXTS):
            # skip non-images
            continue

        chosen_src = None
        method = None

        # 1) exact filename (case-insensitive)
        if fname.lower() in by_fullname:
            chosen_src = by_fullname[fname.lower()]
            method = "exact_filename"

        # 2) stem match
        if chosen_src is None:
            tstem = os.path.splitext(fname)[0]
            tnorm = normalize_stem(tstem)
            if tnorm in by_stem:
                chosen_src = by_stem[tnorm][0]   # pick first match
                method = "stem_match"

        # 3) fuzzy match
        if chosen_src is None:
            candidates = difflib.get_close_matches(tnorm, by_stem.keys(), n=1, cutoff=FUZZY_CUTOFF)
            if candidates:
                chosen_src = by_stem[candidates[0]][0]
                method = f"fuzzy_match({candidates[0]})"

        # 4) partial containment (target in website or website in target)
        if chosen_src is None:
            for wnorm, paths in by_stem.items():
                if tnorm in wnorm or wnorm in tnorm:
                    chosen_src = paths[0]
                    method = f"partial({wnorm})"
                    break

        if chosen_src is None:
            unmatched.append(target_path)
            continue

        # Make backup then replace
        if MAKE_BACKUP and not DRY_RUN:
            backup_target = os.path.join(backup_root, os.path.relpath(target_path, ASSETS_IMAGES))
            os.makedirs(os.path.dirname(backup_target), exist_ok=True)
            shutil.copy2(target_path, backup_target)

        if not DRY_RUN:
            shutil.copy2(chosen_src, target_path)

        replacements.append((target_path, chosen_src, method))
        print(f"{'DRY:' if DRY_RUN else 'REPL:'} {target_path} <= {chosen_src}  ({method})")

# Summary
print("\n==== SUMMARY ====")
print(f"Total website images scanned: {len(website_files)}")
print(f"Total replacements performed: {len(replacements)}")
if replacements:
    print("\nReplacements (target <= source) :")
    for t, s, m in replacements:
        print(f" - {t} <= {s}   [{m}]")

if unmatched:
    print(f"\nFiles left unmatched under assets/images: {len(unmatched)}")
    print("Examples (first 20):")
    for p in unmatched[:20]:
        print(" -", p)

if MAKE_BACKUP:
    print(f"\nBackups (original targets) are in: {backup_root!r}" if backup_root else "No backups created.")
print("\nDone.")

"""Stamp docs/index.html's local asset URLs with a content hash.

Runs locally in .venv, after anything that regenerates a model or an image:

    .venv/bin/python scripts/stamp_assets.py

GitHub Pages serves models and images with a long cache lifetime, so a
visitor who has seen the page once keeps the copy they already have even
after the file changes on the server. That is how a corrected assembly model
kept rendering with its brackets in the old place on a phone that had loaded
the page before: the HTML was current, the GLB beside it was months of cache
old, and nothing about the page looked broken.

Appending ?v=<hash of the file> makes the URL change whenever the bytes do,
so the browser fetches it again, and stay identical when they do not, so it
keeps caching normally. Run it before committing; it is idempotent.
"""

import hashlib
import pathlib
import re

PAGE = pathlib.Path("docs/index.html")
ATTRIBUTE = re.compile(r'(src|href)="(?!https?:|#|mailto:)([^"?]+)(\?v=[0-9a-f]+)?"')


def digest(path):
    """First eight hex characters of the file's SHA-256."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def main():
    """Rewrite every local asset URL in the page with its content hash."""
    text = PAGE.read_text(encoding="utf-8")
    stamped, skipped = [], []

    def replace(match):
        attribute, url, existing = match.group(1), match.group(2), match.group(3)
        target = PAGE.parent / url
        if not url or not target.is_file():
            skipped.append(url or "(empty)")
            return match.group(0)
        stamp = f"?v={digest(target)}"
        stamped.append(f"{url}{stamp}" + ("  (unchanged)" if existing == stamp else ""))
        return f'{attribute}="{url}{stamp}"'

    PAGE.write_text(ATTRIBUTE.sub(replace, text), encoding="utf-8")
    for entry in stamped:
        print(f"  stamped {entry}")
    for entry in skipped:
        print(f"  skipped {entry} -- not a file on disk")
    print(f"{len(stamped)} asset(s) stamped in {PAGE}")


if __name__ == "__main__":
    main()

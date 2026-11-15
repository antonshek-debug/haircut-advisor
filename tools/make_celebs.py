"""Build docs/celebrities.json and docs/celebs/*.jpg.

The list below names well-known people that style articles describe as
having a face shape. Nobody on the list was measured: the label is the
article's opinion, and each entry links to the article.

For each person the script asks Wikipedia for the main photo of their
article, checks on Wikimedia Commons that the photo has a free licence,
downloads a small copy, and records the author and licence for the credit
line. A person without a freely licensed photo is kept without a photo.

Usage (no extra packages):
    python tools/make_celebs.py
"""

import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "docs" / "celebrities.json"
OUT_DIR = ROOT / "docs" / "celebs"
THUMB_WIDTH = 250
USER_AGENT = "haircut-advisor-class-project/1.0 (static demo page; python urllib)"
FREE_LICENCE = re.compile(r"^(cc0|cc by|cc-by|public domain|pd\b)", re.I)

VOU = "https://thevou.com/blog/{}-face-shape-male-celebrities/"
VOU_ROUND = "https://thevou.com/?p=89383"
VOU_TRIANGLE = "https://thevou.com/?p=89406"
PUREWOW = "https://purewow.com/beauty/what-face-shape-do-i-have"
SHINE = "https://www.shinesheets.com/face-shapes/"
TRH = "https://therighthairstyles.com/what-hairstyle-suits-your-face-shape/"
GLASSES = "https://www.glassesshop.com/blog/celebrities-face-shapes"
SOOMPI = "https://www.soompi.com/article/1530986wpp/8-k-pop-idols-who-prove-round-face-shapes-are-peak-adorableness"

# (face shape, style, name, Wikipedia article title, "often seen with", source article)
PEOPLE = [
    # oval
    ("oval", "masculine", "Idris Elba", "Idris Elba", "a short buzz cut and a trimmed beard", VOU.format("oval")),
    ("oval", "masculine", "Chris Evans", "Chris Evans (actor)", "a short side-parted cut", VOU.format("oval")),
    ("oval", "masculine", "Dev Patel", "Dev Patel", "medium-length wavy hair", VOU.format("oval")),
    ("oval", "feminine", "Beyoncé", "Beyoncé", "long waves", TRH),
    ("oval", "feminine", "Meghan Markle", "Meghan, Duchess of Sussex", "long layers with a centre part", PUREWOW),
    ("oval", "feminine", "Olivia Munn", "Olivia Munn", "long layers", PUREWOW),
    # round
    ("round", "masculine", "Leonardo DiCaprio", "Leonardo DiCaprio", "a slicked-back medium cut", VOU_ROUND),
    ("round", "masculine", "Usher", "Usher (musician)", "a short fade", VOU_ROUND),
    ("round", "masculine", "Suga (BTS)", "Suga", "a medium cut with a fringe", SOOMPI),
    ("round", "feminine", "Emma Stone", "Emma Stone", "shoulder-length hair with a side-swept fringe", PUREWOW),
    ("round", "feminine", "Chrissy Teigen", "Chrissy Teigen", "a long bob with waves", PUREWOW),
    ("round", "feminine", "Jennie (BLACKPINK)", "Jennie (singer)", "long straight hair with a centre part", SOOMPI),
    # square
    ("square", "masculine", "Pedro Pascal", "Pedro Pascal", "medium tousled waves", VOU.format("square")),
    ("square", "masculine", "Michael B. Jordan", "Michael B. Jordan", "a short fade", VOU.format("square")),
    ("square", "masculine", "Daniel Dae Kim", "Daniel Dae Kim", "a short textured cut", VOU.format("square")),
    ("square", "feminine", "Zendaya", "Zendaya", "many styles, from long curls to a bob", PUREWOW),
    ("square", "feminine", "Lucy Liu", "Lucy Liu", "long straight hair", PUREWOW),
    ("square", "feminine", "Angelina Jolie", "Angelina Jolie", "long soft layers", SHINE),
    # oblong
    ("oblong", "masculine", "Keanu Reeves", "Keanu Reeves", "shoulder-length hair", VOU.format("oblong")),
    ("oblong", "masculine", "Benedict Cumberbatch", "Benedict Cumberbatch", "medium swept-back waves", VOU.format("oblong")),
    ("oblong", "masculine", "Shawn Mendes", "Shawn Mendes", "short sides with curls on top", VOU.format("oblong")),
    ("oblong", "feminine", "Alexa Chung", "Alexa Chung", "shoulder-length hair with a curtain fringe", PUREWOW),
    ("oblong", "feminine", "Sarah Jessica Parker", "Sarah Jessica Parker", "long waves", SHINE),
    ("oblong", "feminine", "Keke Palmer", "Keke Palmer", "many styles, often shoulder-length or longer", PUREWOW),
    # heart
    ("heart", "masculine", "Bradley Cooper", "Bradley Cooper", "medium swept-back hair", VOU.format("heart")),
    ("heart", "masculine", "Daniel Craig", "Daniel Craig", "a short crop", VOU.format("heart")),
    ("heart", "masculine", "Chris Colfer", "Chris Colfer", "a short side-swept cut", GLASSES),
    ("heart", "feminine", "Reese Witherspoon", "Reese Witherspoon", "a long bob with a side-swept fringe", PUREWOW),
    ("heart", "feminine", "Kerry Washington", "Kerry Washington", "shoulder-length waves", PUREWOW),
    ("heart", "feminine", "Constance Wu", "Constance Wu", "long hair, often with a fringe", PUREWOW),
    # diamond
    ("diamond", "masculine", "Robert Pattinson", "Robert Pattinson", "a tousled textured cut", VOU.format("diamond")),
    ("diamond", "masculine", "Cillian Murphy", "Cillian Murphy", "a textured crop with a fringe", VOU.format("diamond")),
    ("diamond", "masculine", "Mahershala Ali", "Mahershala Ali", "a shaved head", VOU.format("diamond")),
    ("diamond", "feminine", "Jennifer Lopez", "Jennifer Lopez", "long layers", PUREWOW),
    ("diamond", "feminine", "Tyra Banks", "Tyra Banks", "long hair with a side-swept fringe", PUREWOW),
    ("diamond", "feminine", "Eiza González", "Eiza González", "long waves", PUREWOW),
    # triangle (jaw wider than forehead; some articles call it "pear")
    ("triangle", "masculine", "Tom Cruise", "Tom Cruise", "a medium-short layered side part", VOU_TRIANGLE),
    ("triangle", "masculine", "Rami Malek", "Rami Malek", "short curls on top with tapered sides", VOU_TRIANGLE),
    ("triangle", "masculine", "John Krasinski", "John Krasinski", "a short tousled side part", VOU.format("pear")),
    ("triangle", "feminine", "Kelly Osbourne", "Kelly Osbourne", "a short cut with volume on top", SHINE),
    ("triangle", "feminine", "Sophia Bush", "Sophia Bush", "medium-to-long waves", SHINE),
    ("triangle", "feminine", "Jennifer Aniston", "Jennifer Aniston", "long layers", SHINE),
]


def slug(text):
    text = text.lower().replace("é", "e").replace("á", "a")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def strip_tags(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def fetch(url, tries=5):
    """GET with a polite retry when the server says "too many requests"."""
    for attempt in range(tries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as err:
            if err.code != 429 or attempt == tries - 1:
                raise
            wait = int(err.headers.get("Retry-After") or 0) or 20 * (attempt + 1)
            print(f"  rate limited, waiting {wait}s", file=sys.stderr)
            time.sleep(min(wait, 120))


def api(host, **params):
    query = urllib.parse.urlencode({"format": "json", "formatversion": 2, **params})
    return json.loads(fetch(f"https://{host}/w/api.php?{query}"))


def main_photos(titles):
    """One request: Wikipedia article title -> (main photo file name, short description)."""
    data = api("en.wikipedia.org", action="query", titles="|".join(titles), redirects=1,
               prop="pageimages|description", piprop="name", pilimit=50)["query"]
    renamed = {r["from"]: r["to"] for r in data.get("normalized", []) + data.get("redirects", [])}
    pages = {p["title"]: p for p in data["pages"]}
    out = {}
    for title in titles:
        final = renamed.get(renamed.get(title, title), renamed.get(title, title))
        page = pages.get(final, {})
        out[title] = (page.get("pageimage"), page.get("description", ""))
    return out


def photo_details(files):
    """One request: Commons file name -> thumb URL, author, licence, page."""
    data = api("commons.wikimedia.org", action="query", titles="|".join("File:" + f for f in files),
               prop="imageinfo", iiprop="url|extmetadata", iiurlwidth=THUMB_WIDTH)["query"]
    renamed = {r["from"]: r["to"] for r in data.get("normalized", [])}
    pages = {p["title"]: p for p in data["pages"]}
    out = {}
    for f in files:
        page = pages.get(renamed.get("File:" + f, "File:" + f), {})
        if "imageinfo" not in page:
            out[f] = (None, "photo is not on Wikimedia Commons")
            continue
        ii = page["imageinfo"][0]
        meta = ii.get("extmetadata", {})
        licence = strip_tags(meta.get("LicenseShortName", {}).get("value", ""))
        if not FREE_LICENCE.match(licence):
            out[f] = (None, f"licence not free: {licence or 'unknown'}")
            continue
        out[f] = ({
            "thumb": ii["thumburl"],
            "author": strip_tags(meta.get("Artist", {}).get("value", "")) or "Unknown author",
            "licence": licence,
            "page": ii["descriptionurl"],
        }, "")
    return out


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    photos = main_photos([p[3] for p in PEOPLE])
    details = photo_details(sorted({f for f, _ in photos.values() if f}))

    out, wanted = [], set()
    for shape, style, name, title, hair, source in PEOPLE:
        entry = {"face_shape": shape, "style": style, "name": name, "known_for": hair, "source": source, "photo": None}
        file, description = photos[title]
        photo, reason = details.get(file, (None, "no main photo on Wikipedia"))
        if photo:
            file_name = slug(name) + ".jpg"
            target = OUT_DIR / file_name
            try:
                if not target.exists():  # downloads once; delete the file to refresh it
                    target.write_bytes(fetch(photo["thumb"]))
                    time.sleep(2)  # be polite to the image server
                wanted.add(file_name)
                entry["photo"] = {
                    "file": "celebs/" + file_name,
                    "author": photo["author"][:120],
                    "licence": photo["licence"],
                    "page": photo["page"],
                }
            except Exception as err:
                reason = f"download failed: {err}"
        print(f"{shape:9} {name:24} [{description[:40]}] -> "
              + (f"{entry['photo']['licence']} / {entry['photo']['author'][:40]}" if entry["photo"] else f"NO PHOTO ({reason})"),
              file=sys.stderr)
        out.append(entry)

    for old in OUT_DIR.glob("*.jpg"):
        if old.name not in wanted:
            old.unlink()

    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1) + chr(10), encoding="utf-8", newline=chr(10))
    with_photo = sum(1 for e in out if e["photo"])
    print(f"Wrote {len(out)} people, {with_photo} with a photo, to {OUT_JSON.name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

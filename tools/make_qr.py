# /// script
# requires-python = ">=3.10"
# dependencies = ["qrcode[pil]"]
# ///
"""Make a QR code image for a URL.

Usage:
    uv run tools/make_qr.py <url> <output.png>

Example:
    uv run tools/make_qr.py https://antonshek-debug.github.io/haircut-advisor/ tools/qr-page.png
"""

import sys

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2

    url, output = sys.argv[1], sys.argv[2]
    if not url.startswith("https://"):
        print("The URL must start with https:// (a phone camera needs HTTPS).", file=sys.stderr)
        return 2

    # Error correction M (15%) survives a slightly damaged print.
    # box_size 16 gives a large image that stays sharp on paper.
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=16, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    qr.make_image(fill_color="black", back_color="white").save(output)

    print(f"Saved {output} -> {url}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

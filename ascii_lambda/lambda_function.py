"""Turn an image into ASCII art and save it as a .txt in S3.

Two ways to run it:
- S3 trigger: an image uploaded to the bucket is written back beside it as NAME.txt.
- Direct invoke with {"url": "...", "name": "..."}: the function downloads the image
  itself, saves it and NAME.txt to the bucket, and returns the art.

Needs the `pillow` layer (Pillow isn't in the Lambda runtime).
"""

import io
import os
import time
import urllib.parse
import urllib.request

import boto3
from PIL import Image

s3 = boto3.client("s3")

BUCKET = os.environ.get("BUCKET", "demo-taa4uu")
WIDTH = 100  # characters per line of output
RAMP = "@%#*+=-:. "  # darkest to lightest


def lambda_handler(event, context):
    if "url" in event:
        return from_url(event["url"], event.get("name") or f"image_{int(time.time())}")
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        # S3 sends the key URL-encoded: "my pic.png" arrives as "my+pic.png"
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        data = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        save(bucket, key.rsplit(".", 1)[0] + ".txt", to_ascii(data))


def from_url(url, name):
    # some image hosts reject urllib's default user agent
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=15).read()
    art = to_ascii(data)
    s3.put_object(Bucket=BUCKET, Key=f"urls/{name}.img", Body=data)
    save(BUCKET, f"{name}.txt", art)
    return {"key": f"{name}.txt", "art": art}


def save(bucket, key, art):
    s3.put_object(Bucket=bucket, Key=key, Body=art.encode("utf-8"), ContentType="text/plain")
    print(f"wrote s3://{bucket}/{key}")


def to_ascii(data):
    """Shrink the image to one pixel per character and map brightness to RAMP."""
    img = Image.open(io.BytesIO(data))
    img = img.convert("RGBA")
    background = Image.new("RGBA", img.size, "white")  # transparent areas count as white
    img = Image.alpha_composite(background, img).convert("L")
    cols = min(WIDTH, img.width)
    rows = max(1, round(img.height / img.width * cols / 2))  # characters are ~2x taller than wide
    img = img.resize((cols, rows), Image.BOX)  # BOX averages every pixel in each cell
    px = img.load()
    lines = (
        "".join(RAMP[px[x, y] * (len(RAMP) - 1) // 255] for x in range(cols)).rstrip()
        for y in range(rows)
    )
    return "\n".join(lines) + "\n"

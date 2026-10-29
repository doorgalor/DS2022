#!/usr/bin/env bash
# Usage: ./ascii.sh PATH_OR_URL [NAME]
# All image work happens in the ascii Lambda:
# - a local file is uploaded to the bucket, which triggers the Lambda
# - a link is passed to the Lambda, which downloads the image itself
# Then the resulting NAME.txt is printed from S3.
set -euo pipefail

BUCKET="${BUCKET:-demo-taa4uu}"
FUNCTION="${FUNCTION:-ascii}"
SRC="${1:?usage: ./ascii.sh PATH_OR_URL [NAME]}"

if [[ "$SRC" =~ ^https?:// ]]; then
  NAME="${2:-image_$(date +%s)}"
  OUT="$(mktemp)"
  trap 'rm -f "$OUT"' EXIT
  echo "Asking the Lambda to fetch the link..." >&2
  ERR="$(aws lambda invoke --function-name "$FUNCTION" \
    --payload "$(printf '{"url": "%s", "name": "%s"}' "$SRC" "$NAME")" \
    --query FunctionError --output text "$OUT")"
  if [[ "$ERR" != "None" ]]; then
    echo "Lambda failed:" >&2; cat "$OUT" >&2; echo >&2; exit 1
  fi
else
  [[ -f "$SRC" ]] || { echo "No such file: $SRC" >&2; exit 1; }
  EXT="$(echo "${SRC##*.}" | tr '[:upper:]' '[:lower:]')"
  # these suffixes are the bucket's S3 triggers
  [[ "$EXT" =~ ^(png|jpg|jpeg|gif|webp)$ ]] || { echo "Unsupported file type: .$EXT" >&2; exit 1; }
  NAME="${2:-$(basename "${SRC%.*}" | tr ' ' '_')}"
  aws s3 rm "s3://$BUCKET/$NAME.txt" --quiet 2>/dev/null || true
  aws s3 cp "$SRC" "s3://$BUCKET/$NAME.$EXT" --quiet
  echo "Uploaded $NAME.$EXT, waiting for the Lambda..." >&2
  aws s3api wait object-exists --bucket "$BUCKET" --key "$NAME.txt"
fi

aws s3 cp "s3://$BUCKET/$NAME.txt" -

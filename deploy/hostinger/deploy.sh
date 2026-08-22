#!/usr/bin/env bash
# ==============================================================================
# ShoeMatch AI — upload the frontend bundle to Hostinger over FTP.
#
#   1.  npm run build   # produces dist/
#   1b. cp deploy/hostinger/.ftp.env.example deploy/hostinger/.ftp.env
#   2.  fill in .ftp.env   (gitignored)
#   3.  bash deploy/hostinger/deploy.sh
#
# Credentials are read from the file and never printed.
# ==============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(cd "$HERE/../.." && pwd)/dist"
ENV_FILE="$HERE/.ftp.env"

if [ ! -d "$SRC" ] || [ -z "$(ls -A "$SRC" 2>/dev/null)" ]; then
  echo "ERROR: dist/ is missing or empty."
  echo "       Run:  npm run build"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found."
  echo "       npm run build   # produces dist/
#   1b. cp deploy/hostinger/.ftp.env.example deploy/hostinger/.ftp.env  and fill it in."
  exit 1
fi

set -a; . "$ENV_FILE"; set +a

for v in FTP_HOST FTP_USER FTP_PASS FTP_REMOTE_DIR; do
  if [ -z "${!v:-}" ]; then echo "ERROR: $v is empty in .ftp.env"; exit 1; fi
done

FTP_REMOTE_DIR="${FTP_REMOTE_DIR%/}"
HOSTPART="${FTP_HOST#ftp://}"; HOSTPART="${HOSTPART#ftps://}"; HOSTPART="${HOSTPART%/}"

echo "=============================================================="
echo " Uploading to ${HOSTPART}${FTP_REMOTE_DIR}"
echo "=============================================================="

# Connectivity / auth pre-flight before pushing 15 files at a broken target.
if ! curl -sS --ftp-ssl --connect-timeout 20 --max-time 45 \
        --user "$FTP_USER:$FTP_PASS" \
        --list-only "ftp://${HOSTPART}${FTP_REMOTE_DIR}/" >/dev/null 2>&1; then
  echo "Pre-flight LIST failed. Retrying without explicit FTPS..."
  if ! curl -sS --connect-timeout 20 --max-time 45 \
          --user "$FTP_USER:$FTP_PASS" \
          --list-only "ftp://${HOSTPART}${FTP_REMOTE_DIR}/" >/dev/null 2>&1; then
    echo
    echo "ERROR: could not connect or authenticate."
    echo "  - Check FTP_HOST / FTP_USER / FTP_PASS in .ftp.env"
    echo "  - Confirm FTP_REMOTE_DIR exists (hPanel -> File Manager)"
    echo "  - Some networks block port 21; try hPanel File Manager instead."
    exit 1
  fi
  SSL_FLAG=""
else
  SSL_FLAG="--ftp-ssl"
fi
echo "Connected and authenticated."
echo

ok=0; fail=0; failed_list=""
while IFS= read -r file; do
  rel="${file#$SRC/}"
  printf "  %-34s " "$rel"
  if curl -sS $SSL_FLAG --ftp-create-dirs --connect-timeout 20 --max-time 180 \
       --user "$FTP_USER:$FTP_PASS" \
       -T "$file" "ftp://${HOSTPART}${FTP_REMOTE_DIR}/${rel}" >/dev/null 2>&1; then
    echo "ok"; ok=$((ok+1))
  else
    echo "FAILED"; fail=$((fail+1)); failed_list="${failed_list}    ${rel}\n"
  fi
done < <(find "$SRC" -type f | sort)

echo
echo "--------------------------------------------------------------"
echo " uploaded: $ok    failed: $fail"
[ "$fail" -gt 0 ] && { echo " failures:"; printf "$failed_list"; }
echo "--------------------------------------------------------------"

# .htaccess is hidden; `find` catches it, but confirm it actually landed.
if [ "$fail" -eq 0 ] && [ -n "${SITE_URL:-}" ]; then
  echo
  echo "Verifying ${SITE_URL} ..."
  for path in "/" "/app.html" "/static/app.js" "/static/config.js" "/mobile/index.html"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 25 -L "${SITE_URL%/}${path}")
    printf "  %-24s %s\n" "$path" "$code"
  done
fi

[ "$fail" -eq 0 ] && echo && echo "Done." || exit 1

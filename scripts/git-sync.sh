#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Automated Git Sync & Direct Deployment Trigger (scripts/git-sync.sh)
# - Scans all tracked/staged files to guarantee 0 secrets from uploads/
# - Commits any new changes on `main`
# - Pushes to GitHub (`caladofficial/uppsc-beo-examiner-suite`) via transient
#   GIT_ASKPASS so no token is ever written to .git/config or git history
# =============================================================================

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

COMMIT_MSG="${1:-chore: sync UPPSC BEO Mains Examiner Suite updates}"
TOKEN_FILE="/home/user/uploads/github_token.txt"

if [ ! -f "$TOKEN_FILE" ]; then
  echo "Error: GitHub token file not found at $TOKEN_FILE"
  exit 1
fi

echo "[1/3] Running pre-commit secret leakage scan..."
python3 - << 'PYEOF'
import os, subprocess, sys

secrets = []
for fn in ["Api keys.txt", "Manas ka dokha congif supabase.txt", "Manas ka dokha supabase.txt", "vercel token manas ka dokha.txt", "github_token.txt"]:
    p = os.path.join("/home/user/uploads", fn)
    if os.path.exists(p):
        for token in open(p).read().split():
            t = token.strip()
            if len(t) >= 18 and not t.startswith("http") and "=" not in t:
                secrets.append(t)

skip_dirs = {"uploads", "node_modules", ".next", ".git", "__pycache__", ".vercel", ".npm", ".cache"}
leaks = 0
for root, dirs, files in os.walk("/home/user"):
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    for f in files:
        if f.startswith(".env") and f != ".env.example":
            continue
        fp = os.path.join(root, f)
        try:
            data = open(fp, "rb").read().decode("utf-8", errors="ignore")
            for s in secrets:
                if s in data:
                    print("BLOCKING COMMIT - SECRET DETECTED IN:", fp)
                    leaks += 1
        except Exception:
            pass

if leaks > 0:
    sys.exit(1)
print("Secret scan passed (0 leaks).")
PYEOF

echo "[2/3] Staging and committing workspace updates..."
git add -A
if ! git diff --cached --quiet; then
  git commit -m "$COMMIT_MSG"
else
  echo "Working tree already clean; pushing latest HEAD..."
fi

echo "[3/3] Pushing to origin/main (triggers GitHub Actions & Vercel/Pages deployment)..."
ASKPASS_SCRIPT="$(mktemp)"
trap 'rm -f "$ASKPASS_SCRIPT"' EXIT
cat << 'EOF' > "$ASKPASS_SCRIPT"
#!/usr/bin/env bash
case "$1" in
  *Username*) echo "x-access-token" ;;
  *Password*) tr -d '\r\n ' < "/home/user/uploads/github_token.txt" ;;
esac
EOF
chmod 700 "$ASKPASS_SCRIPT"

GIT_TERMINAL_PROMPT=0 GIT_ASKPASS="$ASKPASS_SCRIPT" git push -u origin main
echo "Successfully pushed to https://github.com/caladofficial/uppsc-beo-examiner-suite (branch: main)!"

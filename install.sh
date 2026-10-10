#!/bin/bash
# Install or update Pitwall.
#   curl -fsSL https://raw.githubusercontent.com/vvojciech/pitwall/main/install.sh | bash
# Set PITWALL_DIR to choose where the code goes (default ~/.pitwall/app).
set -euo pipefail

DIR="${PITWALL_DIR:-$HOME/.pitwall/app}"
REPO="https://github.com/vvojciech/pitwall.git"
BIN="$HOME/.local/bin"

fail() { printf 'pitwall: %s\n' "$1" >&2; exit 1; }

[ "$(uname)" = "Darwin" ] || fail "Pitwall needs macOS."
[ -d /Applications/iTerm.app ] || fail "Install iTerm2 first: https://iterm2.com"
command -v git >/dev/null || fail "Install git first: xcode-select --install"
command -v python3 >/dev/null || fail "Install Python 3.9 or newer first."
python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' || fail "Python 3.9 or newer is needed."

if [ -d "$DIR/.git" ]; then
  echo "Updating Pitwall in $DIR"
  git -C "$DIR" pull --ff-only --quiet
else
  echo "Downloading Pitwall to $DIR"
  mkdir -p "$(dirname "$DIR")"
  git clone --quiet --depth 1 "$REPO" "$DIR"
fi

mkdir -p "$BIN"
ln -sf "$DIR/bin/pitwall" "$BIN/pitwall"

"$DIR/bin/pitwall" install

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) printf '\nTo run `pitwall` by name, add %s to your PATH:\n  echo '"'"'export PATH="%s:$PATH"'"'"' >> ~/.zshrc\n' "$BIN" "$BIN" ;;
esac

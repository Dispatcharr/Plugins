#!/bin/bash
set -e

# Generates a GPG Ed25519 signing key for Dispatcharr manifest signing.
# Outputs:
#   dispatcharr-plugins.pub  - public key to bundle in the Dispatcharr app
#   dispatcharr-plugins.key  - private key to set as the GPG_PRIVATE_KEY repo secret
#   dispatcharr-plugins.pass - passphrase to set as the GPG_PASSPHRASE repo secret

EMAIL="plugins@dispatcharr.tv"
NAME="Dispatcharr Plugin Repo"
PASSPHRASE=$(LC_ALL=C tr -dc 'A-Za-z0-9!@#$%^&*' </dev/urandom | head -c 128)
KEYS_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Generating GPG signing key..."
echo "  Identity : $NAME <$EMAIL>"
echo "  Algorithm: Ed25519"
echo "  Passphrase: $PASSPHRASE"
echo ""

gpg --batch --gen-key <<EOF
Key-Type: EdDSA
Key-Curve: ed25519
Key-Usage: sign
Name-Real: ${NAME}
Name-Email: ${EMAIL}
Expire-Date: 0
Passphrase: ${PASSPHRASE}
%commit
EOF

echo ""
gpg --list-secret-keys --keyid-format LONG "$EMAIL"

# Export keys
rm -f "$KEYS_DIR/dispatcharr-plugins.key" "$KEYS_DIR/dispatcharr-plugins.pub" "$KEYS_DIR/dispatcharr-plugins.pass"
gpg --armor --export-secret-keys "$EMAIL" > "$KEYS_DIR/dispatcharr-plugins.key"
gpg --armor --export "$EMAIL" > "$KEYS_DIR/dispatcharr-plugins.pub"
echo "$PASSPHRASE" > "$KEYS_DIR/dispatcharr-plugins.pass"

echo ""
echo "Files written:"
echo "  dispatcharr-plugins.pub   → bundle into Dispatcharr app (included in this repo)"
echo "  dispatcharr-plugins.key   → set as GPG_PRIVATE_KEY repo secret (ignored by .gitignore)"
echo "  dispatcharr-plugins.pass  → set as GPG_PASSPHRASE repo secret (ignored by .gitignore)"
echo ""

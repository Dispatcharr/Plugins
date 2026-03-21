#!/bin/bash
set -e

# Generates a GPG Ed25519 signing key for Dispatcharr manifest signing.
# Outputs:
#   dispatcharr-plugins.pub  - public key to bundle in the Dispatcharr app
#   dispatcharr-plugins.key  - private key to set as the GPG_PRIVATE_KEY repo secret
#   dispatcharr-plugins.pass - passphrase to set as the GPG_PASSPHRASE repo secret

EMAIL="plugins@dispatcharr.tv"
NAME="Dispatcharr Plugin Repo"
PASSPHRASE=$(LC_ALL=C tr -dc 'A-Za-z0-9!@#$%^&*' </dev/urandom | head -c 12)

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
gpg --armor --export-secret-keys "$EMAIL" > dispatcharr-plugins.key
gpg --armor --export "$EMAIL" > dispatcharr-plugins.pub
echo "$PASSPHRASE" > dispatcharr-plugins.pass

echo ""
echo "Files written:"
echo "  dispatcharr-plugins.pub   → bundle into Dispatcharr app"
echo "  dispatcharr-plugins.key   → set as GPG_PRIVATE_KEY repo secret"
echo "  dispatcharr-plugins.pass  → set as GPG_PASSPHRASE repo secret"
echo ""
echo "Delete dispatcharr-plugins.key and dispatcharr-plugins.pass after"
echo "uploading to GitHub secrets. Keep dispatcharr-plugins.pub in source control."

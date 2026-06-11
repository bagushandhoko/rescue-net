#!/bin/sh
set -eu

# Build sensitive patterns in pieces so this helper does not match itself.
openai_key='sk-[A-Za-z0-9_-]{20,}'
db_password='rescuenet_dev_''password'
postgres_env='POSTGRES_''PASSWORD=[^[:space:]]+'
dsn='postgresql''://[^:]+:[^@]+@'
pattern="$openai_key|$db_password|$postgres_env|$dsn"

grep -RInE "$pattern" . \
  --exclude-dir="@eaDir" \
  --exclude-dir=".git" \
  --exclude="*.bak*" \
  --exclude="*.zip" \
  --exclude=".env" \
  --exclude="*.png" \
  --exclude="*.jpg" \
  --exclude="*.jpeg" \
  --exclude="*.webp" \
  --exclude="*.mp4" \
  --exclude="rn-push*.sh" \
  | head -50

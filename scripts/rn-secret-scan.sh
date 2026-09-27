#!/bin/sh
set -eu

# Build sensitive patterns in pieces so this helper does not match itself.
openai_key='sk-[A-Za-z0-9_-]{20,}'
db_password='rescuenet_dev_''password'
postgres_env='POSTGRES_''PASSWORD=[^[:space:]]+'
dsn='postgresql''://[^:]+:[^@]+@'
# a literal value after MYSQL_ROOT_PASSWORD / MARIADB_ROOT_PASSWORD (a ${VAR} reference is fine)
mysql_env='(MYSQL|MARIADB)_ROOT_''PASSWORD(:[[:space:]]+|=)["'"'"']?[^$"'"'"'[:space:]]'
gemini_key='AIza''[0-9A-Za-z_-]{35}'
pattern="$openai_key|$db_password|$postgres_env|$dsn|$mysql_env|$gemini_key"

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

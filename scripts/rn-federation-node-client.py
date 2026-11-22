#!/usr/bin/env python3
"""Reference client for Rescue-Net federation over HTTPS."""

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time
from urllib.parse import urlsplit
from uuid import UUID

import requests


def sign(key, command, receiver, peer, timestamp, nonce, body):
    prefix = (f"RN-FEDERATION/1 {command}", receiver, peer, timestamp, nonce)
    message = b"\n".join([*(part.encode("ascii") for part in prefix), body])
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def canonical_uuid(value):
    if str(UUID(value)) != value:
        raise ValueError("ID node harus berupa UUID kanonik.")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("info")
    pull = commands.add_parser("pull")
    pull.add_argument("--since", type=int, required=True)
    pull.add_argument("--limit", type=int, default=100)
    push = commands.add_parser("push")
    push.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        base = os.environ["RN_FEDERATION_API"].rstrip("/")
        endpoint = urlsplit(base)
        if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username is not None or endpoint.query or endpoint.fragment:
            raise ValueError("RN_FEDERATION_API harus URL HTTPS tanpa kredensial, query, atau fragmen.")
        with requests.Session() as client:
            # A signed POST must never be redirected or use an inherited login.
            client.trust_env = False
            if args.command == "info":
                response = client.get(f"{base}.node_info", timeout=30, allow_redirects=False)
            else:
                key = os.environ["RN_FEDERATION_SHARED_SECRET"]
                if not re.fullmatch("[0-9a-f]{64}", key):
                    raise ValueError("Kunci harus berupa 64 karakter hex huruf kecil.")
                peer = canonical_uuid(os.environ["RN_FEDERATION_PEER_ID"])
                receiver = canonical_uuid(os.environ["RN_FEDERATION_RECEIVER_ID"])
                if args.command == "pull":
                    body = json.dumps({"since_seq": args.since, "limit": args.limit}, separators=(",", ":")).encode()
                else:
                    with args.file.open("rb") as source:
                        body = source.read(512 * 1024 + 1)
                    if len(body) > 512 * 1024:
                        raise ValueError("Berkas push melebihi 512 KiB.")
                timestamp, nonce = str(int(time.time())), secrets.token_hex(16)
                response = client.post(f"{base}.{args.command}", data=body, timeout=30, allow_redirects=False,
                                       headers={"Content-Type": "application/json", "X-RN-Peer": peer,
                                                "X-RN-Timestamp": timestamp, "X-RN-Nonce": nonce,
                                                "X-RN-Signature": sign(bytes.fromhex(key), args.command, receiver,
                                                                       peer, timestamp, nonce, body)})
            if response.status_code != 200:
                sys.exit(f"Federasi gagal (HTTP {response.status_code}).")
            result = response.json()["message"]
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except KeyError as error:
        sys.exit(f"Variabel konfigurasi atau field respons belum tersedia: {error}")
    except (requests.RequestException, ValueError, OSError) as error:
        sys.exit(f"Federasi gagal ({type(error).__name__}).")


if __name__ == "__main__":
    main()

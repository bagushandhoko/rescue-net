#!/usr/bin/env python3
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

LOCAL_BASE = "http://127.0.0.1:8092"
LAN_BASE = "http://192.168.100.32:8092"

CHECKS = [
    ("Health", "/health"),
    ("Disasters", "/disasters"),
    ("Organizations", "/organizations"),
    ("Poskos", "/poskos"),

    ("AI Context / War Room", "/ai/context/event-aceh-2025"),
    ("Posko Detail", "/posko-context/posko-logistik-aceh"),
    ("Kitchen / Dapur Umum", "/kitchen-context/posko-dapur-melati"),
    ("Medical Posko", "/medical-context/posko-medis-aceh"),
    ("Shelter", "/shelter-context/posko-shelter-melati"),
    ("Search & Found", "/search-found-context/event-aceh-2025"),

    ("Volunteer", "/volunteer-context/event-aceh-2025"),
    ("Work Tools", "/work-tools-context/event-aceh-2025"),
    ("Verification", "/verification-context/event-aceh-2025"),
    ("Evidence", "/evidence"),
    ("Donor Program", "/donor-program-context/event-aceh-2025"),
    ("Auth Roles", "/auth/roles"),
    ("Map", "/map-context/event-aceh-2025"),
    ("Sync Pull", "/sync/pull/event-aceh-2025"),
]

POST_CHECKS = [
    (
        "Auth Demo Login",
        "/auth/demo-login",
        {"username": "command"},
    ),
]


def run_cmd(cmd):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        return 0, out.strip()
    except Exception as e:
        return 1, str(e)


def request_json(base, path, method="GET", payload=None, timeout=15):
    url = base + path
    data = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            body = res.read(700).decode("utf-8", "replace")
            return {
                "ok": 200 <= res.status < 300,
                "status": res.status,
                "url": url,
                "body": body,
            }
    except urllib.error.HTTPError as e:
        body = e.read(1200).decode("utf-8", "replace")
        return {
            "ok": False,
            "status": e.code,
            "url": url,
            "body": body,
        }
    except Exception as e:
        return {
            "ok": False,
            "status": "ERR",
            "url": url,
            "body": str(e),
        }


def print_result(name, result):
    status = result["status"]
    mark = "OK" if result["ok"] else "FAIL"
    print(f"{mark:5} {name:28} {status:>4} {result['url']}")
    if not result["ok"]:
        print(f"      {result['body'][:500]}")


def main():
    failed = []

    print("=== Rescue-Net Health Check ===")
    print(datetime.now().isoformat())
    print()

    print("=== Container Status ===")
    code, out = run_cmd(["sudo", "docker", "ps", "-a"])
    if code == 0:
        lines = [line for line in out.splitlines() if "rescue-net-api" in line or "postgres-main" in line]
        if lines:
            for line in lines:
                print(line)
        else:
            print("FAIL  rescue-net-api/postgres-main not found in docker ps -a")
            failed.append(("docker", "container missing"))
    else:
        print("WARN  cannot run docker ps -a")
        print(out)
    print()

    print("=== Local API Endpoints ===")
    for name, path in CHECKS:
        result = request_json(LOCAL_BASE, path)
        print_result(name, result)
        if not result["ok"]:
            failed.append((name, result))

    for name, path, payload in POST_CHECKS:
        result = request_json(LOCAL_BASE, path, method="POST", payload=payload)
        print_result(name, result)
        if not result["ok"]:
            failed.append((name, result))

    print()
    print("=== LAN Browser Access Smoke Test ===")
    for name, path in [
        ("LAN Health", "/health"),
        ("LAN Posko Detail", "/posko-context/posko-logistik-aceh"),
        ("LAN AI Context", "/ai/context/event-aceh-2025"),
    ]:
        result = request_json(LAN_BASE, path, timeout=10)
        print_result(name, result)
        if not result["ok"]:
            failed.append((name, result))

    print()
    print("=== Summary ===")
    if failed:
        print(f"FAILED: {len(failed)} item(s)")
        for item in failed:
            print("-", item[0])
        print()
        print("Next: run:")
        print("  sudo docker logs rescue-net-api --tail 160")
        sys.exit(1)

    print("NO_FAILED_ENDPOINTS")
    sys.exit(0)


if __name__ == "__main__":
    main()

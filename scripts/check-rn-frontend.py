#!/usr/bin/env python3
import re
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path("/volume1/web/rescue-net")

LIVE_PAGES = [
    "index.html",
    "pages/war-room.html",
    "pages/disaster-detail.html",
    "pages/organisasi-posko.html",
    "pages/posko-detail.html",
    "pages/management-relawan.html",
    "pages/posko-logistik.html",
    "pages/management-distribusi.html",
    "pages/dapur-umum.html",
    "pages/posko-medis-detail.html",
    "pages/shelter-detail.html",
    "pages/search-found.html",
    "pages/alat-kerja.html",
    "pages/verification-approval.html",
    "pages/evidence.html",
    "pages/donor-program.html",
    "pages/auth.html",
    "pages/map.html",
    "pages/contact-directory.html",
    "pages/kirim-bantuan.html",
    "pages/edit-bantuan.html",
    "pages/sync-console.html",
    "pages/ai-analyst.html",
    "pages/ai-settings.html",
]

REQUIRED_MENU_ITEMS = [
    "Active Disasters",
    "War Room",
    "Organisasi & Posko",
    "Relawan",
    "Logistik",
    "Distribusi",
    "Dapur Umum",
    "Posko Medis",
    "Shelter",
    "Search & Found",
    "Alat Kerja",
    "Verification",
    "Evidence",
    "Donor Program",
    "Auth & Role",
    "Map",
    "Contacts",
    "AI Analyst",
    "AI Settings",
]

BAD_FRONTEND_API = [
    "http://127.0.0.1:8092",
    "http://localhost:8092",
]

GOOD_FRONTEND_API = "http://192.168.100.32:8092"


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def check_file_exists(path: str, failures):
    p = ROOT / path
    if not p.exists():
        failures.append(("MISSING_PAGE", path))
        print(f"FAIL  MISSING_PAGE {path}")
        return False
    print(f"OK    PAGE         {path}")
    return True


def script_paths_from_html(html_path: Path):
    text = html_path.read_text(errors="replace")
    return re.findall(r'<script[^>]+src="([^"]+)"', text), text


def hrefs_from_html(text: str):
    return re.findall(r'href="([^"]+)"', text)


def resolve_asset(html_path: Path, src: str) -> Path:
    clean = src.split("?")[0]
    if clean.startswith("http://") or clean.startswith("https://"):
        return None
    return (html_path.parent / clean).resolve()


def main():
    failures = []

    print("=== Rescue-Net Frontend Check ===")
    print(datetime.now().isoformat())
    print()

    print("=== Live Page Existence ===")
    for page in LIVE_PAGES:
        check_file_exists(page, failures)

    print()
    print("=== Script Reference Check ===")
    for page in LIVE_PAGES:
        html = ROOT / page
        if not html.exists():
            continue

        scripts, text = script_paths_from_html(html)
        for src in scripts:
            resolved = resolve_asset(html, src)
            if resolved is None:
                continue
            if not resolved.exists():
                failures.append(("MISSING_JS", page, src, str(resolved)))
                print(f"FAIL  MISSING_JS   {page} -> {src}")
            else:
                print(f"OK    JS           {page} -> {src}")

    print()
    print("=== Bad Link / Archive Link Check ===")
    for page in LIVE_PAGES:
        html = ROOT / page
        if not html.exists():
            continue
        _, text = script_paths_from_html(html)

        hrefs = hrefs_from_html(text)
        for href in hrefs:
            if "_static_archive" in href:
                failures.append(("ARCHIVE_LINK", page, href))
                print(f"FAIL  ARCHIVE_LINK {page} -> {href}")
            if href.endswith("posko-medis.html") or href.endswith("verification-approval-old.html"):
                failures.append(("OLD_LINK", page, href))
                print(f"FAIL  OLD_LINK     {page} -> {href}")

    print()
    print("=== API Base Check ===")
    for js in sorted((ROOT / "assets/js").glob("*.js")):
        text = js.read_text(errors="replace")
        for bad in BAD_FRONTEND_API:
            if bad in text:
                failures.append(("BAD_API_BASE", rel(js), bad))
                print(f"FAIL  BAD_API_BASE {rel(js)} contains {bad}")

        if "RN_API_BASE" in text and GOOD_FRONTEND_API not in text and "window.OSIUN_API" not in text:
            failures.append(("API_BASE_REVIEW", rel(js)))
            print(f"WARN  API_REVIEW   {rel(js)} has RN_API_BASE but not {GOOD_FRONTEND_API}")

    print()
    print("=== Sidebar/Menu Check ===")
    for page in LIVE_PAGES:
        html = ROOT / page
        if not html.exists():
            continue
        _, text = script_paths_from_html(html)

        if '<aside class="sidebar">' not in text and page != "index.html":
            failures.append(("NO_SIDEBAR", page))
            print(f"FAIL  NO_SIDEBAR   {page}")

        missing_items = [item for item in REQUIRED_MENU_ITEMS if item not in text]
        if missing_items:
            print(f"WARN  MENU_REVIEW  {page} missing: {', '.join(missing_items[:6])}")
        else:
            print(f"OK    MENU         {page}")

    print()
    print("=== Session Role Script Check ===")
    for page in LIVE_PAGES:
        html = ROOT / page
        if not html.exists():
            continue
        _, text = script_paths_from_html(html)
        if "session-role.js" not in text:
            # auth page may include it too; all live pages should have it now.
            failures.append(("NO_SESSION_ROLE", page))
            print(f"FAIL  NO_SESSION_ROLE {page}")
        else:
            print(f"OK    SESSION_ROLE {page}")

    print()
    print("=== Summary ===")
    hard_failures = [f for f in failures if f[0] not in {"API_BASE_REVIEW"}]
    if hard_failures:
        print(f"FAILED: {len(hard_failures)} hard issue(s)")
        for f in hard_failures:
            print("-", f)
        sys.exit(1)

    print("NO_FAILED_FRONTEND_CHECKS")
    sys.exit(0)


if __name__ == "__main__":
    main()

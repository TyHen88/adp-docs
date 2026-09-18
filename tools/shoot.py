#!/usr/bin/env python3
"""docs/adp 의 화면 스크린샷을 다시 굽는다.

    set ADP_PW=...                                   # 비밀번호는 환경변수로만 준다
    python docs/adp/tools/shoot.py                   # 전부 다시 굽는다
    python docs/adp/tools/shoot.py --only frds,menu-tree
    python docs/adp/tools/shoot.py --list            # 대상만 보여준다

⛔ 비밀번호를 이 파일이나 md 에 적지 마라. 저장소에 들어가는 파일이다 —
   `ADP_PW` 환경변수로 준다. 아이디는 `ADP_USER`(기본 admin)다.

⚠ **그림은 글과 달리 코드에 대고 다시 잴 수가 없다.** 다른 쪽은 「verified on DATE」로
   실측을 보증하지만 스크린샷은 조용히 낡는다 — 화면이 바뀌면 이 스크립트를 다시 돌리는 것이
   유일한 방법이다. 그래서 굽는 절차를 사람 기억이 아니라 파일로 둔다.

⚠ 앱이 떠 있어야 한다(기본 http://localhost:8080). 뜨지 않았으면 아무것도 안 굽고 1 로 죽는다 —
   반쯤 구워 놓고 성공한 척하지 않는다.

필요한 것: `pip install playwright` + 브라우저. 이 저장소는 Playwright Java 로 이미
크로미움을 깔아 두므로(README 의 `--only-shell` 없는 설치) 보통 그것을 그대로 쓴다.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ADP = Path(__file__).resolve().parent.parent
SHOTS = ADP / "assets" / "shots"

BASE = os.environ.get("ADP_BASE", "http://localhost:8080")
VIEWPORT = {"width": 1440, "height": 900}
# ⛔ 2 로 올리지 마라 — 같은 화면이 71KB 에서 165KB 가 된다(2026-09-17 실측).
#    문서에 넣는 그림이라 1 로 충분하고, 열셋이면 저장소에 1MB 대 2MB 차이다.
SCALE = 1

# 왼쪽 메뉴 열셋. 열쇠는 그대로 파일 이름이 된다.
# ⚠ 정본은 `ShellContract.ARTIFACT_MENU_KEYS` 다 — 메뉴가 늘면 여기도 한 줄 는다.
MENUS: list[tuple[str, str]] = [
    ("frds", "FRD 작업"),
    ("srts", "SRT"),
    ("dev-requests", "개발요청서"),
    ("menu-tree", "IA"),
    ("design-guide", "디자인가이드"),
    ("business-language", "정책·표준용어"),
    ("solution-mockups", "솔루션 템플릿"),
    ("functional-specs", "기능명세서"),
    ("screen-designs", "화면설계서"),
    ("unit-tests", "단위테스트"),
    ("integration-tests", "통합테스트"),
    ("user-manual", "사용자 매뉴얼"),
]

# 관리 화면은 프로젝트 밖이라 주소 모양이 다르다.
ADMIN: list[tuple[str, str, str]] = [
    ("admin-system", "/admin/system", "시스템 관리"),
]


def login(page, user: str, password: str) -> str:
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.fill('input[name="username"]', user)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"], input[type="submit"]')
    page.wait_for_load_state("networkidle")
    if "/login" in page.url:
        raise SystemExit("로그인하지 못했다 — ADP_USER / ADP_PW 를 확인해라")
    # ⚠ 첫 로그인이면 비밀번호 변경 화면으로 간다. 그 상태로는 아무것도 못 찍는다.
    if "/password" in page.url:
        raise SystemExit("최초 비밀번호 변경이 안 끝난 계정이다 — 브라우저에서 먼저 끝내라")
    return page.url


def project_id(url: str) -> str:
    """로그인 뒤 떨어진 주소에서 프로젝트 번호를 집는다."""
    parts = url.split("/projects/")
    if len(parts) < 2:
        raise SystemExit(
            "준비된 프로젝트가 없다 — 관리 화면에서 클론이 끝난 프로젝트가 하나는 있어야 한다")
    return parts[1].split("/")[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="adp 화면 스크린샷을 굽는다")
    parser.add_argument("--only", help="쉼표로 구분한 열쇠만 굽는다")
    parser.add_argument("--list", action="store_true", help="대상만 보여주고 끝낸다")
    args = parser.parse_args()

    wanted = {k.strip() for k in args.only.split(",")} if args.only else None
    targets = [(k, v) for k, v in MENUS if not wanted or k in wanted]
    admin = [t for t in ADMIN if not wanted or t[0] in wanted]

    if args.list:
        for key, label in targets:
            print(f"{key:20} {label}")
        for key, _path, label in admin:
            print(f"{key:20} {label}")
        return 0

    password = os.environ.get("ADP_PW")
    if not password:
        print("ADP_PW 환경변수가 없다 — 비밀번호는 파일에 적지 않는다", file=sys.stderr)
        return 1
    user = os.environ.get("ADP_USER", "admin")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright 가 없다 — pip install playwright", file=sys.stderr)
        return 1

    SHOTS.mkdir(parents=True, exist_ok=True)
    made = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport=VIEWPORT, device_scale_factor=SCALE)
        page = context.new_page()
        landed = login(page, user, password)
        pid = project_id(landed)
        print(f"프로젝트 {pid} · {BASE}")

        for key, label in targets:
            page.goto(f"{BASE}/projects/{pid}/artifacts/{key}", wait_until="networkidle")
            # ⚠ 공용 껍데기가 로딩 덮개를 잠깐 띄운다 — 그대로 찍으면 덮개가 찍힌다.
            page.wait_for_timeout(600)
            target = SHOTS / f"{key}.png"
            page.screenshot(path=str(target))
            made += 1
            print(f"  {key:20} {label:16} {target.stat().st_size // 1024:>4} KB")

        for key, path, label in admin:
            page.goto(f"{BASE}{path}", wait_until="networkidle")
            page.wait_for_timeout(600)
            target = SHOTS / f"{key}.png"
            page.screenshot(path=str(target))
            made += 1
            print(f"  {key:20} {label:16} {target.stat().st_size // 1024:>4} KB")

        browser.close()

    write_manifest(made)
    print(f"{made} 장 구웠다 → {SHOTS.relative_to(ADP.parent.parent)}")
    return 0


def source_revision() -> str | None:
    """구운 순간의 소스 판. 잴 수 없으면 거짓말하지 말고 {@code None} 이다.

    ⚠ 이 작업 폴더는 git 저장소가 아닐 수 있다(2026-09-17 현재 그렇다) — 그때는 잴 것이 없다.
    ⛔ 없는 값을 「unknown」 같은 글자로 채우지 마라. 나중에 그 글자를 판으로 대조하려 든다.
    """
    import subprocess
    try:
        done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ADP,
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def write_manifest(count: int) -> None:
    """무엇을 언제 어느 판에서 구웠나를 파일로 남긴다.

    ⭐ <b>캡션의 날짜는 사람이 읽는 것이고 이 파일은 기계가 재는 것이다.</b> 그림은 글과 달리
    코드에 대고 다시 잴 수가 없어서 조용히 낡는데, 여기 적힌 판과 지금 판을 대조하면
    <b>얼마나 낡았나를 잴 수 있다</b>(2026-09-17 · we-adk-builder-main-56 제안).
    """
    import json
    from datetime import datetime, timezone

    shots = {}
    for path in sorted(SHOTS.glob("*.png")):
        shots[path.stem] = {"file": path.name, "bytes": path.stat().st_size}
    manifest = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "baseUrl": BASE,
        "viewport": VIEWPORT,
        "deviceScaleFactor": SCALE,
        "sourceRevision": source_revision(),
        "count": count,
        "shots": shots,
    }
    (SHOTS / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env bash
# cafe-os → 깃헙 푸시 스크립트
# 사용법: bash push_to_github.sh
#
# 사전준비: git 설치, 깃헙 로그인(또는 Personal Access Token)
set -e
cd "$(dirname "$0")"

REPO="https://github.com/waterfirst/cafe_moning_breez.git"

echo "☕ cafe-os 를 깃헙에 푸시합니다..."
echo "   대상: $REPO"
echo ""

# git 초기화 (이미 됐으면 통과)
if [ ! -d .git ]; then
    git init
    git config user.email "nakcho.choi@gmail.com"
    git config user.name "waterfirst"
fi

# 원격 저장소 연결 (이미 있으면 갱신)
if git remote | grep -q origin; then
    git remote set-url origin "$REPO"
else
    git remote add origin "$REPO"
fi

# 민감파일 재확인 (혹시 모를 키 노출 방지)
if git ls-files | grep -qE "cafe_config|\.db$"; then
    echo "⛔ 경고: 민감파일이 추적되고 있습니다. .gitignore 확인 필요!"
    git ls-files | grep -E "cafe_config|\.db$"
    exit 1
fi

# 커밋 (변경사항 있으면)
git add -A
if ! git diff --cached --quiet; then
    git commit -m "update: cafe-os $(date '+%Y-%m-%d %H:%M')"
fi

# 기존 저장소에 이미지/README가 있으므로, 먼저 가져와 병합
echo "기존 원격 내용 병합 중..."
git fetch origin main 2>/dev/null || true
git branch -M main

# 병합 (충돌 없이 합치기. 기존 이미지 보존)
if git rev-parse origin/main >/dev/null 2>&1; then
    git merge origin/main --allow-unrelated-histories -m "merge: 기존 저장소와 병합" || {
        echo ""
        echo "⚠️ 자동 병합 충돌. 아래 명령으로 수동 해결:"
        echo "   git status 로 충돌 파일 확인 → 수정 → git add → git commit"
        exit 1
    }
fi

# 푸시
echo "푸시 중..."
git push -u origin main

echo ""
echo "✅ 완료! https://github.com/waterfirst/cafe_moning_breez 확인하세요."

# CLAUDE.md — AI 작업 지침

> 이 파일은 Claude Code(AI)가 이 프로젝트에서 작업할 때 참조하는 런타임 컨텍스트입니다.
> 사람이 읽는 문서는 [README.md](README.md), 프로젝트 철학은 [SOUL.md](SOUL.md).

---

## 환경

| 항목 | 값 |
|------|-----|
| Python 실행 경로 | `C:\Users\Admin\AppData\Local\Programs\Python\Python313\python.exe` |
| 작업 디렉터리 | `C:\Users\Admin\Desktop\workspace` |
| Shell | PowerShell (Windows 11) |
| GitHub 리포 | `DSR-family/daily-brief` (branch: `master`) |

---

## 프로그램 실행

```powershell
$env:PYTHONIOENCODING = "utf-8"
& "C:\Users\Admin\AppData\Local\Programs\Python\Python313\python.exe" shipbuilding_daily.py
```

정상 실행 시 `reports/DSR동향_YYYYMMDD.html`이 생성되고 브라우저가 열린다.

---

## PowerShell 필수 주의사항

- `&&` 연산자 없음 → `;` 또는 순차 명령 사용
- 한글 출력 깨짐 → `$env:PYTHONIOENCODING = "utf-8"` 먼저 설정
- gh CLI 한글 이슈 등록 → `--body` 직접 사용 금지, 반드시 임시파일 경유:

```powershell
$tmp = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllText($tmp, $body, [System.Text.Encoding]::UTF8)
gh issue create --repo js-oh503/ai-test --title "제목" --body-file $tmp --label "bug"
Remove-Item $tmp
```

- gh CLI PATH 갱신 필요 시:

```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
```

---

## 커스텀 스킬 목록

| 스킬 이름 | 호출 예시 | 역할 |
|-----------|----------|------|
| `report-audit` | "보고서 감사해줘" | 최신 HTML 보고서 품질 검토 → GitHub 이슈 등록 |
| `fix-issue` | "이슈 #N 수정해줘" | 이슈 확인 → 댓글 → 코드수정 → 커밋 → 닫기 |
| `issue-write` | "이슈 등록해줘" | 문제를 GitHub 이슈로 작성·등록 |
| `issue-runner` | "이슈 러너" | 열린 이슈 전체를 우선순위순 자동 처리 |
| `code-audit-fix` | "오류 분석하고 수정해줘" | 코드 전체 분석 → 버그 발굴 → 이슈 등록 → 수정 → 커밋 전 사이클 |

스킬 파일 위치: `.claude/skills/<name>/SKILL.md`

---

## 코드 수정 규칙

- HTML/CSS는 `build_html()` 함수 내 f-string 안에 있음 (이중 중괄호 `{{`, `}}` 필수)
- 번역 대상 요소: `.card-title`(링크 텍스트 노드만 교체), `.card-body`
- DSR 분석 텍스트(`.itext`)는 Python에서 한국어로 직접 생성 → 번역 불필요
- `score_article()`, `dsr_relevance()`, `action_recommendation()` 세 함수가 분석 핵심
- 보고서 파일명: `reports/DSR동향_YYYYMMDD.html`

---

## 의존성

```
feedparser   # requirements.txt에 명시
```

Claude API 키 불필요. 번역은 브라우저에서 `translate.googleapis.com` 무료 엔드포인트 사용.

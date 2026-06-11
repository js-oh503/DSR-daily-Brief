---
name: briefing-improver
description: >
  보고서 품질 감사 → 이슈 등록 → 이슈 전체 수정 → 문서 최신화를
  한 번에 순서대로 실행한다.
  "브리핑 개선해줘", "보고서 전체 점검해줘", "/briefing-improver" 요청에 사용한다.
when_to_use: >
  보고서·코드·문서를 한꺼번에 점검하고 고치고 싶을 때 호출한다.
  개별 스킬(issue-write / issue-runner / doc-optimizer)을 따로 부를 필요 없이
  이 스킬 하나로 전체 사이클을 완료한다.
argument-hint: "[repo]"
arguments: [repo]
allowed-tools: Read, Glob, Grep, Edit, Write, Bash, PowerShell
---

## 역할

아래 4단계를 순서대로 실행한다.
각 단계가 완전히 끝난 뒤 다음 단계로 넘어간다.

```
[1] 보고서 감사    → 문제 목록 도출
[2] 이슈 등록     → 문제를 GitHub 이슈로 기록
[3] 이슈 전체 수정 → 등록된 이슈를 우선순위순 자동 처리
[4] 문서 최신화   → 변경 내용을 세 문서에 반영
```

---

## 실행 절차

### 공통 준비

```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
$env:PYTHONIOENCODING = "utf-8"
```

`$repo`가 없으면 현재 디렉터리의 git remote origin에서 추출:
```powershell
git remote get-url origin
# → https://github.com/owner/repo.git 에서 owner/repo 추출
```

---

### 1단계: 보고서 감사 (`report-audit` 위임)

`reports/` 폴더에서 가장 최근 HTML 파일을 찾아 아래 4가지 기준으로 분석:

| 기준 | 확인 내용 |
|------|----------|
| 관련성 | 업무·도메인과 무관한 기사 포함 여부 |
| 시의성 | 최근 24시간 밖의 오래된 기사 포함 여부 |
| 중복 | 동일 사건의 중복 기사 여부 |
| 수치 출처 | 구체적 수치에 출처 표기 여부 |

결과를 아래 표 형식으로 보고 후 2단계 진행:

```
## 감사 결과
| 기준     | 건수 | 내용 요약 |
|----------|------|-----------|
| 관련성   | N건  | ...       |
| 시의성   | N건  | ...       |
| 중복     | N건  | ...       |
| 수치출처 | N건  | ...       |
```

문제가 0건이면 1·2단계를 건너뛰고 3단계(이슈 러너)로 이동.

---

### 2단계: 이슈 등록 (`issue-write` 위임)

1단계에서 발견한 문제마다 GitHub 이슈를 등록한다.

분류 기준:
- 코드 결함 → `bug` 라벨
- 필터·로직 개선 → `enhancement` 라벨

한글 인코딩 문제 방지: 반드시 임시 파일 경유:
```powershell
$tmp = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllText($tmp, $body, [System.Text.Encoding]::UTF8)
gh issue create --repo $repo --title "[버그/개선] 제목" --body-file $tmp --label "bug"
Remove-Item $tmp
```

등록 후 이슈 URL 목록을 보고:
```
등록된 이슈:
- #N [제목](URL) — bug
- #N [제목](URL) — enhancement
```

---

### 3단계: 이슈 전체 수정 (`issue-runner` 위임)

열린 이슈를 우선순위순으로 전부 처리:

우선순위: `bug` → `enhancement` → `question` → 번호 오름차순

각 이슈마다:
1. `gh issue view [번호] --repo $repo` 로 내용 확인
2. 관련 코드 Grep·Read로 파악
3. **코드 수정 전** 수정 계획을 이슈 댓글로 등록 (임시 파일 경유)
4. Edit로 코드 최소 수정
5. 실행 확인:
   ```powershell
   & "C:\Users\Admin\AppData\Local\Programs\Python\Python313\python.exe" shipbuilding_daily.py
   ```
6. 커밋 & 푸시 (`close #N` 포함):
   ```powershell
   git add [수정파일]
   git commit -m "fix: [요약] (close #[번호])"
   git push origin master
   ```

이슈 1개가 완전히 끝난 뒤 다음 이슈로 이동 (병렬 처리 금지).

완료 후 요약 보고:
```
## 이슈 처리 결과
| # | 제목 | 결과 |
|---|------|------|
| #N | ... | 완료 (커밋 SHA) |
```

---

### 4단계: 문서 최신화 (`doc-optimizer` 위임)

3단계에서 코드가 변경됐다면 세 문서가 현재 상태를 정확히 반영하는지 점검하고 업데이트:

점검 항목:
- `CLAUDE.md` — 새 함수·경로·스킬·주의사항이 추가됐는가?
- `README.md` — 파일 구조·실행 방법·FAQ가 바뀌었는가?
- `SOUL.md` — 발전 방향 메모에 반영할 내용이 있는가?

변경이 없으면 이 단계는 건너뜀.

변경이 있으면 해당 문서만 최소 수정 후 커밋:
```powershell
git add CLAUDE.md README.md SOUL.md   # 변경된 것만
git commit -m "docs: update after briefing-improver run"
git push origin master
```

---

## 최종 보고 형식

```
## briefing-improver 실행 결과

### 1. 보고서 감사
[감사 결과 표]

### 2. 등록된 이슈
[이슈 URL 목록]

### 3. 이슈 처리
[이슈 처리 결과 표]

### 4. 문서 업데이트
[변경된 문서 목록 또는 "변경 없음"]
```

---

## 주의사항

- PowerShell `&&` 사용 불가 → `;` 사용
- 각 단계는 반드시 순서대로, 이전 단계 완료 후 진행
- 이슈가 없거나 코드 변경이 없는 단계는 자동으로 건너뜀

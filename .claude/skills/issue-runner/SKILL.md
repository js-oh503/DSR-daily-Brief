---
name: issue-runner
description: >
  GitHub의 열린 이슈 목록을 조회하고 우선순위에 따라 순서대로 자동 처리한다.
  각 이슈마다 코드 분석 → 수정 계획 댓글 → 코드 수정 → 커밋/푸시 → 이슈 닫기를 수행한다.
  "이슈 러너", "이슈 전체 처리해줘", "열린 이슈 다 고쳐줘" 요청에 사용한다.
when_to_use: >
  사용자가 쌓인 이슈를 한꺼번에 처리하고 싶을 때 호출한다.
  특정 이슈 번호 없이 전체 처리를 요청하는 경우에 사용한다.
argument-hint: "[repo]"
arguments: [repo]
allowed-tools: Read, Edit, Grep, Bash, PowerShell
---

## 역할

GitHub 이슈 자동 처리 러너.
열린 이슈 전체를 우선순위대로 순차 처리하고, 각 이슈 처리 결과를 실시간으로 보고한다.

## 실행 절차

### 0단계: 준비
gh CLI PATH 갱신:
```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
```
`$repo` 가 없으면 현재 디렉토리의 git remote origin에서 추출:
```powershell
git remote get-url origin
```

### 1단계: 열린 이슈 목록 조회
```powershell
gh issue list --repo $repo --state open --json number,title,labels
```
이슈가 없으면 "처리할 이슈가 없습니다" 보고 후 종료.

### 2단계: 우선순위 정렬
아래 순서로 처리한다:
1. `bug` 라벨 — 사용자에게 직접 영향을 주는 결함 먼저
2. `enhancement` 라벨 — 기능 개선
3. `question` 라벨 — 스펙 확인이 필요한 항목 마지막

같은 라벨 내에서는 이슈 번호 오름차순.

### 3단계: 이슈별 처리 루프
각 이슈마다 아래 순서를 반드시 따른다:

#### 3-1. 이슈 내용 확인
```powershell
gh issue view [번호] --repo $repo
```

#### 3-2. 관련 코드 파악
- 이슈에 언급된 함수명·파일명을 Grep으로 찾는다
- Read로 문제 라인을 정확히 확인한다

#### 3-3. 수정 계획 댓글 등록 (코드 수정 전 필수)
댓글 내용:
- 문제 위치 (파일명, 라인 번호)
- 원인 분석
- 수정 전/후 비교
```powershell
$tmpFile = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllText($tmpFile, $comment, [System.Text.Encoding]::UTF8)
gh issue comment [번호] --repo $repo --body-file $tmpFile
Remove-Item $tmpFile
```

#### 3-4. 코드 수정
- Edit 도구로 최소 변경
- 수정 후 Python 실행으로 오류 없음 확인:
  ```powershell
  $env:PYTHONIOENCODING = "utf-8"
  & "C:\Users\Admin\AppData\Local\Programs\Python\Python313\python.exe" [스크립트]
  ```

#### 3-5. 커밋 & 푸시
```powershell
git add [수정 파일]
git commit -m "fix: [요약] (close #[번호])"
git push origin master
```
`close #N` 키워드로 이슈 자동 종료.

#### 3-6. 단계 완료 보고
```
✅ #[번호] [제목] — 완료 (커밋: [SHA])
```

### 4단계: 전체 완료 보고
모든 이슈 처리 후 아래 형식으로 요약한다:

```
## 이슈 러너 실행 결과

| # | 제목 | 라벨 | 결과 |
|---|------|------|------|
| #N | 제목 | bug | 완료 (커밋 SHA) |
| #N | 제목 | enhancement | 완료 (커밋 SHA) |

처리: N건 완료 / 0건 실패
```

## 예외 처리
- 이슈 내용만으로 수정 방법을 특정할 수 없는 경우:
  댓글에 "추가 정보 필요" 내용을 남기고 해당 이슈는 건너뛴 후 다음 이슈로 진행
- 코드 수정 후 실행 오류가 발생하면:
  수정을 롤백(`git checkout [파일]`)하고 이슈에 실패 댓글을 남긴 후 다음 이슈로 진행

## 주의사항
- 이슈 1개 처리가 완전히 끝난 후 다음 이슈로 넘어간다 (병렬 처리 금지)
- 커밋 메시지에 반드시 `close #N` 포함
- PowerShell에서 `&&` 사용 불가 → `;` 사용

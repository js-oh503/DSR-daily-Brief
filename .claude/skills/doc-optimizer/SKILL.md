---
name: doc-optimizer
description: >
  프로젝트 문서 상태를 점검하고 CLAUDE.md·SOUL.md·README.md 세 문서로
  역할을 분리해 중복 없이 최소·정확하게 재작성한다.
  낡거나 중복된 문서는 삭제하고 GitHub에 커밋·푸시한다.
  "문서화해줘", "문서 정리해줘", "/doc-optimizer" 요청에 사용한다.
when_to_use: >
  프로젝트 문서가 없거나 낡았거나 중복·혼재된 상태일 때 호출한다.
argument-hint: "[repo]"
arguments: [repo]
allowed-tools: Read, Glob, Grep, Edit, Write, Bash, PowerShell
---

## 역할

프로젝트 문서를 세 파일로 정리한다.
각 사실은 한 문서에만 존재하고, 나머지는 링크로 참조한다.

| 파일 | 독자 | 담당 |
|------|------|------|
| `SOUL.md` | 사람 (전략·기획) | 프로젝트 존재 이유, 배경, "좋은 결과물" 기준, 의도적 제약 |
| `README.md` | 사람 (운영·개발) | 설치·실행·파일 구조·FAQ |
| `CLAUDE.md` | Claude Code (AI) | 환경 변수·경로, 셸 함정, 명령 패턴, 스킬 목록, 코드 수정 규칙 |

---

## 실행 절차

### 1단계: 현황 파악

```powershell
git ls-files | Select-String "\.md$"
```

- 어떤 `.md` 파일이 있는지 목록화
- 각 파일을 Read로 전체 내용 확인
- 세 문서 중 없는 것, 낡은 것, 중복 내용이 있는 것을 메모

파악 후 아래 형식으로 사용자에게 먼저 보고한다:

```
## 현황
| 파일 | 상태 | 조치 |
|------|------|------|
| README.md | 없음 | 신규 생성 |
| 설정방법.md | 낡음 (구 파일명·API키 언급) | README.md로 통합 후 삭제 |
| CLAUDE.md | 없음 | 신규 생성 |
| SOUL.md | 없음 | 신규 생성 |
```

### 2단계: SOUL.md 작성

아래 구조로 작성한다:

```markdown
# SOUL.md — 프로젝트 존재 이유

> 기술 설정은 [README.md](README.md), AI 작업 지침은 [CLAUDE.md](CLAUDE.md).

## 우리는 누구인가
## 왜 이것을 만들었는가
## 무엇이 "좋은 결과물"인가
## 의도적으로 하지 않는 것
## 발전 방향 (메모)
```

규칙:
- 코드·명령어 없음. 철학·배경·기준만.
- 기술 세부사항은 README로 링크.

### 3단계: README.md 작성

아래 구조로 작성한다:

```markdown
# 프로젝트명

한 줄 소개. → 배경은 [SOUL.md](SOUL.md) 참고.

## 무엇을 하는가 (기능 요약)
## 사전 준비
## 실행 방법
## 자동화 설정 (있을 경우)
## 파일 구조
## 기타 도구·스킬 (있을 경우)
## FAQ
```

규칙:
- AI 작업 지침(Python 경로, 셸 함정 등)은 CLAUDE.md로 링크.
- 프로젝트 철학은 SOUL.md로 링크.

### 4단계: CLAUDE.md 작성

아래 구조로 작성한다:

```markdown
# CLAUDE.md — AI 작업 지침

> 사람이 읽는 문서는 [README.md](README.md), 철학은 [SOUL.md](SOUL.md).

## 환경 (경로·버전·리포)
## 프로그램 실행 명령
## 셸 함정·주의사항
## 스킬 목록
## 코드 수정 규칙
## 의존성
```

규칙:
- 운영 방법(설치·실행)은 README로 링크.
- 이 파일에는 AI가 작업할 때만 필요한 정보만.

### 5단계: 낡은 문서 삭제

중복·대체된 파일을 git에서 제거:

```powershell
git rm <낡은파일.md>
```

### 6단계: 커밋 & 푸시

```powershell
git add CLAUDE.md SOUL.md README.md
git commit -m "docs: restructure into CLAUDE.md / SOUL.md / README.md"
git push origin master
```

---

## 중복 제거 원칙

- **한 사실은 한 문서에만.** 같은 내용이 두 곳에 있으면 한쪽을 삭제하고 링크로 대체.
- **낡은 사실은 즉시 삭제.** 더 이상 맞지 않는 내용(구 파일명, 삭제된 기능, 구 API 키 안내 등)은 수정하지 말고 삭제.
- **최소화.** 추가할 때마다 "이게 없으면 작업이 막히는가?"를 확인. 아니라면 쓰지 않는다.

## 주의사항

- gh CLI PATH 갱신:
  `$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")`
- PowerShell `&&` 사용 불가 → `;` 사용

# FP Studio 0.3.0

**OpenWorker 원본 GUI에서 대화로 리서치하고 인포그래픽을 만드는 추가 기능 소스.**

이 패키지는 실행 가능한 독립 DMG가 아니라, 고정된 OpenWorker 원본에 적용하는 **소스 overlay + 조립 도구**다. 원본 전체 저장소, 모델 키, 폰트 파일, 서명 인증서, 이미 빌드된 앱은 포함하지 않는다. v0.1의 별도 GUI는 사용하지 않는다.

## 제품의 경계

- Sidebar, Composer, Transcript, Settings, 원본 RightRail/Artifact Viewer를 유지한다.
- 사용자는 같은 채팅에서 요청, 리서치, 확인, 수정, 최종 파일 요청을 한다.
- 새로운 Canvas, Inspector, 프로젝트 대시보드, 템플릿 선택 화면은 없다.
- Agent는 FP SDK의 문법과 composition API로 내용을 구성한다. 준비된 결과물을 고르는 제품이 아니다.
- OMP 또는 Figma 연결은 필요하지 않다. 모델·세션·승인·검색은 OpenWorker가 담당한다.
- 원본 OpenWorker의 일반 도구와 권한 체계는 남아 있다. 이 빌드가 OS 수준의 제한된 그래픽 전용 sandbox라는 뜻은 아니다.

### 좁힌 표면 (0.3.0)

원본에서 **제거하거나 감춘** 것과 그 이유:

| 표면 | 상태 | 이유 |
|---|---|---|
| 모델 공급자 | 4개 벤더 × (API 키 \| 구독 로그인) = 8가지 | 제품이 실제로 지원하는 경로만 설정에 노출. 나머지 descriptor는 router 호환을 위해 남지만 설정에 없다 |
| 모델 목록 | 연결·검증 시 벤더 목록을 조회해 자동 갱신 | 사람이 모델 id를 손으로 입력하지 않는다. 목록을 못 받으면 기존 목록 유지 |
| 언어 | 시스템 / English / 한국어 | 중국어 선택 제거(카탈로그는 parity 검사를 위해 유지) |
| 작업 공간 | `~/fpstudio` 고정, 기본 신뢰 | 폴더 선택기·신뢰 프롬프트·신뢰 목록 화면 없음 |
| 코워커(페르소나) 설정 탭 | 숨김 (`ocw.flag.personas`) | 단일 작업 방식 제품에 선택기는 잡음 |
| 자동화 / 수신함 / 클라우드 로그인 | 화면 제거 | 로그인 계층이 없으므로 계정 행 대신 커넥터·설정·활동 아이콘 |
| 업데이트 | UI·배너 제거, updater endpoint 없음 | 이 빌드는 자체 업데이트를 하지 않는다 |
| 표면 문구 | "OpenWorker"·"coworker" 미표시 | 내부 식별자/경로는 그대로, 사용자에게 보이는 문구만 FP Studio·에이전트 |

앱 아이콘은 흰 바탕의 FOUR PILLARS 4점 마크다. `assets/icons`가 원본 아이콘 슬롯을 대체하며, 각 파일의 sha256이 patch manifest에 기록된다.

### 디자인 규칙은 런타임 강제 규칙이다

FOUR PILLARS 디자인 가이드라인을 **앱 번들 안에 원문 그대로** 넣고, 인덱스 스킬로 라우팅한다. 각 규칙은 두 부분으로 제공된다: `SKILL.md`는 모델이 실제로 결정하는 것(프레임/배경 준수, 타이포 위계, 컬러 상황, 원본 충실도)만 담는 결정 카드이고, `APPENDIX.md`는 렌더러가 Frame Guide에서 그려내는 프레임 산술·Figma 노드 id·정확한 fill/stroke/마커 기하를 원문 그대로 보관한다. 카드는 저작하는 모든 호출에 재전송되고, 부록은 값이 의심될 때만 읽는다. digest 하나가 두 파일을 함께 덮으므로 어느 쪽을 고쳐도 이전 acknowledgement는 무효가 된다.

- `fp-design-system` (인덱스: 프레임·타이포·컬러 + 문법별 라우팅 표는 부록)
- `fp-design-table`, `fp-design-chart`, `fp-design-flowchart`, `fp-design-reproduce`

`fp_guide('draw', name='<문법>')`가 한 번의 호출로 문법 계약·프레임 필드·필요한 카드 전체와 digest 맵을 돌려주고(규칙만 따로 읽으려면 `fp_design_rules(kind)`, 부록은 `appendix=True`), `fp_render`는 **문서에 쓰인 문법이 요구하는 모든 규칙의 현재 digest를 제시하지 않으면 렌더를 거부**한다. 추가로 결정 가능한 항목(24 미만/4의 배수 아닌 글자 크기, 팔레트 변수 대신 raw hex, 비어 있거나 placeholder인 H1/H2/Source/Date/Note)은 렌더 전에 기계적으로 거부한다.

강조 선택, 범례 마커 모양, x축 라벨 기울기, 벡터 stroke, 샘플 충실도는 **기계가 검사하지 않는다.** 규칙이 컨텍스트에 있고 사용자가 검토하는 것으로 보장한다. 렌더가 통과했다는 사실이 디자인 규칙 준수의 증거는 아니다.

### 표는 잘리지 않고 줄바꿈하고, 가로줄만 갖는다

셀은 최대 4줄까지 줄바꿈하고 행 높이는 그 줄 수를 따른다. 열 너비는 그 열의 **가장 긴 단어**보다 좁아지지 않으므로 단어 중간에서 끊기지 않는다(`recordkeepin / g` 같은 것이 나오지 않는다). 0.3.0까지는 셀이 `maxLines: 1` + 고정 행 pitch로 그려져서 긴 문장이 `…`로 잘려 나갔고, 행 높이를 키우면 프레임만 늘어났다. 그리고 헤더 아래와 모든 행 사이에 가로 구분선이 들어간다 — **세로줄은 없다**. 열 간격이 이미 열을 구분하고, 격자를 다 그으면 스프레드시트로 읽힌다.

### 한 행에 막대 두 개는 `style:'paired'`다

before/after, 두 날짜, 계획 대 실적처럼 **한 행에 막대가 둘인 원본**은 `template:'bar'` +
`style:'paired'`로 그린다. `fields.columns`가 계열을 원본의 순서대로 지명하고, 범례·행
라벨·두 값 모두 함께 나온다. 값은 원본이 쓴 문자열(`839.8M`, `$0.58`, `7.0%`) 그대로 둘 수
있다 — 인쇄는 문자 그대로, 막대 길이는 그 크기에서 계산한다. 행마다 단위가 다르면(개수 ·
APT · % · USD) 기본값인 **행별 정규화**가 적용되고, 그래서 막대 쌍이 낙폭을, 인쇄된 숫자가
수준을 전달한다. 모든 행이 한 단위면 `scale:'shared'`로 행끼리도 길이를 비교한다.
`fields.unit`은 행 라벨 아래 단위, `fields.delta`는 오른쪽 변화 열, `fields.group`은 그룹
머리글이다. 0.3.2까지는 이 문법이 없어서 두 계열을 넣을 자리가 없었고, 실제 재현 요청에서
모델이 한 계열을 100으로 지수화해 **같은 길이의 막대 7개**를 내보냈다. 문법에 없는 것은
프롬프트로 고쳐지지 않는다.

### 한 장을 만드는 데 쓰는 호출 수가 비용이다

모든 호출은 그 대화 전체를 다시 보낸다. 그래서 0.3.1에서 경로를 줄였다: **재현은 리서치도 리뷰도 필요 없다**(원본이 증거다) — `fp_guide('draw', name, redraw=True)` → `fp_render`가 전부다. `fp_review`는 최종 납품 단계 것이고 초안마다 돌리는 것이 아니다. `fp_guide('draw')` 한 번이 브리핑 전체라서 vocabulary·input·grammar를 따로 받을 이유가 없다. 0.3.0 실제 세션이 인포그래픽 한 장에 입력 토큰 1,869,070개를 쓴 이유는 이 세 가지에 첨부 캡처 버그와 잘림 경고 루프가 겹친 것이었다.

0.3.3에서 하나 더 막았다: **이미 받은 계약은 두 번 주지 않는다.** 두 번째 사본이야말로 비싼
쪽이다 — 대화에 남아 이후 모든 호출에서 다시 청구된다. 같은 문법 계약·프레임 필드·규칙
카드를 다시 요청하면 본문 대신 포인터가 돌아오고, 압축(compaction)으로 정말 사라졌을 때만
`again=True`로 본문을 다시 받는다(부록은 억제하지 않는다). 그리고 `fp_guide('vocabulary')`의
`next` 문구가 옛 4-콜 경로를 가리키고 있었고 문법의 `style` 목록이 어디에도 공개되지 않아
모델이 렌더러 소스를 뒤졌다 — 카탈로그가 이제 문법별 style과 용도를 함께 돌려준다.

## 실제 대화 흐름

0. 사용자가 이미지를 첨부했거나 다이어그램·표를 붙여넣었다면 흐름은 여기서 갈린다. **재현이 1원칙**이고, 아래 4번은 "새로 구성"이 아니라 "전사 → FP 시각 체계로만 교체"가 된다. 모델 지시문의 첫 항목도 이것이다.
1. 사용자가 자료와 전달하려는 메시지를 채팅에 넣는다.
2. 중요한 조건이 빠졌을 때만 기존 채팅/ask_user로 확인한다.
3. 기존 web_search로 찾고 web_fetch로 본문을 읽는다. 성공한 fetch의 실제 텍스트, URL, 해시, 조회 시각을 보관한다.
4. Agent가 내용과 관계에 맞춰 초안을 구성해 fp_render를 호출한다.
5. 기존 Artifact Viewer가 열리고 실제 SVG가 표시된다. PNG도 기존 artifact 링크로 열 수 있다.
6. 사용자가 같은 채팅에서 수정한다. 수정은 `fp_edit`가 JSON pointer 연산으로 처리한다 - 문서 전체를 다시 보내지 않는다. 완료된 렌더 체크포인트마다 열려 있는 결과가 갱신된다. 토큰마다 SVG를 만드는 방식은 아니다.
7. fp_review로 미해결 질문, 출처에 없는 인용문, 변경된 숫자 연결을 검사한다.
8. 사용자가 최종 파일을 요청하면 fp_publish가 버전 고정된 SVG/PNG와 출처 보고서를 만든다.

### 사용자가 건네준 것은 새로 창작하지 않고 그대로 다시 그린다

사용자가 이미지를 붙이거나 ASCII 다이어그램·mermaid·표를 **채팅에 그대로 붙여넣고** "우리 디자인으로"라고 하면, 문법·구조·계층·화살표·데이터·문구는 이미 그 원본이 정했다. 바뀌어야 하는 것은 FP의 시각 체계뿐이다. 텍스트로 붙여넣은 구조도 첨부 이미지와 똑같은 원본이다 — 이미지만 원본으로 취급한 것이 붙여넣은 아키텍처 다이어그램을 "라우팅"해서 계층이 다른 새 구성으로 만들어버린 원인이었다.

그래서 메시지가 서버에 도착하는 즉시, 첨부 이미지와 붙여넣은 구조가 모두 워크스페이스에 파일로 저장되고 sha256 영수증이 남는다(`fp/attachments/`, base64는 히스토리에 남기지 않는다). 붙여넣은 텍스트는 그대로 읽을 수 있는 증거라서 `fp_source_text`로 원문을 다시 인용할 수 있다. 탐지기는 일부러 좁다: 박스 그리기/화살표 글리프, ASCII 박스 괘선(`+---`), 마크다운 표 구분선, 다이어그램 언어를 지정한 코드펜스만 잡는다. 산문과 붙여넣은 코드는 잡히지 않는다.

Agent는 `fp_inspect`의 `references`에서 source id를 받아 문서에 `reference`(원본에서 읽은 블록·노드·엣지·범주·계열·값)를 쓰고 렌더한다.

게이트가 기계적으로 막는 것: 원본과 다른 문법으로 갈아타기, 원본에 없는 블록 추가, **빠뜨리거나 새로 만든 노드**, **빠뜨리거나 새로 만들거나 방향이 뒤집힌 화살표**, 전사에 없는 값(반올림·추정 포함), 전사에 없는 라벨(고쳐 쓴 문구). 그리고 사용자가 건네준 원본은 더 이상 조용히 무시할 수 없다 — 전사하거나, 사용자가 다른 것을 요청했다는 **그 사람의 말**을 `referenceWaiver`에 적거나 둘 중 하나다. 커밋된 revision의 영수증에는 어떤 원본을(sha256) 몇 개의 노드·엣지로 다시 그렸는지 남는다. 규칙 본문은 `fp-design-reproduce`이며 재현 모드에서 필수다.

게이트가 보장하지 못하는 것: **전사 자체가 원본을 옳게 읽었는지**. 그건 규칙(전사 먼저, 못 읽은 값은 질문)과 사용자 확인의 몫이다.

### 각주(note)는 출처가 있어야 프레임에 들어간다

프레임 하단 밴드의 `note`는 모델이 떠올린 캡션이 아니다. 세 가지 출처 중 하나여야 하고, 아니면 렌더 전에 거부된다: 사용자가 요청했고 **그 사람의 말**이 `noteRequest`에 적혀 있거나, 다시 그리는 원본의 각주가 `reference.note`에 전사되어 있거나, illustrative(가상/예시) 모드가 요구하는 라벨이거나. 길이 제한(한 줄, 80자)은 그대로다 — 워터마크 아래로 흐르는 문장을 막는 기하 제약이고, 출처 규칙은 "아무도 부탁하지 않은 한 줄"을 막는 제약이다.

### 최종 검수는 선언이 아니라 게이트다

설계 규칙을 세션 초반에 읽고 마지막에 "다 됐습니다"라고 말하는 사이에는 수십 번의 호출이 있다. 컴파일러가 잡지 못하는 규칙(x축 라벨 기울이기, 범례 마커가 렌더 타입과 일치, 첫 열은 음영 금지, 샘플에 있던 색을 빼지 않기)이 바로 그 사이에서 잊힌다.

그래서 `fp_review`가 **이 문서의 문법에 해당하는 규칙만 골라 원문 그대로** 다시 돌려준다(항목마다 id). `fp_publish`는 모든 id에 판정(`pass`, 또는 사유가 붙은 `n/a`)이 오기 전까지 거부한다. 표 문서면 fp-design-system + fp-design-table(84항목), 차트면 chart 규칙이 대신 들어간다. 발행 영수증에는 몇 개 규칙을 어떤 digest의 규칙으로 검수했는지 기록된다.

이 게이트가 증명하는 것은 **규칙이 다시 제시되고 답변됐다**는 사실이지, 답변이 참이라는 것이 아니다. 검수 체크리스트는 최종 발행 직전 1회만 주입된다(표 기준 약 17,000자) — 렌더·편집 결과에는 절대 붙지 않는다.

### 대화 비용은 설계 대상이다

실제 세션 1건(인포그래픽 1장, 모델 호출 50회)의 입력은 약 397만 토큰이었다. 히스토리는 호출마다 전량 재전송되므로, 한 번 남긴 큰 payload는 이후 모든 호출에서 다시 청구된다. 측정된 원인은 `fp_research` 인자 25%, `fp_render` 인자 17%, web_fetch 본문 17%, SDK 전체 dump 14%였다.

그래서 쓰기와 읽기 경로를 바꿨다. `fp_edit`/`fp_research_edit`는 변경 지점만 pointer 연산으로 보내고(같은 문법 검사·설계 게이트·revision CAS·컴파일러를 그대로 통과한다), `fp_inspect`는 문서 대신 outline과 해시를 돌려주며 필요한 부분만 `fp_source`로 읽는다. web_fetch는 페이지 앞부분만 반환하고 전문은 provenance receipt에 남아 `fp_source_text(source_id, find=...)`로 검색한다. 같은 세션을 새 도구 표면으로 환산하면 약 194만 토큰(-52%)이다. 이 수치는 실제 기록을 재계산한 것이고, 편집 연산 크기는 실측 평균(182자)을 사용한 추정이다.

남은 고정비도 정리했다. FP 지시문과 도구 스키마는 결과와 달리 **모든 모델 호출에 무조건 실린다**(기본 한 턴 최대 12회). 지시문은 정책만, docstring은 호출 방법만 담도록 중복을 걷어내 15,479자 → 12,762자로 줄였고, 여기에 기능을 세 번 더했다: 재현 모드(`fp_capture_image` + 재현 규칙), 최종 검수 게이트(`fp_review`/`fp_publish`), 그리고 사용자가 건네준 원본의 라우팅(붙여넣은 구조 포착과 `referenceWaiver`). 현재 15,158자다. 예산은 `test_fp_token_economy.py`가 상한(스키마+지시문 15,300자, 도구 1개당 1,300자)으로 고정하므로, 정책을 docstring에 다시 쓰거나 호출 방법을 지시문에 다시 쓰면 테스트가 깨진다. 상한을 올리는 것은 리팩터링이 아니라 제품 결정이고, 이유는 테스트 docstring에 남는다.

실측(120행 표 문서 10,383자, 규칙 2건 + 문법 2건 읽기 + 최초 렌더 + 편집 5회):

| 프로토콜 | 모델 호출 | 세션 총 입력 |
|---|---:|---:|
| 전체 스냅샷(v0.2 방식, 추정) | 15 | 약 333,000 토큰 |
| 델타 방식 + 편집마다 fp_inspect | 15 | 212,234 토큰 |
| 델타 방식, 쓰기 결과의 revision 재사용(현재 지시문) | 10 | **115,866 토큰** |

남은 최대 항목은 고정비(호출당 14,143자)와 설계 규칙 본문(index 8,830 + 문법 3,564자)이다. 규칙은 요약이 아니라 원문이어야 하므로 한 번은 반드시 히스토리에 남는다 — 대신 필요한 문법의 규칙만 라우팅해서 읽는다.

**출처를 읽었다는 기록은 주장의 진실성을 증명하지 않는다.** 도구는 원문 수신과 일치, 숫자 연결을 검사한다. 자료 신뢰도, 의미상 뒷받침, 인과관계, 미적 완성도는 사용자와 Agent가 별도로 검토해야 한다.

## v0.2에서 바꾼 핵심

| 문제 | 변경 |
|---|---|
| 저장 도구가 READ로 분류 | FP 변경 도구를 WRITE_LOCAL로 고정, 기존 승인·Plan 정책 유지 |
| 중첩 JSON이 해시에서 누락 | 재귀 직렬화, 입력형·크기 검사 |
| 동시 변경 덮어쓰기 | 문서·리서치 revision CAS |
| 저장 도중 원본/그림 불일치 | SQLite 트랜잭션에 원본·SVG·PNG 저장, 표시 파일은 복구 가능한 캐시 |
| 과거 복원이 현재 renderer에 의존 | 보관된 원본과 SVG/PNG 바이트를 그대로 새 revision으로 복원 |
| 뒤늦은 프리뷰 응답 | latest-request guard와 session cleanup |
| Stop이 렌더 프로세스를 남김 | 기존 Stop hook에 렌더 프로세스 그룹 취소 연결 |
| 개발 환경에서만 찾는 SDK | 설치 앱의 runtime resource 경로 지원 |
| 중첩 Node와 compiler 의존성 누락 | node_modules 포함, 서명 시점·JIT entitlement·빌드 manifest 추가 |
| 리서치가 채팅 텍스트에만 존재 | 실제 수신 자료와 주장·수치 연결, 버전별 출처 보고서 |

전체 리뷰: [docs/REVIEW.md](docs/REVIEW.md).

## 검증 상태

이 패키지에서 실행한 검사: **Python 74개, JavaScript 27개, TypeScript 미리보기 helper 3개, 총 104개 통과.**

조립한 checkout에서 실행한 검사(이 패키지 밖, 원본 포함): **Python 2082개 통과 + 1 skip, GUI vitest 189개 통과, tsc 통과.** 조립 결과가 검증한 트리와 **바이트 단위로 동일**함을 `diff -r`로 확인했다.

여기에는 의도적으로 명시한 모의 렌더러, 합성 PNG, patch-anchor fixture가 포함된다. **원본 compiler/resvg 렌더링, 원본 전체 GUI E2E, 실제 모델 호출, macOS 빌드·서명·공증은 실행하지 못했다.** 이를 완료했다고 주장하지 않는다.

실제 compiler와 권한 통합 검사를 추가했으며, Mac 패키징 스크립트가 이를 건너뛰지 않고 실행하도록 했다. 테스트 누락이나 실패 시 배포 빌드를 중단한다. 상세: [TEST-REPORT](docs/TEST-REPORT.md).

## 원본 조립

빌드 머신에 Git, Python, Node/npm이 필요하다. 기존 디렉터리는 덮어쓰지 않는다.

```bash
python scripts/assemble.py --dest /absolute/new/path/fp-studio
cd /absolute/new/path/fp-studio
```

네트워크 대신 이미 받아 놓은 원본 clone을 사용할 수도 있다. 각 clone에 lock 파일의 정확한 commit이 있어야 한다.

```bash
python scripts/assemble.py \
  --dest /absolute/new/path/fp-studio \
  --openworker-source /path/to/openworker \
  --fp-kit-source /path/to/fp-infographic-agent-kit
```

OpenWorker 원본은 `5bc10d928e0b64aae74313349a3b17bd19643ae2`, FP kit는 `5acc411000dcb76baa1b9dc841f9385d1bf42aa0`에 고정한다. 원본 anchor가 다르면 조립을 중단한다. npm의 전이 의존성 lock은 해당 설치에서 생성/검증하고 release에 보관해야 한다. 이 archive는 확인하지 못한 lock/integrity 값을 만들어 넣지 않았다.

## Mac 개발 실행

조립된 원본 checkout에서 실행한다.

```bash
bash packaging/setup_dev_env.sh
.venv/bin/pip install -e '.[dev,messaging,browser,bedrock]' pyinstaller typer
(cd surfaces/gui && npm ci)
export FP_FONT_DIR=/absolute/path/to/pretendard-fonts
mkdir -p surfaces/gui/src-tauri/binaries/fp-runtime
(cd surfaces/gui && npm run tauri dev)
```

폰트 디렉터리는 사용자 소유/사용 가능한 Pretendard TTF/OTF와 관련 notice를 준비한다. 폰트는 제공하지 않는다. 실제 개발 실행도 Mac에서 검증해야 한다.

## DMG

```bash
export FP_FONT_DIR=/absolute/path/to/pretendard-fonts
export FP_NODE_BINARY=/absolute/path/to/self-contained-node/bin/node
export APPLE_SIGNING_IDENTITY='Developer ID Application: YOUR COMPANY (TEAMID)'
# 원본 build_dmg.sh가 사용하는 NOTARYTOOL_API_* 공증 자격 증명 별도 설정
bash packaging/build_fp_studio_dmg.sh --release
```

배포 산출물은 원본 Tauri의 `surfaces/gui/src-tauri/target/release/bundle/dmg/`에 생성하도록 구성했다. 이 패키지 자체에는 DMG가 없다. 개발용 `--development` 결과와 서명·공증된 release를 구분한다. [Mac 빌드·배포 체크리스트](docs/DMG.md)를 먼저 확인한다.

## 작업물 보존

```text
session-workspace/
  .fpstudio/fp.sqlite3       # 원본·연구·모든 revision·SVG/PNG의 권위 저장소
  fp/infographic.svg        # 기존 Viewer가 읽는 현재 결과 캐시
  fp/infographic.png
  fp/infographic.fp.json
  fp/exports/infographic/   # revision 고정 최종 결과와 연구 버전별 출처 보고서
```

열람 도구는 손상된 표시 캐시를 조용히 수정하지 않는다. 명시적인 `fp_repair`가 복원한다. 과거 복원은 현재 renderer를 실행하지 않는다. SDK·폰트·테마가 바뀐 후 재렌더링은 명시적인 upgrade 경로를 요구한다.

## 로컬 회귀 검사

원본 소스나 폰트 없이 실행 가능한 국소 검사다. Python pytest, Node, tsc가 필요하다.

```bash
bash scripts/validate_local.sh
```

원본 UI diff 검사는 조립 시와 DMG 빌드 시 고정 upstream commit을 기준으로 수행한다. 기준을 downstream HEAD로 이동시켜 GUI 변경을 숨기지 않는다.

검사 방식은 allowlist가 아니라 **재구성**이다. `scripts/fp_edits.py`의 선언된 패치 집합(앵커는 upstream blob에서 유일)을 `patch_openworker.py`가 적용하면서 `.fp-patch-manifest.json`에 기록하고, `check_upstream_ui.py`가 그 기록을 upstream blob에 다시 적용해 **바이트가 같은지** 검사한다. 선언되지 않은 변경·새 파일·아이콘 교체는 모두 실패한다. 표는 `scripts/regen_edits.py`로 실제 검증한 checkout에서 생성하며 손으로 고치지 않는다.

## 알려진 제한

구독 로그인은 각 벤더의 공개 CLI 클라이언트 흐름을 그대로 쓴다: ChatGPT(PKCE 루프백 1455), Claude Pro/Max(PKCE 루프백 54545 + 30일 절대 만료), Gemini(Google 루프백 8085 + Cloud Code Assist 프로젝트), Grok(RFC 8628 device code). **실제 구독 계정으로 각 흐름을 끝까지 통과시킨 검증은 이 환경에서 ChatGPT·Claude·Grok 로그인 관찰까지이며, Gemini Code Assist 온보딩과 네 경로의 실제 추론 호출은 사용자 환경에서 확인해야 한다.** 토큰 갱신이 grant 거부(invalid_grant/401/403)일 때만 로그인을 지우고, 일시적 오류에서는 로그인을 유지한다.

전체 FP grammar의 시각적 golden test와 실제 사용자 동행 실험은 미완료다. 생성된 PNG를 vision 모델에 자동 주입하는 self-review는 아직 없다. 사용자는 기존 Viewer로 보고 채팅에서 검토하며, 원본 첨부 이미지 흐름은 유지한다.

OpenWorker의 원본 SecretStore는 0600 JSON이다. Keychain으로 바뀌었다고 주장하지 않는다. 소스·결과는 로컬에 있으나 선택한 클라우드 모델과 검색 도구를 사용하면 해당 context/query가 외부로 전송될 수 있다.

배포 전 우선순위: 실제 원본 조립 → 원본 테스트/renderer 통합 → 같은 채팅 실사용 검증 → 깨끗한 Mac 실행 → 서명·공증 검증.

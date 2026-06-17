---
name: frontend-builder
description: React + Vite 프론트엔드 빌더. MVC 패턴(services/api.js · hooks · pages)으로 페이지/컴포넌트를 구현한다. ui-ux-designer의 설계를 코드로 옮긴다.
user_invocable: true
---

# /frontend-builder - 프론트엔드 빌더 (React + Vite)

## 역할
`frontend/src/`의 페이지/훅/서비스를 구현/수정한다. UI/UX 설계는 `/ui-ux-designer`가 선행하고,
이 스킬은 그 설계를 코드로 옮긴다.

## MVC 구조
- **Model**: `services/api.js` — axios 인스턴스(`baseURL=''`, 상대경로), API 함수
- **Controller**: `hooks/use*.js` — useState/useCallback 상태·로직
- **View**: `pages/*.jsx` — JSX 렌더링, `react-markdown`+`remark-gfm`(리포트), bootstrap, lucide-react

## 절대 규칙 (실전 함정)
1. **API는 상대경로** `/api/...` — `services/api.js`의 axios `baseURL=''`. 브라우저 → 프론트 origin → **Vite 프록시(`vite.config.js`) → orchestrator:8000**. 절대 URL(`http://localhost:8000`) 하드코딩 금지(엉뚱한 호스트로 감 + CORS).
2. **baked 이미지**: frontend Dockerfile은 `COPY . .` + `npm run dev` → 소스가 이미지에 구워짐. **JSX/의존성 변경 시 `/runner`로 frontend 리빌드 필수**(핫리로드 안 됨). 사용자에겐 **하드 리프레시(Cmd+Shift+R)** 안내.
3. 새 의존성은 `package.json`에 추가 후 리빌드(npm install은 빌드 시점).
4. 라우트는 `App.jsx`(`<Route>`), 메뉴는 `components/Navbar.jsx`. 둘 다 갱신.
5. 차트는 `lightweight-charts`(캔들). 한국식 색: 상승 빨강(#e03131)/하락 파랑(#1971c2).

## 신규 페이지 절차
1. `pages/<Name>.jsx` 작성 (bootstrap 클래스 우선, 필요 시 `.module.css`)
2. `services/api.js`에 API 함수 추가(상대경로)
3. `App.jsx`에 import + `<Route path="/x" element={<X/>}/>`
4. `Navbar.jsx`에 NavLink + lucide 아이콘
5. `/runner`로 frontend 리빌드 → 라우트 200 + `/api` 프록시 체인 검증

## API 호출 패턴
```js
export const getX = () => api.get('/api/x').then(r => r.data);
export const postX = (body) => api.post('/api/x', body).then(r => r.data);
```
긴 작업(분석 ~1-2분)은 axios timeout 충분히(현재 180s), 로딩 인디케이터 + 경과시간 표시.

## 절대 규칙 (요약)
- 상대경로 API만, 절대 URL 금지
- 변경 후 `/runner` frontend 리빌드 + 하드리프레시 안내
- 디자인 결정은 `/ui-ux-designer` 설계 준수

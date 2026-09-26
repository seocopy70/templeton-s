# Frontend (React Vite)

기존 Streamlit app.py 대신 React 버전

## 생성 방법
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install recharts axios pg? (frontend는 supabase-js 말고 직접 API 호출)
# .env
VITE_API_URL=http://localhost:8000
VITE_NEON_READ_URL= (read-only role, optional)

## 실행
npm run dev

백엔드 FastAPI (api/main.py) 가 Neon에서 데이터 읽어서 /api/prices, /api/scores 제공

기존 Streamlit은 유지하면서 React를 /frontend 로 병행 가능
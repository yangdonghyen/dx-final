// React 애플리케이션 진입점: 전역 스타일을 불러오고 StrictMode로 App을 root에 마운트한다.
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

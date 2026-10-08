import { rebuildComfortPlan, COMFORT_OPTIONS, type ComfortReason } from './lib/comfort'
/**
 * 여행메이트 단일 페이지 애플리케이션.
 * 로그인부터 여행 생성, 지도 탐색, 일정 확인, 길찾기, 지난 여행 관리까지의 화면 전환과
 * 사용자 상태를 이 파일에서 관리한다. 화면 전환은 App 컴포넌트의 nav 함수와 AppState로 제어한다.
 */
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import jeonjuHanokImage from './assets/jeonju-hanok.jpg'
import { buildDays, type DayPlan, type ScheduleItem } from './lib/itinerary'

// ─── Types ────────────────────────────────────────────────────────────────────
type Screen =
  | 'login' | 'register' | 'setup'
  | 'home' | 'search-text' | 'search-voice' | 'camera' | 'analyzing' | 'place-result'
  | 'youtube-saved' | 'ai-analysis' | 'taste-confirm'
  | 'place-detail' | 'map' | 'comfort-travel'
  | 'trip-places' | 'trip-date' | 'trip-people' | 'trip-transport'
  | 'trip-budget' | 'trip-companions' | 'trip-confirm' | 'ai-loading' | 'itinerary'
  | 'accommodation' | 'pre-departure' | 'today-travel' | 'rest-search' | 'weather' | 'directions'
  | 'past-trips' | 'past-itinerary' | 'notifications' | 'profile'

interface Place { id: string; name: string; region: string; tags: string[]; img: string }
interface Companion { name: string; age: string; prefs: string[]; walking: string; avoid: string[]; permission?: 'edit' | 'view' }
interface Trip {
  id: string; title: string; startDate: string; endDate: string
  travelers: number; transport: string[]; budget: string
  companions: Companion[]; hotel: string; days: DayPlan[]; originalDays?: DayPlan[]; status: 'upcoming' | 'ongoing' | 'past'
  selectedPlaces: Place[]
}

// [기능] 저장된 장소의 이미지 식별자를 화면에 사용할 URL로 변환한다. 로컬 저작권 이미지는 외부 URL로 바꾸지 않는다.
function placeImageUrl(image: string, width: number, height: number) {
  return image === jeonjuHanokImage ? image : `https://images.unsplash.com/${image}?w=${width}&h=${height}&fit=crop`
}
// ─── Mock Data ────────────────────────────────────────────────────────────────
const YOUTUBE_SAVED: Place[] = [
  { id: 'p1', name: '안목해변', region: '강원 강릉시', tags: ['바다', '카페', '산책'], img: 'photo-1507525428034-b723cf961d3e' },
  { id: 'p2', name: '황리단길', region: '경북 경주시', tags: ['맛집', '전통', '카페'], img: 'photo-1569383746724-6f1b882b8f46' },
  { id: 'p3', name: '애월 해안도로', region: '제주 제주시', tags: ['바다', '드라이브', '휴식'], img: 'photo-1537996194471-e657df975ab4' },
  { id: 'p4', name: '광안리해수욕장', region: '부산 수영구', tags: ['바다', '야경', '맛집'], img: 'photo-1517404215738-15263e9f9178' },
  { id: 'p5', name: '전주 한옥마을', region: '전북 전주시', tags: ['전통문화', '맛집', '체험'], img: jeonjuHanokImage },
  { id: 'p6', name: '남이섬', region: '강원 춘천시', tags: ['자연', '산책', '체험'], img: 'photo-1464822759023-fed622ff2c3b' },
]

const PAST_TRIPS: Trip[] = [
  { id: 't1', title: '강릉 여행', startDate: '2026-08-20', endDate: '2026-08-22', travelers: 2, transport: ['기차'], budget: '30~50만원', companions: [], hotel: '씨마크 호텔', status: 'past', selectedPlaces: [YOUTUBE_SAVED[0]], days: buildDays('2026-08-20', '2026-08-22', [YOUTUBE_SAVED[0]], ['기차']) },
  { id: 't2', title: '부산 여행', startDate: '2026-07-10', endDate: '2026-07-12', travelers: 3, transport: ['자동차'], budget: '50만원 이상', companions: [], hotel: '파라다이스 호텔', status: 'past', selectedPlaces: [YOUTUBE_SAVED[3]], days: buildDays('2026-07-10', '2026-07-12', [YOUTUBE_SAVED[3]], ['자동차']) },
  { id: 't3', title: '제주 여행', startDate: '2026-06-02', endDate: '2026-06-05', travelers: 2, transport: ['비행기'], budget: '50만원 이상', companions: [], hotel: '제주 신라호텔', status: 'past', selectedPlaces: [YOUTUBE_SAVED[2]], days: buildDays('2026-06-02', '2026-06-05', [YOUTUBE_SAVED[2]], ['비행기']) },
]

const UPCOMING: Trip = {
  id: 'cur', title: '강릉 여행', startDate: '2026-09-24', endDate: '2026-09-26',
  travelers: 2, transport: ['기차', '택시'], budget: '30~50만원',
  companions: [{ name: '아빠', age: '60대', prefs: ['자연', '맛집'], walking: '30분 정도', avoid: ['등산'] }],
  hotel: '', status: 'upcoming', selectedPlaces: [YOUTUBE_SAVED[0]], days: buildDays('2026-09-24', '2026-09-26', [YOUTUBE_SAVED[0]], ['기차', '택시']),
}

// ─── Utils ────────────────────────────────────────────────────────────────────
const fmtDate = (iso: string) => { const d = new Date(iso); return `${d.getMonth() + 1}월 ${d.getDate()}일` }
const fmtShort = (iso: string) => { const d = new Date(iso); return `${d.getMonth() + 1}/${d.getDate()}` }
const daysUntil = (iso: string) => Math.ceil((new Date(iso).getTime() - new Date('2026-09-19').getTime()) / 86400000)
const nightsCount = (s: string, e: string) => Math.ceil((new Date(e).getTime() - new Date(s).getTime()) / 86400000)
const dayCount = (s: string, e: string) => nightsCount(s, e) + 1
const PREFS_E: Record<string, string> = { 바다: '🌊', 자연: '🌿', 도시: '🏙', 전통문화: '🏯', 맛집: '🍲', 카페: '☕', 전시: '🖼', 체험: '🎨', 휴식: '🛋', 등산: '⛰', 낚시: '🎣', 골프: '⛳' }
const ALL_PREFS = Object.keys(PREFS_E)
const TRANSPORTS = [{ id: '자동차', e: '🚗' }, { id: '대중교통', e: '🚌' }, { id: '택시', e: '🚕' }, { id: '도보 중심', e: '🚶' }]
// [기능] 검색 결과에 표시할 지역별 행사·축제 정보다. 실제 지역 행사 API를 연결할 때 이 목록을 API 응답으로 교체한다.
const REGIONAL_EVENT_STATUS = [
  { region: '강릉', name: '강릉커피축제', label: '축제 진행 중' },
  { region: '경주', name: '신라문화제', label: '축제 진행 중' },
  { region: '제주', name: '제주들불축제', label: '축제 진행 중' },
  { region: '부산', name: '부산불꽃축제', label: '행사 진행 중' },
  { region: '전주', name: '전주비빔밥축제', label: '축제 진행 중' },
  { region: '춘천', name: '춘천마임축제', label: '행사 진행 중' },
]
const regionalEventInfo = (region: string) => REGIONAL_EVENT_STATUS.find(event => region.includes(event.region))

interface TravelNotification { id: string; e: string; title: string; body: string; unread: boolean; t: string }
const INITIAL_NOTIFICATIONS: TravelNotification[] = [
  { id: 'trip-reminder-20260924', e: '✈️', title: '여행 D-5', body: '강릉 여행이 5일 남았어요.', unread: true, t: '방금' },
  { id: 'weather-20260924', e: '🌧', title: '오늘 비 예보', body: '강수확률이 높아요. 비 오는 날 일정을 확인해보세요. (오늘 날씨 > 계획 2 확인)', unread: true, t: '방금' },
  { id: 'taste-analysis', e: '🤖', title: 'AI 취향 분석 완료', body: '바다·맛집·휴식을 좋아하신다고 분석했어요.', unread: false, t: '3시간 전' },
  { id: 'itinerary-update', e: '✏️', title: '일정 변경', body: '동행자가 일정을 수정했어요.', unread: false, t: '어제' },
]
const unreadCount = (notifications: TravelNotification[]) => notifications.filter(item => item.unread).length
// [기능] 로그아웃 또는 앱 재시작 시 사용할 초기 사용자·여행·알림 상태를 생성한다.
function initialAppState(): AppState {
  return { ...INIT, notifications: INITIAL_NOTIFICATIONS.map(item => ({ ...item })) }
}
// ─── App State ────────────────────────────────────────────────────────────────
interface AppState {
  screen: Screen; screenHistory: Screen[]
  seniorMode: boolean; userName: string; userPrefs: string[]; travelStyle: string
  currentTrip: Trip; viewedPastTrip?: Trip; notifications: TravelNotification[]
  weatherPlan: 'A' | 'B' | 'C'
  selectedPlace: Place | null; activeSchedule: ScheduleItem | null; savedPlaces: Place[]; aiPrefs: string[]
  draft: { selectedPlaces?: Place[]; startDate?: string; endDate?: string; travelers?: number; transport?: string[]; budget?: string; companions?: Companion[] }
}

const INIT: AppState = {
  screen: 'login', screenHistory: [],
  seniorMode: true, userName: '민우', userPrefs: ['바다', '맛집', '카페'], travelStyle: '여유롭게',
  currentTrip: UPCOMING, notifications: INITIAL_NOTIFICATIONS, weatherPlan: 'A',
  selectedPlace: null, activeSchedule: null, savedPlaces: YOUTUBE_SAVED, aiPrefs: ['바다', '맛집', '휴식'],
  draft: {},
}

// ─── Icons ────────────────────────────────────────────────────────────────────
const HomeIc = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
const MapIc = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg>
const HeartIc = ({ f }: { f?: boolean }) => f ? <svg viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg> : <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg>
const UserIc = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
const BellIc = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>
const MicIc = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5"><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0014 0"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/></svg>
const LeftIc = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-6 h-6"><polyline points="15 18 9 12 15 6"/></svg>
const RightIc = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-5 h-5"><polyline points="9 18 15 12 9 6"/></svg>
const DownIc = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4"><polyline points="6 9 12 15 18 9"/></svg>
const StarIc = () => <svg viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5 text-yellow-400"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
const XIc = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
const PlusIc = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
const MinusIc = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5"><line x1="5" y1="12" x2="19" y2="12"/></svg>
const NavIc = () => <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5"><polygon points="3 11 22 2 13 21 11 13 3 11"/></svg>
const RestIc = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5" aria-hidden="true"><path d="M6 5v9"/><path d="M8 6h2v7H8z"/><path d="M8 13h11v2H8z"/><path d="M10 15 8 19"/><path d="M17 15l2 4"/><path d="M5 19h16"/></svg>
const SearchIc = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
const CheckIc = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="w-3.5 h-3.5"><polyline points="20 6 9 17 4 12"/></svg>
const YtIc = () => <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-red-500"><path d="M22.54 6.42a2.78 2.78 0 00-1.95-1.96C18.88 4 12 4 12 4s-6.88 0-8.59.46a2.78 2.78 0 00-1.95 1.96A29 29 0 001 12a29 29 0 00.46 5.58a2.78 2.78 0 001.95 1.95C5.12 20 12 20 12 20s6.88 0 8.59-.47a2.78 2.78 0 001.95-1.95A29 29 0 0023 12a29 29 0 00-.46-5.58z"/><polygon fill="white" points="9.75 15.02 15.5 12 9.75 8.98 9.75 15.02"/></svg>

// ─── Shared UI ────────────────────────────────────────────────────────────────
// [기능] 장소와 일정의 특징을 작은 태그 형태로 표시하는 공통 UI 컴포넌트다.
function Tag({ label, blue }: { label: string; blue?: boolean }) {
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${blue ? 'bg-[#EEF2FF] text-[#4169D8]' : 'bg-gray-100 text-gray-500'}`}>{label}</span>
}

// [기능] 홈·지도·여행·마이페이지 사이를 이동시키는 하단 고정 내비게이션이다.
function BottomNav({ active, nav, sm, notifs }: { active: string; nav: (s: Screen) => void; sm: boolean; notifs: number }) {
  const tabs = [
    { id: 'home', label: '홈', icon: <HomeIc /> },
    { id: 'map', label: '탐색', icon: <MapIc /> },
    { id: 'youtube-saved', label: '저장', icon: <HeartIc /> },
    { id: 'profile', label: '마이', icon: <UserIc /> },
  ]
  return (
    <div className={`${sm ? 'h-20' : 'h-16'} bg-white border-t border-gray-100 flex`} style={{ boxShadow: '0 -1px 12px rgba(0,0,0,0.06)' }}>
      {tabs.map(t => (
        <button key={t.id} onClick={() => nav(t.id as Screen)}
          className={`flex-1 flex flex-col items-center justify-center gap-0.5 ${sm ? 'py-3 text-sm' : 'py-2 text-xs'} font-medium transition-colors ${active === t.id ? 'text-[#4169D8]' : 'text-gray-400'}`}>
          <div className="relative">
            {t.icon}
            {t.id === 'home' && notifs > 0 && <span className="absolute -top-1 -right-1 w-2 h-2 bg-red-500 rounded-full" />}
          </div>
          {t.label}
        </button>
      ))}
    </div>
  )
}

// [기능] 뒤로 가기 동작과 페이지 제목을 일관된 형태로 제공하는 상단 헤더다.
function PageHeader({ title, back, right }: { title?: string; back?: () => void; right?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-5 pt-12 pb-3 bg-white border-b border-gray-50 flex-shrink-0">
      {back ? <button onClick={back} aria-label="이전 화면으로" className="w-10 h-10 flex items-center justify-center"><LeftIc /></button> : <div className="w-10" />}
      {title && <h1 className="font-bold text-gray-900 text-lg">{title}</h1>}
      <div className="w-10 flex justify-end">{right}</div>
    </div>
  )
}

// [기능] 편한 모드의 큰 터치 영역까지 지원하는 주요 행동 버튼 공통 컴포넌트다.
function PrimaryBtn({ label, onClick, disabled, sm, gradient }: { label: string; onClick?: () => void; disabled?: boolean; sm?: boolean; gradient?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className={`w-full rounded-2xl text-white font-bold transition-all active:scale-95 disabled:opacity-40 ${sm ? 'h-16 text-lg' : 'h-14 text-base'}`}
      style={gradient ? { background: 'linear-gradient(135deg,#4169D8,#6B52D3)' } : { background: '#4169D8' }}>
      {label}
    </button>
  )
}

// ─── Login / Register ─────────────────────────────────────────────────────────
// [기능] 앱 최초 진입 화면으로 일반 로그인, 계정 찾기 및 소셜 로그인 진입점을 제공한다.
function LoginScreen({ onLogin, onRegister }: { onLogin: () => void; onRegister: () => void }) {
  const [id, setId] = useState('')
  const [pw, setPw] = useState('')
  const [help, setHelp] = useState<'id' | 'password' | null>(null)
  const [notice, setNotice] = useState('')

  const handleLogin = (event: React.FormEvent) => {
    event.preventDefault()
    if (!id.trim() || !pw) {
      setNotice('아이디와 비밀번호를 모두 입력해 주세요.')
      return
    }
    onLogin()
  }

  const requestAccountHelp = () => {
    if (!id.trim()) {
      setNotice('가입할 때 사용한 이메일 또는 아이디를 입력해 주세요.')
      return
    }
    setNotice(help === 'id' ? '등록된 이메일이 있으면 아이디 안내를 보냈어요.' : '등록된 이메일이 있으면 비밀번호 재설정 안내를 보냈어요.')
  }

  return (
    <div className="h-full bg-white flex flex-col px-6 pt-16 pb-8 overflow-y-auto scrollbar-hide">
      <div className="text-center mb-8"><div className="inline-flex w-20 h-20 rounded-3xl bg-[#4169D8] items-center justify-center mb-4 shadow-lg"><span className="text-4xl">✈️</span></div><h1 className="text-3xl font-black text-gray-900">여행메이트</h1><p className="text-gray-500 mt-2 text-base">나에게 맞는 여행을 시작해볼까요?</p></div>
      <form onSubmit={handleLogin} noValidate>
        <div className="space-y-3"><label className="sr-only" htmlFor="login-id">아이디 또는 이메일</label><input id="login-id" value={id} onChange={e => { setId(e.target.value); setNotice('') }} autoComplete="username" placeholder="아이디 또는 이메일" className="w-full h-14 px-4 rounded-2xl border border-gray-200 text-base outline-none focus:border-[#4169D8] focus:ring-2 focus:ring-[#4169D8]/20" /><label className="sr-only" htmlFor="login-password">비밀번호</label><input id="login-password" value={pw} onChange={e => { setPw(e.target.value); setNotice('') }} type="password" autoComplete="current-password" placeholder="비밀번호" className="w-full h-14 px-4 rounded-2xl border border-gray-200 text-base outline-none focus:border-[#4169D8] focus:ring-2 focus:ring-[#4169D8]/20" /></div>
        {notice && <p className="mt-3 rounded-xl bg-[#EEF2FF] px-3 py-2 text-sm leading-5 text-[#2749A5]" role="status">{notice}</p>}
        <div className="flex justify-center gap-5 my-5"><button type="button" onClick={() => { setHelp(help === 'id' ? null : 'id'); setNotice('') }} className="text-sm text-gray-600 underline underline-offset-4">아이디 찾기</button><button type="button" onClick={() => { setHelp(help === 'password' ? null : 'password'); setNotice('') }} className="text-sm text-gray-600 underline underline-offset-4">비밀번호 찾기</button><button type="button" onClick={onRegister} className="text-sm text-[#4169D8] font-bold">회원가입</button></div>
        {help && <div className="mb-5 rounded-2xl border border-[#DCE5FF] bg-[#F7F9FF] p-4"><h2 className="text-base font-bold text-gray-900">{help === 'id' ? '아이디 찾기' : '비밀번호 찾기'}</h2><p className="mt-1 text-sm leading-5 text-gray-600">가입할 때 사용한 이메일 또는 아이디를 입력한 뒤 안내를 받아보세요.</p><button type="button" onClick={requestAccountHelp} className="mt-3 min-h-11 rounded-xl bg-white px-4 text-sm font-bold text-[#4169D8] shadow-sm">안내 받기</button></div>}
        <button type="submit" className="w-full h-14 rounded-2xl bg-[#4169D8] text-white font-bold text-lg active:scale-[0.98]">로그인하기</button>
      </form>
      <div className="flex items-center gap-3 my-5"><div className="flex-1 h-px bg-gray-200"/><span className="text-sm text-gray-400">또는</span><div className="flex-1 h-px bg-gray-200"/></div>
      <div className="space-y-3"><button onClick={onLogin} className="w-full h-14 rounded-2xl bg-[#FEE500] font-bold text-[#3C1E1E] flex items-center justify-center gap-2 active:scale-[0.98]"><span className="text-xl">💛</span> 카카오로 로그인하기</button><button onClick={onLogin} className="w-full h-14 rounded-2xl bg-[#03C75A] font-bold text-white flex items-center justify-center gap-2 active:scale-[0.98]"><span className="text-xl">🟢</span> 네이버로 로그인하기</button></div>
    </div>
  )
}
// [기능] 새 사용자 등록 정보를 입력받고 온보딩 설정 화면으로 이동시킨다.
function RegisterScreen({ onDone }: { onDone: () => void }) {
  const [form, setForm] = useState({ name: '', email: '', pw: '', pw2: '' })
  return (
    <div className="h-full bg-white flex flex-col px-6 pt-14 pb-10">
      <button onClick={onDone} className="mb-5 flex items-center gap-1 text-gray-600"><LeftIc /><span>뒤로</span></button>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">회원가입</h1>
      <div className="space-y-3 flex-1">
        {(['name', 'email', 'pw', 'pw2'] as const).map(k => (
          <input key={k} value={form[k]} onChange={e => setForm(f => ({ ...f, [k]: e.target.value }))}
            type={k.startsWith('pw') ? 'password' : 'text'}
            placeholder={{ name: '이름', email: '이메일', pw: '비밀번호', pw2: '비밀번호 확인' }[k]}
            className="w-full h-14 px-4 rounded-2xl border border-gray-200 text-base outline-none focus:border-[#4169D8]" />
        ))}
      </div>
      <button onClick={onDone} className="w-full h-14 rounded-2xl bg-[#4169D8] text-white font-bold text-lg mt-6">가입 완료</button>
    </div>
  )
}

// ─── Setup ────────────────────────────────────────────────────────────────────
// [기능] 사용자 여행 취향과 접근성 선호를 설정해 홈 화면 경험에 반영한다.
function SetupScreen({ onDone }: { onDone: (style: string, prefs: string[], senior: boolean) => void }) {
  const [style, setStyle] = useState('여유롭게')
  const [prefs, setPrefs] = useState<string[]>(['바다', '맛집', '카페'])
  const [senior, setSenior] = useState(true)
  const toggle = (p: string) => setPrefs(s => s.includes(p) ? s.filter(x => x !== p) : [...s, p])
  const styles = [{ id: '여유롭게', e: '🌿', desc: '천천히, 여유 있게' }, { id: '적당하게', e: '⚖️', desc: '관광과 휴식 균형' }, { id: '알차게', e: '🗺', desc: '많은 곳 둘러보기' }]
  return (
    <div className="h-full bg-white flex flex-col px-5 pt-14 pb-6 overflow-y-auto scrollbar-hide">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">어떤 여행을 좋아하세요?</h1>
      <p className="text-sm text-gray-400 mb-6">AI가 맞춤 여행을 만들어드릴게요</p>
      <p className="text-sm font-bold text-gray-700 mb-3">여행 스타일</p>
      <div className="grid grid-cols-3 gap-2 mb-6">
        {styles.map(s => (
          <button key={s.id} onClick={() => setStyle(s.id)}
            className={`rounded-2xl p-3 flex flex-col items-center gap-1 border-2 transition-all active:scale-95 ${style === s.id ? 'bg-[#EEF2FF] border-[#4169D8]' : 'bg-gray-50 border-transparent'}`}>
            <span className="text-2xl">{s.e}</span>
            <span className="font-bold text-sm text-gray-900">{s.id}</span>
            <span className="text-xs text-gray-400 text-center">{s.desc}</span>
          </button>
        ))}
      </div>
      <p className="text-sm font-bold text-gray-700 mb-3">관심사 (여러 개 선택)</p>
      <div className="flex flex-wrap gap-2 mb-6">
        {ALL_PREFS.map(p => (
          <button key={p} onClick={() => toggle(p)}
            className={`flex items-center gap-1 px-3 py-2 rounded-full border-2 text-sm font-medium transition-all active:scale-95 ${prefs.includes(p) ? 'bg-[#4169D8] border-[#4169D8] text-white' : 'bg-white border-gray-200 text-gray-700'}`}>
            {prefs.includes(p) && <CheckIc />}{PREFS_E[p]} {p}
          </button>
        ))}
      </div>
      <p className="text-sm font-bold text-gray-700 mb-3">화면 모드</p>
      <div className="grid grid-cols-2 gap-3 mb-8">
        {[{ v: false, e: '📱', l: '기본 모드', d: '일반 크기' }, { v: true, e: '🔎', l: '편한 모드', d: '크고 단순하게' }].map(m => (
          <button key={String(m.v)} onClick={() => setSenior(m.v)}
            className={`rounded-2xl p-4 flex flex-col items-center gap-2 border-2 transition-all active:scale-95 ${senior === m.v ? 'bg-[#EEF2FF] border-[#4169D8]' : 'bg-gray-50 border-transparent'}`}>
            <span className="text-3xl">{m.e}</span>
            <span className="font-bold text-sm text-gray-900">{m.l}</span>
            <span className="text-xs text-gray-400">{m.d}</span>
          </button>
        ))}
      </div>
      <PrimaryBtn label="저장하기" onClick={() => onDone(style, prefs, senior)} disabled={prefs.length === 0} />
    </div>
  )
}

// [기능] 홈의 오늘 날씨 타일에서 여는 날씨 상세 화면이다. 날씨별 계획 1/2/3 일정을 전환해 보여준다.
// [기능] 현재 날씨를 보여주고, 날씨별 계획 1/2/3를 오늘 일정에 적용한 뒤 오늘의 여행 화면으로 연결한다.
function WeatherScreen({ state, nav, setState }: { state: AppState; nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>> }) {
  const [plan, setPlan] = useState<'A' | 'B' | 'C'>(state.weatherPlan)
  // 현재 날씨 API 연결 전까지는 비 예보 목업을 사용한다. API 응답의 condition/temp/precip 값으로 교체 가능하다.
  const weather = { icon: '🌧️', temp: '19°', label: '비', precip: '70%', humidity: '86%', wind: '3.4m/s', recommended: 'B' as const }
  const plans = {
    A: { title: '계획 1 · 기본 일정', detail: '안목해변 산책 → 커피거리 → 중앙시장', icon: '🌤️', places: ['안목해변 산책', '강릉 커피거리', '강릉 중앙시장'] },
    B: { title: '계획 2 · 비 오는 날 일정', detail: '오죽헌 → 강릉시립미술관 → 실내 카페', icon: '🌧️', places: ['오죽헌', '강릉시립미술관', '실내 카페 휴식'] },
    C: { title: '계획 3 · 더운 날 일정', detail: '이른 해변 산책 → 박물관 → 휴식 카페', icon: '☀️', places: ['이른 안목해변 산책', '강릉 아르떼뮤지엄', '그늘 카페 휴식'] },
  } as const
  const active = plans[plan]
  const applyPlanAndOpenToday = () => {
    setState(current => {
      const dayIndex = current.currentTrip.days.length > 1 ? 1 : 0
      const days = current.currentTrip.days.map((day, index) => {
        if (index !== dayIndex) return day
        let placeCursor = 0
        const places = day.places.map(item => {
          const previousPlan = item.tags.includes('대체 코스') || item.tags.includes('날씨 플랜')
          const isFixed = item.tags.includes('출발') || item.tags.includes('귀가') || item.tags.includes('숙소') || (item.tags.includes('식사') && !previousPlan)
          if (isFixed || placeCursor >= active.places.length) return item
          const place = active.places[placeCursor]
          placeCursor += 1
          return { ...item, place, icon: active.icon, tags: ['날씨 플랜', `계획 ${{ A: 1, B: 2, C: 3 }[plan]}`], rest: plan === 'C' }
        })
        return { ...day, places, notice: `${active.title}을 현재 날씨에 맞춰 적용했어요.` }
      })
      return { ...current, weatherPlan: plan, currentTrip: { ...current.currentTrip, days } }
    })
    nav('today-travel')
  }
  return (
    <div className="flex h-full flex-col bg-[#F3F7FF]">
      <PageHeader title="오늘 날씨" back={() => nav('home')} />
      <div className="flex-1 overflow-y-auto scrollbar-hide px-5 pb-7">
        <section className="rounded-3xl bg-[#173B76] p-5 text-white shadow-lg"><p className="text-sm font-bold text-blue-200">강릉 · 현재 날씨</p><div className="mt-2 flex items-end justify-between"><div className="flex items-end gap-3"><span className="text-5xl">{weather.icon}</span><strong className="text-4xl">{weather.temp}</strong><span className="pb-1 text-base text-blue-100">{weather.label}</span></div><span className="rounded-xl bg-amber-300/20 px-3 py-2 text-sm font-bold text-amber-100">계획 2 추천</span></div><div className="mt-5 grid grid-cols-3 gap-2 text-center text-sm"><div className="rounded-xl bg-white/10 p-3"><p className="text-blue-200">강수확률</p><b className="mt-1 block text-lg">{weather.precip}</b></div><div className="rounded-xl bg-white/10 p-3"><p className="text-blue-200">습도</p><b className="mt-1 block text-lg">{weather.humidity}</b></div><div className="rounded-xl bg-white/10 p-3"><p className="text-blue-200">바람</p><b className="mt-1 block text-lg">{weather.wind}</b></div></div></section>
        <section className="mt-5 rounded-3xl bg-white p-5 shadow-sm"><h2 className="text-xl font-black text-gray-900">날씨별 오늘 일정</h2><p className="mt-1 text-sm text-gray-500">현재 비 예보에는 계획 2를 추천해요. 원하시는 계획을 선택할 수 있어요.</p><div className="mt-4 grid grid-cols-3 gap-2">{(['A', 'B', 'C'] as const).map(item => <button key={item} onClick={() => setPlan(item)} className={`min-h-12 rounded-xl text-sm font-black ${plan === item ? 'bg-[#4169D8] text-white' : 'bg-[#F1F4FF] text-[#4169D8]'}`}>계획 {({ A: 1, B: 2, C: 3 } as const)[item]}</button>)}</div><div className="mt-4 rounded-2xl bg-[#F7F8FF] p-4"><div className="flex items-center gap-2"><span className="text-2xl">{active.icon}</span><h3 className="font-bold text-gray-900">{active.title}</h3></div><p className="mt-2 text-sm leading-6 text-gray-600">{active.detail}</p><button onClick={applyPlanAndOpenToday} className="mt-4 min-h-11 w-full rounded-xl bg-[#4169D8] text-sm font-bold text-white">이 일정으로 여행 보기</button></div></section>
      </div>
    </div>
  )
}// [기능] 편한 모드 홈 화면이다. 큰 기능 타일을 두 페이지로 나누고 명확한 이동 경로를 제공한다.
function SeniorHomeScreen({ state, nav }: { state: AppState; nav: (s: Screen) => void }) {
  const menus = [
    { label: '전체 일정', icon: '📝', to: 'itinerary' as Screen, tone: 'bg-[#4169D8]' },
    { label: '오늘의 일정', icon: '📅', to: 'today-travel' as Screen, tone: 'bg-[#E16A3D]' },
    { label: '여행 만들기', icon: '🧳', to: 'trip-places' as Screen, tone: 'bg-[#6B52D3]' },
    { label: '오늘 날씨', icon: '☀️', to: 'weather' as Screen, tone: 'bg-[#F59E0B]' },
  ]
  return (
    <div className="flex h-full flex-col overflow-hidden" style={{ background: 'linear-gradient(160deg,#F3F7FF 0%,#F9F5FF 46%,#F2FBF8 100%)' }}>
      <header className="flex items-start justify-between gap-3 px-5 pt-5 pb-5"><div><p className="text-base font-bold text-[#4169D8]">여행메이트</p><h1 className="mt-1 text-2xl font-black text-gray-900">안녕하세요, {state.userName}님</h1><p className="mt-1 text-base text-gray-600">어디로 떠나볼까요?</p></div><button type="button" onClick={() => nav('notifications')} aria-label={unreadCount(state.notifications) > 0 ? `알림 ${unreadCount(state.notifications)}개, 눌러서 확인` : '알림 확인'} className="relative flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-transparent text-gray-700 focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-[#4169D8]"><span aria-hidden="true" className="inline-flex [&>svg]:size-[26px]"><BellIc /></span>{unreadCount(state.notifications) > 0 && <span aria-hidden="true" className="absolute right-2 top-2 h-2.5 w-2.5 rounded-full bg-red-500" />}</button></header>
      <main className="flex min-h-0 flex-1 flex-col px-5 pb-3">
        <section aria-label="여행지 검색" className="rounded-3xl bg-white p-4 shadow-sm"><h2 className="text-lg font-bold text-gray-900">어디로 여행 갈까요?</h2><div className="mt-4 grid grid-cols-2 gap-3"><button onClick={() => nav('search-text')} aria-label="텍스트 검색창 열기" className="flex min-h-24 flex-col items-center justify-center gap-2 rounded-2xl border-2 border-[#4169D8] bg-[#EEF2FF] text-[#2F4FBF] focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-[#172554]"><span aria-hidden="true" className="[&>svg]:size-9"><SearchIc /></span><span className="text-base font-bold">직접 입력</span></button><button onClick={() => nav('search-voice')} aria-label="음성 검색 시작" className="flex min-h-24 flex-col items-center justify-center gap-2 rounded-2xl bg-[#4169D8] text-white focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-[#172554]"><span aria-hidden="true" className="[&>svg]:size-9"><MicIc /></span><span className="text-base font-bold">말로 찾기</span></button></div></section>
        <section className="mt-4 flex min-h-0 flex-1 flex-col rounded-3xl bg-white p-5 shadow-sm" aria-label="주요 기능"><h2 className="mb-4 text-xl font-black text-gray-900">무엇을 도와드릴까요?</h2><div className="grid min-h-0 flex-1 grid-cols-2 gap-4">{menus.map(item => <button key={item.label} onClick={() => nav(item.to)} className="flex min-h-0 flex-col items-center justify-center rounded-3xl bg-[#F8FAFF] p-4 text-center active:scale-[0.98] transition-transform"><span aria-hidden="true" className={`flex h-16 w-16 items-center justify-center rounded-full text-3xl shadow-sm ${item.tone}`}>{item.icon}</span><span className="mt-3 block text-lg font-black text-gray-900">{item.label}</span></button>)}</div></section>
      </main>
    </div>
  )
}
// ─── Home ─────────────────────────────────────────────────────────────────────
// [기능] 일반 모드 홈 화면이다. 여행 생성, 예정 여행, 저장 장소 및 지난 여행 진입점을 구성한다.
function HomeScreen({ state, nav }: { state: AppState; nav: (s: Screen) => void }) {
  const { userName, currentTrip, savedPlaces, seniorMode: sm } = state
  const notifs = unreadCount(state.notifications)
  const until = daysUntil(currentTrip.startDate)
  const ongoing = until <= 0
  const tl = sm ? 'text-xl' : 'text-lg'
  const ts = sm ? 'text-base' : 'text-sm'
  if (sm) return <SeniorHomeScreen state={state} nav={nav} />

  return (
    <div className="flex-1 overflow-y-auto scrollbar-hide" style={{ background: 'linear-gradient(160deg,#F0F4FF 0%,#F7F0FF 30%,#F0FAFF 70%,#F7F8FF 100%)' }}>
      {/* Header */}
      <div className="px-5 pt-2 pb-2 flex items-center justify-between flex-shrink-0">
        <div>
          <p className="text-xs text-gray-400 font-medium">여행메이트 ✈️</p>
          <h1 className={`font-bold text-gray-900 ${sm ? 'text-2xl' : 'text-xl'}`}>안녕하세요, {userName}님</h1>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => nav('profile')} className="w-10 h-10 rounded-full bg-[#4169D8] flex items-center justify-center text-white font-bold">{userName[0]}</button>
        </div>
      </div>

      {/* Search */}
      <div className="px-5 mb-4">
        <div className="flex items-center bg-white rounded-2xl px-4 gap-3 h-12" style={{ boxShadow: '0 2px 12px rgba(65,105,216,0.1)' }}>
          <SearchIc />
          <input readOnly placeholder="여행지나 장소를 검색해보세요" onClick={() => nav('search-voice')}
            className="flex-1 text-sm text-gray-400 outline-none bg-transparent cursor-pointer" />
          <button onClick={() => nav('search-voice')} className="w-8 h-8 rounded-full bg-[#4169D8] flex items-center justify-center text-white flex-shrink-0"><MicIc /></button>
        </div>
      </div>

      <div className="px-5 space-y-4 pb-8">
        <button onClick={() => nav('comfort-travel')} className="w-full rounded-3xl bg-[#172554] p-5 text-left text-white shadow-lg active:scale-[0.98] transition-transform">
          <div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold text-blue-200">큰 글씨 · 간단한 안내</p><h2 className={`mt-1 font-bold ${sm ? 'text-2xl' : 'text-xl'}`}>편안한 여행</h2><p className="mt-1 text-sm leading-5 text-blue-100">다음 일정과 길찾기를 더 쉽고 크게 확인하세요.</p></div><span aria-hidden="true" className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-2xl bg-white/15 text-2xl">🌿</span></div>
          <span className="mt-4 inline-flex min-h-11 items-center rounded-xl bg-white px-4 py-2 text-sm font-bold text-[#172554]">편안한 여행으로 보기</span>
        </button>
        {/* 여행 계획하기 */}
        <div className="bg-white rounded-3xl p-5" style={{ boxShadow: '0 2px 12px rgba(65,105,216,0.1)' }}>
          <div className="flex items-start justify-between mb-3">
            <div>
              <h2 className={`font-bold text-gray-900 ${tl}`}>여행 계획하기</h2>
              <p className={`text-gray-400 mt-0.5 ${ts}`}>저장해둔 장소를 바탕으로<br />나에게 맞는 여행을 만들어드릴게요</p>
            </div>
            <span className="text-3xl">🗺</span>
          </div>
          <button onClick={() => nav('trip-places')}
            className={`w-full rounded-2xl bg-[#4169D8] text-white font-bold active:scale-95 transition-transform ${sm ? 'h-14 text-base' : 'h-12 text-sm'}`}>
            여행 만들기
          </button>
          <div className="flex gap-2 mt-3">
            <button onClick={() => nav('camera')} className="flex-1 h-9 rounded-xl bg-gray-50 text-xs font-medium text-gray-600 flex items-center justify-center gap-1">📷 사진으로 찾기</button>
            <button onClick={() => nav('search-voice')} className="flex-1 h-9 rounded-xl bg-gray-50 text-xs font-medium text-gray-600 flex items-center justify-center gap-1">🔎 직접 검색</button>
          </div>
        </div>

        {/* 현재/다가오는 여행 */}
        {ongoing ? (
          <div className="rounded-3xl p-5 text-white" style={{ background: 'linear-gradient(135deg,#2E5DB8,#6B52D3)' }}>
            <p className="text-blue-200 text-xs font-semibold mb-1">현재 내 여행 일정</p>
            <h2 className={`font-bold ${tl}`}>{currentTrip.title}</h2>
            <p className="text-blue-200 text-xs">DAY 2 · {fmtDate(currentTrip.days[1]?.date || currentTrip.startDate)}</p>
            <div className="bg-white/15 rounded-2xl p-3 my-3 space-y-1.5">
              <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-green-400" /><p className="text-sm font-semibold">지금 여기</p></div>
              <div className="flex items-center gap-3 ml-1"><div className="w-px h-5 bg-white/30" />
                <div><p className="text-xs text-blue-200">11:00 안목해변</p><p className="text-xs text-blue-200">→ 13:00 강릉 중앙시장 · 도보 12분</p></div>
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={() => nav('today-travel')} className="flex-1 h-10 rounded-xl bg-white/20 text-sm font-bold">여행 보기</button>
              <button onClick={() => nav('directions')} className="flex-1 h-10 rounded-xl bg-white text-[#4169D8] text-sm font-bold">길찾기</button>
            </div>
          </div>
        ) : (
          <button onClick={() => nav('itinerary')} className="w-full rounded-3xl p-5 text-left active:scale-95 transition-transform"
            style={{ background: 'linear-gradient(135deg,#4169D8,#6B8EFF)', boxShadow: '0 4px 20px rgba(65,105,216,0.3)' }}>
            <p className="text-blue-200 text-xs font-semibold mb-1">다가오는 여행</p>
            <h2 className={`font-bold text-white ${tl}`}>{currentTrip.title} D-{until}</h2>
            <p className="text-blue-100 text-sm mt-0.5">{fmtDate(currentTrip.startDate)} ~ {fmtDate(currentTrip.endDate)} · {nightsCount(currentTrip.startDate, currentTrip.endDate)}박</p>
            <div className="flex items-center justify-between mt-3">
              <span className="text-blue-100 text-xs">{currentTrip.transport.join(' + ')} · {currentTrip.travelers}명</span>
              <span className="text-xs font-bold bg-white/20 px-3 py-1 rounded-full text-white">일정 확인 →</span>
            </div>
          </button>
        )}

        {/* 내가 발견한 여행지 */}
        <div className="bg-white rounded-3xl p-5" style={{ boxShadow: '0 2px 12px rgba(0,0,0,0.05)' }}>
          <div className="flex items-center justify-between mb-1">
            <h2 className={`font-bold text-gray-900 ${sm ? 'text-xl' : 'text-base'}`}>내가 발견한 여행지</h2>
            <button onClick={() => nav('youtube-saved')} className="text-xs text-[#4169D8] font-semibold">둘러보기 →</button>
          </div>
          <p className={`text-gray-400 mb-3 ${ts}`}>YouTube에서 저장한 여행지 {savedPlaces.length}곳</p>
          <div className="flex gap-3 overflow-x-auto scrollbar-hide -mx-1 px-1 pb-1">
            {savedPlaces.slice(0, 4).map(p => (
              <button key={p.id} onClick={() => nav('place-detail')} className="flex-shrink-0 w-24 active:scale-95 transition-transform">
                <div className="w-24 h-20 rounded-xl overflow-hidden bg-gray-100 mb-1.5">
                  <img src={placeImageUrl(p.img, 200, 160)} alt={p.name} className="w-full h-full object-cover" />
                </div>
                <p className="text-xs font-semibold text-gray-900 truncate">{p.name}</p>
                <p className="text-xs text-gray-400 truncate">{p.region.split(' ')[0]}</p>
              </button>
            ))}
          </div>
          <button onClick={() => nav('ai-analysis')} className="w-full mt-3 h-10 rounded-xl bg-[#F0F4FF] text-[#4169D8] text-xs font-bold flex items-center justify-center gap-1.5">
            <YtIc /> AI로 취향 분석하기
          </button>
        </div>

        {/* 지난 여행 */}
        <div className="bg-white rounded-3xl p-5" style={{ boxShadow: '0 2px 12px rgba(0,0,0,0.05)' }}>
          <div className="flex items-center justify-between mb-3">
            <h2 className={`font-bold text-gray-900 ${sm ? 'text-xl' : 'text-base'}`}>지난 여행</h2>
            <button onClick={() => nav('past-trips')} className="text-xs text-[#4169D8] font-semibold">더보기 →</button>
          </div>
          <div className="space-y-2">
            {PAST_TRIPS.slice(0, 2).map(t => (
              <button key={t.id} onClick={() => nav('past-trips')}
                className="w-full flex items-center gap-3 p-2 rounded-xl hover:bg-gray-50 active:scale-95 transition-all text-left">
                <img src={placeImageUrl(t.selectedPlaces[0].img, 100, 100)} alt={t.title} className="w-12 h-12 rounded-xl object-cover flex-shrink-0" />
                <div className="flex-1">
                  <p className={`font-semibold text-gray-900 ${sm ? 'text-base' : 'text-sm'}`}>{t.title}</p>
                  <p className="text-xs text-gray-400">{t.startDate.slice(0, 7).replace('-', '.')} · {t.travelers}명</p>
                </div>
                <span className="text-xs text-[#4169D8] font-medium whitespace-nowrap">다시보기</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Voice Search ─────────────────────────────────────────────────────────────
interface VoiceRecognition {
  lang: string
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
  onstart: (() => void) | null
  start(): void
  abort(): void
}

// [기능] 텍스트/음성 입력으로 장소를 검색하고 브라우저 음성 인식 권한 및 오류 상태를 처리한다.
function PlaceSearchScreen({ voice, startVoiceRef, nav, onSelect }: { voice: boolean; startVoiceRef: React.RefObject<(() => void) | null>; nav: (s: Screen) => void; onSelect: (place: Place) => void }) {
  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState('')
  const [message, setMessage] = useState('마이크 연결 중이에요. 권한 요청이 뜨면 허용해주세요.')
  const [listening, setListening] = useState(false)
  const [starting, setStarting] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const recognitionRef = useRef<VoiceRecognition | null>(null)
  useLayoutEffect(() => {
    if (!voice) { inputRef.current?.focus(); return }
    const browser = window as unknown as { SpeechRecognition?: new () => VoiceRecognition; webkitSpeechRecognition?: new () => VoiceRecognition }
    const Recognition = browser.SpeechRecognition ?? browser.webkitSpeechRecognition
    if (!Recognition) {
      setMessage('이 브라우저는 음성 검색을 지원하지 않아요. 직접 입력으로 전환해주세요.')
      inputRef.current?.focus()
      return
    }
    const recognition = new Recognition()
    recognitionRef.current = recognition
    recognition.lang = 'ko-KR'
    let received = false
    let failed = false
    recognition.onstart = () => { setStarting(false); setListening(true); setMessage('듣고 있어요. 여행지 이름을 말씀해주세요.') }
    recognition.onresult = event => {
      const text = event.results[0]?.[0]?.transcript?.trim() ?? ''
      received = Boolean(text)
      setQuery(text)
      setSubmitted(text)
      setMessage(text ? '말씀하신 내용으로 검색했어요. 검색어를 수정할 수도 있어요.' : '말씀을 듣지 못했어요. 다시 시도해주세요.')
    }
    recognition.onerror = event => {
      failed = true
      setStarting(false)
      setListening(false)
      setMessage(event.error === 'not-allowed' || event.error === 'service-not-allowed'
        ? '마이크 권한을 허용하거나 직접 입력으로 전환해주세요.'
        : '음성을 인식하지 못했어요. 마이크와 연결을 확인하거나 직접 입력해주세요.')
    }
    recognition.onend = () => {
      setStarting(false)
      setListening(false)
      if (!received && !failed) setMessage('음성 입력이 끝났어요. 다시 말하거나 직접 입력해주세요.')
    }
    startVoiceRef.current = () => {
      received = false
      failed = false
      setSubmitted('')
      setStarting(true)
      setMessage('마이크 연결 중이에요. 권한 요청이 뜨면 허용해주세요.')
      try { recognition.start() } catch {
        setStarting(false)
        setMessage('마이크를 시작할 수 없어요. 다시 시도하거나 직접 입력해주세요.')
      }
    }
    return () => {
      startVoiceRef.current = null
      recognition.onstart = null
      recognition.onresult = null
      recognition.onerror = null
      recognition.onend = null
      recognition.abort()
      recognitionRef.current = null
    }
  }, [voice, startVoiceRef])
  const normalize = (value: string) => value.replace(/[^가-힣a-zA-Z0-9]/g, '').toLowerCase()
  const normalized = normalize(submitted)
  const results = normalized ? YOUTUBE_SAVED.filter(place =>
    [place.name, place.region, ...place.tags].some(value => normalize(value).includes(normalized))
    || normalized.includes(normalize(place.name))
  ) : []
  // 직접 입력 검색에서만 지역 행사·축제 상태를 결과 카드의 별도 태그로 노출한다.
  const resultsWithEvent = results.map(place => ({ place, event: !voice ? regionalEventInfo(place.region) : undefined }))
  return (
    <div className="h-full min-h-0 flex flex-col bg-white [&_button]:focus-visible:outline-4 [&_button]:focus-visible:outline-offset-2 [&_button]:focus-visible:outline-[#172554]">
      <PageHeader title={voice ? '말로 여행지 찾기' : '여행지 검색'} back={() => nav('home')} />
      <div className={`flex-1 min-h-0 overflow-y-auto px-5 py-6 ${voice && !submitted ? 'flex flex-col justify-center' : ''}`}>
        {voice && <section className="mb-6 rounded-3xl bg-[#EEF2FF] px-5 py-10 text-center" aria-label="음성 입력">
          <span aria-hidden="true" className={`mx-auto flex size-28 items-center justify-center rounded-full bg-[#4169D8] text-white shadow-lg [&>svg]:size-14 ${listening ? 'motion-safe:animate-pulse' : ''}`}><MicIc /></span><h2 className="mt-6 text-2xl font-bold text-gray-900">어디로 여행 갈까요?</h2>
          <p role="status" className="mt-4 text-base font-semibold leading-7 text-gray-800">{message}</p>
          <button onClick={() => { if (listening || starting) recognitionRef.current?.abort(); else startVoiceRef.current?.() }} className="mt-4 min-h-12 rounded-xl bg-white px-5 font-bold text-[#2F4FBF]">{listening || starting ? '음성 입력 중지' : '다시 말하기'}</button>
        </section>}
        {(!voice || Boolean(submitted)) && <><form onSubmit={event => { event.preventDefault(); recognitionRef.current?.abort(); setSubmitted(query.trim()) }}>
          <label htmlFor="place-query" className="mb-3 block text-lg font-bold text-gray-900">어디로 여행 갈까요?</label>
          <div className="flex gap-2">
            <input ref={inputRef} id="place-query" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="예: 강릉, 바다, 안목해변" className="min-w-0 flex-1 rounded-2xl border-2 border-[#4169D8] px-3 py-4 text-base outline-none focus:ring-4 focus:ring-blue-200" />
            <button type="submit" disabled={!query.trim()} className="min-h-14 shrink-0 rounded-2xl bg-[#4169D8] px-4 font-bold text-white disabled:opacity-40">찾기</button>
          </div>
        </form>
        </>}
        {voice && <button onClick={() => nav('search-text')} className="min-h-14 w-full rounded-2xl border-2 border-[#4169D8] px-4 font-bold text-[#2F4FBF]">직접 입력으로 전환</button>}
        {(!voice || Boolean(submitted)) && <div className="mt-6" aria-live="polite">
          {!submitted ? <p className="text-base text-gray-600">가고 싶은 여행지 이름이나 지역을 입력해주세요.</p> : <>
            <h2 className="text-lg font-bold text-gray-900">검색 결과 {results.length}곳</h2>
            {results.length === 0 && <p className="mt-3 leading-7 text-gray-600">일치하는 여행지가 없어요. 다른 지역이나 짧은 검색어로 찾아보세요.</p>}
            <div className="mt-3 space-y-3">{resultsWithEvent.map(({ place, event }) => <button key={place.id} onClick={() => onSelect(place)} className="w-full rounded-2xl border border-gray-200 p-4 text-left">
              <span className="block text-lg font-bold text-gray-900">{place.name}</span>
              <span className="mt-1 block text-base text-gray-600">{place.region} · {place.tags.join(' · ')}</span>
              {event && <span className="mt-2 inline-flex items-center rounded-lg bg-amber-50 px-2.5 py-1.5 text-sm font-bold text-amber-900">🎉 {event.label} · {event.name}</span>}
              <span className="mt-2 block font-semibold text-[#2F4FBF]">장소 자세히 보기 →</span>
            </button>)}</div>
          </>}
        </div>}
      </div>
    </div>
  )
}
// ─── Camera / Analyzing ───────────────────────────────────────────────────────
// [기능] 카메라 또는 사진 선택을 통해 여행 장소를 찾는 흐름을 안내한다.
function CameraScreen({ nav }: { nav: (s: Screen) => void }) {
  return (
    <div className="h-full bg-black flex flex-col">
      <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between px-5 pt-12 pb-4" style={{ background: 'linear-gradient(to bottom,rgba(0,0,0,0.6),transparent)' }}>
        <button onClick={() => nav('home')} className="text-white p-2"><LeftIc /></button>
        <p className="text-white font-semibold text-sm">궁금한 장소를 찍어주세요</p>
        <div className="w-8" />
      </div>
      <div className="flex-1 relative">
        <img src="https://images.unsplash.com/photo-1596524430615-b46475ddff6e?w=600&h=800&fit=crop" alt="카메라 뷰" className="w-full h-full object-cover opacity-70" />
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-56 h-56 border-2 border-white/70 rounded-2xl" style={{ boxShadow: '0 0 0 9999px rgba(0,0,0,0.4)' }} />
        </div>
      </div>
      <div className="bg-black pb-10 pt-5 flex items-center justify-around px-10">
        <button className="w-14 h-14 rounded-2xl bg-white/20 flex items-center justify-center text-2xl">🖼</button>
        <button onClick={() => nav('analyzing')} className="w-20 h-20 rounded-full border-4 border-white flex items-center justify-center active:scale-95">
          <div className="w-16 h-16 rounded-full bg-white" />
        </button>
        <button className="w-14 h-14 rounded-2xl bg-white/20 flex items-center justify-center text-2xl">📷</button>
      </div>
    </div>
  )
}

// [기능] 사진 또는 입력 정보를 AI가 분석하는 중간 로딩 상태를 표시한다.
function AnalyzingScreen({ nav }: { nav: (s: Screen) => void }) {
  const [step, setStep] = useState(0)
  const msgs = ['사진 속 장소를 찾고 있어요...', '위치 정보를 분석하고 있어요...', '장소를 확인했어요!']
  useEffect(() => {
    const t = setInterval(() => setStep(s => { if (s >= 2) { clearInterval(t); setTimeout(() => nav('place-result'), 600); return s }; return s + 1 }), 1000)
    return () => clearInterval(t)
  }, [])
  return (
    <div className="h-full flex flex-col items-center justify-center" style={{ background: 'linear-gradient(160deg,#F0F4FF,#F7F0FF)' }}>
      <div className="relative w-28 h-28 mb-8">
        <div className="w-28 h-28 rounded-full border-4 border-[#4169D8]/20 border-t-[#4169D8] animate-spin" />
        <div className="absolute inset-0 flex items-center justify-center text-4xl">📸</div>
      </div>
      <p className="text-lg font-bold text-gray-900">{msgs[step]}</p>
    </div>
  )
}

// [기능] 분석·검색 결과로 찾은 장소의 요약 정보를 보여주고 다음 행동을 연결한다.
function PlaceResultScreen({ nav, setState }: { nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>> }) {
  const places = [
    { id: 'p1', name: '안목해변', region: '강원 강릉시', tags: ['바다', '카페', '산책'], img: 'photo-1507525428034-b723cf961d3e', primary: true },
    { id: 'p2', name: '경포해변', region: '강원 강릉시', tags: ['바다', '관광'], img: 'photo-1596524430615-b46475ddff6e', primary: false },
  ]
  return (
    <div className="h-full flex flex-col px-5 pt-14 pb-6" style={{ background: 'linear-gradient(160deg,#F0F4FF,#F7F8FF)' }}>
      <button onClick={() => nav('home')} className="mb-4 flex items-center gap-1 text-gray-600"><LeftIc /><span>뒤로</span></button>
      <h1 className="text-xl font-bold text-gray-900 mb-1">사진 속 장소를 찾았어요</h1>
      <p className="text-sm text-gray-400 mb-5">가장 비슷한 장소를 골라주세요</p>
      <div className="space-y-3 flex-1">
        {places.map(p => (
          <button key={p.id} onClick={() => { setState(s => ({ ...s, selectedPlace: p })); nav('place-detail') }}
            className="w-full bg-white rounded-2xl flex overflow-hidden active:scale-95 transition-transform text-left" style={{ boxShadow: '0 2px 12px rgba(0,0,0,0.07)' }}>
            <img src={placeImageUrl(p.img, 200, 200)} alt={p.name} className="w-24 h-24 object-cover flex-shrink-0" />
            <div className="p-3 flex flex-col justify-between flex-1">
              <div>
                <div className="flex items-center gap-2 mb-0.5">
                  {p.primary && <span className="text-xs bg-[#4169D8] text-white px-2 py-0.5 rounded-full">가장 유사</span>}
                  <span className="font-bold text-gray-900 text-sm">{p.name}</span>
                </div>
                <p className="text-xs text-gray-400">{p.region}</p>
              </div>
              <div className="flex gap-1 flex-wrap mt-1">{p.tags.map(t => <Tag key={t} label={t} blue />)}</div>
            </div>
            <div className="flex items-center pr-3 text-[#4169D8]"><RightIc /></div>
          </button>
        ))}
      </div>
      <div className="mt-4 p-4 bg-[#EEF2FF] rounded-2xl">
        <p className="text-sm font-bold text-[#4169D8] mb-2">이 장소로 여행을 만들까요?</p>
        <button onClick={() => nav('trip-places')} className="w-full h-11 rounded-xl bg-[#4169D8] text-white font-bold text-sm">이 장소로 여행 만들기</button>
      </div>
    </div>
  )
}

// ─── YouTube Saved ────────────────────────────────────────────────────────────
// [기능] YouTube 등에서 저장한 장소 목록을 관리하고 여행 계획에 추가할 수 있게 한다.
function YouTubeSavedScreen({ state, nav, setState }: { state: AppState; nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>> }) {
  const sm = state.seniorMode
  return (
    <div className="flex flex-col h-full" style={{ background: 'linear-gradient(160deg,#F0F4FF,#F7F8FF)' }}>
      <div className="px-5 pt-12 pb-3 flex-shrink-0">
        <div className="flex items-center justify-between mb-1">
          <h1 className={`font-bold text-gray-900 ${sm ? 'text-2xl' : 'text-xl'}`}>내가 발견한 여행지</h1>
          <span className="flex items-center gap-1 text-xs text-gray-400"><YtIc /> YouTube 저장</span>
        </div>
        <p className="text-sm text-gray-400">YouTube에서 발견하고 저장한 여행지예요</p>
      </div>
      <div className="mb-4 grid flex-shrink-0 grid-cols-2 gap-3 px-5">
        <button onClick={() => nav('ai-analysis')} className="flex h-32 flex-col items-center justify-center gap-2 rounded-3xl p-3 text-center font-bold text-[#4169D8] active:scale-[0.98] transition-transform focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-[#4169D8]"
          style={{ background: 'linear-gradient(135deg,#EEF2FF,#F0F4FF)', border: '1.5px solid #C7D4F8' }}>
          <span aria-hidden="true" className="[&>svg]:size-8"><YtIc /></span>
          <span className={sm ? 'text-base leading-6' : 'text-sm leading-5'}>AI로 내 여행<br />취향 분석하기</span>
        </button>
        <button onClick={() => nav('past-trips')} className="flex h-32 flex-col items-center justify-center gap-2 rounded-3xl bg-white p-3 text-center font-bold text-[#8B5E3C] shadow-sm active:scale-[0.98] transition-transform focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-[#8B5E3C]">
          <span aria-hidden="true" className="text-3xl">📷</span>
          <span className={sm ? 'text-base leading-6' : 'text-sm leading-5'}>지난 여행 보기</span>
        </button>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-hide px-5 pb-4">
        <div className="grid grid-cols-2 gap-3">
          {state.savedPlaces.map(p => (
            <button key={p.id} onClick={() => { setState(s => ({ ...s, selectedPlace: p })); nav('place-detail') }}
              className="bg-white rounded-2xl overflow-hidden active:scale-95 transition-transform text-left" style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <div className="relative">
                <img src={placeImageUrl(p.img, 300, 200)} alt={p.name} className="w-full h-28 object-cover" />
                <div className="absolute top-2 left-2 bg-white/90 rounded-full p-1"><YtIc /></div>
              </div>
              <div className="p-3">
                <p className={`font-bold text-gray-900 ${sm ? 'text-base' : 'text-sm'}`}>{p.name}</p>
                <p className="text-xs text-gray-400 mb-1.5">{p.region}</p>
                <div className="flex flex-wrap gap-1">{p.tags.slice(0, 2).map(t => <Tag key={t} label={t} blue />)}</div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── AI Analysis / Taste ─────────────────────────────────────────────────────
// [기능] 저장 장소와 사용자 취향을 바탕으로 AI 취향 분석 결과를 보여준다.
function AIAnalysisScreen({ state, nav, setState }: { state: AppState; nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>> }) {
  const [done, setDone] = useState(false)
  useEffect(() => { const t = setTimeout(() => setDone(true), 2000); return () => clearTimeout(t) }, [])
  const sm = state.seniorMode
  if (!done) return (
    <div className="h-full flex flex-col items-center justify-center" style={{ background: 'linear-gradient(160deg,#F0F4FF,#F7F0FF)' }}>
      <div className="relative w-28 h-28 mb-6">
        <div className="w-28 h-28 rounded-full border-4 border-[#4169D8]/20 border-t-[#4169D8] animate-spin" />
        <div className="absolute inset-0 flex items-center justify-center"><YtIc /></div>
      </div>
      <p className="text-lg font-bold text-gray-900">저장한 콘텐츠를 분석하고 있어요</p>
      <p className="text-sm text-gray-400 mt-1">{state.savedPlaces.length}개의 여행지 분석 중...</p>
    </div>
  )
  return (
    <div className="h-full flex flex-col px-5 pt-14 pb-6" style={{ background: 'linear-gradient(160deg,#F0F4FF,#F7F8FF)' }}>
      <button onClick={() => nav('youtube-saved')} className="mb-5 flex items-center gap-1 text-gray-600"><LeftIc /><span>뒤로</span></button>
      <div className="text-center mb-6">
        <div className="text-5xl mb-3">🎯</div>
        <h1 className={`font-bold text-gray-900 mb-1 ${sm ? 'text-2xl' : 'text-xl'}`}>여행 취향을 알아봤어요</h1>
        <p className="text-sm text-gray-400">저장한 {state.savedPlaces.length}개의 여행 콘텐츠를 분석해보니</p>
      </div>
      <div className="bg-white rounded-3xl p-5 mb-5 flex-1" style={{ boxShadow: '0 2px 16px rgba(65,105,216,0.1)' }}>
        <p className={`text-gray-700 mb-4 ${sm ? 'text-lg' : 'text-base'}`}>이런 여행을 좋아하시는 것 같아요!</p>
        <div className="flex flex-wrap gap-2 mb-5">
          {state.aiPrefs.map(p => <span key={p} className="flex items-center gap-1 px-4 py-2 bg-[#EEF2FF] text-[#4169D8] rounded-full font-bold text-sm">{PREFS_E[p]} {p}</span>)}
        </div>
        <div className="space-y-2 text-sm text-gray-400">
          <p>• 바다와 해변을 즐기는 콘텐츠를 많이 저장했어요</p>
          <p>• 맛집 탐방 여행에 관심이 높아요</p>
          <p>• 여유로운 휴식형 여행을 선호하는 것 같아요</p>
        </div>
      </div>
      <div className="space-y-3">
        <PrimaryBtn label="맞아요 — 취향 저장" onClick={() => { setState(s => ({ ...s, userPrefs: state.aiPrefs })); nav('home') }} sm={sm} />
        <button onClick={() => nav('taste-confirm')} className={`w-full rounded-2xl border-2 border-gray-200 text-gray-600 font-bold active:scale-95 ${sm ? 'h-16 text-lg' : 'h-12 text-sm'}`}>수정할게요</button>
      </div>
    </div>
  )
}

// [기능] AI가 추정한 여행 취향을 사용자가 확인·수정한 뒤 여행 생성에 반영하게 한다.
function TasteConfirmScreen({ state, nav, setState }: { state: AppState; nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>> }) {
  const [prefs, setPrefs] = useState(state.aiPrefs)
  const sm = state.seniorMode
  const toggle = (p: string) => setPrefs(current => current.includes(p) ? current.filter(item => item !== p) : [...current, p])
  return (
    <div className="flex h-full flex-col bg-[#F5F7FF]">
      <header className="flex-shrink-0 px-5 pt-12 pb-4">
        <button onClick={() => nav('ai-analysis')} className="flex h-11 items-center gap-1 rounded-xl px-2 text-sm font-bold text-gray-600 active:bg-white"><LeftIc /><span>뒤로</span></button>
        <h1 className={`mt-4 font-black text-gray-900 ${sm ? 'text-2xl' : 'text-xl'}`}>취향을 수정해주세요</h1>
        <p className={`mt-1 text-gray-500 ${sm ? 'text-base' : 'text-sm'}`}>원하는 여행 스타일을 골라주세요.</p>
      </header>
      <main className="min-h-0 flex-1 overflow-y-auto px-5 pb-4 scrollbar-hide">
        <section className="rounded-3xl bg-white p-4 shadow-sm">
          <div><div className="flex items-center justify-between gap-3"><h2 className="font-black text-gray-900">여행 취향 선택</h2><span className="shrink-0 whitespace-nowrap rounded-full bg-[#EEF2FF] px-2.5 py-1.5 text-xs font-black text-[#4169D8]">복수 선택 가능</span></div><p className="mt-1 text-sm text-gray-500">원하는 항목을 여러 개 골라주세요.</p></div>
          <div className="mt-4 grid grid-cols-3 gap-2.5">
            {ALL_PREFS.map(p => {
              const selected = prefs.includes(p)
              return <button key={p} type="button" onClick={() => toggle(p)} aria-pressed={selected} className={`relative flex min-h-24 flex-col items-center justify-between rounded-2xl border-2 p-3 text-center shadow-sm transition-all active:scale-[0.98] ${selected ? 'border-[#4169D8] bg-[#EEF2FF] text-[#2447B5]' : 'border-transparent bg-[#FAFBFF] text-gray-800'}`}>
                <span aria-hidden="true" className={`flex h-10 w-10 items-center justify-center rounded-xl text-xl ${selected ? 'bg-white shadow-sm' : 'bg-white'}`}>{PREFS_E[p]}</span>
                <span className={`w-full whitespace-nowrap text-center font-black leading-tight ${sm ? 'text-base' : 'text-sm'}`}>{p}</span>
                {selected && <span aria-label="선택됨" className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-[#4169D8] text-white [&>svg]:size-3"><CheckIc /></span>}
              </button>
            })}
          </div>
        </section>
      </main>
      <footer className="flex-shrink-0 border-t border-[#E5E9FA] bg-white px-5 py-4">
        <PrimaryBtn label="수정한 취향 저장하기" onClick={() => { setState(current => ({ ...current, userPrefs: prefs, aiPrefs: prefs })); nav('profile') }} disabled={prefs.length === 0} sm={sm} />
      </footer>
    </div>
  )
}
// ─── Place Detail ─────────────────────────────────────────────────────────────
// [기능] 선택 장소의 이미지, 태그, 평점과 여행 계획 추가 행동을 제공하는 상세 화면이다.
function PlaceDetailScreen({ state, nav }: { state: AppState; nav: (s: Screen) => void }) {
  const [saved, setSaved] = useState(true)
  const p = state.selectedPlace || YOUTUBE_SAVED[0]; const sm = state.seniorMode
  const infos = [{ e: '🚗', l: '주차 가능' }, { e: '🚶', l: '걷기 쉬움' }, { e: '♿', l: '이동 편리' }, { e: '🚻', l: '화장실 있음' }, { e: '🪜', l: '계단 없음' }, { e: '💰', l: '무료 입장' }]
  return (
    <div className="h-full flex flex-col bg-white">
      <div className="relative h-60">
        <img src={placeImageUrl(p.img, 600, 400)} alt={p.name} className="w-full h-full object-cover" />
        {p.img === jeonjuHanokImage && <a href="https://commons.wikimedia.org/wiki/File:Jeonju_Hanok_Village_20220701_001.jpg" target="_blank" rel="noreferrer" className="absolute bottom-2 left-2 rounded bg-black/75 px-2 py-1 text-xs text-white underline">사진: Mobius6 · CC BY-SA 4.0</a>}
        <div className="absolute inset-0" style={{ background: 'linear-gradient(to top,rgba(0,0,0,0.5) 0%,transparent 50%)' }} />
        <button onClick={() => nav('youtube-saved')} className="absolute top-12 left-4 w-10 h-10 rounded-full bg-white/80 flex items-center justify-center"><LeftIc /></button>
        <button onClick={() => setSaved(s => !s)} className={`absolute top-12 right-4 w-10 h-10 rounded-full flex items-center justify-center ${saved ? 'bg-red-500 text-white' : 'bg-white/80 text-gray-700'}`}>
          <HeartIc f={saved} />
        </button>
      </div>
      <div className="flex-1 px-5 pt-4 pb-28 overflow-y-auto scrollbar-hide">
        <div className="flex items-start justify-between mb-1">
          <h1 className={`font-bold text-gray-900 ${sm ? 'text-2xl' : 'text-xl'}`}>{p.name}</h1>
          <div className="flex items-center gap-1"><StarIc /><span className="font-semibold text-sm text-gray-900">4.8</span></div>
        </div>
        <p className="text-gray-400 text-sm mb-3">{p.region}</p>
        <div className="flex gap-2 mb-5 flex-wrap">{p.tags.map(t => <Tag key={t} label={`${PREFS_E[t] || ''} ${t}`} blue />)}</div>
        <div className="grid grid-cols-3 gap-2 mb-5">
          {infos.map((info, i) => (
            <div key={i} className="bg-gray-50 rounded-xl p-3 text-center">
              <div className="text-xl mb-0.5">{info.e}</div>
              <p className="text-xs text-gray-600 font-medium">{info.l}</p>
            </div>
          ))}
        </div>
        <div className="bg-[#F7F9FF] rounded-2xl p-4">
          <p className="text-sm font-semibold text-gray-900 mb-2">이런 분들께 추천해요</p>
          {['걷기 어려우신 분도 해안 데크로 편하게', '주차장이 넓어 자가용 방문에 좋아요', '화장실이 바로 근처에 있어요'].map((t, i) => (
            <p key={i} className="text-xs text-gray-400 flex gap-2 mb-1"><span className="text-[#4169D8]">✓</span>{t}</p>
          ))}
        </div>
      </div>
      <div className="flex-shrink-0 px-5 pb-6 pt-3 bg-white border-t border-gray-100">
        <PrimaryBtn label="이 장소로 여행 만들기" onClick={() => nav('trip-places')} sm={sm} />
      </div>
    </div>
  )
}

// ─── Map ──────────────────────────────────────────────────────────────────────
const FALLBACK_LOCATION = {
  lat: 35.1102272,
  lng: 126.8819292,
  label: '광주광역시 남구 송하동 60 (기본 위치)',
}

const MAP_CATS = ['전체', '관광지', '맛집', '카페', '전시', '숙소']
const MAP_PTS = [
  { name: '주변 산책 명소', lat: 35.1122, lng: 126.8840, cat: '관광지', r: 4.8, dist: '도보 약 12분' },
  { name: '휴식 카페 추천', lat: 35.1088, lng: 126.8850, cat: '카페', r: 4.6, dist: '도보 약 8분' },
  { name: '가까운 식당 추천', lat: 35.1092, lng: 126.8788, cat: '맛집', r: 4.5, dist: '도보 약 15분' },
  { name: '주변 숙소 추천', lat: 35.1144, lng: 126.8797, cat: '숙소', r: 4.7, dist: '차량 약 5분' },
  { name: '문화 공간 추천', lat: 35.1069, lng: 126.8822, cat: '전시', r: 4.4, dist: '차량 약 10분' },
]

type MapLocation = { lat: number; lng: number; label: string }

// [기능] GPS 또는 기본 위치가 변경될 때 Leaflet 지도의 중심 좌표를 최신 위치로 이동시킨다.
function MapRecenter({ location }: { location: MapLocation }) {
  const map = useMap()
  useEffect(() => {
    map.setView([location.lat, location.lng], 15, { animate: true })
  }, [location.lat, location.lng, map])
  return null
}
// [기능] 큰 글씨와 단순한 행동을 중심으로 구성한 시니어 친화 여행 보조 화면이다.
function ComfortTravelScreen({ state, nav }: { state: AppState; nav: (s: Screen) => void }) {
  const trip = state.currentTrip
  const next = trip.days[0]?.places[0]
  return (
    <div className="h-full flex flex-col bg-[#F7F8FF]">
      <PageHeader title="편안한 여행" back={() => nav('home')} />
      <main className="flex-1 overflow-y-auto px-5 py-5 space-y-4 scrollbar-hide" aria-label="편안한 여행 안내">
        <section className="rounded-3xl bg-[#172554] p-5 text-white" aria-labelledby="comfort-summary"><p className="text-base font-semibold text-blue-200">오늘의 여행 안내</p><h2 id="comfort-summary" className="mt-1 text-2xl font-bold">{trip.title}</h2><p className="mt-2 text-lg text-blue-100">오늘 일정을 쉽고 크게 안내해 드릴게요.</p></section>
        <section className="rounded-3xl bg-white p-5 shadow-sm" aria-labelledby="next-action-title"><p className="text-base font-bold text-[#4169D8]">지금 할 일</p>{next ? <><h2 id="next-action-title" className="mt-2 text-2xl font-black text-gray-900">{next.place}</h2><p className="mt-2 text-lg leading-7 text-gray-700">{next.time} · {next.walk || '이동 정보를 확인해 주세요'}</p><button onClick={() => nav('directions')} className="mt-5 min-h-14 w-full rounded-2xl bg-[#4169D8] px-5 text-lg font-bold text-white active:scale-[0.98]" aria-label={`${next.place} 길찾기 시작`}>길찾기 시작</button></> : <><h2 id="next-action-title" className="mt-2 text-2xl font-black text-gray-900">다음 일정이 없어요</h2><button onClick={() => nav('itinerary')} className="mt-5 min-h-14 w-full rounded-2xl bg-[#4169D8] px-5 text-lg font-bold text-white">오늘 일정 보기</button></>}</section>
        <section className="rounded-3xl bg-white p-5 shadow-sm" aria-labelledby="today-list-title"><div className="flex items-center justify-between gap-3"><h2 id="today-list-title" className="text-xl font-bold text-gray-900">오늘의 일정</h2><button onClick={() => nav('itinerary')} className="min-h-11 px-2 text-base font-bold text-[#4169D8]">전체 보기</button></div><ol className="mt-3 space-y-3">{(trip.days[0]?.places.slice(0, 3) || []).map(item => <li key={`${item.time}-${item.place}`} className="rounded-2xl bg-[#F7F8FF] p-4"><p className="text-base font-bold text-[#4169D8]">{item.time}</p><p className="mt-1 text-xl font-bold text-gray-900">{item.place}</p><p className="mt-1 text-base text-gray-600">{item.walk || '이동 정보는 일정에서 확인할 수 있어요.'}</p></li>)}</ol></section>
        <section className="rounded-3xl bg-white p-5 shadow-sm" aria-labelledby="quick-help-title"><h2 id="quick-help-title" className="text-xl font-bold text-gray-900">빠른 도움</h2><div className="mt-3 grid gap-3"><button onClick={() => nav('itinerary')} className="min-h-14 rounded-2xl border-2 border-[#4169D8] bg-white px-4 text-left text-lg font-bold text-[#2749A5]">오늘 일정 다시 보기</button><button onClick={() => nav('map')} className="min-h-14 rounded-2xl border-2 border-gray-200 bg-white px-4 text-left text-lg font-bold text-gray-800">목적지 찾아보기</button></div><p className="mt-4 text-base leading-6 text-gray-600">도움이 필요하면 일정 화면에서 이동 방법을 다시 확인할 수 있어요.</p></section>
        <section className="rounded-3xl border border-[#DCE5FF] bg-[#EEF2FF] p-5" aria-labelledby="display-title"><h2 id="display-title" className="text-xl font-bold text-gray-900">화면을 더 편하게 보기</h2><p className="mt-2 text-base leading-6 text-gray-700">글자를 크게 보거나 일반 화면으로 언제든 바꿀 수 있어요.</p><button onClick={() => nav('profile')} className="mt-3 min-h-12 rounded-xl bg-white px-4 text-base font-bold text-[#2749A5]">화면 설정 열기</button></section>
      </main>
    </div>
  )
}
// [기능] GPS 현재 위치(실패 시 송하동 기본값)를 중심으로 장소 탐색, 분류, 일반/위성 지도를 제공한다.
function MapScreen({ nav }: { nav: (s: Screen) => void }) {
  const [cat, setCat] = useState('전체')
  const [sel, setSel] = useState<typeof MAP_PTS[0] | null>(null)
  const [location, setLocation] = useState<MapLocation>(FALLBACK_LOCATION)
  const [locationStatus, setLocationStatus] = useState<'locating' | 'gps' | 'fallback'>('locating')
  const [mapStyle, setMapStyle] = useState<'standard' | 'satellite'>('standard')
  const hasRequestedLocation = useRef(false)
  const pts = cat === '전체' ? MAP_PTS : MAP_PTS.filter(p => p.cat === cat)

  const requestLocation = () => {
    if (!navigator.geolocation) {
      setLocation(FALLBACK_LOCATION)
      setLocationStatus('fallback')
      return
    }
    setLocationStatus('locating')
    navigator.geolocation.getCurrentPosition(
      position => {
        setLocation({ lat: position.coords.latitude, lng: position.coords.longitude, label: '현재 위치' })
        setLocationStatus('gps')
      },
      () => {
        setLocation(FALLBACK_LOCATION)
        setLocationStatus('fallback')
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 },
    )
  }

  useEffect(() => {
    if (hasRequestedLocation.current) return
    hasRequestedLocation.current = true
    requestLocation()
  }, [])

  const locationMessage = locationStatus === 'gps'
    ? 'GPS 현재 위치를 표시하고 있어요.'
    : locationStatus === 'locating'
      ? '현재 위치를 확인하고 있어요.'
      : 'GPS를 사용할 수 없어 송하동 기본 위치를 표시하고 있어요.'

  return (
    <div className="flex flex-col h-full bg-white">
      <div className="flex-shrink-0 px-5 pt-12 pb-3 bg-white">
        <div className="flex items-center justify-between gap-3 mb-3"><h1 className="font-bold text-gray-900 text-xl">지도 탐색</h1><button onClick={requestLocation} className="min-h-10 rounded-xl bg-[#EEF2FF] px-3 text-xs font-bold text-[#4169D8]">현재 위치 다시 확인</button></div>
        <p className="mb-3 text-xs leading-5 text-gray-500" role="status">{locationMessage}</p>
        <div className="mb-3 inline-flex rounded-xl bg-gray-100 p-1" aria-label="지도 유형">
          <button onClick={() => setMapStyle('standard')} aria-pressed={mapStyle === 'standard'} className={`min-h-9 rounded-lg px-3 text-xs font-bold ${mapStyle === 'standard' ? 'bg-white text-[#4169D8] shadow-sm' : 'text-gray-500'}`}>일반 지도</button>
          <button onClick={() => setMapStyle('satellite')} aria-pressed={mapStyle === 'satellite'} className={`min-h-9 rounded-lg px-3 text-xs font-bold ${mapStyle === 'satellite' ? 'bg-white text-[#4169D8] shadow-sm' : 'text-gray-500'}`}>위성 지도</button>
        </div>
        <div className="flex gap-2 overflow-x-auto scrollbar-hide -mx-1 px-1 pb-1" aria-label="장소 분류">
          {MAP_CATS.map(c => <button key={c} onClick={() => setCat(c)} aria-pressed={cat === c} className={`flex-shrink-0 min-h-10 px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${cat === c ? 'bg-[#4169D8] text-white' : 'bg-gray-100 text-gray-600'}`}>{c}</button>)}
        </div>
      </div>
      <div className="flex-1 relative min-h-0" aria-label="현재 위치 기반 지도">
        <MapContainer attributionControl={false} center={[location.lat, location.lng]} zoom={15} scrollWheelZoom className="h-full w-full" aria-label="OpenStreetMap 지도">
          <MapRecenter location={location} />
          <ExploreMapTiles style={mapStyle} />
          <CircleMarker center={[location.lat, location.lng]} radius={10} pathOptions={{ color: '#ffffff', weight: 3, fillColor: '#16A34A', fillOpacity: 1 }}>
            <Tooltip permanent direction="top" offset={[0, -12]}>현재 위치</Tooltip>
            <Popup><strong>{location.label}</strong><br />{locationStatus === 'gps' ? 'GPS 기반 위치' : 'GPS 미사용 시 기본 위치'}</Popup>
          </CircleMarker>
          {pts.map(p => <CircleMarker key={p.name} center={[p.lat, p.lng]} radius={sel?.name === p.name ? 11 : 8} pathOptions={{ color: '#ffffff', weight: 2, fillColor: '#4169D8', fillOpacity: 1 }} eventHandlers={{ click: () => setSel(sel?.name === p.name ? null : p) }}><Tooltip direction="top" offset={[0, -8]}>{p.name}</Tooltip></CircleMarker>)}
        </MapContainer>
        <button onClick={() => nav('trip-places')} className="absolute top-4 right-4 z-[500] min-h-10 rounded-xl bg-white px-3 py-2 text-xs font-bold text-[#4169D8] shadow-md">추천 코스</button>
        {sel && <div className="absolute bottom-4 left-4 right-4 z-[500] rounded-2xl bg-white p-4 shadow-lg"><div className="flex items-start justify-between mb-2"><div><h2 className="font-bold text-gray-900">{sel.name}</h2><p className="text-xs text-gray-500">{sel.dist} · {sel.cat}</p></div><div className="flex items-center gap-1"><StarIc /><span className="text-sm font-semibold">{sel.r}</span></div></div><div className="flex gap-2"><button onClick={() => nav('place-detail')} className="flex-1 min-h-11 rounded-xl bg-gray-100 text-sm font-semibold text-gray-700">상세보기</button><button onClick={() => nav('trip-places')} className="flex-1 min-h-11 rounded-xl bg-[#4169D8] text-sm font-semibold text-white">여행 만들기</button></div></div>}
      </div>
      <div className="shrink-0 border-t border-gray-100 bg-white px-3 py-1.5 text-[11px] leading-4 text-gray-500" aria-label="지도 출처">
        {mapStyle === 'standard'
          ? <span>지도 출처: © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer" className="underline">OpenStreetMap 기여자</a></span>
          : <span>위성영상 출처: © <a href="https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9" target="_blank" rel="noreferrer" className="underline">Esri, Maxar, Earthstar Geographics</a> 및 GIS 사용자 커뮤니티</span>}
      </div>
    </div>
  )
}
// ─── Trip: Places ─────────────────────────────────────────────────────────────
// [기능] 여행 생성 1단계로 사용자가 방문 후보 장소를 복수 선택한다.
function TripPlacesScreen({ state, nav, setState }: { state: AppState; nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>> }) {
  const [sel, setSel] = useState<Place[]>(state.draft.selectedPlaces || [])
  const toggle = (p: Place) => setSel(s => s.find(x => x.id === p.id) ? s.filter(x => x.id !== p.id) : [...s, p])
  const sm = state.seniorMode
  return (
    <div className="h-full bg-white flex flex-col">
      <PageHeader title="장소 선택" back={() => nav('home')} />
      <div className="px-5 py-3 flex-shrink-0">
        <p className="text-sm font-semibold text-[#4169D8] mb-0.5">여행 만들기 1/6</p>
        <p className="text-sm text-gray-400">가보고 싶은 여행지를 선택해주세요 (복수 선택)</p>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-hide px-5 pb-24 space-y-3">
        {state.savedPlaces.map(p => {
          const on = !!sel.find(x => x.id === p.id)
          return (
            <button key={p.id} onClick={() => toggle(p)}
              className={`w-full flex gap-3 rounded-2xl p-3 border-2 transition-all active:scale-95 text-left ${on ? 'border-[#4169D8] bg-[#EEF2FF]' : 'border-gray-100 bg-white'}`}
              style={!on ? { boxShadow: '0 1px 6px rgba(0,0,0,0.05)' } : {}}>
              <img src={placeImageUrl(p.img, 100, 100)} alt={p.name} className="w-16 h-16 rounded-xl object-cover flex-shrink-0" />
              <div className="flex-1">
                <div className="flex items-start justify-between">
                  <div>
                    <p className={`font-bold text-gray-900 ${sm ? 'text-base' : 'text-sm'}`}>{p.name}</p>
                    <p className="text-xs text-gray-400">{p.region}</p>
                  </div>
                  {on && <div className="w-6 h-6 rounded-full bg-[#4169D8] flex items-center justify-center flex-shrink-0 text-white"><CheckIc /></div>}
                </div>
                <div className="flex gap-1 mt-1 flex-wrap">{p.tags.slice(0, 2).map(t => <Tag key={t} label={t} />)}</div>
              </div>
            </button>
          )
        })}
      </div>
      <div className="flex-shrink-0 px-5 pb-6 pt-3 bg-white border-t border-gray-100">
        <PrimaryBtn label={sel.length > 0 ? `선택 완료 (${sel.length}곳)` : '장소를 선택해주세요'} disabled={sel.length === 0}
          onClick={() => { setState(s => ({ ...s, draft: { ...s.draft, selectedPlaces: sel } })); nav('trip-date') }} sm={sm} />
      </div>
    </div>
  )
}

// ─── Trip: Date ───────────────────────────────────────────────────────────────
// [기능] 여행 생성 2단계로 시작일과 종료일을 검증하며 선택한다.
// [기능] 여행 생성 2단계에서 기기 기준 현재 월의 여행 날짜를 선택한다. 오늘 이전 날짜는 비활성화한다.
function TripDateScreen({ state, nav, setState }: { state: AppState; nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>> }) {
  const [start, setStart] = useState(state.draft.startDate || '')
  const [end, setEnd] = useState(state.draft.endDate || '')
  const sm = state.seniorMode
  // 기기 기준 오늘 날짜를 사용해 현재 달력을 만들고, 오늘 이전 날짜는 선택 대상에서 제외한다.
  const today = new Date()
  const currentMonth = today.getFullYear() * 12 + today.getMonth()
  const [visibleMonth, setVisibleMonth] = useState(() => {
    const saved = state.draft.startDate
    if (!saved) return currentMonth
    const [year, month] = saved.split('-').map(Number)
    return Math.max(currentMonth, year * 12 + month - 1)
  })
  const calendarYear = Math.floor(visibleMonth / 12)
  const calendarMonth = visibleMonth % 12
  const monthDays = Array.from({ length: new Date(calendarYear, calendarMonth + 1, 0).getDate() }, (_, i) => i + 1)
  const firstDay = new Date(calendarYear, calendarMonth, 1).getDay()
  const toIso = (year: number, month: number, day: number) => `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
  const todayIso = toIso(today.getFullYear(), today.getMonth(), today.getDate())

  // [기능] 날짜 선택 화면에서 시작일·종료일의 순서와 오늘 이전 날짜 차단을 처리하는 내부 선택 함수다.
  function pick(day: number) {
    const iso = toIso(calendarYear, calendarMonth, day)
    if (iso < todayIso) return
    if (!start || (start && end)) { setStart(iso); setEnd('') }
    else if (iso >= start) setEnd(iso)
    else { setEnd(start); setStart(iso) }
  }

  const mk = (day: number) => toIso(calendarYear, calendarMonth, day)
  const nights = start && end ? nightsCount(start, end) : 0
  const days = start && end ? dayCount(start, end) : 0
  const validRange = Boolean(start && end && start >= todayIso && end >= start && days <= 366)
  return (
    <div className="h-full bg-white flex flex-col">
      <PageHeader title="날짜 선택" back={() => nav('trip-places')} />
      <div className="px-5 py-3 flex-shrink-0"><p className="text-sm font-semibold text-[#4169D8] mb-0.5">여행 만들기 2/6</p><p className={`font-bold text-gray-900 ${sm ? 'text-xl' : 'text-lg'}`}>언제 떠나세요?</p><p className="mt-1 text-xs text-gray-400">오늘 이전 날짜는 선택할 수 없어요.</p></div>
      <div className="flex-1 min-h-0 overflow-y-auto px-5">
        <div className="bg-white rounded-2xl p-4 mb-3" style={{ boxShadow: '0 2px 12px rgba(0,0,0,0.06)' }}>
                    <div className="mb-3 flex items-center justify-between gap-2">
            <button type="button" aria-label="이전 달" disabled={visibleMonth <= currentMonth} onClick={() => setVisibleMonth(month => Math.max(currentMonth, month - 1))} className="flex size-11 shrink-0 items-center justify-center rounded-xl text-[#4169D8] disabled:text-gray-300 focus-visible:outline-2"><LeftIc /></button>
            <p aria-live="polite" className="min-w-0 flex-1 text-center text-base font-bold text-gray-900">{calendarYear}년 {calendarMonth + 1}월</p>
            <button type="button" aria-label="다음 달" disabled={visibleMonth >= 9999 * 12 + 11} onClick={() => setVisibleMonth(month => month + 1)} className="flex size-11 shrink-0 items-center justify-center rounded-xl text-[#4169D8] disabled:text-gray-300 focus-visible:outline-2"><RightIc /></button>
          </div>
          <div className="grid grid-cols-7 gap-1 mb-1">{['일', '월', '화', '수', '목', '금', '토'].map(day => <div key={day} className="text-center text-xs text-gray-400 py-1">{day}</div>)}</div>
          <div className="grid grid-cols-7 gap-1">
            {Array(firstDay).fill(null).map((_, index) => <div key={`empty-${index}`} />)}
            {monthDays.map(day => {
              const iso = mk(day); const isStart = start === iso; const isEnd = end === iso
              const between = start && end && iso > start && iso < end
              const isPast = iso < todayIso
              return <button key={day} onClick={() => pick(day)} disabled={isPast} aria-label={isPast ? `${day}일은 지난 날짜로 선택할 수 없어요` : `${day}일 선택`}
                className={`${sm ? 'h-11 text-base' : 'h-9 text-sm'} flex items-center justify-center font-medium transition-all ${isPast ? 'cursor-not-allowed text-gray-300' : isStart || isEnd ? 'rounded-full bg-[#4169D8] text-white' : between ? 'rounded-full bg-[#EEF2FF] text-[#4169D8]' : 'rounded-full text-gray-700 hover:bg-gray-100'}`}>{day}</button>
            })}
          </div>
        </div>
        {start && end && <div className="bg-[#EEF2FF] rounded-2xl p-4 text-center mb-4"><p className={`font-bold text-[#4169D8] ${sm ? 'text-xl' : 'text-lg'}`}>{start.replace(/-/g, '.')} ~ {end.replace(/-/g, '.')}</p><p className="text-sm text-gray-500 mt-1">{nights}박 {days}일 · DAY 1~{days}</p></div>}
      </div>
      <div className="px-5 pb-6 flex-shrink-0">{days > 366 && <p role="alert" className="mb-2 text-sm text-red-600">여행 기간은 366일 이내로 선택해주세요.</p>}<PrimaryBtn label="날짜 선택 완료" disabled={!validRange} onClick={() => { if (!validRange) return; setState(current => ({ ...current, draft: { ...current.draft, startDate: start, endDate: end } })); nav('trip-people') }} sm={sm} /></div>
    </div>
  )
}
// ─── Trip: People ─────────────────────────────────────────────────────────────
// [기능] 여행 생성 단계에서 여행 인원수를 설정한다.
function TripPeopleScreen({ state, nav, setState }: { state: AppState; nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>> }) {
  const [count, setCount] = useState(state.draft.travelers || 2); const sm = state.seniorMode
  const labels = ['혼자', '2명', '3명', '4명', '5명 이상']
  return (
    <div className="h-full bg-white flex flex-col">
      <PageHeader title="여행 인원" back={() => nav('trip-date')} />
      <div className="px-5 py-3 flex-shrink-0">
        <p className="text-sm font-semibold text-[#4169D8] mb-0.5">여행 만들기 3/6</p>
        <p className={`font-bold text-gray-900 ${sm ? 'text-xl' : 'text-lg'}`}>누구와 떠나세요?</p>
      </div>
      <div className="flex-1 px-5">
        <div className="flex flex-col items-center justify-center h-48 gap-6">
          <span className="text-6xl">👥</span>
          <div className="flex items-center gap-8">
            <button onClick={() => setCount(c => Math.max(1, c - 1))} className={`rounded-full bg-gray-100 flex items-center justify-center ${sm ? 'w-16 h-16' : 'w-14 h-14'}`}><MinusIc /></button>
            <span className={`font-bold text-gray-900 w-16 text-center ${sm ? 'text-5xl' : 'text-4xl'}`}>{count}</span>
            <button onClick={() => setCount(c => Math.min(20, c + 1))} className={`rounded-full bg-[#4169D8] text-white flex items-center justify-center ${sm ? 'w-16 h-16' : 'w-14 h-14'}`}><PlusIc /></button>
          </div>
          <p className={`text-gray-400 ${sm ? 'text-xl' : 'text-lg'}`}>{count < 5 ? labels[count - 1] : '5명 이상'}</p>
        </div>
        <div className="grid grid-cols-5 gap-2 mt-4">
          {labels.map((l, i) => (
            <button key={l} onClick={() => setCount(i === 4 ? 5 : i + 1)}
              className={`rounded-xl py-2 text-xs font-medium transition-all ${count === (i === 4 ? 5 : i + 1) ? 'bg-[#4169D8] text-white' : 'bg-gray-50 text-gray-600'}`}>{l}</button>
          ))}
        </div>
      </div>
      <div className="px-5 pb-6">
        <PrimaryBtn label="다음" onClick={() => { setState(s => ({ ...s, draft: { ...s.draft, travelers: count } })); nav('trip-transport') }} sm={sm} />
      </div>
    </div>
  )
}

// ─── Trip: Transport ──────────────────────────────────────────────────────────
// [기능] 여행 생성 단계에서 사용할 이동수단을 복수 선택한다.
function TripTransportScreen({ state, nav, setState }: { state: AppState; nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>> }) {
  const [sel, setSel] = useState<string[]>(state.draft.transport || []); const sm = state.seniorMode
  const toggle = (id: string) => setSel(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id])
  return (
    <div className="h-full bg-white flex flex-col">
      <PageHeader title="이동수단" back={() => nav('trip-people')} />
      <div className="px-5 py-3 flex-shrink-0">
        <p className="text-sm font-semibold text-[#4169D8] mb-0.5">여행 만들기 4/6</p>
        <p className={`font-bold text-gray-900 mb-1 ${sm ? 'text-xl' : 'text-lg'}`}>어떻게 이동하시나요?</p>
        <p className="text-sm text-gray-400">복수 선택 가능해요</p>
      </div>
      <div className="flex-1 px-5 py-3">
        <div className="grid grid-cols-2 gap-3">
          {TRANSPORTS.map(t => {
            const on = sel.includes(t.id)
            return (
              <button key={t.id} onClick={() => toggle(t.id)}
                className={`rounded-2xl p-5 flex flex-col items-center gap-2 border-2 transition-all active:scale-95 ${on ? 'bg-[#EEF2FF] border-[#4169D8]' : 'bg-gray-50 border-transparent'}`}>
                <span className={sm ? 'text-4xl' : 'text-3xl'}>{t.e}</span>
                <span className={`font-medium text-gray-900 ${sm ? 'text-base' : 'text-sm'}`}>{t.id}</span>
                {on && <div className="w-5 h-5 rounded-full bg-[#4169D8] flex items-center justify-center text-white"><CheckIc /></div>}
              </button>
            )
          })}
        </div>
      </div>
      <div className="px-5 pb-6">
        <PrimaryBtn label="다음" disabled={sel.length === 0}
          onClick={() => { setState(s => ({ ...s, draft: { ...s.draft, transport: sel } })); nav('trip-budget') }} sm={sm} />
      </div>
    </div>
  )
}

// ─── Trip: Budget ─────────────────────────────────────────────────────────────
const BUDGETS = [
  { id: '저예산', desc: '10만원 이하', e: '💚' }, { id: '보통', desc: '10~30만원', e: '💛' },
  { id: '여유롭게', desc: '30~50만원', e: '🧡' }, { id: '넉넉하게', desc: '50만원 이상', e: '❤️' },
]
// [기능] 여행 생성 단계에서 예산 범위를 선택한다.
function TripBudgetScreen({ state, nav, setState }: { state: AppState; nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>> }) {
  const [sel, setSel] = useState(state.draft.budget || ''); const [custom, setCustom] = useState(''); const sm = state.seniorMode
  return (
    <div className="h-full bg-white flex flex-col">
      <PageHeader title="예산" back={() => nav('trip-transport')} />
      <div className="px-5 py-3 flex-shrink-0">
        <p className="text-sm font-semibold text-[#4169D8] mb-0.5">여행 만들기 5/6</p>
        <p className={`font-bold text-gray-900 ${sm ? 'text-xl' : 'text-lg'}`}>예산은 어느 정도인가요?</p>
        <p className="text-sm text-gray-400">1인 기준이에요</p>
      </div>
      <div className="flex-1 px-5 py-3 space-y-3">
        {BUDGETS.map(b => (
          <button key={b.id} onClick={() => setSel(b.id)}
            className={`w-full rounded-2xl p-4 flex items-center gap-3 border-2 transition-all active:scale-95 ${sel === b.id ? 'bg-[#EEF2FF] border-[#4169D8]' : 'bg-gray-50 border-transparent'}`}>
            <span className="text-2xl">{b.e}</span>
            <div className="flex-1 text-left">
              <p className={`font-bold text-gray-900 ${sm ? 'text-lg' : 'text-base'}`}>{b.id}</p>
              <p className="text-xs text-gray-400">{b.desc}</p>
            </div>
            {sel === b.id && <div className="w-6 h-6 rounded-full bg-[#4169D8] flex items-center justify-center text-white"><CheckIc /></div>}
          </button>
        ))}
        <button onClick={() => setSel('직접 입력')} className={`w-full rounded-2xl p-4 flex items-center gap-3 border-2 transition-all ${sel === '직접 입력' ? 'bg-[#EEF2FF] border-[#4169D8]' : 'bg-gray-50 border-transparent'}`}>
          <span className="text-2xl">✏️</span>
          <span className={`font-bold text-gray-900 ${sm ? 'text-lg' : 'text-base'}`}>직접 입력</span>
        </button>
        {sel === '직접 입력' && (
          <div className="bg-white rounded-2xl border border-gray-200 px-4 flex items-center h-14">
            <span className="text-gray-400 mr-2">₩</span>
            <input value={custom} onChange={e => setCustom(e.target.value)} placeholder="금액 입력" className="flex-1 outline-none text-base text-gray-900" />
          </div>
        )}
      </div>
      <div className="px-5 pb-6">
        <PrimaryBtn label="다음" disabled={!sel}
          onClick={() => { setState(s => ({ ...s, draft: { ...s.draft, budget: sel === '직접 입력' ? custom : sel } })); nav('trip-companions') }} sm={sm} />
      </div>
    </div>
  )
}

// ─── Trip: Companions ─────────────────────────────────────────────────────────
// [기능] 동행자의 취향·보행 조건을 입력해 일정 추천 기준에 반영한다.
function TripCompanionsScreen({ state, nav, setState }: { state: AppState; nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>> }) {
  const [companions, setCompanions] = useState<Companion[]>(state.draft.companions || [{ name: '아빠', age: '60대', prefs: ['자연'], walking: '30분 정도', avoid: ['등산'] }])
  const [editIdx, setEditIdx] = useState<number | null>(null); const sm = state.seniorMode
  const ages = ['20대', '30대', '40대', '50대', '60대 이상']
  const walkings = ['10분 이내', '30분 정도', '1시간 정도', '걷기 괜찮음']
  const avoids = ['장시간 걷기', '계단', '등산', '사람 많은 곳', '야외 활동']
  const extras = ['택시 적극 이용', '실내 선호', '화장실 가까운 곳', '한적한 장소']
  // [기능] 입력한 동행자 정보를 목록에 추가하고 다음 동행자 입력을 위한 상태를 초기화한다.
  function addComp() {
    const nc = [...companions, { name: `동행자 ${companions.length + 1}`, age: '30대', prefs: [], walking: '30분 정도', avoid: [] }]
    setCompanions(nc); setEditIdx(nc.length - 1)
  }
  return (
    <div className="h-full bg-white flex flex-col">
      <PageHeader title="동행자 조건" back={() => nav('trip-budget')} />
      <div className="px-5 py-3 flex-shrink-0">
        <p className="text-sm font-semibold text-[#4169D8] mb-0.5">여행 만들기 6/6</p>
        <p className={`font-bold text-gray-900 ${sm ? 'text-xl' : 'text-lg'}`}>동행자 정보를 알려주세요</p>
        <p className="text-sm text-gray-400">AI 일정에 반영돼요 (선택 사항)</p>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-hide px-5 pb-24 space-y-3">
        {companions.map((c, i) => (
          <div key={i} className="bg-gray-50 rounded-2xl overflow-hidden">
            <button onClick={() => setEditIdx(editIdx === i ? null : i)} className="w-full flex items-center justify-between p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-[#EEF2FF] flex items-center justify-center font-bold text-[#4169D8]">{c.name[0]}</div>
                <div className="text-left">
                  <p className="font-semibold text-gray-900 text-sm">{c.name}</p>
                  <p className="text-xs text-gray-400">{c.age} · 걷기 {c.walking}</p>
                </div>
              </div>
              <DownIc />
            </button>
            {editIdx === i && (
              <div className="px-4 pb-4 border-t border-gray-200 pt-3 space-y-4">
                <div>
                  <p className="text-xs font-bold text-gray-500 mb-1.5">이름</p>
                  <input value={c.name} onChange={e => { const nc = [...companions]; nc[i] = { ...c, name: e.target.value }; setCompanions(nc) }}
                    className="w-full h-10 px-3 rounded-xl border border-gray-200 text-sm outline-none focus:border-[#4169D8]" />
                </div>
                <div>
                  <p className="text-xs font-bold text-gray-500 mb-1.5">연령대</p>
                  <div className="flex flex-wrap gap-2">
                    {ages.map(a => (
                      <button key={a} onClick={() => { const nc = [...companions]; nc[i] = { ...c, age: a }; setCompanions(nc) }}
                        className={`px-3 py-1.5 rounded-xl text-xs font-medium border-2 transition-all ${c.age === a ? 'bg-[#4169D8] border-[#4169D8] text-white' : 'bg-white border-gray-200 text-gray-600'}`}>{a}</button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-bold text-gray-500 mb-1.5">걷기 정도</p>
                  {walkings.map(w => (
                    <button key={w} onClick={() => { const nc = [...companions]; nc[i] = { ...c, walking: w }; setCompanions(nc) }}
                      className={`w-full mb-1 text-left px-3 py-2 rounded-xl text-sm border-2 transition-all ${c.walking === w ? 'bg-[#EEF2FF] border-[#4169D8] text-[#4169D8]' : 'bg-white border-transparent text-gray-700'}`}>{w}</button>
                  ))}
                </div>
                <div>
                  <p className="text-xs font-bold text-gray-500 mb-1.5">피하고 싶은 활동</p>
                  <div className="flex flex-wrap gap-2">
                    {[...avoids, ...extras].map(a => (
                      <button key={a} onClick={() => { const nc = [...companions]; nc[i] = { ...c, avoid: c.avoid.includes(a) ? c.avoid.filter(x => x !== a) : [...c.avoid, a] }; setCompanions(nc) }}
                        className={`px-2.5 py-1.5 rounded-xl text-xs font-medium border-2 transition-all ${c.avoid.includes(a) ? 'bg-red-50 border-red-300 text-red-600' : 'bg-white border-gray-200 text-gray-600'}`}>{a}</button>
                    ))}
                  </div>
                </div>
                <fieldset>
                  <legend className="text-sm font-bold text-gray-600 mb-2">편집 권한</legend>
                  <div className="flex gap-2">
                    {([{ value: 'edit', label: '편집 가능' }, { value: 'view', label: '보기만' }] as const).map(opt => (
                      <label key={opt.value} className="flex-1 cursor-pointer">
                        <input type="radio" name={`companion-permission-${i}`} value={opt.value}
                          checked={(c.permission ?? 'view') === opt.value}
                          onChange={() => {
                            const next = companions.map((companion, index) => index === i ? { ...companion, permission: opt.value } : companion)
                            setCompanions(next)
                            setState(previous => ({ ...previous, draft: { ...previous.draft, companions: next } }))
                          }}
                          className="peer sr-only" />
                        <span className="flex min-h-12 items-center justify-center gap-2 rounded-xl border-2 border-gray-200 bg-white px-3 py-2 text-sm font-semibold text-gray-600 peer-checked:border-[#4169D8] peer-checked:bg-[#EEF2FF] peer-checked:text-[#2F4FBF] peer-focus-visible:outline-4 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[#4169D8]">
                          {(c.permission ?? 'view') === opt.value && <span aria-hidden="true">✓</span>}
                          {opt.label}
                        </span>
                      </label>
                    ))}
                  </div>
                </fieldset>
              </div>
            )}
          </div>
        ))}
        <button onClick={addComp} className="w-full h-14 rounded-2xl border-2 border-dashed border-[#4169D8]/40 text-[#4169D8] font-medium flex items-center justify-center gap-2 text-sm">
          <PlusIc /> 동행자 추가
        </button>
      </div>
      <div className="flex-shrink-0 px-5 pb-6 pt-3 bg-white border-t border-gray-100">
        <PrimaryBtn label="다음" onClick={() => { setState(s => ({ ...s, draft: { ...s.draft, companions } })); nav('trip-confirm') }} sm={sm} />
      </div>
    </div>
  )
}

// ─── Trip Confirm ─────────────────────────────────────────────────────────────
// [기능] 여행 생성 입력값을 최종 확인하고 AppState의 현재 여행 데이터로 저장한다.
function TripConfirmScreen({ state, nav, setState }: { state: AppState; nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>> }) {
  const d = state.draft; const sm = state.seniorMode
  const places = d.selectedPlaces || state.savedPlaces.slice(0, 2)
  const days = d.startDate && d.endDate ? dayCount(d.startDate, d.endDate) : 3
  const items = [
    { e: '📍', l: '목적지', v: places.map(p => p.name).join(', ') },
    { e: '📅', l: '날짜', v: d.startDate && d.endDate ? `${fmtDate(d.startDate)} ~ ${fmtDate(d.endDate)} · ${days}일` : '미선택' },
    { e: '👥', l: '인원', v: `${d.travelers || 2}명` },
    { e: '🚗', l: '이동수단', v: (d.transport || []).join(' + ') || '미선택' },
    { e: '💰', l: '예산', v: d.budget || '미선택' },
    { e: '🌿', l: '여행 스타일', v: state.travelStyle },
  ]
  return (
    <div className="h-full bg-white flex flex-col">
      <PageHeader title="일정 확인" back={() => nav('trip-companions')} />
      <div className="flex-1 overflow-y-auto scrollbar-hide px-5 py-4">
        <h2 className={`font-bold text-gray-900 mb-1 ${sm ? 'text-xl' : 'text-lg'}`}>이 조건으로 여행을 만들어드릴게요</h2>
        <p className="text-sm text-gray-400 mb-4">조건을 확인해주세요</p>
        <div className="bg-gray-50 rounded-2xl p-4 mb-4 space-y-3">
          {items.map((item, i) => (
            <div key={i} className="flex items-start gap-3">
              <span className="text-xl">{item.e}</span>
              <div><p className="text-xs text-gray-400">{item.l}</p><p className={`font-semibold text-gray-900 ${sm ? 'text-base' : 'text-sm'}`}>{item.v}</p></div>
            </div>
          ))}
        </div>
        <div className="bg-[#F0F4FF] rounded-2xl p-4 text-sm">
          <p className="font-semibold text-[#4169D8] mb-1">AI가 만들어드릴 일정</p>
          <p className="text-xs text-blue-600">• DAY 1~{days}의 일정을 자동 생성해요</p>
          <p className="text-xs text-blue-600">• 동행자 조건을 반영한 편안한 일정이에요</p>
          <p className="text-xs text-blue-600">• 저장한 여행지를 중심으로 구성돼요</p>
        </div>
      </div>
      <div className="px-5 pb-6">
        <button onClick={() => {
          const sd = d.startDate || '2026-09-24', ed = d.endDate || '2026-09-26'
          const newTrip: Trip = { id: 'new', title: `${places[0]?.region?.split(' ')[0] || '강릉'} 여행`, startDate: sd, endDate: ed, travelers: d.travelers || 2, transport: d.transport || ['자동차'], budget: d.budget || '보통', companions: d.companions || [], hotel: '', status: 'upcoming', selectedPlaces: places, days: buildDays(sd, ed, places, d.transport || ['자동차']) }
          setState(s => ({ ...s, currentTrip: newTrip, draft: {} })); nav('ai-loading')
        }} className={`w-full rounded-2xl text-white font-bold active:scale-95 ${sm ? 'h-16 text-lg' : 'h-14'}`}
          style={{ background: 'linear-gradient(135deg,#4169D8,#6B52D3)' }}>
          🤖 AI 일정 만들기
        </button>
      </div>
    </div>
  )
}

// ─── AI Loading ───────────────────────────────────────────────────────────────
const AI_LOADING_MESSAGES = ['저장한 여행지를 분석하고 있어요...', '이동 거리와 휴식 시간을 계산해요...', '동행자 조건을 반영하고 있어요...', '최적의 일정을 생성하고 있어요...']

// [기능] AI 일정 생성과 일정 재생성에서 동일하게 사용하는 로딩 연출(로봇·회전 링·단계 표시)이다.
function AILoadingVisual({ step, messages = AI_LOADING_MESSAGES }: { step: number; messages?: string[] }) {
  const safeStep = Math.min(step, messages.length - 1)
  return (
    <div className="h-full flex flex-col items-center justify-center" style={{ background: 'linear-gradient(160deg,#F0F4FF,#F7F0FF)' }}>
      <div className="relative w-28 h-28 mb-8"><div className="w-28 h-28 rounded-full border-4 border-[#4169D8]/20 border-t-[#4169D8] animate-spin" /><div className="absolute inset-0 flex items-center justify-center text-4xl">🤖</div></div>
      <p className="text-lg font-bold text-gray-900 text-center px-6 mb-3">{messages[safeStep]}</p>
      <div className="flex gap-1">{messages.map((_, i) => <div key={i} className={`h-1.5 rounded-full transition-all ${i <= safeStep ? 'bg-[#4169D8] w-6' : 'bg-gray-200 w-3'}`} />)}</div>
    </div>
  )
}

// [기능] 여행 조건을 바탕으로 일정 생성 중임을 보여준 뒤 전체 일정 화면으로 이동한다.
function AILoadingScreen({ nav }: { nav: (s: Screen) => void }) {
  const [step, setStep] = useState(0)
  useEffect(() => {
    const timer = window.setInterval(() => setStep(current => {
      if (current >= AI_LOADING_MESSAGES.length - 1) { window.clearInterval(timer); window.setTimeout(() => nav('itinerary'), 600); return current }
      return current + 1
    }), 1200)
    return () => window.clearInterval(timer)
  }, [nav])
  return <AILoadingVisual step={step} />
}
// [기능] 일반 OpenStreetMap 또는 위성 타일을 선택해 Leaflet 지도에 공급한다.
function ExploreMapTiles({ style }: { style: 'standard' | 'satellite' }) {
  return style === 'standard'
    ? <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
    : <TileLayer attribution='Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community' url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" />
}

// City-level overview centers; these are not recorded visit coordinates.
const TRIP_MAP_REGIONS: { name: string; center: [number, number]; zoom: number }[] = [
  { name: '강릉', center: [37.7519, 128.8761], zoom: 12 },
  { name: '부산', center: [35.1796, 129.0756], zoom: 11 },
  { name: '제주', center: [33.38, 126.55], zoom: 10 },
  { name: '경주', center: [35.8562, 129.2247], zoom: 12 },
  { name: '전주', center: [35.8242, 127.1480], zoom: 12 },
  { name: '춘천', center: [37.8813, 127.7298], zoom: 12 },
]

// [기능] 지난 여행의 지역 범위를 지도에 표시하며 일반/위성 지도 전환을 제공한다.
function PastTripMap({ trip, back }: { trip: Trip; back: () => void }) {
  const [style, setStyle] = useState<'standard' | 'satellite'>('standard')
  const regionText = trip.selectedPlaces.map(place => place.region).join(' ') || trip.title
  const regions = TRIP_MAP_REGIONS.filter(region => regionText.includes(region.name))
  const region = regions[0]
  return (
    <section className="flex-shrink-0 bg-white" aria-label="지난 여행 지도">
      <div className="flex items-center gap-3 px-4 pt-3 pb-2">
        <button type="button" onClick={back} aria-label="지난 여행 목록으로" className="flex size-[39.6px] shrink-0 items-center justify-center rounded-xl [&>svg]:scale-[0.48] focus-visible:outline-4 focus-visible:outline-[#4169D8]"><LeftIc /></button>
        <div className="min-w-0"><h1 className="text-base font-bold text-gray-900">{trip.title}</h1><p className="text-sm text-gray-500">{fmtShort(trip.startDate)} ~ {fmtShort(trip.endDate)}</p></div>
      </div>
      <div className="flex items-center justify-between gap-2 px-4 pb-2">
        <p className="text-sm font-semibold text-gray-600">여행 지역 지도</p>
        <div className="flex gap-1 rounded-xl bg-gray-100 p-1" role="group" aria-label="지도 유형">
          {([{ value: 'standard', label: '일반 지도' }, { value: 'satellite', label: '위성 지도' }] as const).map(option => <button type="button" key={option.value} aria-pressed={style === option.value} onClick={() => setStyle(option.value)} className={`min-h-11 rounded-lg px-3 text-sm font-bold focus-visible:outline-4 focus-visible:outline-[#4169D8] ${style === option.value ? 'bg-white text-[#4169D8] shadow-sm' : 'text-gray-600'}`}>{option.label}</button>)}
        </div>
      </div>
      <div className="relative isolate h-[187.2px]">
        <MapContainer key={trip.id} center={region?.center ?? [36.3, 127.8]} zoom={region?.zoom ?? 7} bounds={regions.length > 1 ? regions.map(item => item.center) : undefined} boundsOptions={{ padding: [24, 24] }} scrollWheelZoom={false} className="h-full w-full" aria-label={`${trip.title} 여행 지역 지도`}>
          <ExploreMapTiles style={style} />
        </MapContainer>
      </div>
    </section>
  )
}
// [기능] 현재 여행의 일차별 장소 번호와 이동 경로를 실제 지도 위에 표시한다.
function CurrentTripMap({ trip, day, back }: { trip: Trip; day: Trip['days'][number]; back: () => void }) {
  const [style, setStyle] = useState<'standard' | 'satellite'>('standard')
  const regionText = trip.selectedPlaces.map(place => place.region).join(' ') || trip.title
  const region = TRIP_MAP_REGIONS.find(item => regionText.includes(item.name)) ?? TRIP_MAP_REGIONS[0]
  const offsets: [number, number][] = [[-0.006, -0.009], [-0.001, -0.004], [0.003, -0.001], [0.005, 0.004], [0.001, 0.008]]
  const points = day.places.map((item, index) => {
    const offset = offsets[index % offsets.length]
    return { item, index, position: [region.center[0] + offset[0], region.center[1] + offset[1]] as [number, number] }
  })
  return (
    <section className="flex-shrink-0 bg-white" aria-label="전체 일정 지도">
      <div className="flex items-center gap-3 px-4 pt-3 pb-2">
        <button type="button" onClick={back} aria-label="홈으로" className="flex size-[39.6px] shrink-0 items-center justify-center rounded-xl [&>svg]:scale-[0.48] focus-visible:outline-4 focus-visible:outline-[#4169D8]"><LeftIc /></button>
        <div className="min-w-0 flex-1"><h1 className="truncate text-base font-bold text-gray-900">{trip.title}</h1><p className="text-sm text-gray-500">DAY {day.dayNumber} · {fmtShort(day.date)}</p></div>
        <div className="flex gap-1 rounded-xl bg-gray-100 p-1" role="group" aria-label="지도 유형">
          {([{ value: 'standard', label: '일반' }, { value: 'satellite', label: '위성' }] as const).map(option => <button type="button" key={option.value} aria-pressed={style === option.value} onClick={() => setStyle(option.value)} className={`min-h-9 rounded-lg px-2.5 text-xs font-bold ${style === option.value ? 'bg-white text-[#4169D8] shadow-sm' : 'text-gray-600'}`}>{option.label}</button>)}
        </div>
      </div>
      <div className="relative isolate h-52" aria-label="일정 장소와 이동 경로 지도">
        <MapContainer key={`${trip.id}-${day.dayNumber}-${style}`} center={region.center} zoom={region.zoom} scrollWheelZoom={false} className="h-full w-full" aria-label={`${trip.title} 일정 지도`}>
          <ExploreMapTiles style={style} />
          {points.length > 1 && <Polyline positions={points.map(point => point.position)} pathOptions={{ color: '#4169D8', weight: 4, opacity: 0.8 }} />}
          {points.map(point => <CircleMarker key={`${point.item.time}-${point.item.place}`} center={point.position} radius={11} pathOptions={{ color: '#ffffff', weight: 3, fillColor: point.index === 0 ? '#16A34A' : '#4169D8', fillOpacity: 1 }}><Tooltip permanent direction="center" className="!border-0 !bg-transparent !p-0 !font-bold !text-white !shadow-none">{point.index + 1}</Tooltip><Popup><strong>{point.index + 1}. {point.item.place}</strong><br />{point.item.time} 일정</Popup></CircleMarker>)}
        </MapContainer>
        <p className="pointer-events-none absolute left-3 top-3 z-[1000] rounded-xl bg-white/95 px-3 py-2 text-xs font-bold text-[#4169D8] shadow-md">번호는 아래 일정 순서와 같아요.</p>
      </div>
    </section>
  )
}
// ─── Itinerary ────────────────────────────────────────────────────────────────
// [기능] 전체 일정 조회·편집·불편 사유 기반의 더 여유로운 일정 재생성을 담당한다.
// pastTrip이 전달되면 전역 현재 여행을 변경하지 않고, 지난 여행을 읽기 전용으로 표시한다.
function ItineraryDaySelector({ days, selected, onSelect, senior }: { days: DayPlan[]; selected: number; onSelect: (index: number) => void; senior: boolean }) {
  const scroller = useRef<HTMLDivElement>(null)
  const activeButton = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const container = scroller.current
    const button = activeButton.current
    if (!container || !button) return
    const viewport = container.getBoundingClientRect()
    const bounds = button.getBoundingClientRect()
    if (bounds.left < viewport.left) container.scrollLeft += bounds.left - viewport.left
    else if (bounds.right > viewport.right) container.scrollLeft += bounds.right - viewport.right
  }, [selected, days.length])
  return (
    <nav aria-label="여행 날짜 선택" className="flex w-full min-w-0 max-w-full shrink-0 items-center border-b border-gray-100 bg-white">
      <button type="button" aria-label="이전 DAY 보기" disabled={selected === 0} onClick={() => onSelect(selected - 1)} className="flex h-12 w-10 shrink-0 items-center justify-center text-[#4169D8] disabled:text-gray-300 focus-visible:outline-2 focus-visible:outline-[#4169D8]"><LeftIc /></button>
      <div ref={scroller} className="flex min-w-0 flex-1 overflow-x-auto overscroll-x-contain scrollbar-hide">
        {days.map((day, index) => (
          <button type="button" key={day.date} ref={index === selected ? activeButton : undefined}
            onClick={() => onSelect(index)} aria-current={index === selected ? 'date' : undefined}
            aria-label={`DAY ${day.dayNumber}, ${fmtDate(day.date)} 일정`}
            className={`min-w-[76px] shrink-0 grow basis-[76px] border-b-2 px-2 py-3 text-center focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[#4169D8] ${index === selected ? 'border-[#4169D8] text-[#4169D8]' : 'border-transparent text-gray-500'}`}>
            <span className={`block whitespace-nowrap font-semibold ${senior ? 'text-base' : 'text-sm'}`}>DAY {day.dayNumber}</span>
            <span className="block text-xs text-gray-500">{fmtShort(day.date)}</span>
          </button>
        ))}
      </div>
      <button type="button" aria-label="다음 DAY 보기" disabled={selected >= days.length - 1} onClick={() => onSelect(selected + 1)} className="flex h-12 w-10 shrink-0 items-center justify-center text-[#4169D8] disabled:text-gray-300 focus-visible:outline-2 focus-visible:outline-[#4169D8]"><RightIc /></button>
    </nav>
  )
}
function ItineraryScreen({ state, nav, setState, pastTrip }: { state: AppState; nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>>; pastTrip?: Trip }) {
  const currentTrip = pastTrip ?? state.currentTrip
  const sm = state.seniorMode
  const [dayIdx, setDayIdx] = useState(0); const [showAlt, setShowAlt] = useState(false)
  const [editMenu, setEditMenu] = useState<number | null>(null); const [showHard, setShowHard] = useState(false)
  const [hardSel, setHardSel] = useState<ComfortReason[]>([])
  useEffect(() => {
    if (!showHard) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setShowHard(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [showHard])
  const [isRebuilding, setIsRebuilding] = useState(false)
  const [rebuildStep, setRebuildStep] = useState(0)
  const readOnly = Boolean(pastTrip)
  const [detail, setDetail] = useState<ScheduleItem | null>(null)
  const detailHeading = useRef<HTMLHeadingElement>(null)
  const detailTrigger = useRef<HTMLButtonElement | null>(null)
  useEffect(() => {
    if (detail) detailHeading.current?.focus()
    else detailTrigger.current?.focus()
  }, [detail])
  useEffect(() => {
    if (!isRebuilding) { setRebuildStep(0); return }
    const timer = window.setInterval(() => setRebuildStep(step => Math.min(step + 1, AI_LOADING_MESSAGES.length - 1)), 250)
    return () => window.clearInterval(timer)
  }, [isRebuilding])
  const days = currentTrip.days
  const hardOpts = COMFORT_OPTIONS
// 다른 추천 일정 선택 시 관광 장소를 해당 테마의 대체 코스로 실제 교체한다.
  const applyAlternativeSchedule = (theme: 'nature' | 'food') => {
    const options = theme === 'nature'
      ? { label: '자연 중심 코스', icon: '🌿', tags: ['대체 코스', '자연', '산책', '휴식'], places: ['경포호 산책', '강릉솔향수목원', '안목해변 산책로', '경포대 숲길', '오죽헌 정원'] }
      : { label: '맛집 집중 코스', icon: '🍲', tags: ['대체 코스', '맛집', '식사', '휴식'], places: ['초당두부마을', '강릉 중앙시장', '강릉 커피거리', '주문진 수산시장', '명주동 카페거리'] }
    const knownAlternativeNames = ['경포호 산책', '강릉솔향수목원', '안목해변 산책로', '경포대 숲길', '오죽헌 정원', '초당두부마을', '강릉 중앙시장', '강릉 커피거리', '주문진 수산시장', '명주동 카페거리']
    const updatedDays = currentTrip.days.map((day, dayIndex) => {
      let placeCursor = dayIndex * 2
      const places = day.places.map(item => {
        const alreadyAlternative = item.tags.includes('대체 코스') || knownAlternativeNames.includes(item.place)
        const ordinaryVisit = !item.tags.includes('출발') && !item.tags.includes('귀가') && !item.tags.includes('숙소') && !item.tags.includes('식사') && !item.rest
        if (!alreadyAlternative && !ordinaryVisit) return item
        const place = options.places[placeCursor % options.places.length]
        placeCursor += 1
        return { ...item, place, icon: options.icon, tags: options.tags, walk: '도보 8분', rest: theme === 'nature' }
      })
      // 하루에 교체할 방문 장소가 없으면 추천 장소 두 곳을 추가해 코스 변경이 즉시 보이게 한다.
      const changed = places.some(item => item.tags.includes('대체 코스'))
      const nextPlaces = changed ? places : [...places, ...options.places.slice(0, 2).map((place, index) => ({ time: index === 0 ? '13:30' : '15:00', place, icon: options.icon, tags: options.tags, walk: '도보 8분', cost: '무료', rest: theme === 'nature' }))].sort((a, b) => a.time.localeCompare(b.time))
      return { ...day, places: nextPlaces, notice: `${options.label} 전체 코스를 적용했어요. 지도와 일정 목록에서 변경된 장소를 확인하세요.` }
    })
    setState(current => ({ ...current, currentTrip: { ...current.currentTrip, title: `${current.currentTrip.title.replace(/ · (자연 중심 코스|맛집 집중 코스)$/, '')} · ${options.label}`, days: updatedDays } }))
    setDayIdx(0); setShowAlt(false); setShowHard(false); setHardSel([]); setEditMenu(null)
  }
  const rebuildComfortableSchedule = () => {
    if (isRebuilding || hardSel.length === 0 || readOnly) return
    setIsRebuilding(true)
    const rebuiltTrip = rebuildComfortPlan(currentTrip, hardSel)
    // 실제 AI/API 연결 전에도 재생성 과정을 인지할 수 있도록 짧은 로딩 후 새 일정을 적용한다.
    window.setTimeout(() => {
      setState(current => ({ ...current, currentTrip: { ...current.currentTrip, originalDays: rebuiltTrip.originalDays, days: rebuiltTrip.days }, activeSchedule: null }))
      setDayIdx(0)
      setShowAlt(false)
      setShowHard(false)
      setHardSel([])
      setIsRebuilding(false)
    }, 900)
  }
  if (readOnly && detail) {
    const place = [...currentTrip.selectedPlaces, ...YOUTUBE_SAVED].find(candidate => candidate.name === detail.place)
    return (
      <div className="flex h-full min-h-0 flex-col bg-gray-50">
        <PageHeader title="지난 여행 상세정보" back={() => setDetail(null)} />
        <div className="flex-1 overflow-y-auto px-5 py-5">
          {place && <div className="relative mb-5 h-48 overflow-hidden rounded-2xl">
            <img src={placeImageUrl(place.img, 600, 400)} alt={place.name} className="h-full w-full object-cover" />
            {place.img === jeonjuHanokImage && <a href="https://commons.wikimedia.org/wiki/File:Jeonju_Hanok_Village_20220701_001.jpg" target="_blank" rel="noreferrer" className="absolute bottom-2 left-2 rounded bg-black/75 px-2 py-1 text-xs text-white underline">사진: Mobius6 · CC BY-SA 4.0</a>}
          </div>}
          <p className="mb-2 text-sm font-semibold text-[#4169D8]">{currentTrip.title} · DAY {days[dayIdx].dayNumber}</p>
          <h1 ref={detailHeading} tabIndex={-1} className="text-2xl font-bold text-gray-900 outline-none"><span aria-hidden="true">{detail.icon} </span>{detail.place}</h1>
          <p className="mt-2 text-sm leading-6 text-gray-600">지난 여행에 기록된 정보입니다. 수정할 수 없어요.</p>
          <dl className="mt-5 space-y-4 rounded-2xl bg-white p-5">
            {[
              ['방문 날짜', fmtDate(days[dayIdx].date)],
              ['일정 시간', detail.time],
              ...(place ? [['지역', place.region]] : []),
              ['이동 정보', detail.transport || detail.walk || '기록된 이동 정보가 없어요.'],
              ...(detail.rest ? [['휴식', '휴식이 포함된 일정이에요.']] : []),
            ].map(([label, value]) => <div key={label}><dt className="text-sm text-gray-500">{label}</dt><dd className="mt-1 text-base font-semibold text-gray-900">{value}</dd></div>)}
          </dl>
          {detail.tags.length > 0 && <section className="mt-5"><h2 className="mb-2 text-base font-bold text-gray-900">일정 특징</h2><div className="flex flex-wrap gap-2">{detail.tags.map(tag => <Tag key={tag} label={tag} blue />)}</div></section>}
        </div>
        <div className="flex-shrink-0 border-t border-gray-100 bg-white p-5"><PrimaryBtn label="전체 일정으로 돌아가기" onClick={() => setDetail(null)} sm={sm} /></div>
      </div>
    )
  }
  return (
    <div className="relative isolate flex h-full w-full min-h-0 min-w-0 max-w-full flex-col overflow-hidden bg-gray-50" onClick={event => { const target = event.target as HTMLElement; if (showHard && !target.closest('[data-hard-panel]')) setShowHard(false); if (showAlt && !target.closest('[data-alt-panel]')) setShowAlt(false) }}>
      {readOnly ? <PastTripMap trip={currentTrip} back={() => nav('past-trips')} /> : <CurrentTripMap trip={currentTrip} day={days[dayIdx]} back={() => nav('home')} />}
      <ItineraryDaySelector days={days} selected={dayIdx} onSelect={index => { setDayIdx(index); setShowHard(false); setShowAlt(false); setEditMenu(null) }} senior={sm} />
      {/* Schedule */}
      <div className="flex-1 overflow-y-auto scrollbar-hide px-5 py-4 pb-36 space-y-1">
        {days[dayIdx]?.notice && <p role="status" className="mb-4 rounded-2xl bg-amber-50 p-4 text-base leading-7 text-amber-900">{days[dayIdx].notice}</p>}
        {(days[dayIdx]?.places || []).map((item, i, arr) => (
          <div key={i} className="relative">
            {i < arr.length - 1 && <div className="absolute left-7 top-14 bottom-0 w-0.5 bg-gray-200 z-0" />}
            <div className="relative z-10 flex gap-3 mb-3">
              <div className="flex-shrink-0 w-14 h-14 rounded-full bg-white flex items-center justify-center text-2xl" style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>{item.icon}</div>
              <div className="flex-1 bg-white rounded-2xl p-3" style={{ boxShadow: '0 1px 6px rgba(0,0,0,0.06)' }}>
                <div className="flex items-start justify-between">
                  <div><p className="text-xs text-[#4169D8] font-semibold">{item.time}</p><p className={`font-bold text-gray-900 ${sm ? 'text-base' : 'text-sm'}`}>{item.place}</p></div>
                                    <button type="button" aria-label={readOnly ? `${item.place} 상세정보 보기` : `${item.place} 일정 편집`}
                    onClick={event => {
                      if (readOnly) { detailTrigger.current = event.currentTarget; setDetail(item) }
                      else { setShowHard(false); setEditMenu(editMenu === i ? null : i) }
                    }}
                    className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl text-sm font-semibold text-[#4169D8] focus-visible:outline-4 focus-visible:outline-[#4169D8]">{readOnly ? '상세' : '수정'}</button>
                </div>
                {!readOnly && editMenu === i && (
                  <div className="mt-2 bg-gray-50 rounded-xl overflow-hidden">
                    {['장소 바꾸기', '순서 변경', '삭제'].map(opt => (
                      <button key={opt} onClick={() => setEditMenu(null)}
                        className={`w-full text-left px-3 py-2.5 text-sm border-b border-gray-100 last:border-0 ${opt === '삭제' ? 'text-red-500' : 'text-gray-700'}`}>{opt}</button>
                    ))}
                  </div>
                )}
                <div className="flex flex-wrap gap-1 mt-2">{item.tags.map(t => <Tag key={t} label={t} blue />)}</div>
                <div className="flex flex-wrap gap-3 mt-1.5 text-xs text-gray-400">
                  {item.walk && <span>🚶 {item.walk}</span>}
                  {item.cost && <span>💰 {item.cost}</span>}
                  {item.rest && <span>☕ 휴식 가능</span>}
                  {item.transport && <span>🚆 {item.transport}</span>}
                </div>
              </div>
            </div>
          </div>
        ))}
        {!readOnly && (!showAlt ? (
          <button onClick={() => { setShowAlt(true); setShowHard(false); setEditMenu(null) }} className="w-full py-3.5 text-sm text-[#4169D8] font-semibold border-2 border-dashed border-[#4169D8]/30 rounded-2xl">다른 일정 보기</button>
        ) : (
          <div data-alt-panel className="bg-[#EEF2FF] rounded-2xl p-4">
            <div className="mb-3 flex items-center justify-between"><p className="font-semibold text-[#4169D8] text-sm">다른 추천 일정</p><button onClick={() => setShowAlt(false)} className="text-xs font-semibold text-gray-500">닫기</button></div>
            <div className="space-y-2">
              <button onClick={() => applyAlternativeSchedule('nature')} className="w-full rounded-xl bg-white p-3 text-left shadow-sm active:scale-[0.98]"><p className="font-bold text-gray-900">🌿 다른 일정 1 · 자연 중심 코스</p><p className="mt-1 text-xs text-gray-500">산책과 휴식 시간을 넉넉하게 반영해요.</p><span className="mt-2 inline-block text-xs font-bold text-[#4169D8]">이 일정 선택하기 →</span></button>
              <button onClick={() => applyAlternativeSchedule('food')} className="w-full rounded-xl bg-white p-3 text-left shadow-sm active:scale-[0.98]"><p className="font-bold text-gray-900">🍲 다른 일정 2 · 맛집 집중 코스</p><p className="mt-1 text-xs text-gray-500">식사와 카페 방문 중심으로 구성해요.</p><span className="mt-2 inline-block text-xs font-bold text-[#4169D8]">이 일정 선택하기 →</span></button>
            </div>
          </div>
        ))}
      </div>
      {showHard && !isRebuilding && <button type="button" aria-label="일정 불편 사유 선택 닫기" onClick={() => setShowHard(false)} className="absolute inset-0 z-[900] cursor-default bg-transparent" />}
      {/* Bottom */}
      <div className={`flex-shrink-0 bg-white border-t border-gray-100 px-5 py-3 space-y-2 ${showHard ? 'relative z-[901]' : ''}`}>
        {readOnly ? (
          <><p className="text-center text-sm text-gray-600">지난 여행은 상세정보만 확인할 수 있어요.</p><PrimaryBtn label="지난 여행 목록으로" onClick={() => nav('past-trips')} sm={sm} /></>
        ) : showHard ? (
          <div data-hard-panel className="bg-orange-50 rounded-2xl p-4">
            <p className="font-semibold text-gray-900 text-sm mb-2">어떤 점이 힘드세요?</p><p className="mb-3 text-sm leading-6 text-gray-600">선택한 이유에 맞춰 일정을 새로 바꿔요</p>
            <div className="flex flex-wrap gap-2 mb-3">
              {hardOpts.map(h => (
                <button key={h.id} aria-pressed={hardSel.includes(h.id)} onClick={() => setHardSel(s => s.includes(h.id) ? s.filter(x => x !== h.id) : [...s, h.id])}
                  className={`text-xs px-3 py-1.5 rounded-full border-2 transition-all ${hardSel.includes(h.id) ? 'bg-orange-100 border-orange-400 text-orange-700' : 'bg-white border-gray-200 text-gray-600'}`}>{h.label}</button>
              ))}
            </div>

            <button onClick={rebuildComfortableSchedule} disabled={isRebuilding || hardSel.length === 0} className="w-full py-3 bg-[#4169D8] text-white rounded-xl text-sm font-bold disabled:opacity-60">{isRebuilding ? '일정을 다시 만들고 있어요…' : '일정 다시 만들기'}</button>
          </div>
        ) : (
          <>
            <button onClick={() => { setShowHard(true); setShowAlt(false); setEditMenu(null) }} className="w-full py-3 border-2 border-orange-200 text-orange-500 rounded-2xl text-sm font-semibold">😥 일정이 힘들어요</button>
            <div className="flex gap-2">
              <button onClick={() => nav('accommodation')} className={`flex-1 rounded-2xl bg-[#4169D8] text-white font-bold text-sm ${sm ? 'h-14' : 'h-12'}`}>숙소 확정하기</button>
              <button onClick={() => nav('today-travel')} className={`flex-1 rounded-2xl bg-[#EEF2FF] text-[#4169D8] font-bold text-sm ${sm ? 'h-14' : 'h-12'}`}>오늘의 여행</button>
            </div>
          </>
        )}
      </div>
      {isRebuilding && <div role="status" aria-live="assertive" className="absolute inset-0 z-[1000]"><AILoadingVisual step={rebuildStep} /></div>}
    </div>
  )
}

// ─── Accommodation ────────────────────────────────────────────────────────────
const HOTELS = [
  { name: '씨마크 호텔', dist: '안목해변 도보 3분', price: '180,000원/박', tags: ['엘리베이터', '주차', '계단 없음'], img: 'photo-1566073771259-6a8506099945', r: 4.8 },
  { name: '강릉 세인트존스', dist: '경포해변 인근', price: '120,000원/박', tags: ['조식 포함', '주차'], img: 'photo-1551882547-ff40c63fe5fa', r: 4.5 },
  { name: '아레나 리조트', dist: '강릉역 택시 10분', price: '90,000원/박', tags: ['가성비', '엘리베이터'], img: 'photo-1564501049412-61c2a3083791', r: 4.3 },
]
// [기능] 동행 조건에 맞춘 숙소 후보를 선택하고 출발 전 확인 화면으로 연결한다.
function AccommodationScreen({ state, nav }: { state: AppState; nav: (s: Screen) => void }) {
  const [sel, setSel] = useState(-1); const sm = state.seniorMode
  return (
    <div className="flex flex-col h-full">
      <PageHeader title="숙소 선택" back={() => nav('itinerary')} />
      <div className="flex-1 overflow-y-auto scrollbar-hide px-5 py-3 pb-24 space-y-3" style={{ background: 'linear-gradient(160deg,#F0F4FF,#F7F8FF)' }}>
        <p className="text-sm text-gray-400">동행자 조건에 맞는 숙소를 추천해드렸어요</p>
        {HOTELS.map((h, i) => (
          <button key={i} onClick={() => setSel(i)}
            className={`w-full bg-white rounded-2xl overflow-hidden text-left border-2 transition-all active:scale-95 ${sel === i ? 'border-[#4169D8]' : 'border-transparent'}`} style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
            <img src={`https://images.unsplash.com/${h.img}?w=600&h=200&fit=crop`} alt={h.name} className="w-full h-36 object-cover" />
            <div className="p-4">
              <div className="flex items-center justify-between mb-1">
                <h3 className={`font-bold text-gray-900 ${sm ? 'text-lg' : 'text-base'}`}>{h.name}</h3>
                <div className="flex items-center gap-1"><StarIc /><span className="text-sm font-semibold">{h.r}</span></div>
              </div>
              <p className="text-sm text-gray-400 mb-2">{h.dist}</p>
              <p className={`font-bold text-[#4169D8] mb-2 ${sm ? 'text-lg' : 'text-base'}`}>{h.price}</p>
              <div className="flex flex-wrap gap-1">{h.tags.map(t => <Tag key={t} label={t} />)}</div>
            </div>
          </button>
        ))}
      </div>
      <div className="px-5 py-4 bg-white border-t border-gray-100">
        <PrimaryBtn label={sel >= 0 ? `${HOTELS[sel].name} 선택 완료` : '숙소를 선택해주세요'} disabled={sel < 0}
          onClick={() => nav('pre-departure')} sm={sm} />
      </div>
    </div>
  )
}

// ─── Pre-Departure ────────────────────────────────────────────────────────────
// [기능] 출발 전 일정, 숙소, 교통, 동행자, 비용을 최종 확인하는 화면이다.
function PreDepartureScreen({ state, nav }: { state: AppState; nav: (s: Screen) => void }) {
  const { currentTrip, seniorMode: sm } = state
  const items = [
    { e: '📍', l: '목적지', v: currentTrip.selectedPlaces.map(p => p.name).join(', ') },
    { e: '📅', l: '날짜', v: `${fmtDate(currentTrip.startDate)} ~ ${fmtDate(currentTrip.endDate)}` },
    { e: '🏨', l: '숙소', v: '씨마크 호텔' },
    { e: '🚆', l: '이동수단', v: currentTrip.transport.join(' + ') },
    { e: '👥', l: '동행자', v: `${currentTrip.travelers}명` },
    { e: '💰', l: '예상 비용', v: currentTrip.budget },
  ]
  return (
    <div className="h-full flex flex-col px-5 pt-14 pb-6" style={{ background: 'linear-gradient(160deg,#F0F4FF,#F7F8FF)' }}>
      <button onClick={() => nav('accommodation')} className="mb-5 flex items-center gap-1 text-gray-600"><LeftIc /><span>뒤로</span></button>
      <div className="text-center mb-5">
        <div className="text-5xl mb-3">🎉</div>
        <h1 className={`font-bold text-gray-900 ${sm ? 'text-2xl' : 'text-xl'}`}>여행을 떠날 준비가 되었어요!</h1>
        <p className="text-sm text-gray-400 mt-1">최종 일정을 확인해주세요</p>
      </div>
      <div className="bg-white rounded-3xl p-5 mb-5 flex-1" style={{ boxShadow: '0 2px 16px rgba(65,105,216,0.1)' }}>
        <div className="space-y-4">{items.map((item, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="text-xl">{item.e}</span>
            <div><p className="text-xs text-gray-400">{item.l}</p><p className={`font-semibold text-gray-900 ${sm ? 'text-base' : 'text-sm'}`}>{item.v}</p></div>
          </div>
        ))}</div>
        <button onClick={() => nav('itinerary')} className="mt-4 w-full pt-4 border-t border-gray-100 text-sm text-[#4169D8] font-semibold flex items-center gap-1">
          최종 일정 확인 <RightIc />
        </button>
      </div>
      <PrimaryBtn label="여행 시작하기 🚀" onClick={() => nav('today-travel')} sm={sm} gradient />
    </div>
  )
}

// ─── Today Travel ─────────────────────────────────────────────────────────────
// [기능] 당일 일정의 번호 마커 지도와 일정 상세 바텀시트를 제공하고 장소별 길찾기로 연결한다.
// [기능] 당일 일정의 지도·장소 상세·길찾기와, 동선에서 벗어나지 않는 휴식 장소 추가를 제공한다.
function TodayTravelScreen({ state, nav, setState }: { state: AppState; nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>> }) {
  const { currentTrip, seniorMode: sm } = state
  // 계획 2에서는 지도와 일정 영역 뒤에만 차분한 흐린 날 배경을 보여준다.
  const isRainyPlan = state.weatherPlan === 'B'
  const day = currentTrip.days[1] || currentTrip.days[0]
  const [selectedSchedule, setSelectedSchedule] = useState<ScheduleItem | null>(null)
  const [restMode, setRestMode] = useState(false)
  const [restTarget, setRestTarget] = useState<ScheduleItem | null>(null)
  const [isSearchingRest, setIsSearchingRest] = useState(false)
  const [restSearchComplete, setRestSearchComplete] = useState(false)
  const schedule = day?.places || []
  const restSpots = [
    { name: '안목 해변 쉼터', icon: '🪑', time: '현재 위치에서 4분', features: ['앉아서 쉴 수 있음', '화장실 있음', '그늘 있음', '카페 있음'] },
    { name: '경포호 작은 공원', icon: '🌳', time: '현재 위치에서 6분', features: ['벤치 있음', '화장실 있음', '그늘 있음', '산책로 있음'] },
  ]
  const itineraryCenter: [number, number] = [37.7519, 128.8761]
  const routeOffsets: [number, number][] = [[-0.006, -0.009], [-0.001, -0.004], [0.003, -0.001], [0.005, 0.004], [0.001, 0.008]]
  const itineraryPoints = schedule.map((item, index) => {
    const [latOffset, lngOffset] = routeOffsets[index % routeOffsets.length]
    return { item, index, position: [itineraryCenter[0] + latOffset, itineraryCenter[1] + lngOffset] as [number, number] }
  })
  const pickRestTarget = (item: ScheduleItem) => { setRestTarget(item); setRestSearchComplete(false); setSelectedSchedule(null) }
  const toggleRestMode = () => { setRestMode(mode => !mode); setRestTarget(null); setRestSearchComplete(false); setIsSearchingRest(false); setSelectedSchedule(null) }
  const shiftTime = (time: string, minutesToAdd: number) => {
    const [hours, minutes] = time.split(':').map(Number)
    if (!Number.isFinite(hours) || !Number.isFinite(minutes)) return time
    const total = hours * 60 + minutes + minutesToAdd
    return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
  }
  const addRestStop = (spot: typeof restSpots[number]) => {
    if (!restTarget || !day) return
    setState(current => {
      const dayIndex = current.currentTrip.days.findIndex(item => item.dayNumber === day.dayNumber)
      if (dayIndex < 0) return current
      const targetIndex = current.currentTrip.days[dayIndex].places.findIndex(item => item.time === restTarget.time && item.place === restTarget.place)
      if (targetIndex < 0) return current
      const restStop: ScheduleItem = { time: restTarget.time, place: spot.name, icon: spot.icon, tags: ['AI 추천', '휴식'], walk: spot.time, cost: '무료', rest: true }
      const updatedDay = {
        ...current.currentTrip.days[dayIndex],
        places: [
          ...current.currentTrip.days[dayIndex].places.slice(0, targetIndex + 1),
          { ...restStop, time: shiftTime(restTarget.time, 30) },
          ...current.currentTrip.days[dayIndex].places.slice(targetIndex + 1).map(item => ({ ...item, time: shiftTime(item.time, 30) })),
        ],
        notice: '선택한 일정 다음에 AI 추천 휴식 장소를 추가하고, 이후 일정을 30분씩 여유롭게 조정했어요.',
      }
      const days = current.currentTrip.days.map((item, index) => index === dayIndex ? updatedDay : item)
      return { ...current, currentTrip: { ...current.currentTrip, days } }
    })
    setRestMode(false)
    setRestTarget(null)
    setRestSearchComplete(false)
  }
  // 선택한 일정 아래에만 표시되는 휴식 장소 탐색·추천·삽입 패널이다.
  const restRecommendationPanel = restMode && restTarget ? (
    <section className="mt-2 rounded-3xl bg-[#EEF2FF] p-4 shadow-sm">
      <p className="text-sm font-black text-[#4169D8]">🤖 AI 휴식 장소 추천</p>
      <p className="mt-2 text-sm leading-6 text-gray-700"><b>{restTarget.place}</b> 다음 동선을 기준으로, 길에서 크게 벗어나지 않는 휴식 장소를 찾아드릴게요.</p>
      {!isSearchingRest && !restSearchComplete && <button onClick={() => { setIsSearchingRest(true); window.setTimeout(() => { setIsSearchingRest(false); setRestSearchComplete(true) }, 900) }} className="mt-4 h-12 w-full rounded-xl bg-[#4169D8] text-sm font-bold text-white">휴식 장소 탐색하기</button>}
      {isSearchingRest && <div role="status" className="mt-4 rounded-2xl bg-white p-5 text-center"><div className="mx-auto h-8 w-8 rounded-full border-4 border-[#4169D8]/20 border-t-[#4169D8] animate-spin" /><p className="mt-3 text-sm font-bold text-gray-700">주변 쉼터와 공원을 찾고 있어요…</p></div>}
      {restSearchComplete && <div className="mt-4 space-y-3">{restSpots.map(spot => <div key={spot.name} className="rounded-2xl bg-white p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-bold text-gray-900">{spot.icon} {spot.name}</p><p className="mt-1 text-sm font-semibold text-[#4169D8]">{spot.time}</p></div><span className="rounded-full bg-green-50 px-2 py-1 text-xs font-bold text-green-700">동선 이탈 적음</span></div><div className="mt-3 flex flex-wrap gap-2">{spot.features.map(feature => <span key={feature} className="rounded-full bg-[#F0F4FF] px-3 py-1.5 text-xs font-semibold text-[#4169D8]">✓ {feature}</span>)}</div><button onClick={() => addRestStop(spot)} className="mt-4 h-11 w-full rounded-xl bg-[#4169D8] text-sm font-bold text-white">이곳에서 휴식하기</button></div>)}</div>}
    </section>
  ) : null
  return (
    <div className={`relative flex h-full flex-col overflow-hidden ${isRainyPlan ? 'weather-rain-gradient' : 'bg-white'}`}>
      <div className={`relative z-[2] flex-shrink-0 border-b px-5 pt-4 pb-3 flex items-center justify-between ${isRainyPlan ? 'border-slate-400/30 bg-transparent' : 'border-gray-100 bg-white'}`}><button onClick={() => nav('home')} aria-label="홈으로 돌아가기"><LeftIc /></button><div className="relative z-[1] text-center"><h1 className={`font-bold text-gray-900 ${sm ? 'text-xl' : 'text-lg'}`}>오늘의 여행</h1><p className={`${isRainyPlan ? 'text-slate-600' : 'text-gray-400'} text-xs`}>DAY {day?.dayNumber} · {day ? fmtDate(day.date) : ''}</p></div><div className="w-8" /></div>
      <div className="relative flex min-h-0 flex-1 flex-col bg-transparent">
        <div className="relative h-48 flex-shrink-0 bg-blue-50" aria-label="오늘 일정 경로 지도">
          <MapContainer center={itineraryCenter} zoom={13} scrollWheelZoom className="h-full w-full" aria-label="오늘 여행 일정 지도"><TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />{itineraryPoints.length > 1 && <Polyline positions={itineraryPoints.map(point => point.position)} pathOptions={{ color: restMode ? '#9CA3AF' : '#4169D8', weight: 4, opacity: 0.8 }} />}{itineraryPoints.map(point => <CircleMarker key={`${point.item.time}-${point.item.place}`} center={point.position} radius={11} pathOptions={{ color: '#ffffff', weight: 3, fillColor: restMode ? '#9CA3AF' : point.index === 0 ? '#16A34A' : '#4169D8', fillOpacity: 1 }} eventHandlers={{ click: () => restMode ? pickRestTarget(point.item) : setSelectedSchedule(point.item) }}><Tooltip permanent direction="center" className="!border-0 !bg-transparent !p-0 !font-bold !text-white !shadow-none">{point.index + 1}</Tooltip><Popup><strong>{point.item.time} · {point.item.place}</strong><br />{restMode ? '휴식 전 장소로 선택할 수 있어요.' : '지도를 눌러 상세 정보를 확인하세요.'}</Popup></CircleMarker>)}</MapContainer>
          <div className="pointer-events-none absolute left-3 top-3 z-[1000] rounded-xl bg-white/95 px-3 py-2 shadow-md"><p className={`text-xs font-bold ${restMode ? 'text-gray-500' : 'text-[#4169D8]'}`}>{restMode ? '휴식할 다음 일정을 골라주세요' : '오늘의 이동 경로'}</p><p className="mt-0.5 text-xs text-gray-600">지도 번호와 아래 일정 번호가 같아요.</p></div>
        </div>
        <div className={`relative z-[2] flex-shrink-0 px-5 py-3 ${isRainyPlan ? 'bg-transparent' : 'bg-[#F0F4FF]/90'}`}><p className="mb-1 text-xs text-gray-500">현재 일정</p><div className="flex items-center justify-between gap-3"><div><p className={`font-bold text-gray-900 ${sm ? 'text-xl' : 'text-lg'}`}>{schedule[0]?.icon} {schedule[0]?.place}</p><p className="text-sm text-gray-500">{schedule[0]?.time}</p></div></div></div>
        <div className="relative z-[2] flex-1 min-h-0 space-y-2 overflow-y-auto px-5 py-3 scrollbar-hide">
          {restMode && !restTarget && <p className="rounded-2xl bg-gray-100 px-4 py-3 text-sm font-bold text-gray-600">휴식하고 싶은 일정 카드를 눌러주세요.</p>}
          {schedule.map((item, index) => (
            <div key={`${item.time}-${item.place}`}>
              <button onClick={() => restMode ? pickRestTarget(item) : setSelectedSchedule(item)} aria-label={restMode ? `${item.place} 다음에 휴식 장소 찾기` : `${item.place} 일정 자세히 보기`} className={`w-full rounded-2xl border-2 p-4 text-left transition-all active:scale-[0.98] ${restMode ? (restTarget?.time === item.time && restTarget.place === item.place ? 'border-gray-500 bg-gray-200' : 'border-transparent bg-gray-100') : index === 1 ? 'border-[#4169D8] bg-[#EEF2FF]/90' : index === 0 ? 'border-green-300 bg-green-50/90' : 'border-transparent bg-white/85 shadow-sm'}`}>
                <div className="flex items-center gap-3"><span aria-hidden="true" className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-sm font-black text-white ${restMode ? 'bg-gray-400' : index === 0 ? 'bg-green-500' : 'bg-[#4169D8]'}`}>{index + 1}</span><span aria-hidden="true" className={`flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-2xl bg-white text-3xl shadow-sm ${restMode ? 'grayscale opacity-60' : ''} ${sm ? 'text-4xl' : ''}`}>{item.icon}</span><div className="min-w-0 flex-1"><p className={`text-sm ${restMode ? 'text-gray-400' : 'text-gray-500'}`}>{item.time}</p><p className={`truncate font-bold ${restMode ? 'text-gray-500' : 'text-gray-900'} ${sm ? 'text-lg' : 'text-base'}`}>{item.place}</p><p className={`mt-1 truncate text-xs ${restMode ? 'text-gray-400' : 'text-gray-500'}`}>{restMode ? '다음에 휴식 장소 추가하기' : item.transport ? `🚕 ${item.transport}` : item.walk ? `🚶 ${item.walk}` : '자세히 보기'}</p></div><span className={`flex-shrink-0 text-xs font-bold ${restMode ? 'text-gray-500' : 'text-[#4169D8]'}`}>{restMode ? '선택' : '상세'}</span></div>
              </button>
              {restMode && restTarget?.time === item.time && restTarget.place === item.place && restRecommendationPanel}
            </div>
          ))}
        </div>
      </div>
      {selectedSchedule && <div className="absolute inset-0 z-50 flex items-end bg-black/50" onClick={() => setSelectedSchedule(null)}><section role="dialog" aria-modal="true" aria-labelledby="schedule-detail-title" className="max-h-[82%] w-full overflow-y-auto rounded-t-3xl bg-white px-5 pt-3 pb-6 shadow-2xl" onClick={event => event.stopPropagation()}><div className="mx-auto mb-3 h-1 w-10 rounded-full bg-gray-200" /><div className="flex items-start justify-between gap-3"><div><p className="text-sm font-bold text-[#4169D8]">{selectedSchedule.time} 일정</p><h2 id="schedule-detail-title" className="mt-1 text-2xl font-black text-gray-900">{selectedSchedule.icon} {selectedSchedule.place}</h2></div><button onClick={() => setSelectedSchedule(null)} aria-label="일정 상세 닫기" className="flex h-11 w-11 items-center justify-center rounded-xl bg-gray-100 text-xl text-gray-700">×</button></div><div className="mt-4 grid grid-cols-2 gap-3"><div className="rounded-2xl bg-[#F7F9FF] p-3"><p className="text-xs text-gray-500">이동</p><p className="mt-1 text-base font-bold text-gray-900">{selectedSchedule.transport || selectedSchedule.walk || '이동 정보 없음'}</p></div><div className="rounded-2xl bg-[#F7F9FF] p-3"><p className="text-xs text-gray-500">예상 비용</p><p className="mt-1 text-base font-bold text-gray-900">{selectedSchedule.cost || '무료'}</p></div></div><div className="mt-4"><p className="text-sm font-bold text-gray-900">이 일정의 특징</p><div className="mt-2 flex flex-wrap gap-2">{selectedSchedule.tags.map(tag => <span key={tag} className="rounded-full bg-[#EEF2FF] px-3 py-1.5 text-sm font-semibold text-[#2749A5]">{tag}</span>)}</div></div>{selectedSchedule.rest && <p className="mt-4 rounded-2xl bg-green-50 p-3 text-sm font-semibold text-green-700">휴식하기 좋은 일정이에요.</p>}<button onClick={() => { setState(current => ({ ...current, activeSchedule: selectedSchedule })); setSelectedSchedule(null); nav('rest-search') }} className="mt-5 h-14 w-full rounded-2xl bg-[#4169D8] text-base font-bold text-white active:scale-[0.98]">{selectedSchedule.place} 주변 휴식 장소 찾기</button></section></div>}
    </div>
  )
}
// ─── Rest Search ─────────────────────────────────────────────────────────────
// [기능] 선택한 일정 장소를 기준으로 다음 동선에서 크게 벗어나지 않는 휴식 공간을 추천하고, 선택 시 기존 일정 뒤에 삽입한다.
function RestSearchScreen({ state, nav, setState }: { state: AppState; nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>> }) {
  const sm = state.seniorMode
  const target = state.activeSchedule
  const day = state.currentTrip.days[1] || state.currentTrip.days[0]
  const [isSearching, setIsSearching] = useState(true)
  const restSpots = [
    { name: `${target?.place || '선택한 장소'} 인근 쉼터`, icon: '🪑', time: '현재 위치에서 4분', features: ['앉아서 쉴 수 있음', '화장실 있음', '그늘 있음', '카페 있음'] },
    { name: '가까운 작은 공원', icon: '🌳', time: '현재 위치에서 6분', features: ['벤치 있음', '화장실 있음', '그늘 있음', '산책로 있음'] },
  ]

  useEffect(() => {
    const timer = window.setTimeout(() => setIsSearching(false), 900)
    return () => window.clearTimeout(timer)
  }, [])

  const shiftTime = (time: string, minutesToAdd: number) => {
    const [hours, minutes] = time.split(':').map(Number)
    if (!Number.isFinite(hours) || !Number.isFinite(minutes)) return time
    const total = hours * 60 + minutes + minutesToAdd
    return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
  }

  const addRestStop = (spot: typeof restSpots[number]) => {
    if (!target || !day) return
    setState(current => {
      const dayIndex = current.currentTrip.days.findIndex(item => item.dayNumber === day.dayNumber)
      if (dayIndex < 0) return current
      const places = current.currentTrip.days[dayIndex].places
      const targetIndex = places.findIndex(item => item.time === target.time && item.place === target.place)
      if (targetIndex < 0) return current
      const restStop: ScheduleItem = { time: shiftTime(target.time, 30), place: spot.name, icon: spot.icon, tags: ['AI 추천', '휴식'], walk: spot.time, cost: '무료', rest: true }
      const updatedDay: DayPlan = {
        ...current.currentTrip.days[dayIndex],
        places: [...places.slice(0, targetIndex + 1), restStop, ...places.slice(targetIndex + 1).map(item => ({ ...item, time: shiftTime(item.time, 30) }))],
        notice: `${target.place} 다음에 AI 추천 휴식 장소를 추가하고, 이후 일정은 30분씩 여유롭게 조정했어요.`,
      }
      return { ...current, activeSchedule: null, currentTrip: { ...current.currentTrip, days: current.currentTrip.days.map((item, index) => index === dayIndex ? updatedDay : item) } }
    })
    nav('today-travel')
  }

  if (!target) {
    return <div className="flex h-full flex-col bg-[#F7F9FF]"><PageHeader title="휴식 장소 찾기" back={() => nav('today-travel')} /><div className="flex flex-1 flex-col items-center justify-center px-8 text-center"><p className="text-lg font-bold text-gray-900">선택한 일정이 없어요.</p><p className="mt-2 text-sm text-gray-500">오늘의 여행에서 장소를 상세보기로 열어주세요.</p></div></div>
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#F7F9FF]">
      <PageHeader title="휴식 장소 찾기" back={() => nav('today-travel')} />
      <main className="flex-1 overflow-y-auto px-5 py-5 scrollbar-hide">
        <section className="rounded-3xl bg-[#4169D8] p-5 text-white shadow-lg">
          <p className="text-sm font-semibold text-white/80">선택한 장소</p>
          <h2 className={`mt-1 font-black ${sm ? 'text-2xl' : 'text-xl'}`}>{target.icon} {target.place}</h2>
          <p className="mt-3 text-sm leading-6 text-white/90">현재 위치와 다음 장소로 가는 동선을 살펴, 크게 벗어나지 않는 휴식 공간을 찾았어요.</p>
        </section>
        {isSearching ? <div role="status" className="mt-5 rounded-3xl bg-white p-8 text-center shadow-sm"><div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-[#4169D8]/20 border-t-[#4169D8]" /><p className="mt-4 font-bold text-gray-800">주변 쉼터와 공원을 찾고 있어요.</p><p className="mt-1 text-sm text-gray-500">다음 장소로 가는 길도 함께 확인하고 있어요.</p></div> : <section className="mt-5"><h3 className="text-lg font-black text-gray-900">{target.place} 주변 추천</h3><p className="mt-1 text-sm text-gray-500">다음 장소로 가는 길에서 크게 벗어나지 않아요.</p><div className="mt-3 space-y-3">{restSpots.map(spot => <article key={spot.name} className="rounded-3xl bg-white p-4 shadow-sm"><div className="flex items-start justify-between gap-3"><div><h4 className="text-lg font-bold text-gray-900">{spot.icon} {spot.name}</h4><p className="mt-1 text-sm font-semibold text-[#4169D8]">{spot.time}</p></div><span className="rounded-full bg-green-50 px-2.5 py-1 text-xs font-bold text-green-700">동선 이탈 적음</span></div><div className="mt-3 flex flex-wrap gap-2">{spot.features.map(feature => <span key={feature} className="rounded-full bg-[#F0F4FF] px-3 py-1.5 text-xs font-semibold text-[#4169D8]">✓ {feature}</span>)}</div><button onClick={() => addRestStop(spot)} className="mt-4 h-12 w-full rounded-2xl bg-[#4169D8] text-sm font-bold text-white active:scale-[0.98]">이곳에서 휴식하기</button></article>)}</div></section>}
      </main>
    </div>
  )
}
// ─── Directions ───────────────────────────────────────────────────────────────
// [기능] 선택한 일정 장소를 목적지로 삼아 이동수단별 길찾기 정보를 표시한다.
function DirectionsScreen({ state, nav }: { state: AppState; nav: (s: Screen) => void }) {
  const [mode, setMode] = useState('택시')
  const modes = [{ id: '도보', t: '35분', cost: '무료' }, { id: '대중교통', t: '22분', cost: '1,500원' }, { id: '택시', t: '12분', cost: '8,000원' }, { id: '자동차', t: '10분', cost: '주차비 별도' }]
  const selectedMode = modes.find(item => item.id === mode)!
  const day = state.currentTrip.days[1] || state.currentTrip.days[0]
  const schedule = day?.places || []
  const restSpots = [
    { name: '안목 해변 쉼터', icon: '🪑', time: '현재 위치에서 4분', features: ['앉아서 쉴 수 있음', '화장실 있음', '그늘 있음', '카페 있음'] },
    { name: '경포호 작은 공원', icon: '🌳', time: '현재 위치에서 6분', features: ['벤치 있음', '화장실 있음', '그늘 있음', '산책로 있음'] },
  ]
  const destination = state.activeSchedule || schedule[1] || schedule[0]
  const destinationIndex = Math.max(0, schedule.findIndex(item => item.time === destination?.time && item.place === destination?.place))
  const center: [number, number] = [37.7519, 128.8761]
  const offsets: [number, number][] = [[-0.006, -0.009], [-0.001, -0.004], [0.003, -0.001], [0.005, 0.004], [0.001, 0.008]]
  const startPosition = [center[0] + offsets[0][0], center[1] + offsets[0][1]] as [number, number]
  const destinationOffset = offsets[destinationIndex % offsets.length]
  const destinationPosition = [center[0] + destinationOffset[0], center[1] + destinationOffset[1]] as [number, number]
  const mapCenter = [(startPosition[0] + destinationPosition[0]) / 2, (startPosition[1] + destinationPosition[1]) / 2] as [number, number]
  return (
    <div className="flex h-full flex-col overflow-hidden bg-blue-50">
      <div className="flex items-center gap-3 border-b border-gray-100 bg-white px-5 pt-12 pb-3"><button onClick={() => nav('today-travel')} aria-label="오늘의 일정으로 돌아가기"><LeftIc /></button><h1 className="font-bold text-gray-900">길찾기</h1></div>
      <div className="relative flex-1 min-h-0">
        <MapContainer center={mapCenter} zoom={14} scrollWheelZoom className="h-full w-full" aria-label="선택한 일정 길찾기 지도"><TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" /><Polyline positions={[startPosition, destinationPosition]} pathOptions={{ color: '#4169D8', weight: 5, opacity: 0.85 }} /><CircleMarker center={startPosition} radius={10} pathOptions={{ color: '#ffffff', weight: 3, fillColor: '#16A34A', fillOpacity: 1 }}><Tooltip permanent direction="top">현재 일정</Tooltip></CircleMarker><CircleMarker center={destinationPosition} radius={11} pathOptions={{ color: '#ffffff', weight: 3, fillColor: '#4169D8', fillOpacity: 1 }}><Tooltip permanent direction="top">{destination?.place || '목적지'}</Tooltip><Popup><strong>{destination?.place || '다음 장소'}</strong></Popup></CircleMarker></MapContainer>
        <div className="pointer-events-none absolute left-4 right-4 top-4 z-[500] rounded-2xl bg-white/95 p-4 shadow-lg"><div className="flex items-center gap-3"><div className="flex flex-col items-center gap-1"><div className="h-3 w-3 rounded-full bg-green-500" /><div className="h-7 w-0.5 bg-gray-300" /><div className="h-3 w-3 rounded-full bg-[#4169D8]" /></div><div className="space-y-2"><p className="text-sm font-semibold text-gray-900">현재 일정</p><p className="text-sm font-semibold text-[#4169D8]">{destination?.place || '다음 장소'}</p></div></div></div>
        <div className="absolute bottom-0 left-0 right-0 z-[500] rounded-t-3xl bg-white p-5 shadow-[0_-4px_18px_rgba(0,0,0,0.12)]"><div className="mb-3 flex gap-2 overflow-x-auto scrollbar-hide">{modes.map(item => <button key={item.id} onClick={() => setMode(item.id)} className={`min-h-10 flex-shrink-0 rounded-full px-3 text-xs font-semibold ${mode === item.id ? 'bg-[#4169D8] text-white' : 'bg-gray-100 text-gray-600'}`}>{item.id}</button>)}</div><div className="mb-3 flex justify-around text-center"><div><p className="text-2xl font-bold text-[#4169D8]">{selectedMode.t}</p><p className="text-xs text-gray-400">예상 시간</p></div><div><p className="text-xl font-bold text-gray-700">{selectedMode.cost}</p><p className="text-xs text-gray-400">예상 비용</p></div></div><button className="h-12 w-full rounded-xl bg-[#4169D8] text-sm font-bold text-white">{mode} 이용하기</button></div>
      </div>
    </div>
  )
}
// ─── Past Trips ───────────────────────────────────────────────────────────────
// [기능] 완료된 여행 기록을 카드로 보여주고 다시보기 흐름을 제공한다.
function PastTripsScreen({ state, nav, setState }: { state: AppState; nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>> }) {
  const sm = state.seniorMode
  return (
    <div className="flex flex-col h-full" style={{ background: 'linear-gradient(160deg,#F0F4FF,#F7F8FF)' }}>
      <div className="px-5 pt-12 pb-3 flex-shrink-0">
        <h1 className={`font-bold text-gray-900 ${sm ? 'text-2xl' : 'text-xl'}`}>지난 여행</h1>
        <p className="text-sm text-gray-400 mt-1">소중한 여행 기록이에요</p>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-hide px-5 pb-4 space-y-4">
        {PAST_TRIPS.map(t => (
          <div key={t.id} className="bg-white rounded-3xl overflow-hidden" style={{ boxShadow: '0 2px 12px rgba(0,0,0,0.06)' }}>
            <div className="relative h-40">
              <img src={placeImageUrl(t.selectedPlaces[0].img, 600, 250)} alt={t.title} className="w-full h-full object-cover" />
              <div className="absolute inset-0" style={{ background: 'linear-gradient(to top,rgba(0,0,0,0.6),transparent 60%)' }} />
              <div className="absolute bottom-3 left-4">
                <h2 className={`text-white font-bold ${sm ? 'text-xl' : 'text-lg'}`}>{t.title}</h2>
                <p className="text-white/70 text-xs">{t.startDate} ~ {t.endDate.slice(5)} · {t.travelers}명</p>
              </div>
            </div>
            <div className="p-4">
              <div className="flex flex-wrap gap-1 mb-3">
                {t.days.slice(0, 2).flatMap(d => d.places.slice(0, 2)).map((p, i) => (
                  <span key={i} className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-full">{p.place}</span>
                )).slice(0, 4)}
              </div>
              <button onClick={() => { setState(s => ({ ...s, viewedPastTrip: t })); nav('past-itinerary') }}
                className="w-full h-11 rounded-xl bg-[#EEF2FF] text-[#4169D8] font-bold text-sm active:scale-95">
                여행 다시보기 →
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Notifications ────────────────────────────────────────────────────────────
// [기능] 여행·날씨·일정 관련 알림을 표시하고 화면 진입 시 읽음 상태를 갱신한다.
function NotificationsScreen({ notifications, nav, setState }: { notifications: TravelNotification[]; nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>> }) {
  // [기능] 개별 알림을 읽음으로 변경해 읽지 않은 알림 수를 다시 계산한다.
  function markRead(id: string) {
    setState(previous => {
      if (!previous.notifications.some(item => item.id === id && item.unread)) return previous
      return { ...previous, notifications: previous.notifications.map(item => item.id === id ? { ...item, unread: false } : item) }
    })
  }
  return (
    <div className="flex flex-col h-full" style={{ background: 'linear-gradient(160deg,#F0F4FF,#F7F8FF)' }}>
      <PageHeader title="알림" back={() => nav('home')} />
      <p role="status" className="sr-only">읽지 않은 알림 {unreadCount(notifications)}개</p>
      <div className="flex-1 overflow-y-auto scrollbar-hide px-5 py-3 space-y-2">
        {notifications.map(n => (
          <button type="button" key={n.id} onClick={() => { markRead(n.id); if (n.id === 'weather-20260924') { setState(previous => ({ ...previous, weatherPlan: 'B' })); nav('weather') } }}
            aria-label={`${n.title}, ${n.body}, ${n.unread ? '읽지 않음, 눌러서 확인' : '읽음'}`}
            className={`w-full text-left rounded-2xl p-4 flex gap-3 focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-[#4169D8] ${n.unread ? 'bg-[#EEF2FF] border border-[#4169D8]/20' : 'bg-white border border-transparent'}`}
            style={!n.unread ? { boxShadow: '0 1px 6px rgba(0,0,0,0.05)' } : {}}>
            <span aria-hidden="true" className="text-2xl flex-shrink-0">{n.e}</span>
            <span className="flex-1">
              <span className="flex justify-between mb-0.5"><span className="font-semibold text-gray-900 text-sm">{n.title}</span><span className="text-xs text-gray-400">{n.t}</span></span>
              <span className="block text-sm text-gray-500">{n.body}</span>
            </span>
            {n.unread && <span aria-hidden="true" className="w-2 h-2 rounded-full bg-[#4169D8] flex-shrink-0 mt-1" />}
          </button>
        ))}
      </div>
    </div>
  )
}
// ─── Profile ──────────────────────────────────────────────────────────────────
// [기능] 사용자 정보, 접근성 설정, 여행 관리 메뉴와 선호 저장 기능을 제공한다.
// [기능] 사용자 정보·여행 현황·빠른 메뉴·접근성 설정을 한눈에 확인하고 관리하는 마이페이지다.
// [기능] 사용자 정보와 여행 관리·개인 설정을 카드형 빠른 메뉴로 한눈에 보여주는 마이페이지다.
function ProfileScreen({ state, nav, setState }: { state: AppState; nav: (s: Screen) => void; setState: React.Dispatch<React.SetStateAction<AppState>> }) {
  const sm = state.seniorMode
  const travelMenus = [
    { icon: '🗺️', label: '내 여행 일정', desc: '오늘 일정 확인', to: 'today-travel' as Screen, tone: 'bg-[#4169D8]' },
    { icon: '✈️', label: '지난 여행', desc: '추억과 기록 보기', to: 'past-trips' as Screen, tone: 'bg-[#8B5E3C]' },
    { icon: '❤️', label: '저장한 장소', desc: `${state.savedPlaces.length}곳 다시 보기`, to: 'youtube-saved' as Screen, tone: 'bg-[#D14D72]' },
  ]
  return (
    <div className="h-full overflow-y-auto scrollbar-hide" style={{ background: 'linear-gradient(160deg,#F3F7FF 0%,#F9F5FF 50%,#F2FBF8 100%)' }}>
      <header className="px-5 pt-7 pb-3"><p className="text-sm font-bold text-[#4169D8]">여행메이트</p><h1 className={`mt-1 font-black text-gray-900 ${sm ? 'text-3xl' : 'text-2xl'}`}>마이페이지</h1></header>
      <main className="space-y-4 px-5 pb-5">
        <section className="rounded-3xl bg-white p-4 shadow-sm"><div className="flex items-center gap-4"><div className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-2xl bg-[#4169D8] text-2xl font-black text-white">{state.userName[0]}</div><div><p className={`font-black text-gray-900 ${sm ? 'text-2xl' : 'text-xl'}`}>{state.userName}님</p></div></div><div className="mt-3 grid grid-cols-2 divide-x divide-gray-100 rounded-2xl bg-[#F8FAFF] py-2 text-center"><div><p className="text-xs text-gray-500">지난 여행</p><p className="mt-1 text-lg font-black text-gray-900">{PAST_TRIPS.length}회</p></div><div><p className="text-xs text-gray-500">저장 장소</p><p className="mt-1 text-lg font-black text-gray-900">{state.savedPlaces.length}곳</p></div></div></section>
        <section aria-label="마이페이지 메뉴" className="rounded-3xl bg-white p-4 shadow-sm">
          <div className="grid grid-cols-2 gap-4">
            {travelMenus.map(card => <button key={card.label} onClick={() => nav(card.to)} className="h-30 rounded-2xl bg-white p-3.5 text-left shadow-sm active:scale-[0.98] transition-transform"><span aria-hidden="true" className={`flex h-11 w-11 items-center justify-center rounded-xl text-xl shadow-sm ${card.tone}`}>{card.icon}</span><span className={`mt-2 block font-black text-gray-900 ${sm ? 'text-base' : 'text-sm'}`}>{card.label}</span></button>)}
            <button onClick={() => setState(current => ({ ...current, seniorMode: !current.seniorMode }))} className={`h-30 rounded-2xl p-3.5 text-left shadow-sm active:scale-[0.98] transition-transform ${sm ? 'bg-[#EEF2FF] ring-2 ring-[#4169D8]' : 'bg-white'}`}><span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#0F766E] text-xl shadow-sm">🔎</span><span className={`mt-2 block font-black text-gray-900 ${sm ? 'text-base' : 'text-sm'}`}>편한 모드</span></button>
          </div>
          <button onClick={() => nav('ai-analysis')} className="mt-4 flex min-h-22 w-full items-center gap-3 rounded-2xl border border-[#D8D0F8] bg-[#F4F1FF] p-4 text-left shadow-sm transition-transform active:scale-[0.98]">
            <span aria-hidden="true" className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-[#6B52D3] text-2xl shadow-sm">🤖</span>
            <span className="min-w-0 flex-1"><span className={`block font-black text-gray-900 ${sm ? 'text-xl' : 'text-lg'}`}>AI 취향 재분석</span></span>
            <span aria-hidden="true" className="text-xl font-bold text-[#6B52D3]">›</span>
          </button>
        </section>
        </main>
    </div>
  )
}
// ─── App ──────────────────────────────────────────────────────────────────────
const NAV_SCREENS: Screen[] = ['home', 'map', 'youtube-saved', 'profile', 'past-trips', 'notifications', 'itinerary', 'today-travel']
const NO_NAV: Screen[] = ['login', 'register', 'setup', 'analyzing', 'ai-loading', 'camera']

export default function App() {
  const [state, setState] = useState<AppState>(initialAppState)
  const [showRainAlert, setShowRainAlert] = useState(false)
  const rainAlertShown = useRef(false)

  // 로그인·설정 후 홈에 처음 도착하면 일반 날씨 알림을 5초 동안 보여준다.
  useEffect(() => {
    // 홈을 떠나면 남아 있던 알림을 즉시 숨기고 타이머도 정리한다.
    if (state.screen !== 'home') {
      setShowRainAlert(false)
      return
    }
    if (rainAlertShown.current) return
    rainAlertShown.current = true
    setShowRainAlert(true)
    const timer = window.setTimeout(() => setShowRainAlert(false), 5000)
    return () => window.clearTimeout(timer)
  }, [state.screen])
  const openRainPlan = () => {
    setShowRainAlert(false)
    setState(current => ({ ...current, weatherPlan: 'B', notifications: current.notifications.map(item => item.id === 'weather-20260924' ? { ...item, unread: false } : item) }))
    nav('weather')
  }
  const startVoiceRef = useRef<(() => void) | null>(null)
  const nav = (screen: Screen) => {
    // 알림을 누르지 않고 다른 화면으로 이동한 경우에도 팝업이 남지 않도록 즉시 닫는다.
    if (screen !== 'home') setShowRainAlert(false)
    const navigate = () => setState(s => ({ ...s, screen, screenHistory: [...s.screenHistory, s.screen] }))
    if (screen === 'search-voice') {
      // Mount the recognition handlers, then start within the user's click.
      flushSync(navigate)
      startVoiceRef.current?.()
    } else {
      navigate()
    }
  }
  const sm = state.seniorMode
  const showNav = NAV_SCREENS.includes(state.screen) && !NO_NAV.includes(state.screen)

  const screenEl = (() => {
    switch (state.screen) {
      case 'login': return <LoginScreen onLogin={() => nav('setup')} onRegister={() => nav('register')} />
      case 'register': return <RegisterScreen onDone={() => nav('setup')} />
      case 'setup': return <SetupScreen onDone={(style, prefs, senior) => { setState(s => ({ ...s, travelStyle: style, userPrefs: prefs, seniorMode: senior })); nav('home') }} />
      case 'home': return <HomeScreen state={state} nav={nav} />
      case 'search-text':
      case 'search-voice': return <PlaceSearchScreen startVoiceRef={startVoiceRef} key={state.screen} voice={state.screen === 'search-voice'} nav={nav} onSelect={place => { setState(s => ({ ...s, selectedPlace: place })); nav('place-detail') }} />
      case 'camera': return <CameraScreen nav={nav} />
      case 'analyzing': return <AnalyzingScreen nav={nav} />
      case 'place-result': return <PlaceResultScreen nav={nav} setState={setState} />
      case 'youtube-saved': return <YouTubeSavedScreen state={state} nav={nav} setState={setState} />
      case 'ai-analysis': return <AIAnalysisScreen state={state} nav={nav} setState={setState} />
      case 'taste-confirm': return <TasteConfirmScreen state={state} nav={nav} setState={setState} />
      case 'place-detail': return <PlaceDetailScreen state={state} nav={nav} />
      case 'map': return <MapScreen nav={nav} />
      case 'comfort-travel': return <ComfortTravelScreen state={state} nav={nav} />
      case 'trip-places': return <TripPlacesScreen state={state} nav={nav} setState={setState} />
      case 'trip-date': return <TripDateScreen state={state} nav={nav} setState={setState} />
      case 'trip-people': return <TripPeopleScreen state={state} nav={nav} setState={setState} />
      case 'trip-transport': return <TripTransportScreen state={state} nav={nav} setState={setState} />
      case 'trip-budget': return <TripBudgetScreen state={state} nav={nav} setState={setState} />
      case 'trip-companions': return <TripCompanionsScreen state={state} nav={nav} setState={setState} />
      case 'trip-confirm': return <TripConfirmScreen state={state} nav={nav} setState={setState} />
      case 'ai-loading': return <AILoadingScreen nav={nav} />
      case 'itinerary': return <ItineraryScreen key={'current-' + state.currentTrip.id} state={state} nav={nav} setState={setState} />
      case 'past-itinerary': return state.viewedPastTrip ? <ItineraryScreen key={'past-' + state.viewedPastTrip.id} state={state} nav={nav} setState={setState} pastTrip={state.viewedPastTrip} /> : <PastTripsScreen state={state} nav={nav} setState={setState} />
      case 'accommodation': return <AccommodationScreen state={state} nav={nav} />
      case 'pre-departure': return <PreDepartureScreen state={state} nav={nav} />
      case 'today-travel': return <TodayTravelScreen state={state} nav={nav} setState={setState} />
      case 'rest-search': return <RestSearchScreen state={state} nav={nav} setState={setState} />
      case 'weather': return <WeatherScreen state={state} nav={nav} setState={setState} />
      case 'directions': return <DirectionsScreen state={state} nav={nav} />
      case 'past-trips': return <PastTripsScreen state={state} nav={nav} setState={setState} />
      case 'notifications': return <NotificationsScreen notifications={state.notifications} nav={nav} setState={setState} />
      case 'profile': return <ProfileScreen state={state} nav={nav} setState={setState} />
      default: return <HomeScreen state={state} nav={nav} />
    }
  })()

  return (
    <div className="flex items-center justify-center min-h-screen" style={{ background: 'linear-gradient(135deg,#BDC8E2 0%,#C2B8D8 100%)' }}>
      <div className={`relative w-full max-w-sm bg-white overflow-hidden flex flex-col ${sm ? 'senior-mode' : ''}`}
        style={{ height: 'min(844px, 100dvh)', borderRadius: '40px', boxShadow: '0 30px 80px rgba(0,0,0,0.35)' }}>
        <div className="flex items-center justify-between px-6 text-xs font-semibold text-gray-600 bg-white flex-shrink-0" style={{ paddingTop: '14px', paddingBottom: '4px' }}>
          <span>9:41</span>
          <div className="flex items-center gap-1.5"><span>●●●●</span><span>WiFi</span><span>🔋</span></div>
        </div>
        <div className="flex-1 min-h-0 min-w-0 overflow-hidden flex flex-col">{screenEl}</div>
        {showRainAlert && <button type="button" onClick={openRainPlan} className="absolute inset-x-4 top-16 z-[2000] rounded-2xl border border-[#4169D8]/20 bg-white p-4 text-left shadow-lg" aria-label="비 예보 알림. 눌러서 비 오는 날 일정 계획 2 확인"><div className="flex items-start gap-3"><span className="text-3xl">🌧️</span><div className="min-w-0 flex-1"><p className="text-sm font-black text-[#4169D8]">날씨 알림</p><p className="mt-1 text-base font-bold text-gray-900">강릉 지역에 비가 올 예정이에요.</p><p className="mt-1 text-sm leading-5 text-gray-600">강수확률 70% · 실내 중심 계획 2를 확인해보세요.</p><p className="mt-2 text-xs font-bold text-[#4169D8]">눌러서 오늘 일정 확인하기</p></div></div></button>}
        {showNav && <BottomNav active={state.screen === 'today-travel' ? 'home' : state.screen} nav={nav} sm={sm} notifs={unreadCount(state.notifications)} />}
      </div>
    </div>
  )
}

/**
 * 일정 생성 도메인 로직.
 * 선택 장소와 여행 기간을 바탕으로 일차별 방문 순서·식사·휴식·교통 정보를 포함한 DayPlan을 만든다.
 * 실제 경로·영업 정보 API가 아닌 로컬 후보 데이터 기반의 추천 알고리즘이다.
 */

export interface ScheduleItem { time: string; place: string; icon: string; tags: string[]; walk: string; cost: string; rest: boolean; transport?: string }
export interface DayPlan { dayNumber: number; date: string; places: ScheduleItem[]; notice?: string }
interface Destination { name: string; region: string; tags: string[] }

// Local candidate data, not live availability or route optimization.
const REGIONAL_PLACES: Record<string, string[]> = {
  '강릉': ['안목해변', '경포해변', '오죽헌', '선교장', '경포대', '강릉 중앙시장', '월화거리', '강릉솔향수목원', '정동진', '하슬라아트월드', '주문진항', '사천해변', '허균·허난설헌 기념공원', '강릉 아르떼뮤지엄', '초당두부마을', '경포호', '안반데기', '대관령박물관', '정동심곡 바다부채길', '연곡해변', '영진해변', '옥계해변', '금진해변', '강릉 통일공원', '강릉 대도호부관아', '명주동', '강릉시립미술관', '보헤미안 박이추커피', '테라로사 커피공장', '정동진 시간박물관'],
  '경주': ['황리단길', '대릉원', '첨성대', '동궁과 월지', '월정교', '경주 교촌마을', '국립경주박물관', '불국사', '석굴암', '보문호', '경주 동궁원', '분황사', '황룡사지', '포석정', '경주 양동마을', '김유신장군묘', '경주 동부사적지', '경주읍성', '경주 중앙시장', '봉황대', '경주 엑스포대공원', '경주월드', '경주 버드파크', '주상절리 파도소리길', '문무대왕릉', '감은사지', '기림사', '골굴사', '경주 감포항', '경주 양남 주상절리 전망대'],
  '제주': ['애월 해안도로', '한담해안산책로', '협재해수욕장', '금능해수욕장', '한림공원', '오설록 티뮤지엄', '제주 동문시장', '용두암', '이호테우해변', '곽지해수욕장', '함덕해수욕장', '김녕해수욕장', '월정리해변', '성산일출봉', '섭지코지', '비자림', '사려니숲길', '에코랜드', '산굼부리', '제주 돌문화공원', '천지연폭포', '정방폭포', '서귀포 매일올레시장', '중문색달해수욕장', '대포 주상절리대', '천제연폭포', '카멜리아힐', '산방산', '송악산', '제주 아르떼뮤지엄'],
  '부산': ['광안리해수욕장', '해운대해수욕장', '동백섬', '해동용궁사', '감천문화마을', '자갈치시장', '국제시장', '용두산공원', '태종대', '송도해수욕장', '흰여울문화마을', '오륙도 스카이워크', '이기대', '다대포해수욕장', '부산시민공원', '범어사', '금정산성', '부산박물관', '국립해양박물관', '부산현대미술관', '을숙도', '삼락생태공원', '온천천 시민공원', '청사포', '송정해수욕장', '해운대 달맞이길', '전포카페거리', '부평깡통시장', '보수동 책방골목', '부산 차이나타운'],
  '전주': ['전주 한옥마을', '경기전', '전동성당', '풍남문', '오목대', '전주향교', '자만벽화마을', '남부시장', '덕진공원', '국립전주박물관', '전주한지박물관', '전주수목원', '전주난장', '전주동물원', '팔복예술공장', '전라감영', '전주객사', '최명희문학관', '전주부채문화관', '전주공예품전시관', '어진박물관', '전주전통술박물관', '학인당', '완판본문화관', '전주자연생태관', '전주천', '청연루', '한벽당', '전주 영화의 거리', '서학동예술마을'],
  '춘천': ['남이섬', '소양강스카이워크', '춘천 명동닭갈비골목', '김유정문학촌', '강촌레일파크', '제이드가든', '구봉산 전망대', '춘천 삼악산 호수케이블카', '공지천', '의암호', '춘천 애니메이션박물관', '국립춘천박물관', '청평사', '소양강댐', '춘천막국수체험박물관', '춘천중앙시장', '강원도립화목원', '춘천 육림고개', '춘천 칠층석탑', '봉의산', '춘천향교', '죽림동성당', '춘천 문학공원', '춘천 인형극장', '춘천 토이로봇관', '춘천 물레길', '강촌 구곡폭포', '등선폭포', '춘천 레고랜드', '춘천 이상원미술관'],
}

// 날짜 차이를 일 단위로 계산하기 위한 밀리초 상수.
const DAY_MS = 86_400_000
// 입력 날짜가 YYYY-MM-DD 형식의 실제 날짜인지 검증하고 UTC 자정 타임스탬프로 변환한다.
function parseDate(value: string): number {
  const timestamp = Date.parse(value + 'T00:00:00Z')
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(timestamp) || new Date(timestamp).toISOString().slice(0, 10) !== value) {
    throw new Error('올바른 여행 날짜를 선택해주세요.')
  }
  return timestamp
}

// 선택 장소를 우선 배치하고, 지역별 후보 장소·식사·휴식·숙소 이벤트를 포함해 일차별 일정으로 만든다.
export function buildDays(startDate: string, endDate: string, selectedPlaces: Destination[], transport: string[] = []): DayPlan[] {
  const start = parseDate(startDate)
  const count = (parseDate(endDate) - start) / DAY_MS + 1
  if (count < 1) throw new Error('여행 종료일은 시작일보다 빠를 수 없어요.')
  if (count > 366) throw new Error('여행 기간은 366일 이내로 선택해주세요.')
  const seen = new Set<string>()
  const unique = (places: Destination[]) => places.filter(place => {
    const key = place.name.replace(/\s/g, '')
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
  const selected = unique(selectedPlaces)
  const regions = [...new Set(selected.map(place =>
    Object.keys(REGIONAL_PLACES).find(region => place.region.includes(region))
  ).filter((region): region is string => Boolean(region)))]
  const candidates = unique(regions.flatMap(region =>
    REGIONAL_PLACES[region].map(name => ({ name, region, tags: ['관광'] }))
  ))
  const capacity = count * 2
  // Selected destinations take priority. Keep visits from each region together.
  const visits = [...selected, ...candidates.slice(0, Math.max(0, capacity - selected.length))]
  visits.sort((a, b) => {
    const regionIndex = (place: Destination) => regions.findIndex(region => place.region.includes(region))
    return regionIndex(a) - regionIndex(b)
  })
  let cursor = 0
  const event = (time: string, place: string, icon: string, tags: string[], rest = false): ScheduleItem =>
    ({ time, place, icon, tags, walk: '', cost: '', rest })
  return Array.from({ length: count }, (_, dayIndex) => {
    const first = dayIndex === 0
    const last = dayIndex === count - 1
    const remainingDays = count - dayIndex
    const today = visits.slice(cursor, cursor + Math.ceil((visits.length - cursor) / remainingDays))
    cursor += today.length
    const places: ScheduleItem[] = []
    if (first) places.push({ ...event('09:00', '여행지로 출발', '🧳', ['출발']), transport: transport.join(' · ') || undefined })
    else places.push(event('09:00', '아침 식사', '🍳', ['식사'], true))
    if (last && !first) places.push(event('09:30', '숙소 체크아웃', '🏨', ['숙소']))
    today.forEach((destination, index) => {
      const minutes = 10 * 60 + Math.floor(index * 360 / Math.max(today.length - 1, 1))
      const time = String(Math.floor(minutes / 60)).padStart(2, '0') + ':' + String(minutes % 60).padStart(2, '0')
      places.push(event(time, destination.name, '📍', ['관광', ...destination.tags.filter(tag => tag !== '관광')]))
    })
    places.push(event('12:30', '점심 식사와 휴식', '🍲', ['식사', '휴식'], true))
    if (last) places.push({ ...event('18:00', '여행 마무리 · 귀가', '🧳', ['귀가']), transport: transport.join(' · ') || undefined })
    else places.push(event('18:00', first ? '숙소 체크인' : '숙소에서 휴식', '🏨', ['숙소'], true))
    places.sort((a, b) => a.time.localeCompare(b.time))
    const notices: string[] = []
    if (!today.length) notices.push('중복 없이 추천할 여행지가 부족해요. 장소를 추가해 일정을 완성해주세요.')
    if (today.length > 2) notices.push('선택한 장소가 많아요. 여유로운 여행을 위해 기간을 늘리거나 장소를 줄여주세요.')
    return {
      dayNumber: dayIndex + 1,
      date: new Date(start + dayIndex * DAY_MS).toISOString().slice(0, 10),
      places,
      ...(notices.length ? { notice: notices.join(' ') } : {}),
    }
  })
}
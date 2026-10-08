import type { DayPlan, ScheduleItem } from './itinerary'

export const COMFORT_OPTIONS = [
  { id: 'walking', label: '🚶 너무 많이 걸어요', solution: '방문 장소를 유지하고 관광지 이동을 차량 이용 권장으로 바꿔요.' },
  { id: 'places', label: '📍 장소가 너무 많아요', solution: '하루 관광지 수를 절반으로 줄여 여유를 만들어요.' },
  { id: 'travel', label: '🚗 이동시간이 길어요', solution: '하루 한 관광지에 머무르며 장소 간 이동 횟수를 줄여요.' },
  { id: 'rest', label: '☕ 쉬는 시간 부족해요', solution: '관광 후 일정 사이에 별도의 휴식 시간을 넣어요.' },
] as const
export type ComfortReason = typeof COMFORT_OPTIONS[number]['id']

const minute = (time: string) => { const [h, m] = time.split(':').map(Number); return h * 60 + m }
const clock = (value: number) => String(Math.floor(value / 60)).padStart(2, '0') + ':' + String(value % 60).padStart(2, '0')

export function adjustComfort(days: DayPlan[], reasons: readonly ComfortReason[]): DayPlan[] {
  return days.map(day => {
    let places = day.places.map(item => ({ ...item, tags: [...item.tags] }))
    const notes: string[] = []
    if (reasons.includes('places')) {
      const count = places.filter(item => item.tags.includes('관광')).length
      const keep = Math.max(1, Math.ceil(count / 2))
      let seen = 0
      places = places.filter(item => !item.tags.includes('관광') || ++seen <= keep)
      notes.push(count > keep ? `관광지를 ${count}곳에서 ${keep}곳으로 줄였어요.` : '이미 하루 관광지가 1곳 이하라 그대로 유지했어요.')
    }
    if (reasons.includes('travel')) {
      const attractions = places.filter(item => item.tags.includes('관광'))
      let seen = 0
      places = places.filter(item => !item.tags.includes('관광') || ++seen <= 1)
      places = places.map(item => item.tags.includes('관광') ? { ...item, tags: [...new Set([...item.tags, '한 장소에서 여유롭게'])] } : item)
      notes.push(attractions.length > 1 ? '하루 한 관광지에 머무르도록 다른 관광지로의 이동을 제외했어요. 실제 이동시간은 경로 확인이 필요해요.' : '추가 관광지 이동 없이 현재 일정을 유지해요. 실제 이동시간은 경로 확인이 필요해요.')
    }
    if (reasons.includes('walking')) {
      const hasVisits = places.some(item => item.tags.includes('관광'))
      places = places.map(item => item.tags.includes('관광') ? {
        ...item, walk: '', transport: '택시·차량 이용 권장', tags: [...new Set([...item.tags, '도보 이동 최소화'])],
      } : item)
      notes.push(hasVisits ? '관광지 이동을 택시·차량 이용 권장으로 바꿨어요. 현장 내 도보 구간은 별도 확인이 필요해요.' : '조정할 관광지 이동이 없어요.')
    }
    if (reasons.includes('rest')) {
      const sorted = [...places].sort((a, b) => a.time.localeCompare(b.time))
      const restStops: ScheduleItem[] = []
      let existing = 0
      sorted.forEach((item, index) => {
        if (!item.tags.includes('관광')) return
        const next = sorted[index + 1]
        if (next?.tags.includes('추가 휴식')) { existing++; return }
        const from = minute(item.time)
        const until = next ? minute(next.time) : 18 * 60
        if (until - from < 20) return
        const at = from + Math.min(60, Math.floor((until - from) / 2))
        restStops.push({ time: clock(at), place: '관광 후 앉아서 쉬기', icon: '☕', tags: ['휴식', '추가 휴식'], walk: '', cost: '', rest: true })
      })
      places.push(...restStops)
      notes.push(restStops.length ? `관광 후 별도 휴식 ${restStops.length}회를 추가했어요.` : existing ? '관광 후 추가한 휴식 시간을 유지했어요.' : '추가 휴식을 넣을 시간 여유가 없어요. 장소 수를 줄이거나 시간을 조정해주세요.')
    }
    return { ...day, places: places.sort((a, b) => a.time.localeCompare(b.time)), notice: [day.notice, ...notes].filter(Boolean).join(' ') || undefined }
  })
}
// Every request replaces the previous adjustment using the original trip plan.
export function rebuildComfortPlan<T extends { days: DayPlan[]; originalDays?: DayPlan[] }>(trip: T, reasons: readonly ComfortReason[]) {
  const originalDays = trip.originalDays ?? structuredClone(trip.days)
  return { ...trip, originalDays, days: adjustComfort(originalDays, reasons) }
}
import test from 'node:test'
import assert from 'node:assert/strict'
import { buildDays } from '../src/lib/itinerary.ts'

const destinations = [
  { name: '안목해변', region: '강원 강릉시', tags: ['바다'] },
  { name: '황리단길', region: '경북 경주시', tags: ['전통'] },
  { name: '애월 해안도로', region: '제주 제주시', tags: ['바다'] },
  { name: '광안리해수욕장', region: '부산 수영구', tags: ['바다'] },
  { name: '전주 한옥마을', region: '전북 전주시', tags: ['전통'] },
  { name: '남이섬', region: '강원 춘천시', tags: ['자연'] },
]
const visits = days => days.flatMap(day => day.places.filter(item => item.tags.includes('관광')))

test('each region has unique destinations on every day for all selectable durations', () => {
  for (const destination of destinations) {
    for (let duration = 1; duration <= 30; duration++) {
      const end = '2026-09-' + String(duration).padStart(2, '0')
      const days = buildDays('2026-09-01', end, [destination], ['자동차'])
      assert.equal(days.length, duration)
      assert.equal(days.at(-1).date, end)
      assert.ok(days.every(day => day.places.some(item => item.tags.includes('관광'))))
      const names = visits(days).map(item => item.place)
      assert.equal(new Set(names).size, names.length)
      assert.ok(names.includes(destination.name))
      assert.equal(days.flatMap(day => day.places).filter(item => item.tags.includes('출발')).length, 1)
      assert.equal(days.flatMap(day => day.places).filter(item => item.tags.includes('귀가')).length, 1)
      assert.ok(days[0].places.some(item => item.tags.includes('출발')))
      assert.ok(days.at(-1).places.at(-1).tags.includes('귀가'))
      for (const day of days) {
        assert.deepEqual(day.places.map(item => item.time), day.places.map(item => item.time).sort())
      }
    }
  }
})

test('DAY 4 does not restart DAY 1 or return home before the final day', () => {
  const days = buildDays('2026-09-01', '2026-09-07', [destinations[0]])
  assert.ok(!days[3].places.some(item => item.place.includes('출발')))
  assert.ok(days.slice(0, -1).every(day => !day.places.some(item => item.tags.includes('귀가'))))
  assert.notDeepEqual(visits([days[0]]), visits([days[3]]))
})

test('day trip has departure and return without overnight check-in', () => {
  const days = buildDays('2026-09-01', '2026-09-01', [destinations[4]])
  assert.equal(days.length, 1)
  assert.ok(!days[0].places.some(item => item.tags.includes('숙소')))
})

test('all selected places are retained and duplicates are removed', () => {
  const days = buildDays('2026-09-01', '2026-09-03', [...destinations, destinations[0]])
  const names = visits(days).map(item => item.place)
  for (const destination of destinations) assert.ok(names.includes(destination.name))
  assert.equal(names.length, new Set(names).size)
})

test('Busan and Jeju do not receive the old fixed Gangneung itinerary', () => {
  for (const destination of [destinations[2], destinations[3]]) {
    const names = visits(buildDays('2026-09-01', '2026-09-07', [destination])).map(item => item.place)
    assert.ok(!names.includes('안목해변'))
    assert.ok(!names.includes('오죽헌'))
  }
})

test('month and year boundaries and leap days keep exact calendar dates', () => {
  assert.deepEqual(buildDays('2028-02-28', '2028-03-01', [destinations[0]]).map(day => day.date), ['2028-02-28', '2028-02-29', '2028-03-01'])
  assert.deepEqual(buildDays('2026-12-31', '2027-01-02', [destinations[0]]).map(day => day.date), ['2026-12-31', '2027-01-01', '2027-01-02'])
})

test('invalid dates fail explicitly', () => {
  for (const [start, end] of [['invalid', '2026-09-01'], ['2026-02-30', '2026-03-01'], ['2026-09-02', '2026-09-01']]) {
    assert.throws(() => buildDays(start, end, destinations))
  }
})

test('candidate exhaustion reports missing places without repeating destinations', () => {
  const days = buildDays('2026-09-01', '2026-10-05', [destinations[0]])
  assert.ok(days.some(day => day.notice))
  const names = visits(days).map(item => item.place)
  assert.equal(names.length, new Set(names).size)
  assert.ok(buildDays('2026-09-01', '2026-09-02', []).every(day => day.notice))
})

test('generated days and separate trips do not share mutable schedule items', () => {
  const first = buildDays('2026-09-01', '2026-09-04', [destinations[0]])
  const second = buildDays('2026-09-01', '2026-09-04', [destinations[0]])
  first[0].places[0].place = 'changed'
  assert.notEqual(second[0].places[0].place, 'changed')
  assert.notEqual(first[3].places[0].place, 'changed')
})
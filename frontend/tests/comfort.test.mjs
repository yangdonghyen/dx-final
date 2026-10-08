import test from 'node:test'
import assert from 'node:assert/strict'
import { adjustComfort, rebuildComfortPlan } from '../src/lib/comfort.ts'
const item = (time, place, tags) => ({time, place, tags, icon: '', walk: '20분', cost: '', rest: false})
const original = [{dayNumber: 1, date: '2026-09-22', places: [
  item('09:00', '출발', ['출발']), item('10:00', 'A', ['관광']),
  item('11:30', 'B', ['관광']), item('13:00', '점심', ['식사']),
  item('14:00', 'C', ['관광']), item('16:00', 'D', ['관광']), item('18:00', '귀가', ['귀가']),
]}]
const visits = day => day.places.filter(item => item.tags.includes('관광'))
test('walking preserves destinations but changes transport recommendations', () => {
 const [day] = adjustComfort(original, ['walking'])
 assert.equal(visits(day).length, 4)
 assert.ok(visits(day).every(item => item.transport && !item.walk))
})
test('too many places halves visits while long travel keeps one base', () => {
 assert.equal(visits(adjustComfort(original, ['places'])[0]).length, 2)
 assert.equal(visits(adjustComfort(original, ['travel'])[0]).length, 1)
})
test('rest adds dedicated breaks without deleting destinations or duplicating breaks', () => {
 const result = adjustComfort(original, ['rest'])
 assert.equal(visits(result[0]).length, 4)
 assert.equal(result[0].places.filter(item => item.tags.includes('추가 휴식')).length, 4)
 assert.equal(adjustComfort(result, ['rest'])[0].places.length, result[0].places.length)
})
test('combined reasons compose and preserve essential events without mutating input', () => {
 const snapshot = JSON.stringify(original)
 const [day] = adjustComfort(original, ['places', 'travel', 'walking', 'rest'])
 assert.equal(visits(day).length, 1)
 assert.ok(visits(day)[0].transport)
 assert.ok(day.places.some(item => item.tags.includes('추가 휴식')))
 assert.equal(day.places[0].place, '출발')
 assert.equal(day.places.at(-1).place, '귀가')
 assert.equal(JSON.stringify(original), snapshot)
 assert.equal(new Set(day.places.map(item => item.time)).size, day.places.length)
})
test('tight schedules do not create overlapping rest stops', () => {
 const tight = [{ ...original[0], places: [item('10:00', 'A', ['관광']), item('10:10', '귀가', ['귀가'])]}]
 assert.equal(adjustComfort(tight, ['rest'])[0].places.length, 2)
})
test('new reasons replace earlier changes and notices using original plan', () => {
  const first = rebuildComfortPlan({ days: original }, ['places', 'rest'])
  assert.equal(visits(first.days[0]).length, 2)
  const second = rebuildComfortPlan(first, ['walking'])
  assert.equal(visits(second.days[0]).length, 4)
  assert.ok(!second.days[0].places.some(item => item.tags.includes('추가 휴식')))
  assert.deepEqual(second.days, adjustComfort(original, ['walking']))
  assert.deepEqual(second.originalDays, original)
})
test('repeating the same request does not progressively remove more places', () => {
  const first = rebuildComfortPlan({ days: original }, ['places'])
  const second = rebuildComfortPlan(first, ['places'])
  assert.deepEqual(first.days, second.days)
})
test('replacement survives serialization and remains isolated between trips', () => {
  const stored = JSON.parse(JSON.stringify(rebuildComfortPlan({ days: original }, ['walking'])))
  const replaced = rebuildComfortPlan(stored, ['rest'])
  assert.deepEqual(replaced.days, adjustComfort(original, ['rest']))
  assert.ok(visits(replaced.days[0]).every(item => !item.transport))
  assert.deepEqual(original[0].places[1].tags, ['관광'])
})
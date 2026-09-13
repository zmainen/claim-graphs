// The JS reader, checked against the same facts the Python side pins.
//
//   node js/test-claim-set.mjs
//
// The one that matters is the cyclic projection. The graph is cyclic by construction — a
// hypothesis `entails` a prediction and the prediction `tests` it back — and a naive tree walk
// over it does not return. Nothing else here would catch that: every other test passes on a
// reader that hangs.

import { claimSet } from './claim-set.mjs'

const UUID = '0b3d5a4e-1c2b-4d3e-8f90-1a2b3c4d5e6f'
const set = (over = {}) => ({
  schemaVersion: '0',
  document: { id: 'd' },
  provenance: { reviewed: 'none' },
  questions: [{ id: 'q1', text: 'Does it?' }],
  claims: [
    { id: 'h', uuid: UUID, text: 'A hypothesis, as the authors put it.', plain: 'Plainly.', type: 'hypothesis' },
    { id: 'p', uuid: UUID, text: 'A prediction.', type: 'prediction' },
    { id: 'r', uuid: UUID, text: 'A result.', type: 'empirical' }
  ],
  edges: [
    { from: 'h', rel: 'entails', to: 'p' },
    { from: 'r', rel: 'tests', to: 'p' },
    { from: 'p', rel: 'tests', to: 'h' }   // the cycle: p tests h, h entails p
  ],
  ...over
})

let failed = 0
const check = (name, fn) => {
  try { fn(); console.log(`PASS  ${name}`) } catch (e) { failed++; console.log(`FAIL  ${name}: ${e.message}`) }
}
const eq = (a, b, what) => {
  const [x, y] = [JSON.stringify(a), JSON.stringify(b)]
  if (x !== y) throw new Error(`${what || ''} ${x} !== ${y}`)
}

check('a non-claim-set is refused rather than half-read', () => {
  for (const bad of [null, {}, { claims: 'no' }, 42]) {
    let threw = false
    try { claimSet(bad) } catch { threw = true }
    if (!threw) throw new Error(`accepted ${JSON.stringify(bad)}`)
  }
})

check('has() is the check an editor does before accepting a mark', () => {
  const s = claimSet(set())
  eq(s.has('h'), true); eq(s.has('nope'), false)
})

check('keys() is document order, for completion', () => eq(claimSet(set()).keys(), ['h', 'p', 'r']))

check('text() prefers the plain wording, and can be asked for the authors\'', () => {
  const s = claimSet(set())
  eq(s.text('h'), 'Plainly.')
  eq(s.text('h', { plain: false }), 'A hypothesis, as the authors put it.')
  eq(s.text('p'), 'A prediction.')          // no plain wording: falls back
  eq(s.text('nope'), undefined)
})

check('edges() reaches both directions; out() and into() do not', () => {
  const s = claimSet(set())
  eq(s.edges('p').length, 3)
  eq(s.out('p').map(e => e.to), ['h'])
  eq(s.into('p').map(e => e.from), ['h', 'r'])
  eq(s.out('r', 'tests').length, 1)
  eq(s.out('r', 'supports').length, 0)
})

check('view() terminates on a cycle instead of recurring for ever', () => {
  const s = claimSet(set())
  const v = s.view({ follow: ['entails', 'tests'] })
  eq(v.length, 1, 'one hypothesis root')
  eq(v[0].key, 'h')
  eq(v[0].children.map(c => c.key), ['p'])
  // h -> p -> h would be the cycle; the walk stops at the already-visited h.
  eq(v[0].children[0].children.map(c => c.key), [])
})

check('view() over the whole corpus-shaped fan-out still terminates', () => {
  const claims = Array.from({ length: 200 }, (_, i) => ({ id: `c${i}`, uuid: UUID, text: 't', type: i ? 'empirical' : 'hypothesis' }))
  const edges = []
  for (let i = 0; i < 200; i++) for (let j = 0; j < 200; j++) if (i !== j) edges.push({ from: `c${i}`, rel: 'supports', to: `c${j}` })
  const t0 = Date.now()
  claimSet({ ...set(), claims, edges }).view({ follow: ['supports'] })
  if (Date.now() - t0 > 5000) throw new Error('a fully connected 200-node graph took over 5s')
})

check('a paper with no hypothesis yields no roots, which is true not broken', () => {
  const s = claimSet(set({ claims: [{ id: 'r', uuid: UUID, text: 'A result.', type: 'empirical' }], edges: [] }))
  eq(s.view(), [])
})

check('unaccounted() is the coverage denominator', () => {
  const s = claimSet(set())
  eq(s.unaccounted([]), ['h', 'p', 'r'])
  eq(s.unaccounted(['h', 'r']), ['p'])
})

check('dangling() finds what the schema cannot say', () => {
  const s = claimSet(set({ edges: [{ from: 'h', rel: 'supports', to: 'absent' }], questions: [] }))
  const d = s.dangling()
  if (!d.some(m => m.includes("to 'absent'"))) throw new Error('missed a dangling edge')
  eq(d.filter(m => m.includes('addresses')).length, 0)   // no claim addresses anything here
})

check('reviewed defaults to none rather than to silence', () => {
  eq(claimSet(set({ provenance: {} })).reviewed, 'none')
  eq(claimSet(set()).reviewed, 'none')
})

console.log(`\n${failed ? failed + ' failed' : 'all passed'}`)
process.exit(failed ? 1 : 0)

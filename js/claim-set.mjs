// Reading a claim set. No dependencies, no build step, no network.
//
// The interchange form is `schema/claim-set-v0.schema.json` — one JSON document per source
// document. This is the consumer side of it, for a tool that wants to resolve a claim key to a
// claim: tika's `claim=KEY` marks, an editor offering completion, a viewer drawing a lane.
//
// It deliberately does not fetch. A caller passes a parsed object, because where the set comes
// from is the caller's business — a file beside the manuscript, a bundled fixture, a URL — and an
// editor that needs the network to render a mark is worse than one that does not.
//
// The graph is directed, typed, multi-edged and CYCLIC: a hypothesis `entails` a prediction and
// the prediction `tests` the hypothesis, and both directions carry information. Nothing here
// walks the graph transitively for that reason; `view()` projects a tree and says how.

const WILDCARD = '*'

/** Wrap a parsed claim set. Throws only if it is not a claim set at all. */
export function claimSet (doc) {
  if (!doc || typeof doc !== 'object' || !Array.isArray(doc.claims)) {
    throw new TypeError('not a claim set: expected an object with a `claims` array')
  }

  const byId = new Map(doc.claims.filter(c => c && c.id).map(c => [c.id, c]))
  const edges = Array.isArray(doc.edges) ? doc.edges.filter(e => e && e.from && e.rel) : []

  const out = {
    /** The raw document, for anything this wrapper does not cover. */
    doc,

    /** The source document's identity. */
    document: doc.document || {},

    /**
     * Whether a person has checked any of this. `none` means every claim and edge is machine
     * output that nobody has verified — a viewer showing these should say so.
     */
    reviewed: (doc.provenance || {}).reviewed || 'none',

    /** Every claim key, in document order. For completion, and for `has`. */
    keys: () => [...byId.keys()],

    /** True if `key` names a claim here — the check an editor does before accepting a mark. */
    has: key => byId.has(key),

    /** One claim, or undefined. */
    claim: key => byId.get(key),

    /**
     * The wording to show a reader: the plain sentence where there is one, else the document's
     * own. `plain` exists because the authors' sentence carries statistics and jargon that a
     * margin note cannot hold.
     */
    text: (key, { plain = true } = {}) => {
      const c = byId.get(key)
      if (!c) return undefined
      return (plain && c.plain) || c.text
    },

    /** Every edge touching `key`, in either direction. */
    edges: key => edges.filter(e => e.from === key || e.to === key),

    /** Edges out of `key`, optionally of one relation. */
    out: (key, rel) => edges.filter(e => e.from === key && (!rel || e.rel === rel)),

    /** Edges into `key`, optionally of one relation. */
    into: (key, rel) => edges.filter(e => e.to === key && (!rel || e.rel === rel)),

    /** The questions the document set out to answer. */
    questions: () => doc.questions || [],

    /**
     * Claim keys that `asserted` does not account for — the coverage denominator.
     *
     * A tool marking up a document knows which claims its marks name; the set supplies what
     * there was to name. Sorted, so a diff between two runs is readable.
     */
    unaccounted: asserted => {
      const seen = new Set(asserted || [])
      return [...byId.keys()].filter(k => !seen.has(k)).sort()
    },

    /**
     * An acyclic projection, for anything that needs a tree. Walks `follow` in order and stops
     * at the first already-visited node, which is what makes the result a tree rather than a
     * hang. Returns `{key, rel, children}` roots.
     */
    view: ({ roots, follow = ['entails', 'tests', 'supports'] } = {}) => {
      const seen = new Set()
      const walk = (key, rel) => {
        seen.add(key)
        const children = []
        for (const r of follow) {
          for (const e of edges) {
            if (e.from !== key || e.rel !== r) continue
            if (e.to === WILDCARD || seen.has(e.to) || !byId.has(e.to)) continue
            children.push(walk(e.to, e.rel))
          }
        }
        return { key, rel, children }
      }
      const start = (roots && roots.length)
        ? roots
        : doc.claims.filter(c => c.type === 'hypothesis').map(c => c.id)
      return start.filter(k => byId.has(k) && !seen.has(k)).map(k => walk(k, null))
    },

    /**
     * References that do not resolve. The schema cannot express this — JSON Schema has no way to
     * say "this string is a key elsewhere in the document" — and a dangling edge is the defect
     * this corpus actually had. Same checks as the Python `validate`, minus the shape ones.
     */
    dangling: () => {
      const problems = []
      const qs = new Set((doc.questions || []).map(q => q && q.id))
      edges.forEach((e, i) => {
        if (!byId.has(e.from) && !String(e.from).includes(':')) {
          problems.push(`edges/${i}: from '${e.from}' is not a claim in this set`)
        }
        if (e.to === WILDCARD) {
          if (e.rel !== 'scopes') problems.push(`edges/${i}: only \`scopes\` may target '*'`)
        } else if (!byId.has(e.to) && !String(e.to).includes(':')) {
          problems.push(`edges/${i}: to '${e.to}' is not a claim in this set`)
        }
      })
      for (const c of doc.claims) {
        for (const q of c.addresses || []) {
          if (!qs.has(q)) problems.push(`claims/${c.id}: addresses '${q}', not a question here`)
        }
      }
      return problems
    }
  }
  return out
}

export default claimSet

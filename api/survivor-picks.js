// Shared, cross-device storage for the /survivor pool's official picks.
//
//   GET  /api/survivor-picks  -> { picks, updatedAt, source }   (public, never cached)
//   POST /api/survivor-picks  -> body { picks }, header x-survivor-passcode
//
// Picks live in Vercel Blob. Every save writes a new, uniquely named blob, and reads
// take the newest one, so a read can never be served a stale CDN-cached copy. Older
// versions are kept (up to KEEP_VERSIONS) as an undo history.
//
// Writes require SURVIVOR_EDIT_PASSCODE (set in the Vercel project's environment
// variables). Without it, the endpoint is read-only.
import { readFileSync } from 'node:fs';
import { createHash, timingSafeEqual } from 'node:crypto';
import { put, list, del } from '@vercel/blob';

const PREFIX = 'survivor/picks-';
const KEEP_VERSIONS = 50;
const MAX_BODY_BYTES = 20_000;
const DOUBLE_WEEKS = new Set([6, 11, 12, 13, 16, 17, 18]);
const TEAMS = new Set([
  'ARI', 'ATL', 'BAL', 'BUF', 'CAR', 'CHI', 'CIN', 'CLE', 'DAL', 'DEN', 'DET', 'GB',
  'HOU', 'IND', 'JAX', 'KC', 'LA', 'LAC', 'LV', 'MIA', 'MIN', 'NE', 'NO', 'NYG',
  'NYJ', 'PHI', 'PIT', 'SEA', 'SF', 'TB', 'TEN', 'WAS',
]);

// The checked-in picks.json seeds the store until the first save through this endpoint.
function seedPicks() {
  try {
    return JSON.parse(readFileSync(new URL('../survivor/picks.json', import.meta.url), 'utf8'));
  } catch {
    return {};
  }
}

async function versions() {
  const blobs = [];
  let cursor;
  do {
    const page = await list({ prefix: PREFIX, cursor, limit: 1000 });
    blobs.push(...page.blobs);
    cursor = page.hasMore ? page.cursor : undefined;
  } while (cursor);
  return blobs.sort((a, b) => new Date(b.uploadedAt) - new Date(a.uploadedAt));
}

async function readCurrent() {
  const [latest] = await versions();
  if (!latest) return { picks: seedPicks(), updatedAt: null, source: 'seed' };
  const res = await fetch(latest.url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Blob read failed: ${res.status}`);
  return { picks: await res.json(), updatedAt: latest.uploadedAt, source: 'blob' };
}

function passcodeOk(given) {
  const expected = process.env.SURVIVOR_EDIT_PASSCODE;
  if (!expected || typeof given !== 'string' || !given) return false;
  const a = createHash('sha256').update(given).digest();
  const b = createHash('sha256').update(expected).digest();
  return timingSafeEqual(a, b);
}

// Returns a cleaned copy of the picks, or throws with a human-readable reason.
function validate(picks) {
  if (!picks || typeof picks !== 'object' || Array.isArray(picks)) throw new Error('picks must be an object');
  const clean = {};
  const seen = new Map();
  for (const [wk, record] of Object.entries(picks)) {
    const w = Number(wk);
    if (!Number.isInteger(w) || w < 1 || w > 18) throw new Error(`bad week "${wk}"`);
    if (!record || typeof record !== 'object') throw new Error(`week ${w}: bad record`);
    const picked = record.picked ?? [];
    const recommended = record.recommended ?? [];
    for (const [name, arr] of [['picked', picked], ['recommended', recommended]]) {
      if (!Array.isArray(arr) || arr.some((t) => !TEAMS.has(t))) throw new Error(`week ${w}: bad ${name} list`);
    }
    const max = DOUBLE_WEEKS.has(w) ? 2 : 1;
    if (picked.length > max) throw new Error(`week ${w} allows ${max} pick(s)`);
    for (const t of picked) {
      if (seen.has(t)) throw new Error(`${t} is already used in week ${seen.get(t)}`);
      seen.set(t, w);
    }
    if (!picked.length && !recommended.length) continue;
    clean[String(w)] = recommended.length ? { picked, recommended } : { picked };
  }
  return clean;
}

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  try {
    if (req.method === 'GET') {
      return res.status(200).json(await readCurrent());
    }

    if (req.method === 'POST') {
      if (!process.env.SURVIVOR_EDIT_PASSCODE) {
        return res.status(503).json({ error: 'Editing is not set up yet (SURVIVOR_EDIT_PASSCODE is missing).' });
      }
      if (!passcodeOk(req.headers['x-survivor-passcode'])) {
        return res.status(401).json({ error: 'Wrong passcode.' });
      }
      const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : req.body || {};
      if (JSON.stringify(body).length > MAX_BODY_BYTES) return res.status(413).json({ error: 'Too large.' });

      let picks;
      try {
        picks = validate(body.picks);
      } catch (e) {
        return res.status(400).json({ error: e.message });
      }

      const blob = await put(`${PREFIX}${Date.now()}.json`, JSON.stringify(picks), {
        access: 'public',
        addRandomSuffix: true,
        contentType: 'application/json',
      });

      const old = (await versions()).slice(KEEP_VERSIONS);
      if (old.length) await del(old.map((b) => b.url));

      return res.status(200).json({ picks, updatedAt: blob.uploadedAt ?? new Date().toISOString(), source: 'blob' });
    }

    res.setHeader('Allow', 'GET, POST');
    return res.status(405).json({ error: 'Method not allowed' });
  } catch (e) {
    console.error(e);
    return res.status(500).json({ error: 'Server error' });
  }
}

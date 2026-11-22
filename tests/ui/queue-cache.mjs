import assert from 'node:assert/strict';
import { api } from '../../web/src/desk/api.js';

let calls = 0;
let release;
globalThis.fetch = async () => {
  calls += 1;
  if (calls === 1) await new Promise((resolve) => { release = resolve; });
  return { ok: true, text: async () => JSON.stringify({ items: [], total: calls }) };
};

const old = api.queue('review', {});
await Promise.resolve();
api.clearCases();
release();
await old;
const fresh = await api.queue('review', {});
assert.equal(calls, 2, 'odpowiedź sprzed unieważnienia nie może trafić do cache');
assert.equal(fresh.total, 2);
await api.queue('review', {});
assert.equal(calls, 2, 'powrót korzysta z cache');
api.clearCases();
await api.queue('review', {});
assert.equal(calls, 3, 'koniec serii zdarzeń usuwa cache wypełniony podczas serii');
console.log('queue cache: żądanie w locie, powrót i koniec serii zdarzeń OK');

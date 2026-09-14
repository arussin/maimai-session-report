import assert from 'node:assert/strict';
import test from 'node:test';
import { getIntlCatalog, describeFailure } from '../adapters/tomomai/catalog.mjs';

const versions = { currentVersion: 13, versions: [{ id: 12, name: 'Previous' }, { id: 13, name: 'Current' }] };
const song = { songId: 'abcd1234:i13', songName: 'Synthetic chart', cover: '/res/icons/base.png',
  region: 'intl', gameVersion: 13, type: 'dx', difficulty: 'expert' };
const response = (body, status = 200) => ({ ok: status === 200, status, json: async () => body });
function mockFetch(...responses) {
  const calls = [];
  const fetcher = async (url, options) => {
    calls.push({ url, options });
    assert.ok(responses.length, 'Unexpected network request');
    const next = responses.shift();
    if (next instanceof Error) throw next;
    return next;
  };
  return { calls, fetcher };
}

test('discovers INTL current version before fetching exactly that catalogue', async () => {
  const { fetcher, calls } = mockFetch(response(versions), response({ songs: [song] }));
  const catalog = await getIntlCatalog(fetcher);
  assert.deepEqual([...catalog.values()], [song]);
  assert.deepEqual(calls.map(c => c.url), [
    'https://tomomai.lol/api/v1/songs/versions?region=intl',
    'https://tomomai.lol/api/v1/songs?region=intl&gameVersion=13',
  ]);
  for (const { options } of calls) {
    assert.deepEqual(Object.keys(options), ['signal']);
    assert.ok(options.signal instanceof AbortSignal);
  }
});

test('uses the declared current version, not the largest known version', async () => {
  const { fetcher, calls } = mockFetch(response({ ...versions, versions: [...versions.versions, { id: 99 }] }), response({ songs: [song] }));
  await getIntlCatalog(fetcher);
  assert.ok(calls[1].url.endsWith('gameVersion=13'));
});

test('accepts supported Utage entries and null jackets for the renderer fallback', async () => {
  const entry = { ...song, type: 'utage', difficulty: 'utage', cover: null };
  const catalog = await getIntlCatalog(mockFetch(response(versions), response({ songs: [entry] })).fetcher);
  assert.deepEqual([...catalog.values()], [entry]);
});

test('rejects invalid version metadata before requesting a catalogue', async () => {
  for (const bad of [null, {}, { ...versions, currentVersion: '13' }, { ...versions, currentVersion: 32768 },
    { ...versions, versions: [] }]) {
    const { fetcher, calls } = mockFetch(response(bad));
    await assert.rejects(getIntlCatalog(fetcher), /invalid current international version/);
    assert.equal(calls.length, 1);
  }
});

test('fails closed on missing, empty, malformed, duplicate or wrong-slice songs', async () => {
  for (const body of [{}, { songs: [] }, { songs: [null] }, { songs: [song, song] },
    { songs: [{ ...song, region: 'jp' }] }, { songs: [{ ...song, gameVersion: 12 }] },
    { songs: [{ ...song, type: 'unknown' }] }, { songs: [{ ...song, difficulty: 'unknown' }] }]) {
    await assert.rejects(getIntlCatalog(mockFetch(response(versions), response(body)).fetcher), /B50 catalogue songs:/);
  }
});

test('HTTP errors name the stage and status without reading response bodies or retrying', async () => {
  for (const stage of ['versions', 'songs']) {
    const bad = { ok: false, status: 400, json: () => assert.fail('Must not read an error body') };
    const { fetcher, calls } = stage === 'versions' ? mockFetch(bad) : mockFetch(response(versions), bad);
    await assert.rejects(getIntlCatalog(fetcher), new RegExp(`B50 catalogue ${stage}: HTTP 400`));
    assert.equal(calls.length, stage === 'versions' ? 1 : 2);
  }
});

test('network, TLS, and JSON errors do not expose arbitrary upstream messages', async () => {
  const secret = 'sensitive-upstream-detail';
  const network = new TypeError(secret, { cause: Object.assign(new Error(secret), { code: 'CERT_HAS_EXPIRED' }) });
  for (const next of [network, { ok: true, status: 200, json: async () => { throw new SyntaxError(secret); } }]) {
    await assert.rejects(getIntlCatalog(mockFetch(next).fetcher), e => {
      assert.ok(describeFailure(e).startsWith('B50 catalogue versions:'));
      assert.ok(!describeFailure(e).includes(secret));
      return true;
    });
  }
  assert.ok(!describeFailure(new Error(secret)).includes(secret));
});

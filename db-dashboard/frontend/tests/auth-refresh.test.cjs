const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');

const source = ts.transpileModule(readFileSync('app/lib/api.ts', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const json = (data, status = 200) => new Response(JSON.stringify(data), { status });
const unauthorized = () => json({ error: { code: 'invalid_token', message: 'Expired' } }, 401);

function setup(fetch, extra = {}) {
  const values = new Map([['neuro_token', 'expired'], ['neuro_user', '{"role_key":"ADMIN"}']]);
  const storage = {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  };
  const window = new EventTarget();
  const exports = {};
  vm.runInNewContext(source, { exports, fetch, localStorage: storage, window, Headers, FormData, Event, ...extra });
  return { api: exports, storage, window };
}

test('parallel expired requests share one refresh and retry with its new token', async () => {
  let refreshes = 0;
  const { api, storage } = setup(async (url, init) => {
    if (url.endsWith('/refresh')) {
      refreshes++;
      await new Promise(resolve => setTimeout(resolve, 5));
      assert.equal(init.credentials, 'include');
      return json({ access_token: 'renewed' });
    }
    return init.headers.get('Authorization') === 'Bearer renewed' ? json({ ok: true }) : unauthorized();
  });
  const results = await Promise.all(['/campaign', '/benchmark', '/batches'].map(path => api.apiRequest(path)));
  assert.ok(results.every(value => value.ok));
  assert.equal(refreshes, 1);
  assert.equal(storage.getItem('neuro_token'), 'renewed');
});

test('late 401 response uses the already refreshed token without rotating again', async () => {
  let refreshes = 0;
  const { api } = setup(async (url, init) => {
    if (url.endsWith('/refresh')) { refreshes++; return json({ access_token: 'renewed' }); }
    if (init.headers.get('Authorization') === 'Bearer renewed') return json({ ok: true });
    if (url === '/slow') await new Promise(resolve => setTimeout(resolve, 15));
    return unauthorized();
  });
  await Promise.all([api.apiRequest('/fast'), api.apiRequest('/slow')]);
  assert.equal(refreshes, 1);
});

test('invalid refresh clears the cached role and emits session expiry', async () => {
  const { api, storage, window } = setup(async () => unauthorized());
  let expired = 0;
  window.addEventListener(api.SESSION_EXPIRED_EVENT, () => expired++);
  await assert.rejects(api.apiRequest('/campaign'), error => error.status === 401);
  assert.equal(storage.getItem('neuro_token'), null);
  assert.equal(storage.getItem('neuro_user'), null);
  assert.equal(expired, 1);
});

test('a second 401 stops after one retry and clears stale session state', async () => {
  let refreshes = 0, attempts = 0;
  const { api, storage } = setup(async url => {
    if (url.endsWith('/refresh')) { refreshes++; return json({ access_token: 'renewed' }); }
    attempts++; return unauthorized();
  });
  await assert.rejects(api.apiRequest('/campaign'), error => error.status === 401);
  assert.equal(refreshes, 1);
  assert.equal(attempts, 2);
  assert.equal(storage.getItem('neuro_user'), null);
});

test('wrong login credentials do not trigger session refresh', async () => {
  let requests = 0;
  const { api } = setup(async () => { requests++; return unauthorized(); });
  await assert.rejects(api.apiRequest('/api/v1/auth/login', { method: 'POST', body: '{}' }));
  assert.equal(requests, 1);
});

test('temporary refresh failure retains the stored session for a later retry', async () => {
  const { api, storage } = setup(async url => url.endsWith('/refresh') ? json({}, 503) : unauthorized());
  await assert.rejects(api.apiRequest('/campaign'), error => error.status === 503);
  assert.equal(storage.getItem('neuro_token'), 'expired');
  assert.ok(storage.getItem('neuro_user'));
});

test('CSV FormData and its browser-generated boundary survive an authentication retry', async () => {
  const form = new FormData(); form.append('file', new Blob(['review_id\nr1']), 'reviews.csv');
  let attempts = 0;
  const { api } = setup(async (url, init) => {
    if (url.endsWith('/refresh')) return json({ access_token: 'renewed' });
    assert.equal(init.body, form);
    assert.equal(init.headers.has('Content-Type'), false);
    assert.equal(init.method, 'POST');
    attempts++;
    return attempts === 1 ? unauthorized() : json({ accepted_count: 1 });
  });
  assert.equal((await api.apiRequest('/batch-analyses', { method: 'POST', body: form })).accepted_count, 1);
  assert.equal(attempts, 2);
});

test('a pending refresh cannot resurrect a session after logout', async () => {
  let resolveRefresh;
  const { api, storage } = setup(async url => {
    if (url.endsWith('/refresh')) return new Promise(resolve => { resolveRefresh = resolve; });
    return unauthorized();
  });
  const request = api.apiRequest('/campaign');
  while (!resolveRefresh) await new Promise(resolve => setImmediate(resolve));
  api.clearSession();
  resolveRefresh(json({ access_token: 'renewed' }));
  await assert.rejects(request, error => error.code === 'session_changed');
  assert.equal(storage.getItem('neuro_token'), null);
});

test('a pending refresh does not overwrite a subsequent login', async () => {
  let resolveRefresh;
  const { api, storage } = setup(async url => {
    if (url.endsWith('/refresh')) return new Promise(resolve => { resolveRefresh = resolve; });
    return unauthorized();
  });
  const request = api.apiRequest('/campaign');
  while (!resolveRefresh) await new Promise(resolve => setImmediate(resolve));
  api.saveSession('other-session', { role_key: 'RESEARCHER' });
  resolveRefresh(json({ access_token: 'old-refresh-result' }));
  await assert.rejects(request, error => error.code === 'session_changed');
  assert.equal(storage.getItem('neuro_token'), 'other-session');
});

test('refresh observes a token renewed by another browser tab while waiting for its lock', async () => {
  let lockedOperation, fetches = 0;
  const { api, storage } = setup(async () => { fetches++; return fetches === 1 ? unauthorized() : json({ ok: true }); }, {
    navigator: { locks: { request: async (_name, operation) => {
      lockedOperation = operation;
      await new Promise(resolve => setTimeout(resolve, 5));
      return operation();
    } } },
  });
  const request = api.apiRequest('/campaign');
  while (!lockedOperation) await new Promise(resolve => setImmediate(resolve));
  storage.setItem('neuro_token', 'renewed-in-other-tab');
  assert.equal((await request).ok, true);
  assert.equal(fetches, 2);
});

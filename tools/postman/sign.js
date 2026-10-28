// Collection pre-request script: every request is signed with the environment's API key
// (RFC 9421 HTTP Message Signatures, Ed25519), the way platform/apikeys/signing.py
// verifies it. Before the first call (and when the token expires) it exchanges the key
// for an access token at POST /v1/auth/token. Needs the environment variables base_url,
// key_id and private_key (the PEM the key was issued with). MG_NACL is TweetNaCl, prepended.

// The sandbox modules (the bare globals of the same names are deprecated).
const cryptoJs = require('crypto-js');
const decodeBase64 = require('atob');
const encodeBase64 = require('btoa');
const ACCESS = 'mg_access_token';
const UNTIL = 'mg_access_until';

function utf8Bytes(text) {
  const binary = unescape(encodeURIComponent(text));
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) out[i] = binary.charCodeAt(i);
  return out;
}

function toBase64(bytes) {
  let binary = '';
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
  return encodeBase64(binary);
}

// An Ed25519 PKCS#8 PEM ends with the 32-byte seed.
function secretKey(pem) {
  const binary = decodeBase64(pem.replace(/-----[^-]+-----/g, '').replace(/\s+/g, ''));
  const seed = new Uint8Array(32);
  for (let i = 0; i < 32; i += 1) seed[i] = binary.charCodeAt(binary.length - 32 + i);
  return MG_NACL.sign.keyPair.fromSeed(seed).secretKey;
}

function nonce() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let out = '';
  for (let i = 0; i < 24; i += 1) out += chars[Math.floor(Math.random() * chars.length)];
  return out;
}

function contentDigest(body) {
  return 'sha-256=:' + cryptoJs.SHA256(cryptoJs.enc.Utf8.parse(body)).toString(cryptoJs.enc.Base64) + ':';
}

function signedHeaders(method, path, query, body, token) {
  const headers = { 'content-digest': contentDigest(body) };
  if (token) headers.authorization = 'Signed ' + token;
  const components = ['@method', '@path', '@query', 'content-digest'];
  if (token) components.push('authorization');
  const values = {
    '@method': method.toUpperCase(),
    '@path': path,
    '@query': '?' + query,
    'content-digest': headers['content-digest'],
    authorization: headers.authorization,
  };
  const params = '(' + components.map((c) => '"' + c + '"').join(' ') + ')'
    + ';created=' + Math.floor(Date.now() / 1000) + ';nonce="' + nonce() + '"'
    + ';keyid="' + pm.environment.get('key_id') + '";alg="ed25519"';
  const base = components.map((c) => '"' + c + '": ' + values[c]).join('\n')
    + '\n"@signature-params": ' + params;
  const key = secretKey(pm.environment.get('private_key'));
  const signature = MG_NACL.sign.detached(utf8Bytes(base), key);
  headers['signature-input'] = 'sig1=' + params;
  headers.signature = 'sig1=:' + toBase64(signature) + ':';
  return headers;
}

function splitUrl(url) {
  const match = /^https?:\/\/[^/]+(\/[^?#]*)(?:\?([^#]*))?/.exec(url);
  return { path: match ? match[1] : '/', query: match && match[2] ? match[2] : '' };
}

function withToken(next) {
  const token = pm.collectionVariables.get(ACCESS);
  if (token && Number(pm.collectionVariables.get(UNTIL)) > Date.now()) return next(token);
  const base = pm.environment.get('base_url').replace(/\/$/, '');
  const body = '{}';
  const headers = signedHeaders('POST', '/v1/auth/token', '', body, '');
  pm.sendRequest({
    url: base + '/v1/auth/token',
    method: 'POST',
    header: Object.keys(headers).map((k) => ({ key: k, value: headers[k] }))
      .concat([{ key: 'content-type', value: 'application/json' }]),
    body: { mode: 'raw', raw: body },
  }, (err, res) => {
    if (err || res.code !== 200) {
      throw new Error('token exchange failed: ' + (err || res.code + ' ' + res.text()));
    }
    const pair = res.json();
    pm.collectionVariables.set(ACCESS, pair.access_token);
    pm.collectionVariables.set(UNTIL, String(Date.now() + (pair.expires_in - 60) * 1000));
    next(pair.access_token);
  });
}

withToken((token) => {
  const url = splitUrl(pm.variables.replaceIn(pm.request.url.toString()));
  const raw = pm.request.body && pm.request.body.mode === 'raw' ? pm.request.body.raw : '';
  const body = pm.variables.replaceIn(raw || '');
  if (raw) pm.request.body.update(body);
  const headers = signedHeaders(pm.request.method, url.path, url.query, body, token);
  Object.keys(headers).forEach((k) => pm.request.headers.upsert({ key: k, value: headers[k] }));
});

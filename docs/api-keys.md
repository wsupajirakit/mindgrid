# Calling the API with a key

Machines (scripts, the CLI, other systems) call the API with an **API key**. A browser
session cookie is not accepted for machine calls, and no secret ever travels in a request.

## The key

- A superadmin issues it (UI: *API keys*, or `POST /v1/admin/api-keys`) for one user, with
  scopes (`read` = GET, `edit` = every other write, `run` = run endpoints), an optional list
  of projects, and a lifetime.
- It is an **Ed25519** key pair. The server stores only the public key. The private key is
  shown once (or the caller brings its own key pair and sends only the public key, PEM).
- A key never has superadmin rights; it acts as its owner, limited to its projects.

## Every request is signed (RFC 9421)

| Header | Value |
|--|--|
| `Content-Digest` | `sha-256=:<base64 SHA-256 of the body>:` (RFC 9530; empty body too) |
| `Signature-Input` | `sig1=("@method" "@path" "@query" "content-digest" ["authorization"]);created=<unix s>;nonce="<random>";keyid="<mgk_…>";alg="ed25519"` |
| `Signature` | `sig1=:<base64 Ed25519 signature of the signature base>:` |
| `Authorization` | `Signed <access token>` — every call except the three token endpoints |

The server refuses a request when `created` is more than **300 seconds** from its clock, when
a nonce is reused, when any covered part (method, path, query, body, token) changed, or when
the key is expired, revoked or its owner disabled.

**Rotating.** *API keys → Rotate* (`POST /v1/admin/api-keys/{id}/rotate`, superadmin) makes
a new key pair with the same owner, name, scopes, projects and lifetime.

- The new private key is returned once; the UI shows it to copy.
- The old key and every token issued for it stop working immediately, so put the new key
  everywhere the old one was used.
- A revoked key cannot be rotated.

## Tokens

1. `POST /v1/auth/token` (signed, no token) → `access_token` (15 min) + `refresh_token`.
2. Call the API with `Authorization: Signed <access_token>` **and** the signature.
3. `POST /v1/auth/token/refresh` `{"refresh_token": …}` (signed) → a new pair. A refresh
   token works once; presenting a used one again revokes every token of that sign-in.
4. `POST /v1/auth/token/revoke` `{"token": …}` (signed) ends that sign-in's tokens.

A stolen access token is useless on its own: every call also needs the private key's
signature.

## Python

```python
from mindgrid.platform.apikeys.client import KeyCredentials, Outgoing, signed_headers

creds = KeyCredentials.from_pem("mgk_…", private_key_pem)
headers = signed_headers(creds, Outgoing("GET", "/v1/projects", token=access_token))
```

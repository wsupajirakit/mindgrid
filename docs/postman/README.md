# Postman

`api.postman_collection.json` calls the API with a project API key. API keys sign every
request (RFC 9421 HTTP Message Signatures with Ed25519; see [api-keys.md](../api-keys.md)),
which Postman cannot do on its own. The collection's script does it, using TweetNaCl
(public domain, vendored in `tools/postman/vendor`). It also exchanges the key for an access
token before the first request, so pressing Send is enough.

## Use it

1. Import `api.postman_collection.json`.
2. Import the environment for your project:
   - `tools/demo_projects.py` writes one per API project to
     `~/.config/mindgrid/postman/<project>.postman_environment.json` (file mode 600, because
     it holds the private key);
   - or create one with `base_url`, `project_slug`, `key_id` and `private_key` (the PEM
     shown once when the key was issued, as a secret variable).
3. Pick the environment and run **Projects → List projects** first. It finds the key's
   project and keeps its id for the other requests.
4. Run the requests in order, or run the whole collection. Each request checks its own
   answer. The other requests:
   - categories;
   - recall and context pack (they ask the environment's `question`, set per project);
   - the project's playbooks, one run and its result;
   - datasets and their first rows.

The key only reaches its own project. Its scopes (read, run) decide what the requests may
do.

## Run it from a terminal

    npx newman run docs/postman/api.postman_collection.json \
        -e ~/.config/mindgrid/postman/<project>.postman_environment.json

## Change it

The collection is generated: edit `tools/postman_collection.py` or `tools/postman/sign.js`,
then run `backend/.venv/bin/python tools/postman_collection.py`. The gate fails when the
committed file is out of date.

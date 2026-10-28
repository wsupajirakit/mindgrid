# CLI and MCP: using the knowledge base from bash, Claude Code or a local LLM

Every call goes through the API with an **API key** (signed requests, see
[api-keys.md](api-keys.md)), so a tool has exactly the rights of the key's owner, limited to
the key's projects. Retrieval (hybrid search, reranking, cutoff, citations) is the same
whichever model writes the final answer.

## 1. Get a key and save a profile

1. A superadmin issues a key (UI → *API keys*) with scopes `read` (search, Context Pack) and,
   for server-written answers, `run`.
2. Save the private key in a file only you can read:

   ```bash
   mkdir -p ~/.config/mindgrid/keys && chmod 700 ~/.config/mindgrid
   # paste the private key shown once into the file, then:
   chmod 600 ~/.config/mindgrid/keys/main.pem
   ```

3. Save the profile (the command checks it against the server):

   ```bash
   mindgrid login --server https://mindgrid.example.com --key-id mgk_… \
     --key-file ~/.config/mindgrid/keys/main.pem --profile default
   ```

Profiles live in `~/.config/mindgrid/profiles.json`; tokens are cached per profile in
`~/.cache/mindgrid/tokens/` (owner-only files; a token is useless without the private key).
A key file readable by anyone else is refused.

## 2. bash (scripts, a local LLM)

| Command | Does |
|--|--|
| `mindgrid projects` | projects the key can read |
| `mindgrid categories -p <slug>` | categories of a project |
| `mindgrid pack "<question>" -p <slug>` | the Context Pack: rules + passages P1…Pn |
| `mindgrid ask "<question>" -p <slug> [--llm local\|gemini]` | a server-written answer with its citation check |
| `mindgrid verify --refs P1,P2 < answer.txt` | exit 0 = every citation exists and every paragraph has one, 2 = not |

Add `--json` for the raw response and `--profile <name>` to use another profile
(or set `MINDGRID_PROFILE`). Exit code 1 = the server refused the call.

A local model answers grounded like this:

```bash
mindgrid pack "why did yields rise?" -p markets > pack.txt
ollama run qwen3:8b "$(cat pack.txt)" > answer.txt
mindgrid verify --refs P1,P2,P3 < answer.txt
```

Start that Ollama server with a context window large enough for a pack
(`OLLAMA_CONTEXT_LENGTH=16384 ollama serve`): its default of 4096 tokens silently drops the
front of a longer prompt, and a pack of eight Thai passages runs about 8,000 tokens. The
server-written answer (`mindgrid ask --llm local`) asks for `MINDGRID_LLM_LOCAL_CONTEXT_TOKENS`
itself and leaves out the lowest-ranked passages when they still do not fit.

## 3. MCP (Claude Code and other MCP clients)

`mindgrid mcp` serves over stdio (MCP 2026-07-28) with the profile's key.

```bash
claude mcp add mindgrid --env MINDGRID_PROFILE=default -- mindgrid mcp
```

| Tool | Use |
|--|--|
| `list_projects` · `list_categories` | find the project slug and category ids |
| `recall(project, question, categories?, k?)` | the passages with references and trust tags, plus the answering rules |
| `answer(project, question, llm?)` | the server writes the answer (needs the `run` scope) |
| `verify_citations(answer, refs)` | unknown references and unsourced paragraphs |

The prompt `grounded_answer(project, question)` sets the rules for one question. The
server's instructions tell the model to call `recall` before answering, to answer only
from the passages and to cite each statement.

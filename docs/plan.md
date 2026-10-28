# MindGrid — แผนโปรเจค (RAG engine กลาง + bridge กับ z-service)

> สถานะ: **ร่างเพื่อเคาะ** (25 ต.ค. 2026) — ยังไม่สร้างโค้ด
> เคาะแล้ว: ชื่อ **MindGrid** (เปลี่ยนชื่อที่แสดงได้ด้วย config จุดเดียว §2) · รอเคาะ: §3 ภาษา (Go/Python) · §4 ฐานข้อมูล (Mongo/Postgres)
> ทุกตัวเลขเวอร์ชันดึงจริงวันนี้จาก endoflife.date · PyPI · npm · GitHub (แหล่งใน §16)

---

## 0. สรุปสั้น

| เรื่อง | ข้อเสนอ |
|--|--|
| ชื่อโปรเจค | **MindGrid** ✅ · repo/folder `mindgrid` · ชื่อที่แสดงเปลี่ยนได้ด้วย config เดียว |
| RAG | hybrid (vector + BM25 · RRF) + rerank เลือกได้ + evals เป็น gate · ทุกขั้นเป็น plugin (§7 จากผลค้นคว้า ต.ค. 2026) |
| ภาษา backend | **Python 3.14** (ไม่ใช่ Go) — เหตุผล §3 |
| ฐานข้อมูล | **PostgreSQL 18 + pgvector 0.8** (ไม่ใช่ Mongo) — เหตุผล §4 |
| UI | React 19.3 + Vite 8 + TanStack Router/Query + Tailwind 4 (ชุดเดียวกับ z-service web/) |
| ลำดับชั้น | **User ใหญ่สุด** → project ของตัวเอง (1:m) → category · superadmin เห็นทุก project (§6) |
| ระบบเรียนรู้จาก stock-radar | **Synapse** — อ่าน diff ของ skill → เข้าใจ → dive ใหม่เฉพาะส่วนที่เปลี่ยน → เสนอให้ review (§9) |
| หุ้น | เป็นแค่ **pack หนึ่ง** (`markets`) ลงใน category หนึ่ง · engine กลางไม่รู้จักหุ้น |

---

## 1. งานข้อ 1 — z-service มีทางเข้าตรงที่ปลอดภัยหรือยัง (ตรวจเฉย ๆ)

**มีแล้ว (บน branch `feat/web-ui` — ใช้ได้จริงหลัง deploy)**
- ทางเข้าเครื่อง: key `zsk_<id>_<secret>` ส่งใน header `Authorization: Bearer` เท่านั้น · server เก็บแค่ SHA-256 · มี scope (`read` / `jobs` / `gold:jobs` / `watchlist:write`) · rate limit ต่อ key · audit ทุกครั้ง · มีวันหมดอายุ · `admin` ออกให้เครื่องไม่ได้
- client สำเร็จรูป: `tools/zsvc_client.py` และ `tools/zsvc_curl.sh` (key จาก env หรือ Keychain · ตรวจ TLS เสมอ · ไม่พิมพ์ key)
- endpoint ที่ดึงได้ตรง ๆ ไม่ผ่าน UI:

| ต้องการ | endpoint | scope |
|--|--|--|
| ชุดใหม่ทั้งหมด 9 ไฟล์ | `GET /api/export_zip?all=true` | read |
| TF เดียว | `GET /api/export_zip?interval=1d` หรือ `/api/export?interval=1d&part=1` | read |
| เฉพาะบางตัว/บาง list | `&list_name=A,B` (คั่นด้วย `,` = เลือกหลายชื่อ) | read |
| formula / ข่าว | `/api/export_formula` · `/api/export_news` | read |
| เช็คความสด | `/api/export/check` · `/api/automate/status` | read |
| ประวัติแท่งรายตัว | `/api/history` | read |
| สั่งดึงรอบใหม่ / รอบ radar | `POST /api/automate` · `/api/auto/start` · `/api/radar_round/run` | jobs |

**ยังขาด / ต้องแก้**
1. stock-radar ยังใช้ทางเก่า: `fetch_csv.sh` · `load_all.sh` ใช้ `PULL_KEY` (รั่วแล้ว) + `curl -k` (**ปิดการตรวจ TLS**) + host ฝังในสคริปต์ · `fill_short_hist.py` · `fetch_new_symbols.py` อ่าน key จากไฟล์/env ⇒ ย้ายไป `zsvc_curl.sh` / `zsvc_client.py` **หลัง deploy** (ตามที่ตกลงไว้)
2. ปรับแต่งการดึงได้น้อย: ไม่มีเลือกจำนวนแท่ง · เลือกคอลัมน์ · ดึงเฉพาะที่เปลี่ยน (`since`) · ETag · รูปแบบอื่นนอกจาก CSV ⇒ แก้ใน bridge API v1 (§10)

---

## 2. ชื่อ: **MindGrid** (เคาะแล้ว 25 ต.ค.) + ชื่อกลางทุกชั้น

**ชื่อที่แสดง (brand) เปลี่ยนได้ด้วย config จุดเดียว** — ยกเว้นชื่อ folder / repo / package (`mindgrid`) ที่คงที่

| สิ่ง | ที่มา | เปลี่ยนชื่อแล้วต้องทำอะไร |
|--|--|--|
| ชื่อบน UI ทุกจุด (title แท็บ · header · หน้า login · footer · email/แจ้งเตือน) | config `brand` จุดเดียว → API สาธารณะ `GET /v1/meta/brand` → web อ่านตอนเปิด | แก้ config อย่างเดียว ไม่ต้อง build ใหม่ |
| ข้อความแปล th/en/it ที่มีชื่อระบบ | ใช้ placeholder `{brand}` เสมอ — ห้ามพิมพ์ชื่อตรง ๆ | ไม่ต้องแก้ไฟล์แปล |
| ชื่อในเอกสาร API (OpenAPI title) · หน้า `/docs` | อ่านจาก config เดียวกันตอนบูต | restart |
| CLI help / banner · MCP server name | อ่านจาก config เดียวกัน (หรือถาม `/v1/meta/brand`) | ไม่ต้องแก้โค้ด |
| logo / favicon / สีหลัก | path ใน config เดียวกัน | เปลี่ยนไฟล์ + config |
| ชื่อ folder · repo · package Python · คำสั่ง CLI `mindgrid` · prefix env `MINDGRID_` | คงที่ (ตัวตนของโค้ด) | — |

- config: `brand.name` · `brand.short_name` · `brand.tagline` · `brand.logo` · `brand.favicon` · `brand.primary_color` (เป็น Settings class หนึ่งแบบ z-service · default = MindGrid)
- **เครื่องมือ `check_brand.py` ใน gate:** หาคำว่า "MindGrid" ในโค้ด/ไฟล์แปล/UI — เจอที่ไหนนอกจาก default ของ config = fail (กันชื่อฝังหลุด)

ชื่อระบบข้างใน (กลางทั้งหมด ไม่มีคำว่าหุ้น ไม่ผูก brand):

| ชั้น | ชื่อ | หน้าที่ |
|--|--|--|
| platform | `auth` · `access` · `tenancy` · `settings` · `audit` · `jobs` | ผู้ใช้ · role · project/category · ค่าตั้ง · log · งานเบื้องหลัง |
| knowledge | `intake` · `library` · `recall` | รับเอกสาร → เก็บ/version → ค้นคืน |
| datasets | `datasets` | ข้อมูลตาราง (CSV แท่งราคา ฯลฯ) สำหรับคำนวณ ไม่ใช่ค้นความหมาย |
| reasoning | `functions` · `playbooks` · `runs` | ฟังก์ชันกลาง · playbook (ประกอบฟังก์ชัน) · ผลการรัน |
| models | `providers` | LLM + embedding + reranker (Gemini / local / ไม่ใช้) |
| quality | `evals` | ชุดคำถามทอง + วัดคุณภาพการค้น/คำตอบต่อเนื่อง |
| learning | **`synapse`** | เรียนรู้จาก repo ต้นทาง (stock-radar เป็นแหล่งแรก) |
| connectors | `bridges` | เชื่อมระบบอื่น (z-service เป็นตัวแรก) |
| interfaces | `api` · `cli` · `mcp` · `web` | ทางเรียกใช้ |
| domain packs | `packs/markets` | ฟังก์ชัน + playbook + ความรู้ของหมวดตลาดหุ้น (pack แรก) |

---

## 3. ภาษา: Go vs Python (เลือก **Python 3.14**)

| เกณฑ์ | Python | Go | ใครชนะ |
|--|--|--|--|
| คำนวณตาราง/ตัวเลข (indicator · backtest · stat) | numpy 2.5 · pandas 3.1 · polars 2.0 · pyarrow 26 (มี wheel 3.14/3.15) | gonum เท่านั้น — ไม่มีเทียบ pandas/polars | **Python** ชัด |
| โค้ดเดิมที่ต้องถอด | stock-radar `radar_lib.py` 2,229 บรรทัด + 40 สคริปต์ = pandas ทั้งหมด · ใช้ parity test เทียบผลได้ทันที (แบบที่ z-service ทำ 9/9) | ต้องเขียนใหม่ทั้งหมด + เสี่ยงผลไม่ตรง | **Python** |
| อ่านเอกสาร (PDF ตาราง · OCR · layout) | docling 2.142 (MIT) · pypdf 6.21 (BSD) | แทบไม่มีระดับเดียวกัน | **Python** |
| embedding/ML ในเครื่อง | fastembed 0.9 · sentence-transformers 6.2 | ต้องเรียกผ่าน server อื่น | **Python** |
| SDK LLM | google-genai 2.33 (official) | genai Go SDK (official) ก็มี | เสมอ |
| framework RAG | ครบ (เราไม่ผูก framework — §7) | eino 0.9 · langchaingo 0.1 (ยังไม่ 1.0) | Python |
| ความเร็ว/หน่วยความจำต่อ request | ช้ากว่า · ใช้ RAM มากกว่า | เร็ว · binary เดียว · concurrency ดี | **Go** |
| scale จริงของงานนี้ | คอขวดคือรอ LLM/embedding + DB ไม่ใช่ CPU ของภาษา · API เป็น stateless ขยายแนวนอน · งานหนักแยก worker process | ได้เปรียบเฉพาะ throughput ของ API ล้วน | **พอกัน** สำหรับงานนี้ |

**สรุป:** Python ทั้งระบบ — งาน 80% คือคำนวณข้อมูล + อ่านเอกสาร + ML ที่ ecosystem อยู่ฝั่ง Python · ใช้ 2 ภาษาตั้งแต่ต้น = หนี้ (ซ้ำ contract · ซ้ำ test · ซ้ำ build) · ถ้าวันหนึ่ง gateway รับโหลดสูงจริง ค่อยแยกชั้นนั้นเป็น Go โดยวัดก่อน

**ทำไม 3.14 ไม่ใช่ 3.15:** 3.15 ออก 9 ต.ค. 2026 (อายุ 2 สัปดาห์) · `unstructured` รองรับ <3.14 · `markitdown` <3.15 · 3.14 มี wheel ครบทุกตัวที่ต้องใช้ · CI จะรัน 3.15 คู่ไว้ แล้วขยับเมื่อเขียวครบ

---

## 4. ฐานข้อมูล: MongoDB vs PostgreSQL (เลือก **PostgreSQL 18 + pgvector**)

| เกณฑ์ | PostgreSQL 18.6 + pgvector 0.8.7 | MongoDB 9.0 / 8.3 + mongot | ใครชนะ |
|--|--|--|--|
| โครงข้อมูลของงานนี้ | project → category → user/role/grant → playbook version → run = **ความสัมพันธ์ชัด** · FK + constraint กันข้อมูลเพี้ยน | document อิสระ · ความสัมพันธ์ต้องคุมในโค้ด | **Postgres** |
| แยก project ไม่ให้ข้อมูลข้ามกัน | **Row-Level Security** ในฐานข้อมูลเอง (ลืมใส่ filter ในโค้ดก็ไม่รั่ว) | ไม่มี RLS · ต้อง filter ทุก query ในโค้ด | **Postgres** |
| vector search | ในตารางเดียวกับข้อมูล · HNSW · กรองด้วย project/category ใน query เดียว | GA บน Community ตั้งแต่ 30 มิ.ย. 2026 · ต้องรัน **mongot** แยก + replica set | Postgres (ง่ายกว่า) |
| full-text | built-in (`tsvector`) · ทางเลือก BM25 ด้วย pg_search (AGPL — ใช้เฉพาะถ้ารับ license ได้) | Search ผ่าน mongot | เสมอ |
| คิวงานเบื้องหลัง | procrastinate 3.10 (คิวบน Postgres เลย ไม่ต้องมี Redis) | ต้องมีระบบคิวแยก | **Postgres** |
| ข้อมูลตาราง/time-series (แท่งราคา) | ตาราง partition + index · หรือ Parquet ใน object storage | collection + time-series collection | เสมอ |
| license | PostgreSQL License (เสรี) | SSPL (ข้อจำกัดถ้าให้บริการต่อ) | **Postgres** |
| ops | process เดียว + extension | mongod replica set + mongot | **Postgres** |

**สรุป:** Postgres ฐานเดียวทำครบ: ข้อมูลระบบ + vector + full-text + คิวงาน + RLS แยก project · z-service ยังใช้ Mongo ต่อได้ (ไม่เกี่ยวกัน คุยผ่าน bridge)

**ข้อกำหนดเชิงเทคนิค:** index HNSW ของ pgvector รับ `vector` ได้ถึง 2,000 มิติ (`halfvec` 4,000) · Gemini embedding ออก 3,072 มิติแต่ตัดได้ (MRL) ⇒ ใช้ 1,536 มิติ + normalize เอง · เก็บชื่อโมเดล+มิติต่อ "embedding space" เพื่อเปลี่ยนโมเดลแล้ว re-index ได้

---

## 5. Stack เต็ม (เวอร์ชันล่าสุด · กฎ 7 วัน · lock + hash + OSV แบบ z-service)

| ชั้น | เลือก | เวอร์ชัน (25 ต.ค.) | หมายเหตุ |
|--|--|--|--|
| runtime | Python | 3.14.9 | CI คู่ 3.15 |
| web framework | FastAPI + Starlette | 0.162 / 1.10 | ใหม่กว่า 7 วัน → pin ตัวที่อายุถึง |
| model/config | pydantic + pydantic-settings | 2.14 / 2.16 | config ต่อ module แบบ z-service |
| DB access | SQLAlchemy 2.1 (async) + asyncpg 0.32 + Alembic 1.20 | | migration ทุกครั้ง · ไม่มี DDL ในโค้ด |
| vector | pgvector (ext 0.8.7 · python 0.5.1) | | |
| คิวงาน | procrastinate | 3.10 | worker แยก process · retry · schedule |
| ข้อมูลตาราง | polars 2.0 (ใหม่) + pandas 3.1 (เฉพาะตอน parity กับโค้ดเดิม) | | ค่อย ๆ ย้ายไป polars เมื่อ parity ผ่าน |
| อ่านเอกสาร | docling 2.142 (PDF/DOCX/ตาราง) · pypdf 6.21 (สำรอง) · polars (CSV) | | **ไม่ใช้ PyMuPDF** (AGPL) |
| LLM / embedding | google-genai 2.33 (Gemini · `gemini-embedding-2`) · fastembed 0.9 (local) · local LLM ผ่าน CLI/MCP หรือ Ollama | | ผ่าน `providers` interface |
| auth | argon2-cffi 25.1 (รหัสผ่าน) · token ของเครื่องแบบ hash+scope | | |
| CLI | Typer 0.27 | | |
| MCP | MCP Python SDK ตาม spec **2026-07-28** (stateless · streamable HTTP · stdio) | ตรวจเวอร์ชัน SDK ตอนเริ่ม P3 | ให้ LLM local/agent เรียก engine เป็น tool |
| reranker / embedding local | Qwen3-Reranker / BGE-reranker-v2-m3 · Qwen3-Embedding / EmbeddingGemma (ผ่าน fastembed หรือ sentence-transformers) | เลือกหลังวัดภาษาไทยด้วย evals | Apache-2.0 / MIT เท่านั้น |
| evals | ชุดคำถามทอง + metric (context recall · faithfulness) เขียนเองบน pytest | | gate ก่อนเปิดใช้การเปลี่ยน |
| log/trace | structlog 26 + OpenTelemetry 1.45 | | log เก็บลง DB ต่อ run ให้ดูใน UI |
| server | uvicorn 0.54 (หรือ granian 2.8 — วัดก่อนเลือก) | | |
| test/lint | pytest 9.1 · ruff · pyright | | warning = fail · ไฟล์ ≤300 · ฟังก์ชัน ≤60 |
| UI | React 19.3 · Vite 8.3 · TanStack Router 1.170 / Query 5.104 / Table 9.3 · Tailwind 4.3 · zod 4.6 · Paraglide 2.29 (th/en/it) | | โครง bulletproof-react แบบ z-service |
| deploy | Docker multi-stage (non-root · pin digest) · compose สำหรับเครื่อง · Coolify ได้ | | |

---

## 5.1 UI: React + Vite (SPA) vs Next.js — เลือก **React + Vite**

| เกณฑ์ | React 19 + Vite 8 + TanStack | Next.js 16 | ใครชนะ |
|--|--|--|--|
| backend | ใช้ FastAPI ตัวเดียว · UI เป็นไฟล์ static | ต้องมี Node server อีกตัว (SSR · RSC · Server Actions) = backend ที่สอง · ซ้ำ auth/validation | **Vite** |
| ความปลอดภัย | ไม่มี runtime ฝั่ง server ของ UI | OSV: advisory ของ `next` ปี 2026 = **44** ตัว · 22 ต.ค. 2026 RCE ไม่ต้อง login 2 ตัว (`use cache` · image optimizer SVG) | **Vite** |
| SEO / หน้าแรกเร็ว | ไม่จำเป็น (ทุกหน้าอยู่หลัง login) | จุดแข็งของ Next | ไม่เกี่ยวกับงานนี้ |
| สเกล / deploy | static บน CDN หรือ backend · ไม่มี state | ต้องขยาย Node server + cache | **Vite** |
| ความต่อเนื่อง | ชุดเดียวกับ z-service `web/` | ต่างชุด | **Vite** |
| ถ้าวันหนึ่งต้อง SSR | TanStack Start (SSR บน Vite + router เดิม) ย้ายได้โดยไม่เขียนหน้าใหม่ | — | เปิดทางไว้ |

เครื่องมือเสริม: TanStack Router (type-safe · code split) · Query (cache · retry) · Table + Virtual (ตารางใหญ่) · Form + zod · shadcn/ui + Radix (accessible) · Tailwind 4 · Paraglide (th/en/it) · openapi-typescript (type จาก backend · มี drift check) · react-markdown + rehype-sanitize (คำตอบ RAG + citation) · SSE สำหรับคำตอบแบบ stream · lightweight-charts (กราฟราคา · Apache-2.0) · Vitest + Testing Library + MSW · Playwright (รอสิทธิ์ browser)

## 6. โมเดลข้อมูลหลัก (**User ใหญ่สุด** · 1 user : หลาย project)

```
User (ใหญ่สุด)
 ├─ system role: superadmin | user
 │     superadmin = เห็น/จัดการ ทุก user · ทุก project · ทุก log (ทุกการกระทำลง audit)
 ├─ Projects ที่เป็นเจ้าของ (1:m) — คุมแต่ละ project ตามสิทธิ์ของตัวเอง
 ├─ Memberships (ถูกเชิญเข้า project ของคนอื่น · role ต่อ project) — เปิด/ปิดฟีเจอร์แชร์ได้
 ├─ API tokens ของ user (CLI/เครื่อง · hash + scope + project ที่ใช้ได้ + หมดอายุ)
 └─ Profile / ภาษา / ธีม

Project (เป็นของ user คนเดียว · แยกข้อมูลด้วย RLS)
 ├─ Members + role ของ project: owner / admin / editor / analyst / viewer
 ├─ Categories (หลายหมวด · เช่น markets, legal, research, ops …)
 │    ├─ Grants (member/role ↔ category: read / run / edit / manage)
 │    ├─ Knowledge: Documents → Versions → Chunks → Embeddings (ต่อ embedding space)
 │    ├─ Datasets: ตารางข้อมูล (เช่นแท่งราคาจาก z-service) → Snapshots
 │    ├─ Playbooks: Spec → Versions (draft / provisional / active / paused / retired) → Overrides
 │    └─ Runs: input → steps → output + citations + logs
 ├─ Settings (ค่าตั้ง project · provider key เข้ารหัส · toggle pack/playbook)
 └─ Audit log ของ project (ใคร ทำอะไร เมื่อไร กับอะไร)
```

**ลำดับการตัดสินสิทธิ์ (ทุก request)**
1. ไม่ login → ปฏิเสธ (ยกเว้นหน้า login)
2. **superadmin** → ผ่านทุก project (ลง audit ว่าเข้าในฐานะ superadmin)
3. เป็น **owner** ของ project → ทุกอย่างใน project นั้น
4. เป็น **member** → ตาม role ของ project + grant ราย category
5. นอกนั้น → ไม่เห็นแม้แต่ชื่อ project (ตอบ 404 ไม่ใช่ 403 — ไม่บอกว่ามีอยู่)

- **สิทธิ์ = permission string** (`project.manage`, `category.read`, `playbook.run`, `settings.edit`, `logs.view` …) · role = ชุด permission · ปรับชุดได้ใน UI · ตรวจในโค้ดทุก request + **RLS ใน Postgres เป็นชั้นสอง** (policy: owner หรือ member หรือ superadmin)
- **superadmin แต่ไม่เห็น secret:** provider key / token เป็นแบบเขียนอย่างเดียว (แสดง `••••` + 4 ตัวท้าย) แม้ superadmin ก็อ่านค่าจริงไม่ได้ · superadmin คนแรกสร้างจาก CLI ตอนติดตั้ง (ไม่มีหน้าสมัครเปิดค้าง — บทเรียนจาก z-service)
- **ดู log + ตั้งค่าได้ใน UI** ตามสิทธิ์: user เห็น log ของ project ตัวเอง · superadmin เห็นทุก project + log ระบบ · settings ต่อ user / project / category / playbook
- **ข้อมูลส่วนตัวไม่อยู่ใน engine:** ทุน · จำนวนหุ้นที่ถือ · บัญชีโบรก = **input ของ run** (หรือข้อมูล private ของ project ภายใต้สิทธิ์) ไม่เคยอยู่ใน pack/playbook/ความรู้กลาง

---

## 6.1 API keys สำหรับเครื่อง/สคริปต์/CLI (superadmin จัดการ · เรียก API ด้วย key เท่านั้น)

**หลัก:** key ไม่เคยถูกส่งเป็น plain text · server ไม่เก็บความลับที่ใช้ปลอมตัวได้ · ทุกคำขอเซ็นและมีเวลา (±5 นาที) · token อายุสั้น + refresh หมุนได้ + ยกเลิกได้

| ส่วน | ออกแบบ | มาตรฐาน |
|--|--|--|
| ตัว key | คู่กุญแจ **Ed25519** · server เก็บแค่ public key (ฐานข้อมูลรั่ว = ปลอมตัวไม่ได้) · private key อยู่กับผู้ใช้ (แสดงครั้งเดียวตอนออก หรือผู้ใช้สร้างเองแล้วส่ง public key มา) · key id ขึ้นต้น `mgk_` | — |
| ผูกสิทธิ์ | key เป็นของ user คนหนึ่ง · จำกัด project/category + scope (`read` · `run` · `edit`) · มีวันหมดอายุ · ใช้ RLS ชุดเดิม (ได้สิทธิ์ไม่เกินเจ้าของ key) | — |
| ทุกคำขอเซ็น | header `Signature-Input` + `Signature` ครอบ `@method` `@path` `@query` `content-digest` (SHA-256 ของ body) + `created` + `nonce` + `keyid` · body เปลี่ยน 1 byte = ลายเซ็นไม่ผ่าน | RFC 9421 HTTP Message Signatures · RFC 9530 Digest Fields |
| กันส่งซ้ำ | `created` ต้องห่างเวลา server ไม่เกิน **±300 วินาที** · `nonce` ใช้ได้ครั้งเดียวในช่วงนั้น (เก็บใน Postgres UNLOGGED) | แนวเดียวกับ RFC 9449 DPoP |
| ขอ token | `POST /v1/auth/token` (เซ็น) → access token อายุ 15 นาที + refresh token · access token ใช้คู่กับลายเซ็นทุกครั้ง (ขโมย token อย่างเดียวใช้ไม่ได้) | RFC 9449 (sender-constrained) |
| refresh | `POST /v1/auth/token/refresh` (เซ็น) → คู่ใหม่ · refresh เดิมใช้ไม่ได้อีก · **ถ้ามีคนเอา refresh เก่ามาใช้ซ้ำ = ยกเลิกทั้งสาย** | RFC 9700 OAuth 2.0 Security BCP |
| ยกเลิก | `POST /v1/auth/token/revoke` (RFC 7009) · superadmin ยกเลิก key = token ทุกตัวของ key นั้นตายทันที | RFC 7009 |
| เก็บ token | server เก็บแค่ SHA-256 ของ token · ทุกการออก/ใช้/ยกเลิกลง audit | — |
| UI | superadmin: ออก key (เลือก user · project · scope · วันหมดอายุ) · ดูรายการ · ยกเลิก · หมุน key | — |
| CLI / MCP | `mindgrid` CLI เซ็นคำขอให้เอง (private key จาก Keychain/ไฟล์ 0600) | — |
| เบราว์เซอร์ | UI ยังใช้ session cookie (HttpOnly + CSRF) · เส้นทางเครื่องรับเฉพาะ key + ลายเซ็น | — |

## 7. RAG engine — ออกแบบจากผลค้นคว้าจริง (ต.ค. 2026)

### 7.1 ผลค้นคว้า → สิ่งที่เอามาใช้

| เรื่อง | สิ่งที่แหล่งปี 2026 เห็นตรงกัน | ตัดสินใจใน MindGrid |
|--|--|--|
| ค้นแบบผสม | ค่าเริ่มที่ถูกต้องคือ **dense + BM25 รวมด้วย RRF (k=60)** · BM25 จับคำตรง/รหัส/ตัวย่อที่ vector พลาด | hybrid เป็นค่าเริ่ม (pgvector + full-text ของ Postgres) · ค่า k ปรับได้ |
| rerank | cross-encoder เพิ่มความแม่น ~25–40% แลก ~120 ms · **แต่บางชุดข้อมูลไม่ดีขึ้น (ARAGOG)** ⇒ ต้องวัดบนข้อมูลเราเอง | rerank เป็น plugin เปิด/ปิดต่อ category · ค้น ~50 → rerank เหลือ ~5 · เปิดเมื่อ eval บอกว่าดีขึ้น |
| reranker ที่ใช้ได้ | open weights: Qwen3-Reranker (Apache-2.0 · 100+ ภาษา) · BGE-reranker-v2-m3 (Apache-2.0) · mxbai-rerank-v2 (Apache-2.0) · jina-v3 (เช็ค license) · API: Cohere Rerank 4 · Voyage rerank-2.5 | ค่าเริ่ม local = Qwen3-Reranker-0.6B หรือ BGE-v2-m3 (หลายภาษา รวมไทย) · API เป็นทางเลือก |
| ตัด chunk | ค่าเริ่มที่ชนะ benchmark ก.พ. 2026: **recursive ~512 token** (semantic chunking แพ้ เพราะได้ชิ้นเล็กเกิน) · **เปลี่ยนโมเดล embedding มีผลมากกว่าวิธีตัด** · คุณภาพตกเมื่อ context เกิน ~2,500 token | recursive 512 + overlap 10–15% ตามโครงหัวข้อ · ไม่ตัดกลางตาราง · จำกัด context ที่ส่งให้ LLM |
| เพิ่มบริบทให้ chunk | **Contextual Retrieval** (Anthropic): ใส่คำอธิบายสั้นต่อ chunk ก่อน embed/BM25 → พลาดน้อยลง 35% (49% กับ BM25 · 67% กับ rerank) · **late chunking** ได้ใกล้เคียงแต่ถูกกว่า | contextual เป็นขั้นเลือกได้ใน intake (ใช้ LLM · มีต้นทุน) · late chunking เมื่อโมเดล embedding รองรับ context ยาว |
| โมเดล embedding | API: `gemini-embedding-2` (GA · multimodal · 3,072 มิติ ตัดได้ MRL) · open: Qwen3-Embedding (0.6B/4B/8B · Apache-2.0 · 100+ ภาษา) · Harrier-oss (MIT) · EmbeddingGemma-300M (เล็ก) · **ไม่มีผลวัดภาษาไทยโดยตรง** | provider เลือกได้ต่อ project · เก็บ "embedding space" (โมเดล + มิติ) แยก · เปลี่ยนโมเดล = re-index เป็นงานเบื้องหลัง · **วัดภาษาไทยเองด้วยชุดคำถามทอง** ก่อนเลือกค่าเริ่ม |
| CSV / ตาราง | embed แถวดิบใช้ไม่ได้กับคำถามคำนวณ/กรอง/รวม · ใช้ **SQL / dataframe tool** แทน · embedding ใช้แค่หาโต๊ะ/คอลัมน์ที่เกี่ยว | CSV = dataset → ถามผ่าน function/SQL ที่จำกัดสิทธิ์ (read-only · timeout · จำกัดแถว) · embed แค่ schema + คำอธิบาย |
| PDF ที่มีรูป/ตาราง | ColPali (ค้นจากภาพหน้า) ชนะบนชุดเอกสารสวย ๆ แต่ index ใหญ่ 10–50 เท่า ช้ากว่า · **OCR/การถอดข้อความที่ดีปิดช่องว่างได้เกือบหมด** | ค่าเริ่ม = ถอดข้อความ+ตารางด้วย docling · ภาพ/กราฟใส่คำบรรยาย · ค้นจากภาพหน้า (ColPali/gemini-embedding-2 multimodal) เป็น plugin ในอนาคต |
| GraphRAG | คุ้มเฉพาะคำถามหลายต่อ/ภาพรวมทั้งคลัง · ต้นทุนสร้าง index ~1,000 เท่าของ vector · ผลวัดปนกัน · ถ้าจะใช้ เริ่มที่ LightRAG | **ไม่ใส่ตอนแรก** · เตรียมช่อง retriever plugin ไว้ · เปิดเมื่อ eval แสดงว่า hybrid พลาดคำถามหลายต่อ |
| agentic RAG | ระบบให้ LLM เลือกแหล่ง/ค้นซ้ำได้ (CRAG · Self-RAG · adaptive) · จำกัดรอบ ~3 + งบต่อ tool | โหมด `agentic` เลือกได้ · router เลือก "ไม่ค้น / ค้นครั้งเดียว / ค้นหลายขั้น" · จำกัดรอบ/งบ token เป็น config |
| RAG กับ context ยาว | ฉันทามติ 2026: **RAG หา · context ยาวขัดเกลา** | ส่งเฉพาะชิ้นที่ rerank แล้ว · ไม่ยัดทั้งคลัง |
| สิทธิ์ตอนค้น | การค้นต้องเคารพสิทธิ์ของแหล่ง · vector store ที่คุมสิทธิ์ไม่ดี = ข้อมูลข้าม tenant (OWASP LLM08) | กรอง project/category/สิทธิ์ **ใน query เดียวกับการค้น** + RLS |
| filter + HNSW | ก่อน pgvector 0.8 กรองหลังค้น → ได้แถวไม่ครบ · 0.8 มี **iterative scan** (ต้องเปิดเอง) · tenant เล็กในตารางใหญ่ยังพลาดได้ | เปิด `hnsw.iterative_scan` · partition ตาม project เมื่อโต · project ใหญ่แยก index ได้ · halfvec ลดขนาด |
| ความปลอดภัย | **indirect prompt injection** ผ่านเอกสาร/ชิ้นที่ค้นได้ (EchoLeak CVE-2025-32711) · กรองเนื้อหาอย่างเดียวไม่พอ ต้องแยกสิทธิ์ + ลำดับคำสั่ง + บังคับรูปแบบผลลัพธ์ | เนื้อหาที่ค้นได้ = **ข้อมูล ไม่ใช่คำสั่ง** (คั่นชัดใน prompt) · ลบตัวอักษรซ่อน/zero-width ตอน intake · LLM ไม่มีสิทธิ์เรียก tool เขียน/ลบจากเนื้อหา · ผลลัพธ์บังคับ schema · red-team test ใน CI |
| วัดคุณภาพ | ชุดคำถามทอง 100–200 ข้อ · วัด **context recall + faithfulness** อย่างน้อย · judge ต้องเก่งกว่าตัวถูกวัด · faithfulness สูงไม่ได้แปลว่าเอกสารถูก | module `evals`: ชุดทองต่อ category · รันทุกครั้งที่เปลี่ยน chunk/embedding/rerank/prompt · ผ่านเกณฑ์ถึงเปิดใช้ (gate แบบ test) |
| observability | OpenTelemetry GenAI conventions **ยังไม่ stable** (ต.ค. 2026 · มี span สำหรับ retrieval แล้วใน v1.40) | ใช้ OTel แต่ **pin เวอร์ชัน convention** · log ของเราเอง (structured) เป็นหลักฐานหลักใน UI |
| MCP | spec ล่าสุด **2026-07-28**: core เป็น stateless · Streamable HTTP ไม่มี session แล้ว ต้องส่ง header `Mcp-Method`/`Mcp-Name` · auth แนว OAuth 2.1 (+ RFC 8707 resource) | MCP server ตาม spec 2026-07-28 · stateless · token ต่อ project |
| managed RAG | Gemini File Search: จัดการให้หมด แต่ store จำกัด (10 ต่อ project · ไฟล์ ≤100 MB) · ไม่มี RLS ของเรา | **ไม่ใช้เป็นแกน** (ผูก vendor · คุมสิทธิ์ไม่ได้) · ทำเป็น retriever adapter ทางเลือกได้ |

### 7.2 สถาปัตยกรรม (2 ระนาบ · ทุกขั้นเป็น plugin)

```
ระนาบ indexing (เบื้องหลัง · worker)                ระนาบ query (ออนไลน์ · API)
upload/bridge/synapse                              คำถาม + ผู้ใช้ + project/category
  → detect (ชนิด/ขนาด/ไวรัส)                          → router (ไม่ค้น / ค้น / หลายขั้น / dataset tool)
  → parse (docling · csv · text · md)                 → rewrite query (เลือกได้)
  → sanitize (ตัดตัวซ่อน · ข้อมูลส่วนตัว)              → hybrid search (vector + BM25 · RRF) + กรองสิทธิ์
  → chunk (recursive 512 · ตามหัวข้อ)                  → rerank (เลือกได้)
  → contextualize (เลือกได้ · ใช้ LLM)                  → pack context (จำกัด token · คั่นว่าเป็นข้อมูล)
  → embed (ต่อ embedding space)                       → generate (none / gemini / local) + citation บังคับ
  → index (pgvector HNSW + tsvector)                  → log + trace + feedback → evals
```
- ทุกขั้นมี interface + registry → **เปลี่ยน/เพิ่ม/ปิดได้ต่อ project หรือ category** โดยไม่แก้ core (parser ใหม่ · reranker ใหม่ · retriever แบบ graph ในอนาคต)
- ทุกขั้นเก็บ version ของตัวเองลงผลลัพธ์ → ย้อนดูได้ว่าคำตอบนี้มาจาก chunk/โมเดล/prompt รุ่นไหน
- **ไม่ผูก framework RAG** (LangChain/LlamaIndex) — เขียน pipeline เองเป็นขั้นเล็ก ๆ · เหตุผล: framework เปลี่ยน API บ่อย = หนี้ · ทุก guide บอกว่าส่วนสำคัญคือ hybrid + rerank + eval ซึ่งเขียนเองได้ไม่ยาก

### 7.3 รับเอกสารได้ทุกแบบ

PDF · DOCX · CSV · TXT · Markdown · playbook spec · (ภายหลัง: HTML/URL · รูป · เสียง ผ่าน plugin)
- **CSV สองทาง:** *เอกสาร* (ค้นความหมาย) หรือ *dataset* (คำนวณ) — ผู้ upload เลือก · แท่งราคาเป็น dataset เสมอ
- ทุกเอกสารมี version · tag ความน่าเชื่อ (VERIFIED / CLAIMED / DISPUTED) · แหล่ง · วันที่ · ลบ/แทนที่ได้ แล้ว re-index อัตโนมัติ

### 7.4 รองรับอนาคต / สเกล
- เพิ่มความสามารถ = เพิ่ม plugin (parser · retriever · reranker · provider · pack) ไม่ใช่แก้ core
- embedding space หลายชุดอยู่ร่วมกันได้ → ย้ายโมเดลแบบค่อยเป็นค่อยไป (A/B ด้วย evals)
- สเกล: API stateless หลาย replica · worker แยกตามชนิดงาน (parse / embed / eval) · Postgres partition ตาม project + read replica · project ใหญ่มาก → index แยก หรือย้ายไป vector DB เฉพาะทางผ่าน adapter เดียวกัน (โค้ดส่วนอื่นไม่เปลี่ยน)

---

## 8. functions + playbooks (ถอด skill ทั้งหมดเป็นของกลาง)

**function (skill กลาง)** = ฟังก์ชัน Python บริสุทธิ์ มี input/output เป็น pydantic model · ไม่มีค่าคงที่ฝัง (ทุกเกณฑ์เป็น parameter มี default + ขอบเขต) · ลงทะเบียนผ่าน registry (Python entry points) · pack ใหม่เพิ่ม function ได้โดยไม่แก้ core

**playbook** = ไฟล์ spec (YAML/JSON + JSON Schema) ประกอบ function เป็นขั้น ๆ:
```yaml
id: markets.pullback-reclaim        # ตัวอย่างรูปแบบ ไม่ใช่ของจริง
version: 3
status: provisional                 # draft | provisional | active | paused | retired
inputs:  { dataset: bars.daily, universe: list }
params:  { ext_max_pct: {default: 25, min: 0, max: 100}, rr_min: {default: 1.2} }
steps:   [ {fn: markets.stage}, {fn: markets.gate.trend, with: {ext_max_pct: $params.ext_max_pct}}, … ]
evidence: [ doc:markets/evidence/pullback-v3 ]   # ความรู้ที่รองรับ playbook นี้
outputs: { table: candidates, explain: true }
```
- เลือกได้ เปิด/ปิดได้ override ค่าได้ต่อ project/category · version เก่ารันซ้ำได้ (ผลย้อนหลังตรวจได้)
- สถานะ "พัก/ทดลอง" เป็น **ข้อมูล** ไม่ใช่ข้อความในรายงาน (แก้ปัญหาที่ catalog เจอ: JUMP พัก · TURN ทดลอง อยู่ในร้อยแก้ว)
- ผลลัพธ์เป็น **code ภาษากลาง** (`entry.near`, `entry.wait_pullback`, `gate.fail.ext`) แล้ว UI แปล th/en/it — ไม่มีข้อความไทยใน logic

**pack `markets` (ถอดจาก stock-radar)** — จาก catalog มีของจริง ~40 ความสามารถ:
- ของกลางที่ถอด: อ่าน CSV/ข้อมูล · clock ตลาด · ตรวจข้อมูล (CMF bounds · split · ประวัติสั้น) · indicator (IPI · OBV slope · RVOL) · staging UIPT/ez/short · trap6 · ext200 · coil/levels · regime (HYG · VIX · 10Y · breadth) · sector RS · trade setup / R:R จากโครงสร้าง · entry sanity · lane ต่าง ๆ (REBOUND · ROCKET · TURN · PANIC-DIP · growth · wealth · core-index · bottleneck · pick) · sizing (Kelly · risk-at-stop · tier) · backtest/measure
- **ไม่ถอด (ของส่วนตัว):** port gate · my_port parser · watchlist build · ULTIMATE baskets · รายชื่อหุ้นส่วนตัว · บัญชี Dime!/Webull · NAV · lot % ที่ตัดสินเอง → กลายเป็น input/param ของผู้เรียก
- รวมของซ้ำ: Limit 4 แบบ · csv reader 3 ตัว · trigger 3 ชุด · stats 2 ชุด → **ตัวเดียวต่อเรื่อง**
- ความถูกต้อง: **parity test** เทียบผลกับ stock-radar ต่อ function (แบบ z-service radar parity) ก่อนเปิดใช้

---

## 9. Synapse — ระบบเรียนรู้จากต้นทาง (stock-radar เป็นแหล่งแรก)

เป้าหมาย: stock-radar อัปเดต skill เมื่อไร engine **รู้ว่าเปลี่ยน logic อะไร · ทำความเข้าใจ · dive ใหม่เฉพาะส่วนที่เพิ่ม** แล้วเสนออัปเดตตัวเอง — ไม่ยกมาทั้งก้อน

```
watch → diff → understand → dive → propose → review → apply
```
1. **watch** — อ่าน git ของ repo ต้นทางแบบอ่านอย่างเดียว · จำ commit ล่าสุดที่เรียนแล้ว · สนใจเฉพาะ path ที่ลงทะเบียน (skills · scripts · references)
2. **diff** — แยกการเปลี่ยนต่อไฟล์/ต่อฟังก์ชัน/ต่อกฎ
3. **understand** — จัดประเภท: เกณฑ์เปลี่ยน · กฎใหม่ · playbook ใหม่ · ผลวัดใหม่ · ของส่วนตัว (ทิ้ง) · โยงกับของใน engine ด้วย **ตาราง mapping** (ต้นทาง ↔ function/param/playbook) · ใช้ LLM ช่วยสรุปได้แต่ต้องมี diff จริงแนบ
4. **dive** — ถ้าอ้างตัวเลข (เช่น "win 62%") ให้ **วัดซ้ำบนข้อมูลของ engine** ก่อน · ไม่เชื่อตัวเลขจากข้อความ
5. **propose** — สร้าง "change proposal": playbook version ใหม่ / ค่า default ใหม่ / เอกสารความรู้ใหม่ / งาน code (ถ้าต้องเพิ่ม function)
6. **review** — คิวใน UI · คนที่มีสิทธิ์กดรับ/ปฏิเสธ · เห็น diff ต้นทาง + ผลวัด + ผลกระทบ
7. **apply** — รับแล้วออก version ใหม่ (ของเก่ายังรันได้) · code ไม่แก้อัตโนมัติ — ได้เป็นงาน/PR draft
- **sanitizer** ทุกขั้น: ตัดข้อมูลส่วนตัว (พอร์ต · บัญชี · NAV · ชื่อเครื่อง) ก่อนเข้า engine
- แหล่งอื่นในอนาคต: repo อื่น · โฟลเดอร์เอกสาร · URL — ใช้ pipeline เดียวกัน

---

## 10. Bridge กับ z-service (สองฝั่ง)

| ทิศ | ใช้ทำอะไร | วิธี |
|--|--|--|
| engine → z-service | ดึงแท่งราคา/formula/ข่าวเป็น dataset · สั่งรอบดึงใหม่ | `bridges/zservice` ใช้ key `zsk_` scope `read` (+ `jobs` ถ้าต้องสั่ง) · ตรวจ TLS · เก็บ key ใน settings แบบเข้ารหัส |
| z-service → engine | แจ้ง "มีชุดข้อมูลใหม่" · ขอให้รัน playbook บนรอบล่าสุด · ดึงผลไปแสดงใน UI z-service | z-service เพิ่ม `zservice/integrations/engine/` + config `ENGINE_URL` / token · webhook ลงลายเซ็น HMAC + timestamp (กัน replay) |

- **contract:** OpenAPI ของทั้งสองฝั่ง version ชัด (`/v1`) · contract test ในทั้งสอง repo · เปลี่ยนแบบ breaking ต้องออก v2
- **ฝั่ง z-service ต้องเพิ่ม (งานแยกหลัง engine พร้อม):** export แบบ JSON/Parquet · `since` (เฉพาะที่เปลี่ยน) · เลือกคอลัมน์/จำนวนแท่ง · ETag · webhook ส่งออก · scope ใหม่ `engine:notify`
- idempotent ทุกคำสั่ง (ส่งซ้ำไม่ซ้อน) · retry แบบ backoff · audit ทั้งสองฝั่ง

**ปรับตามคำสั่ง 25 ต.ค. (ทำเป็นท่อกลาง ไม่ผูก z-service):**
- **ขาส่ง (P7) = event pipeline กลาง:** รูปแบบข้อความมาตรฐาน (CloudEvents) + ลงลายเซ็นแบบ Standard Webhooks · ผู้รับลงทะเบียนได้หลายราย (subscription: URL · ประเภท event · project · secret) · คิวส่งแยกต่อผู้รับ + retry/backoff + dead-letter · ผู้รับช้า/ล่มไม่กระทบรายอื่น · z-service = ผู้รับรายหนึ่ง อ่านข้อความเอง
- **ขาดึง (P5) = connector กลาง:** แหล่งข้อมูล HTTP กำหนดด้วยข้อมูล (URL · วิธี auth · รูปแบบ CSV/JSON · การ map field → dataset) ไม่ต้องแก้โค้ดเพื่อรองรับระบบใหม่ · z-service = connector config ชุดหนึ่ง
- ค้นคว้า best practice ล่าสุดก่อนลงมือ (เวอร์ชันสเปก · การลงลายเซ็น · idempotency)

---

## 11. ทางเรียกใช้

| ทาง | สำหรับ | ต้องมี |
|--|--|--|
| REST API (`/v1`) | ระบบอื่น · UI | token ของ user หรือเครื่อง |
| CLI `mindgrid …` | bash · สคริปต์ · **LLM ในเครื่อง** | token (หรือโหมด local ต่อ DB ตรงสำหรับ dev) |
| MCP server | agent/LLM ที่รองรับ MCP เรียก recall + function + playbook เป็น tool | token |
| Web UI | คน | login |

**โหมด LLM (เลือกต่อ project/run):**
- `none` — คำนวณ + ค้นคืนอย่างเดียว คืนผลเป็นโครงสร้าง (ไม่ต้องมี key)
- `gemini` — ตอบ/สรุปด้วย Gemini · ต้องตั้ง Gemini API key (Settings · เข้ารหัส) **เฉพาะโหมดนี้** · embedding เลือกได้แยกต่างหาก (§11.1)
- `local` — LLM ในเครื่องเป็นคนคิด: เรียก engine ผ่าน CLI/MCP เอง · embedding ใช้ fastembed ในเครื่องได้ (ไม่ต้องมี key เลย)

---

### 11.1 Gemini ไม่บังคับ — RAG แยก 3 งาน แต่ละงานเลือกตัวทำได้เอง

| งาน | ทำอะไร | ตัวเลือก | ไม่มี Gemini ได้ไหม |
|--|--|--|--|
| ① embedding | แปลงเอกสาร/คำถามเป็น vector | Gemini · **โมเดลในเครื่อง** (Qwen3-Embedding / EmbeddingGemma) · ไม่ใช้ (BM25 คำตรงอย่างเดียว) | ได้ |
| ② ค้น + rerank + citation | หา chunk ที่เกี่ยว เรียงใหม่ แนบที่มา | **MindGrid ทำเองเสมอ** (Postgres + reranker ในเครื่อง) | ไม่ต้องใช้ LLM เลย |
| ③ เขียนคำตอบ | อ่าน chunk แล้วตอบ | Gemini · **LLM ในเครื่อง** · ไม่เขียน (คืน chunk + citation ให้ผู้เรียก) | ได้ |

**กติกา embedding space:** เอกสารที่ index ด้วยโมเดลไหน คำถามต้อง embed ด้วยโมเดลเดียวกัน · project ที่ต้องใช้ทั้งออนไลน์และออฟไลน์ → เก็บ 2 space (Gemini + ในเครื่อง) · ถ้าโมเดลของ space นั้นใช้ไม่ได้ตอนค้น → ตกไปใช้ BM25 อัตโนมัติ และบอกในผลลัพธ์ว่าตกโหมด

**ขั้นที่ใช้ LLM แบบเลือกได้:** contextual retrieval ตอน index · query rewrite · judge ใน evals → ใช้ Gemini หรือ LLM ในเครื่องก็ได้ · ปิดได้ทั้งหมด

**โหมดออฟไลน์ทั้งหมด:** embedding ในเครื่อง + reranker ในเครื่อง + LLM ในเครื่อง = ข้อมูลไม่ออกจากเครื่องเลย ไม่ต้องมี key

### 11.2 แบบที่แนะนำ: Claude Code เป็นตัวคิด · MindGrid เป็นคลังความรู้ + เครื่องคำนวณ

| ใครทำงาน | ทางเชื่อม | LLM ที่เขียนคำตอบ | ต้องมี key ไหม | ใช้เมื่อ |
|--|--|--|--|--|
| **Claude Code (แนะนำหลัก)** | **MCP** (tool `recall` · `run_playbook` · `get_dataset`) | Claude Code เอง | ไม่ต้องมี Gemini | ทำงานแบบมีคนอยู่หน้าเครื่อง — แทนการอ่านไฟล์ SKILL/references ทั้งก้อน |
| Claude Code (สำรอง) | bash `mindgrid search/run --json` หรือ curl `/v1` | Claude Code เอง | ไม่ต้องมี | สคริปต์ · เครื่องที่ยังไม่ตั้ง MCP |
| ระบบรันเอง (UI ปุ่ม "ถาม" · งานตั้งเวลา · z-service เรียก) | API ฝั่ง server | Gemini หรือ LLM ในเครื่องบน server | Gemini key เฉพาะเลือก Gemini | ไม่มีคนอยู่หน้าเครื่อง |

- **ความรู้ (กฎ · playbook · ผลวัด · เอกสาร) → RAG** · **ตัวเลข (สกรีน · R:R · sizing จาก CSV) → function/playbook** · LLM ไม่คิดตัวเลขเอง แค่อ่านผลแล้วอธิบาย
- embedding ค่าเริ่ม = โมเดลในเครื่อง + BM25 → ทั้งสามแบบใช้ index ชุดเดียวกันได้โดยไม่ต้องมี key

### 11.3 RAG อยู่ใน MindGrid เสมอ — ใครเป็น LLM ก็ได้ผ่าน RAG ชุดเดียวกัน

```
           ┌──────────────────── MindGrid (RAG ชุดเดียว) ────────────────────┐
ผู้เรียก ──▶│ สิทธิ์ → ค้น hybrid → rerank → Context Pack (ชิ้นความรู้ + ที่มา) │
           │                              │                                   │
           │                 ┌────────────┴─────────────┐                    │
           │          ① retrieve                   ② answer                  │
           │     คืน Context Pack ให้          MindGrid เขียนคำตอบเอง          │
           │     LLM ของผู้เรียกเขียนต่อ        ด้วย provider ที่ตั้งไว้          │
           │                                   (gemini · local · none)        │
           │                                   + ตรวจ citation ก่อนคืน         │
           └──────────────────────────────────────────────────────────────────┘
             log ทุกครั้ง (คำถาม · ชิ้นที่ได้ · ผู้เรียก) → evals วัดคุณภาพการค้นแยกจาก LLM
```

| ผู้เรียก | ใช้ | ใครเขียนคำตอบ |
|--|--|--|
| Claude Code (MCP / bash) | ① retrieve + MCP prompt "ตอบจาก Context Pack เท่านั้น · อ้างที่มาทุกข้อ" | Claude |
| LLM ในเครื่อง (Ollama/llama.cpp) | ② answer `--llm local` หรือ ① ผ่าน MCP | LLM ในเครื่อง |
| เว็บ / งานตั้งเวลา / z-service | ② answer | Gemini หรือ LLM ในเครื่องบน server |

- **Context Pack = สัญญากลาง** (version ชัด): ชิ้นความรู้เรียงตามความเกี่ยว · ที่มา (เอกสาร · หัวข้อ · version · tag ความน่าเชื่อ) · คำสั่งการตอบมาตรฐาน · เนื้อหาถูกคั่นว่าเป็น "ข้อมูล" ไม่ใช่คำสั่ง → ทุก LLM ได้ input แบบเดียวกัน คุณภาพการค้นเท่ากันทุกทาง
- **ตรวจ citation:** ทาง ② MindGrid ตรวจเองว่าทุก citation มีอยู่ใน pack จริง · ทาง ① มี tool `verify_citations` ให้ LLM ผู้เรียกใช้ก่อนส่งคำตอบ
- **บังคับให้ใช้ RAG จริง:** ความรู้ย้ายเข้า MindGrid (ไม่ต้องอ่านไฟล์ทั้งก้อนอีก) · ไฟล์แนะนำของ agent (AGENTS/CLAUDE) ชี้ให้ `recall` ก่อนตอบเสมอ
- **เปลี่ยน LLM ไม่กระทบ RAG:** index · การค้น · rerank · สิทธิ์ · evals เหมือนเดิมทุกตัว

## 12. UI (สวย + ครบ)

หน้า: Login · **Admin console (superadmin: ทุก user · ทุก project · log ระบบ)** · Projects ของฉัน · Categories · Knowledge (upload · version · tag · ค้น) · Datasets · Playbooks (เปิด/ปิด · version · override · รัน) · Runs (ผล + citation + log) · **Synapse** (คิวข้อเสนอ · diff · ผลวัด) · Bridges · **Logs** · **Users & Roles** · **Settings** · Audit
- ภาษา th/en/it ทุก label (แบบ z-service) · ธีมมืด/สว่าง · ขนาด bundle มีงบ · component ไม่มีข้อความฝัง

---

## 13. โครง repo (แยก module/folder · ห้ามยัดไฟล์)

```
mindgrid/
├─ backend/
│  ├─ pyproject.toml · requirements*.lock
│  ├─ src/mindgrid/
│  │  ├─ core/            config · errors(code) · ids · clock · logging
│  │  ├─ platform/        auth/ access/ tenancy/ settings/ audit/ jobs/
│  │  ├─ knowledge/       intake/ (parsers/, chunkers/) library/ recall/
│  │  ├─ datasets/
│  │  ├─ functions/       registry · contracts
│  │  ├─ playbooks/       spec/ registry/ runtime/
│  │  ├─ runs/
│  │  ├─ providers/       llm/ (gemini · local · none) embeddings/ (gemini · fastembed)
│  │  ├─ evals/           golden sets · metrics · gates
│  │  ├─ synapse/         sources/ watch/ diff/ understand/ dive/ proposals/
│  │  ├─ bridges/         zservice/ (client · webhooks · contract)
│  │  ├─ db/              session · migrations (alembic) · repos per module
│  │  └─ interfaces/      api/ (router ต่อ module) · cli/ · mcp/
│  ├─ packs/markets/      แยกเป็น package · functions/ playbooks/ knowledge/ tests/
│  └─ tests/              mirror โครง src
├─ web/                   app/ pages/ layouts/ features/ components/ hooks/ services/ stores/ i18n/
├─ docs/                  architecture · config-reference (สร้างจากโค้ด) · runbook
├─ tools/                 check_structure · check_notes · check_private · check_brand · export_openapi
└─ deploy/                Dockerfile · compose
```
- ทิศ import ทางเดียว: `core` ← `platform` ← `knowledge/datasets/functions` ← `playbooks/runs/synapse/bridges` ← `interfaces` · pack import ได้แค่ `functions` contract (ตรวจด้วยเครื่องมือ)

---

## 14. กติกาห้ามสร้างหนี้ (บังคับด้วยเครื่องมือตั้งแต่ commit แรก)

- ไฟล์ ≤300 บรรทัด · ฟังก์ชัน ≤60 · บรรทัด ≤100 · lint ไม่มี warning · test warning = fail
- **note code ภาษาอังกฤษล้วน · ไม่มีเรื่องเล่าว่าใครสั่ง · ไม่มีชื่อเครื่อง/ชื่อ account/โฟลเดอร์ส่วนตัว** (ยก `check_notes.py` · `check_private.py` จาก z-service)
- ไม่มีค่าฝัง: ค่าระบบ → Settings class ต่อ module (สร้างเอกสารอัตโนมัติ) · เกณฑ์ playbook → spec + override
- ข้อความถึงคน = code + ไฟล์แปล · ไม่มีภาษาไทยใน logic
- dependency: pin + hash + กฎ 7 วัน + OSV · ไม่ใช้ license AGPL/SSPL ใน core
- migration ทุกการเปลี่ยน schema · OpenAPI snapshot + type ฝั่ง web มี drift test
- secret ไม่เข้า git · ไม่เข้า log · key ของ provider เข้ารหัสใน DB

---

## 15. ลำดับงาน — เรียง priority ใหม่ (แต่ละ phase จบด้วย test + เอกสาร + push)

หลักที่ใช้เรียง: **ของที่ทุกอย่างต้องพึ่งมาก่อน** (user/สิทธิ์) → **ใช้งานได้จริงเร็วที่สุด** (ถามเอกสารได้) → **เปิดทาง LLM ในเครื่องเร็ว** (CLI/MCP) → **หุ้นเป็น pack แรก** → เชื่อมระบบ → เรียนรู้เอง

| ลำดับ | Phase | งาน | ทำไมอยู่ตรงนี้ | ผลที่ได้ |
|--|--|--|--|--|
| 1 | **P0 ฐานราก** | เคาะชื่อ · ภาษา · DB · repo + gate ทั้งหมด (structure · notes · private · lock/OSV · OpenAPI drift) · CI ใน Docker build | กติกาต้องอยู่ก่อนโค้ดบรรทัดแรก ไม่งั้นหนี้เกิดทันที | repo ว่างที่ gate เขียว |
| 2 | **P1 User + สิทธิ์** | user (ใหญ่สุด) · superadmin (สร้างจาก CLI) · login/session/token · project 1:m · member + role · category + grant · RLS · audit · หน้า Users / Projects / Logs / Settings | ทุก API หลังจากนี้ต้องรู้ว่า "ใคร · project ไหน · มีสิทธิ์อะไร" | login · superadmin เห็นทุก project · user เห็นเฉพาะของตัวเอง |
| 3 | **P2 ความรู้ (RAG core)** | intake (CSV/PDF/TXT/MD) · library + version · recall hybrid · providers (none / gemini / local) · jobs (คิว) · หน้า Knowledge | คุณค่าหลักของ engine — ใช้กับหมวดไหนก็ได้ | อัปโหลดเอกสารแล้วถามได้ พร้อม citation |
| 4 | **P3 CLI + MCP** | CLI ครบคำสั่ง · MCP server · token ต่อ project | เปิดให้ LLM ในเครื่องใช้ engine ได้ตั้งแต่เนิ่น ๆ | bash / agent เรียก recall ได้ |
| 5 | **P4 functions + playbooks** | registry · spec + schema · runtime · version/สถานะ · override · runs + log · หน้า Playbooks / Runs | โครงที่ pack ทุกตัวจะเสียบ | รัน playbook กลางตัวอย่างได้ |
| 6 | **P5 bridge ขาดึง (engine → z-service)** | client `zsk_` scope read · dataset จาก export · สั่งรอบดึง | pack markets ต้องมีข้อมูลจริงป้อน | dataset แท่งราคาใน engine |
| 7 | **P6 pack `markets`** | ถอดทีละกลุ่มตาม catalog · รวมของซ้ำ · parity test กับ stock-radar · evidence เป็นเอกสารความรู้ | หุ้นเป็น category แรกที่ใช้จริง | playbook หุ้นรันได้ ผลตรงกับ stock-radar |
| 8 | **P7 bridge ขาส่ง (z-service → engine)** | ฝั่ง z-service: module engine · webhook HMAC · export JSON/`since` · แสดงผลใน UI z-service | ต้องมี playbook ที่รันได้ก่อนถึงจะมีอะไรให้เรียก | สองระบบคุยกันอัตโนมัติ |
| 9 | **P8 Synapse** | watch/diff/understand/dive/propose/review · sanitizer · mapping table · หน้า Synapse | ต้องมี function/playbook/evidence ให้ map ก่อน | stock-radar เปลี่ยน → มีข้อเสนอให้กดรับ |
| 10 | **P9 ขึ้นใช้จริง** | hardening · load test · backup/restore · runbook · deploy | ปิดงาน | ใช้งานจริง |

UI ไม่แยก phase — **แต่ละ phase ทำหน้า UI ของตัวเองให้เสร็จในรอบนั้น** (ไม่สะสมงานหน้าไว้ท้าย = หนี้)

---

## 15.1 ความคืบหน้า (repo `mindgrid` · local git)

| งาน | สถานะ | commit |
|--|--|--|
| P0 ฐานราก: uv + lock (กฎ 7 วัน) · app factory · brand config จุดเดียว · gate (ruff · pyright strict · structure + ชั้น import · notes · private · brand · config-reference) | ✅ | `f0a700b` |
| P1a DB + identity: async SQLAlchemy + Alembic · UUIDv7 · app role ไม่มี BYPASSRLS · Argon2id · session token เก็บแค่ hash · RLS users/sessions | ✅ | `5fcc8cf` |
| P1b tenancy: project (user 1:m) · member + role · category + restricted · grant · ทุกการตัดสินสิทธิ์อยู่ใน SQL function ตัวเดียว (RLS + Python เรียกตัวเดียวกัน) | ✅ | `a0f3a1f` |
| P1c HTTP sign-in: cookie __Host- HttpOnly/Secure/Strict · CSRF แบบลงลายเซ็น · rate limit แชร์ข้าม replica ใน Postgres | ✅ | `845cb53` |
| P1d API projects/members/categories/grants · admin users (superadmin) · CLI สร้าง superadmin คนแรก | ✅ | `a839bd9` |
| P1e audit log: append-only · actor มาจาก DB (ปลอมไม่ได้) · มองเห็นตามสิทธิ์ · API อ่าน log | ✅ | `c76ef1b` |
| P1f settings (registry ประกาศ key + ชนิด + scope · ค่าไล่ category > project > user/system > default) + secret เข้ารหัส AES-256-GCM ผูกตำแหน่ง · เขียนได้อย่างเดียว | ✅ | `ff61d49` |
| P1g web UI: React 19.3 + Vite 8 + TanStack (Router · Query · Table v9 · Form · Virtual) + Tailwind 4 + Radix · th/en/it · ชื่อ brand มาจาก API · type ของ API สร้างจาก OpenAPI (มี drift check) · backend เสิร์ฟ SPA + security headers | ✅ | `2b4b44f` |
| P2a ความรู้ขาเข้า: documents/versions/chunks · TXT/MD/CSV/PDF · ลบตัวอักษรซ่อน · chunk แบบ recursive · RLS ราย category · full-text + trigram | ✅ | `00b6870` |
| P1h API key (§6.1): Ed25519 · ทุกคำขอเซ็น RFC 9421 (±300 วินาที · nonce ครั้งเดียว · body digest) · access 15 นาที + refresh หมุนได้ + ใช้ซ้ำ = ยกเลิกทั้งสาย · revoke · key จำกัด project ใน DB · หน้า superadmin + docs/api-keys.md | ✅ | `316be76` |
| P2b embedding + job queue: Qwen3-Embedding-0.6B-Q บนเครื่อง (ไม่ต้องมี key) / Gemini (key ใน secret) / hashing (test เท่านั้น) · หลาย embedding space ใน column เดียว + HNSW แยกราย space · คิวงานใน Postgres (SKIP LOCKED · retry หน่วงเวลาทวีคูณ · lease หมด = คนอื่นรับต่อ) · งานรันในนามคนที่อัปโหลด (สิทธิ์ตรวจซ้ำตอนรัน) · enqueue ใน transaction เดียวกับการอัปโหลด · `mindgrid worker run` | ✅ | `0d89e4f` |
| P2c recall แบบ hybrid: vector (HNSW + iterative scan ไม่ให้ filter ทำผลหาย) + full-text + trigram (ภาษาไทย) รวมด้วย RRF · RLS กรองก่อนจัดอันดับ · บอกทุกครั้งว่า retriever ไหนถูกข้ามเพราะอะไร · `POST /v1/projects/{id}/recall` · route ประกาศ scope ของ API key เองได้ (ค้นหา = read) | ✅ | `33d01b6` |
| P2d Context Pack v1 + คำตอบ: ชิ้นความรู้ P1…Pn คั่นเป็น "ข้อมูล" (ข้อความในเอกสารปิด tag เองไม่ได้) + กติกาตอบมาตรฐาน · โหมด none/gemini/local (Ollama) ตั้งราย project (`answer.llm`) · ตรวจ citation (อ้างที่ไม่มีจริง · ย่อหน้าไม่มีที่มา) · recall จบ transaction ก่อนเรียกโมเดล · `POST /context-pack` (read) · `/answer` (run) · `/citations/verify` | ✅ | `2bb5ce3` |
| P2e UI ความรู้: แท็บคลังความรู้ (เลือกหมวด · อัปโหลด TXT/MD/CSV/PDF · tag ความน่าเชื่อ · ดู chunk · ลบ) + แท็บถาม (Context Pack เฉพาะชิ้นความรู้ หรือให้ server เขียนคำตอบ: ค่า project / ในเครื่อง / Gemini · บอก retriever ที่ถูกข้าม · ผลตรวจ citation) · client รองรับ multipart · th/en/it | ✅ | `e2bff61` |
| P2f คุณภาพการค้น + evals: reranker ในเครื่อง bge-reranker-v2-m3-int8 (Apache-2.0 · ไทยได้) จัดอันดับซ้ำ 20 ชิ้นแรก · ตัดชิ้นไม่เกี่ยวด้วยเกณฑ์ที่วัดจริง (relevance ≥ 0.005 · ไม่มี reranker = vector-only ไกลเกิน 0.6 ตัด) · ชุดทดสอบ golden (hit@k · recall@k · MRR · nDCG · การไม่ตอบเมื่อนอกเรื่อง) เก็บทุกรอบพร้อม setup · `mindgrid eval run` + `POST/GET /evals` · recall log (เก็บ 90 วัน · เจ้าของคำถาม/ผู้จัดการ project เห็น · worker ลบเองทุกชั่วโมง) · โหลดโมเดลล่วงหน้าตอนเปิด server · ทดสอบ Ollama ผ่าน HTTP จริงกับ server จำลอง + รูปคำขอ Gemini | ✅ | `ee0c819` |
| P3 CLI + MCP: ทุกทางเรียกผ่าน API key (เซ็นทุกคำขอ · token เก็บไฟล์เจ้าของอ่านได้คนเดียว · หมดอายุ/ถูกยกเลิก = ขอใหม่เอง 1 ครั้ง · ไฟล์ key ที่คนอื่นอ่านได้ = ปฏิเสธ) · bash `mindgrid login/projects/categories/pack/ask/verify` (`--json`) · MCP stdio `mindgrid mcp` (spec 2026-07-28 · tool list_projects/list_categories/recall/answer/verify_citations + prompt grounded_answer) · ทดสอบ end-to-end กับ app จริง + process MCP จริงบน dev server · docs/cli-and-mcp.md | ✅ | `6002c8a` |
| P4 functions + playbooks: function กลาง (pydantic in/out · ไม่มีค่าฝัง · pack เพิ่มผ่าน entry point `mindgrid.functions`) · spec playbook JSON + JSON Schema (`$inputs/$params/$steps` · ตรวจก่อนรับ: function มีจริง · อ้างอิงถูก · default อยู่ในขอบเขต) · สถานะเป็นข้อมูล (draft/provisional/active/paused/retired) · version เปลี่ยนไม่ได้ · override ระบบ/project (ปิด · ตรึงเวอร์ชัน · ค่า param) · runs ผ่านคิว worker + log รายขั้น · สิทธิ์รัน = เจ้าของ/บทบาทระดับ run ขึ้นไป · API + CLI `playbooks/run` + MCP `list_playbooks/run_playbook` · UI แท็บ Playbook (ฟอร์มสร้างจาก spec) + การรัน | ✅ | `fdc5e2f` |
| P5 ขาดึงแบบกลาง: dataset มี version (เก็บไฟล์เดิมบีบ zstd · ข้อมูลเดิม = ไม่สร้าง version ใหม่ · บรรทัด `# key: value` เป็น meta) · connector HTTP กลางกำหนดด้วยข้อมูล (auth none/bearer/header/query/basic จาก secret ของ project · CSV/JSON/NDJSON) · กัน SSRF (https · ห้าม IP ภายในเว้นแต่อนุญาต · ไม่ตาม redirect · จำกัดขนาด) · sync ผ่านคิว + ตั้งเวลา (DB สร้างงานเอง) · template เป็นไฟล์ข้อมูล (z-service = template หนึ่ง) · playbook รับ input เป็น dataset (run ตรึง version) · UI แท็บข้อมูล + Connector | ✅ | `49e1a81` |
| P6 pack `markets` (แยก package · entry point): ถอดแกนวิเคราะห์ของ radar_lib ครบ (อ่านไฟล์ · นาฬิกาตลาด/วันหยุด · flow CMF/OBV/RVOL/IPI · view ราย TF · stage full/short/ez + trap · coil · levels · regime · sector · trade setup (SL ≥1.5 ATR · TP ชนแนวต้านจริง) · rank สั้น · coiled spring · conviction) · ทุกเกณฑ์เป็น `MarketParams` (ค่าเริ่มต้น = ของเดิม) · ผลเป็น code · ไม่มีพอร์ต/บัญชี/NAV · playbook 4 ตัว (uipt-screen · short-rank · high-conviction = active · coiled-spring = provisional) · **parity กับ stock-radar บน export 23 ต.ค.: 855 ตัว · เทียบ 90,925 ค่า · ต่าง 0** (แก้เกณฑ์ 2 ตัว = ต่าง 806 → ตัวเทียบใช้ได้จริง) · รันจริงบน dev ผ่าน worker 9 วินาที · docs/markets-pack.md | ✅ | `87f3a3f` |
| P7 ท่อ event กลาง (ฝั่ง engine): outbox ใน transaction เดียวกับการเปลี่ยน · DB กระจายตามประเภท + project · subscription หลายราย (project / ทั้งระบบ) + callback ต่อคำขอ (run · อัปโหลดเอกสาร · sync · eval · answer) · CloudEvents 1.0 + ลายเซ็น Standard Webhooks (v1 HMAC + v1a Ed25519 กุญแจเผยแพร่) · คิวแยกต่อผู้รับ (ส่งทีละ 1 ต่อราย) · retry 9 ครั้ง ~3 วัน + Retry-After · 410/ตาย 5 ครั้ง = ปิด · dead-letter + ส่งซ้ำ · event บาง + ลิงก์ API/UI (deep link `?tab=runs&run=`) · job.failed กลางทุกงาน · UI แท็บ Event + หน้า admin · docs/events.md | ✅ | `dedb3bd` |
| P7 ฝั่ง z-service: ตัวรับ event กลาง `POST /api/events/inbound/<ผู้ส่ง>` (ตรวจลายเซ็น v1/v1a · เวลา ±300 วิ · CloudEvents 1.0 · เก็บครั้งเดียวต่อ webhook-id · ผู้ส่งเป็น config `ZS_EVENT_SENDERS`) + หน้า UI Event ขาเข้า (ลิงก์กลับไปผลลัพธ์) · ทดสอบจริง 2 ระบบ: subscription + callback ส่งถึง 204 ทั้งหมด | ✅ | z-service `3c3bff6` (branch feat/web-ui) |
| P8 Synapse: แหล่ง git อ่านอย่างเดียว (เฉพาะโฟลเดอร์ที่ operator อนุญาต) · mapping เป็นข้อมูล (include/exclude/rules → rules/evidence/docs/code/ignore) · ตัดข้อมูลส่วนตัวก่อนเก็บ (อีเมล · โฟลเดอร์ home · ชื่อ user/เครื่อง · token/key · pattern ต่อแหล่ง · ลบทั้งบรรทัด) · ตัวเลขในบรรทัดที่เพิ่ม = รายการ measure (ต้องวัดซ้ำ) · ข้อเสนอรีวิวทีละรายการ · รับความรู้ = เอกสาร version ใหม่ (trust claimed) · โค้ด = รายการงาน tasks.md · ตรวจตามเวลา (DB สร้างงาน) · event synapse.proposal_created · UI Admin → Synapse · docs/synapse.md · ทดสอบจริงกับ stock-radar (อ่านอย่างเดียว เฉพาะ SKILL.md + references): ข้อเสนอ 109 รายการ (ความรู้ 33 · ผลวัดที่ต้องวัดซ้ำ 76 เช่น "ชนะ SPY 3/9") · ตัดข้อมูล 195 จุด · ตรวจรั่ว: ไม่มีชื่อ user/โฟลเดอร์ home/ชื่อโบรก/ไฟล์พอร์ต · รับ 1 รายการ = เอกสารใหม่ (claimed) | ✅ | `a3e3903` + `7367319` |
| P9b ตรวจก่อนใช้งานจริง (25 ต.ค.): build image จริง (จำกัด 4 core) · compose ขึ้นครบ (role app ไม่มี BYPASSRLS · migration 0016) · ทดสอบไป-กลับกับ z-service เวอร์ชันใหม่: connector ดึง export จริง 9 ชุด (73 วิ) → screen ได้ 39 ตัว/risk_off ตรงกับ CSV เดิม → z-service รับ event 11 รายการ + callback · Synapse ใน container · backup/restore ตรงทุกตาราง · worker 2 ตัวไม่ทำงานซ้ำ · CLI + MCP ผ่าน key · แก้ที่เจอ: secret แทนที่ซ้ำ 500 · lease งานยาวโดนแย่ง (heartbeat) · git ใน container · โมเดล embedding เปลี่ยนเป็น EmbeddingGemma-300m (เร็วกว่า 6 เท่า คุณภาพเท่ากันเมื่อมี reranker) + `mindgrid admin reindex` | ✅ | (commit นี้) |
| P10 ครบตามแผน §7 (26 ต.ค.): **DOCX** (หัวข้อจาก style/outline หรือขนาดตัวอักษรถ้าไม่มี style · ตาราง · กัน zip bomb + DTD · ทดสอบไฟล์ Word จริงใน container: อัปโหลด → index → ค้นเจอหัวข้อถูก) · **contextual retrieval** (`index.contextualize` · บริบท 1–2 ประโยคต่อ chunk ใช้ทั้ง embed + BM25 · chunk ที่ไม่เปลี่ยนใช้บริบทเดิม · LLM ล่ม = index แบบไม่มีบริบท · migration 0018) · **query rewrite** (`recall.rewrite` · ค้นทั้งคำถามเดิม + คำที่เกลา · reranker เทียบคำถามเดิม · เกินเวลา = ข้าม) · **LLM ตัดสินใน evals** (context yes/partly/no + faithfulness · เป็นงานในคิว · event `eval.judged` · ตาราง eval_judgements migration 0019 · UI Evals เลือก judge ได้) · ทุกขั้นปิดเป็นค่าตั้งต้น ใช้ provider เดียวกับการตอบ (gemini/local) · ทดสอบด้วย LLM จำลอง (ยังไม่ได้ลองกับโมเดลจริง: ถอน qwen ออกจากเครื่องแล้ว · ไม่มี Gemini key) · MCP ลงทะเบียนใน Claude Code (โปรเจค stock-radar · profile docker) ทดสอบจริงด้วย `claude -p`: list_projects · recall · list_playbooks · verify_citations ok · run_playbook 39 ตัว | ✅ | `7184a47` + `42e2f08` |
| P9c วัดกับเอกสารจริง (26 ต.ค.): โปรเจคทดสอบ = ไฟล์ skill จริง 37 ไฟล์ (1,445 chunk) · คำถามไทย/อังกฤษ 18 ข้อ (นอกเรื่อง 4) · reranker 10 ชิ้น × ต้นข้อความ 500 ตัวอักษร = เจอครบ 1.00 · MRR 0.95 · นอกเรื่องตอบว่าไม่มี 4/4 · ~3 วิ/คำถามบน Mac (nice) — เดิม 20 × 2000 ช้า 20 เท่า · ลองตัดส่วนที่ตรงคำถาม (focus window) แพ้ตัดต้นข้อความ → ถอดออก · ไม่ใช้ reranker: 0.5 วิ เจอ 0.93 · นอกเรื่อง 4/4 (ต้องมีคำตรงหรือระยะ ≤ ค่าที่วัดต่อโมเดล: Gemma 0.71 · Qwen 0.6) · ใช้ vector เดิมซ้ำเมื่อข้อความ chunk เหมือนเดิม (migration 0017 · ของจริง 503/624 chunk ไม่ต้อง embed ใหม่) · บั๊ก Ollama: context ตั้งต้น 4096 ตัด prompt ไทยเงียบ ๆ → ขอ `num_ctx` 16384 + ตัดข้อความอันดับท้ายถ้าไม่พอ · ทดสอบคำตอบจริงด้วย qwen3:1.7b: ไทย/อังกฤษถูก มีอ้างอิง · เอกสารขั้นต่อ z-service ตัวจริง docs/zservice-go-live.md | ✅ | (commit นี้) |
| P9 ขึ้นใช้จริง: Docker image เดียว (web build + backend `uv sync --frozen` · non-root · healthcheck · base image ตรึง digest) · compose (Postgres 18 + pgvector · migrate ครั้งเดียว · api · worker scale ได้) · role app ไม่มี BYPASSRLS · `/v1/ready` · runbook (ติดตั้ง · superadmin คนแรก · อัปเกรด · backup/restore · scale · หมุน secret · monitoring) · load test ผ่าน API key จริง: API ธรรมดา p50 9 ms · ค้น+rerank 4 พร้อมกัน p50 1.4 s p95 3.2 s · ยังไม่ได้ build image จริง (Docker daemon ไม่ได้เปิดบนเครื่องนี้) — ตรวจ compose + ขั้น uv แล้ว | ✅ | (commit นี้) |

ทดสอบจริงบน dev server 25 ต.ค.: อัปโหลด → worker → Qwen3-Embedding-0.6B-Q ในเครื่อง → recall 3 ทาง + rerank · eval 12 ข้อ (ไทย+อังกฤษ · นอกเรื่อง 4 ข้อ): มี reranker = hit/MRR/nDCG/การไม่ตอบ 1.0 ทุกตัว · ไม่มี reranker MRR 0.94 nDCG 0.95 · คำถามละ 0.54–0.80 วินาที · ยังไม่ได้ทดสอบกับ Ollama/Gemini ตัวจริง (เครื่องนี้ไม่มี Ollama · ไม่มี Gemini key)

ทดสอบกับ PostgreSQL 18 + pgvector จริง (ฐาน test แยก) · migration ทุกตัว downgrade ได้ (gate รัน round-trip ทุกครั้ง) · `alembic check` ยืนยัน model ตรง schema

## 16. แหล่งอ้างอิง (ดึงจริง 25 ต.ค. 2026)

- endoflife.date API: python · go · postgresql · mongodb · nodejs
- PyPI JSON API: เวอร์ชัน + wheel cp314/cp315 ของทุก library ใน §5
- npm registry: react · vite · @tanstack/* · tailwindcss · zod · paraglide · typescript
- GitHub releases/tags: pgvector · eino · langchaingo · pgx · sqlc · docling · ollama · pgvectorscale · paradedb
- MongoDB Search/Vector Search GA บน Community: https://www.mongodb.com/products/updates/now-ga-mongodb-search-and-vector-search-for-community-edition/ · release notes: https://www.mongodb.com/docs/search/self-managed/current/release-notes/
- Gemini embeddings: https://ai.google.dev/gemini-api/docs/embeddings · Gemini Embedding 2: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/embedding-2
- RAG ค้นคว้า ต.ค. 2026 (ใช้ใน §7):
  - hybrid + rerank + agentic: https://blog.starmorph.com/blog/rag-techniques-compared-best-practices-guide · https://www.atolio.com/blog/enterprise-rag-guide · ARAGOG https://arxiv.org/pdf/2404.01037
  - chunking: https://www.firecrawl.dev/blog/best-chunking-strategies-rag · https://www.premai.io/blog/rag-chunking-strategies-the-2026-benchmark-guide/ · https://www.splunk.com/en_us/blog/artificial-intelligence/chunking-techniques.html
  - reranker: https://mixpeek.com/curated-lists/best-rerankers · https://futureagi.com/blog/best-rerankers-for-rag-2026/
  - GraphRAG: https://atlan.com/know/knowledge-graphs-vs-rag-for-ai/ · https://techsy.io/en/blog/graphrag-guide · https://www.beri.net/article/graphrag-vs-vector-rag-indexing-query-cost-lightrag-lazygraphrag-2026
  - PDF/ภาพ: https://arxiv.org/pdf/2505.05666 · https://arxiv.org/pdf/2603.04238 · https://tensoria.fr/en/blog/multimodal-rag-images-pdfs-tables
  - evals: https://atlan.com/know/llm-evaluation-frameworks-compared/ · https://futureagi.com/blog/what-is-rag-evaluation-2026/
  - security: https://www.wiz.io/academy/ai-security/owasp-llm-top-10 · https://www.lakera.ai/blog/indirect-prompt-injection
  - pgvector filter: https://www.thenile.dev/blog/pgvector-080 · https://render.com/articles/multi-tenant-rag-postgresql-pgvector · https://clickhouse.com/resources/engineering/scale-vector-search-postgres
  - MCP 2026-07-28: https://blog.modelcontextprotocol.io/posts/2026-07-28/ · https://modelcontextprotocol.io/specification/2026-07-28/basic/transports
  - embedding: https://www.premai.io/blog/best-embedding-models-for-rag-2026-ranked-by-mteb-score-cost-and-self-hosting/ · Qwen3 Embedding https://arxiv.org/pdf/2506.05176
  - OTel GenAI: https://john-hodge.com/blog/opentelemetry-genai-semantic-conventions/ · https://greptime.com/blogs/2026-05-09-opentelemetry-genai-semantic-conventions
  - ตาราง/CSV: https://docs.anyscale.com/rag/structured-data · https://arxiv.org/pdf/2605.04962
  - Gemini File Search: https://blog.google/innovation-and-ai/technology/developers-tools/file-search-gemini-api/
- catalog stock-radar (อ่านจริงทุก skill วันนี้): pipeline · ~40 ความสามารถ · กฎ · ของส่วนตัว · ของซ้ำ · blocker
- z-service: `security/machine/scopes.py` · `domains/exports/routes.py` · `tools/zsvc_client.py`

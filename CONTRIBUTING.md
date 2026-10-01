# Contributing to Valkey-Samples

Thank you for contributing! This repository collects cookbooks, sample applications, and integrations that demonstrate Valkey capabilities. Contributions are welcome from everyone.

## Scope

See the [README](README.md) for this repository's audience and purpose. Contributions that fall outside that scope will be redirected during review.

### Out of Scope

The following do **not** belong in this repository:

- **Curated link lists** — belong on the [Valkey website](https://valkey.io) or documentation wiki where they can be maintained as living content.
- **Unreproducible builds** — anything requiring private artifacts, unreleased software, or local-only dependencies.
- **Marketing content** — uncited performance claims, promotional language, or product demos disguised as tutorials.
- **Single-vendor tutorials** — content that can only be completed with one cloud provider's credentials. The default path must be completable without any specific vendor account.
- **Internal tooling experiments** — prototypes, spike work, or internal tools that aren't intended for community use.

## Code of Conduct

This project follows the [Contributor Covenant v2.0](https://www.contributor-covenant.org/version/2/0/code_of_conduct/). By participating you agree to abide by its terms.

## License

All contributions are made under the [BSD-3-Clause License](LICENSE). By submitting a pull request, you agree that your contributions will be licensed under the same terms.

## Developer Certificate of Origin (DCO)

All commits **must** include a `Signed-off-by` trailer certifying you have the right to submit the contribution. This is mandatory across all `valkey-io` repositories.

```
Signed-off-by: Your Name <your.email@example.com>
```

Use `git commit -s` (or `--signoff`) to add this automatically. PRs that fail the DCO check will not be merged.

## Getting Started

**All new content** (cookbooks, demos, and sample apps) **requires a proposal issue before implementation.** Open an issue using the [new-sample template](.github/ISSUE_TEMPLATE/new-sample.md) describing the Valkey concept, target language, and expected scope. A maintainer will approve or request changes before you begin coding. This prevents wasted effort on content that doesn't fit the repository's goals.

1. Open a proposal issue using the [new-sample template](.github/ISSUE_TEMPLATE/new-sample.md)
2. Wait for maintainer approval
3. Fork the repository
4. Create a feature branch from `main`
5. Make your changes
6. Ensure all commits are signed off
7. Open a pull request against `main`

## Acceptance Criteria

Every contribution must meet these requirements to be merged:

- **Buildable from a clean clone** — all dependencies are publicly available and pinned to stable versions
- **Runs against stable Valkey** — use `valkey/valkey-bundle` with a pinned version tag (e.g., `valkey/valkey-bundle:8.1.7`). Never use `:latest` or `:unstable`. CI validates samples against a matrix of supported Valkey versions.
- **Uses current stable client libraries** — use the latest published release of the official Valkey client for your language (valkey-glide, valkey-py, etc.)
- **Focused on Valkey** — the sample demonstrates Valkey features, not application scaffolding. Readers should be able to identify the Valkey patterns without excavating them from UI code.
- **Self-contained** — each sample directory is independently runnable with its own dependency manifest (`pyproject.toml` + `uv.lock` for Python, `go.mod`, `package.json`, etc.)
- **Python cookbooks use [uv](https://docs.astral.sh/uv/)** — manage dependencies with a committed `pyproject.toml` and `uv.lock` (not a bare `requirements.txt`). Pin `requires-python` so the interpreter is reproduced along with the packages, list `uv` in the cookbook's Prerequisites with an install pointer, and have readers run `uv sync` / `uv run`. This locks the full transitive tree, so a clean clone reproduces the exact environment CI tests against.
- **All references publicly accessible** — all links, paths, and package names resolve for any community member (no private trackers, local paths, or internal wikis)
- **Factual and substantiated** — all performance claims backed with objective, measurable proof and linked to source benchmarks. Use a neutral, technical tone.

## Vendor Neutrality

Valkey is a community project under the Linux Foundation. Content in this repository must be vendor-neutral by default:

- **LLM/AI examples** use a widely accessible provider (e.g., OpenAI, Ollama for local) as the default path. Vendor-specific alternatives (AWS Bedrock, GCP Vertex AI, Azure OpenAI) are welcome as clearly labeled optional sections, not the primary walkthrough.
- **Production deployment** guidance must cover at least two cloud providers equally, OR remain generic (connection strings, TLS config) and link to provider-specific documentation externally. No single cloud provider should be the default deployment target.
- **Client libraries** use official Valkey clients. If a cloud-specific client wrapper is demonstrated, the generic equivalent must be shown first.
- **Integrations** are listed based on their relevance to Valkey, not their organizational origin. Disclose provenance where it's not obvious (e.g., "Strands Agents (Amazon)" alongside "CrewAI").
- **Affiliation disclosure** — if a sample integrates a product from a specific company, that relationship must be disclosed in the sample's README (e.g., "Strands Agents is an Amazon open-source project"). Undisclosed corporate promotion is not acceptable in a Linux Foundation project.

Contributions that route readers exclusively through one vendor's ecosystem will be asked to refactor during review.

## Pull Request Guidelines

- **One logical change per PR** — keep PRs focused and reviewable
- **Link related issues** — use "Fixes #N" or "Relates to #N" in the PR description
- **Stay responsive** — address review feedback promptly
- **Rebase on main** — keep your branch up to date before requesting review

## Review Process

- Every PR requires **at least one maintainer approval** before merge
- Samples are **tested in CI** — if CI can't build and run your sample, it won't merge
- For new cookbooks or sample categories, open an issue or discussion **before** writing code to align on scope

### PR Review Checklist

Reviewers evaluate every PR against this checklist. Use it as a self-check before submitting:

- [ ] Builds and runs from a clean clone
- [ ] Runs against current stable Valkey (or Valkey Bundle)
- [ ] No private links, internal references, or local paths
- [ ] No marketing language or uncited claims
- [ ] Vendor-neutral by default (affiliation disclosed where applicable)
- [ ] README explains the Valkey concept demonstrated, prerequisites, and how to run
- [ ] Dependencies pinned to specific versions
- [ ] CI validates the sample

---

## Cookbook Format

Cookbooks are **Jupyter notebooks (`.ipynb`)**, whatever the language. Prose and runnable code live
in one artifact, so the reader executes cells as they read and CI executes the exact code the reader
runs. Jupyter has kernels for the languages this repo uses (Python, and via community kernels Go,
TypeScript/JavaScript, Java), so a cookbook in any of them is a notebook.

A cookbook is **one or more notebooks**. A single self-contained notebook is the default and the
simplest thing that works; only split into a numbered series when the material is genuinely too long
for one notebook to hold comfortably. The notebook's own opening cell carries the title, audience,
and setup, so a single-notebook cookbook needs no separate `README.md` index.

A notebook holds the *content*, but a cookbook still needs a few real files on disk that a notebook
cannot carry — the runtime environment (dependency manifest, `docker-compose.yml`) and any shared
helper module. See [Cookbook Structure](#cookbook-structure) for the layout and
[Cookbook Content Requirements](#cookbook-content-requirements) for the content every notebook must
include.

## Cookbook Content Requirements

These content rules apply to **every** cookbook notebook. [Cookbook Structure](#cookbook-structure)
covers the file layout.

### Required Files

Every cookbook **must** have:

| File | Purpose |
|------|---------|
| Cookbook notebook(s) | One `.ipynb` for a single-notebook cookbook (name it for the topic, e.g. `kv-caching-with-valkey.ipynb`), or a numbered series (`01-getting-started.ipynb`, `02-<topic>.ipynb`, …) when the material needs splitting |
| Dependency manifest | `pyproject.toml` + `uv.lock` (Python) / `package.json` / `go.mod` / `pom.xml` — the language environment CI builds before running the notebooks |
| `docker-compose.yml` | Starts Valkey for the notebooks (include a healthcheck so `--wait` blocks until it's ready) |

They all sit in the same cookbook directory (see [Cookbook Structure](#cookbook-structure)). A
separate `README.md` is **not** required — the notebook's opening cell is the index; add a README
only for a multi-notebook series that benefits from a top-level table (see
[Multi-notebook series](#multi-notebook-series)).

### Notebook Structure

A cookbook notebook follows this shape, expressed across its cells (see
[Notebook Content Structure](#notebook-content-structure) for how the pieces map to cells). Use
topical headings that describe what each part does — not a rigid `## Step 1 / Step 2` sequence:

```markdown
# Title with Framework + Valkey

> One-sentence lead describing what the reader will build or learn.

**Difficulty** · Language · ~Time

**Who is this for:** [Target audience — e.g., "Python developers building RAG pipelines who want low-latency vector caching"]

[Optional 1–2 paragraph intro explaining why this matters]

## How to run this notebook

[Prerequisites, then the setup: `docker compose up -d --wait`, install deps, create/select the
kernel. Include the security callout after the Valkey startup command.]

## <Topic heading> ... ## <Topic heading>

[Runnable cells interleaved with prose. Each code cell prints the signal the reader should look for
(key counts, cache hits, timings) so success is visible. Headings describe the concept, e.g.
"Turn 1: cold", not "Step 3".]

## How It Works   (optional but recommended)

[Table or diagram explaining the architecture]

## Configuration Reference   (when a component has configurable options)

[Table of config options — or an annotated config file alongside the notebook]
```

### Mandatory Elements

| Element | Details |
|---------|---------|
| **Lead blockquote** | One sentence after the `# Title`, wrapped in `> ...` |
| **Difficulty badge line** | `**Difficulty** · Language · ~Time` |
| **Audience line** | `**Who is this for:**` — one sentence identifying the target reader |
| **How-to-run section** | Prerequisites + the setup commands (start Valkey, install deps, select the kernel) |
| **Security callout** | After the Valkey startup command (in the first notebook, for a series) |
| **Runnable cells with visible signals** | Every code cell runs top-to-bottom; cells print what the reader should observe |

A **navigation footer** (prev/next links) is required only for a multi-notebook series — a single
notebook needs none. `## Step N:` headings are **not** required or preferred; use topical headings.

### Security Callout (Required)

The notebook must include this after the Valkey startup command (in the first notebook, for a
series):

```markdown
> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).
```

### Valkey Startup

Cookbooks start Valkey through their `docker-compose.yml` (a required file — see [Required Files](#required-files)), so the how-to-run section uses Compose rather than a bare `docker run`:

````markdown
```bash
docker compose up -d --wait
```
````

Prefer the `valkey/valkey-bundle` image in that compose file — it includes the Search and JSON modules most cookbooks need. Always pin a specific version tag; never use `:latest`. Give the Valkey service a healthcheck so `docker compose up --wait` blocks until Valkey is actually ready (without one, `--wait` can return before the container accepts connections).

### How It Works Section

Include a component table or architecture explanation in at least the first cookbook:

```markdown
## How It Works

| Component | Role |
|-----------|------|
| Component A | What it does |
| Component B | What it does |
| Valkey Search | What it provides |
```

### Configuration Reference Tables

When a component has configurable options, include a reference table:

```markdown
## Configuration Reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `host` | ✓ | — | Valkey host address |
| `port` | — | `6379` | Valkey port |
```

---

## Cookbook Structure

Cookbooks live under `cookbooks/` organized by category and language, with the notebook(s) and the
support files alongside them in the same directory (no separate `sample/` subtree). A single-notebook
cookbook is the default:

```
cookbooks/
├── framework-integrations/
│   └── <language>/
│       └── <framework-name>/
│           ├── <topic>-with-valkey.ipynb   (the cookbook; opening cell is the index)
│           ├── <shared-helper>             (optional — e.g. common.py / common.ts)
│           ├── <config-reference>          (optional — e.g. an annotated <tool>_config.yaml)
│           ├── <test-file>                 (optional — e.g. test_<name>.py for structural/live checks)
│           ├── <dependency-manifest>       (pyproject.toml + uv.lock / package.json / go.mod / pom.xml)
│           ├── docker-compose.yml          (starts Valkey for the notebook)
│           └── .gitignore
└── use-cases/
    └── <language>/
        └── <use-case-name>/
            └── ...
```

For a multi-notebook series, replace the single `.ipynb` with numbered notebooks
(`01-getting-started.ipynb`, `02-<topic>.ipynb`, …) and add a `README.md` index — see
[Multi-notebook series](#multi-notebook-series).

### Directory Naming

- Language directory: lowercase (e.g., `python`, `go`, `typescript`, `java`)
- Cookbook directory: lowercase, hyphenated — match the canonical package/project name where possible
- Example paths: `cookbooks/framework-integrations/python/langchain/`, `cookbooks/use-cases/go/rate-limiting/`

### Why a few files sit alongside the notebooks

A notebook holds the prose and the runnable cells, but not the *environment*:

| File | Why it can't live inside the notebook |
|------|---------------------------------------|
| Dependency manifest | CI (and readers) build the language environment *before* launching the notebook (`pyproject.toml` + `uv.lock` for Python, `package.json`, `go.mod`, `pom.xml`, …). |
| `docker-compose.yml` | Valkey runs as a container started outside the kernel; cells connect to it. |
| Shared helper (optional) | Helpers imported by multiple notebooks — keep them in one module rather than duplicating cells across notebooks (duplicated utility code is a review failure). |
| `.gitignore` | Ignores build/venv dirs and notebook checkpoints (see [`.gitignore`](#gitignore) below). |

### Kernel per language

Each cookbook runs on the Jupyter kernel for its language; the notebook's how-to-run section
documents how to install and select it:

| Language | Kernel |
|----------|--------|
| Python | `ipykernel` (built in) |
| Go | [`gophernotes`](https://github.com/gopherdata/gophernotes) |
| TypeScript / JavaScript | [`tslab`](https://github.com/yunabe/tslab) |
| Java | [`IJava`](https://github.com/SpencerPark/IJava) |

### Notebook Content Structure

Each notebook expresses the [Cookbook Content Requirements](#cookbook-content-requirements) as cells:

- The **opening markdown cell** holds the title, lead blockquote, difficulty badge, and audience
  line. For a single-notebook cookbook it is also the index — there is no separate README.
- A **"How to run this notebook" section** near the top: prerequisites, `docker compose up -d --wait`,
  installing the language deps, and creating/selecting the kernel.
- **Topical markdown headings** describe each part by what it does (e.g. "Turn 1: cold"), followed by
  the code cell for that part. Do **not** use a rigid `## Step N:` sequence.
- **Every code cell must execute top-to-bottom without error** against a running Valkey — this is
  what CI enforces — and should print the signal the reader is meant to observe.
- **Committed notebooks must have cleared or reproducible outputs.** Prefer clearing outputs before
  commit (`jupyter nbconvert --clear-output`); CI re-executes to produce them. Never commit
  notebooks containing secrets, tokens, or machine-specific paths in cell outputs.
- **Make runs reproducible and idempotent.** If a cell's result depends on prior state (e.g. a cache
  that persists across runs), give it a per-run nonce so re-running produces the same story — for a
  cache-hit demo, tag the input with a fresh `uuid` so the "cold" path is genuinely cold on every run.
- **Fail early on unmet requirements.** If the cookbook needs more than a default runtime provides
  (memory, a service, a model), add a preflight cell that checks and stops with a clear message
  rather than failing deep in a later cell.
- The **security callout, How It Works, and Configuration Reference** are markdown cells.
- A **navigation footer** is the final markdown cell **only in a multi-notebook series**; link sibling
  notebooks by their `.ipynb` filenames (e.g. `[← 01 - Getting Started](01-getting-started.ipynb)`).
  A single-notebook cookbook has no footer.

### `.gitignore`

Include at least the notebook checkpoint dir plus your language's build/venv dirs, e.g. for Python:

```gitignore
.venv/
__pycache__/
.ipynb_checkpoints/
```

---

## Multi-notebook series

Most cookbooks are a single notebook. When the material is genuinely too large for one — a multi-part
track that builds across several sittings — split it into numbered notebooks
(`01-getting-started.ipynb`, `02-<topic>.ipynb`, …), give each a prev/next navigation footer, and add
a `README.md` index in the cookbook directory:

```markdown
# Framework with Valkey

> One-line description of the integration.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.ipynb)</nobr> | What this cookbook covers. | Beginner, ~15 min, Python |
| 02 | <nobr>[Topic](02-topic.ipynb)</nobr> | What this cookbook covers. | Intermediate, ~20 min, Python |
```

The `01-getting-started.ipynb` notebook is always Beginner difficulty. A single-notebook cookbook
needs none of this — its opening cell is the index.

---

## Runnable Code & CI

Every cookbook's code lives in its notebook cells; the runtime files
(`docker-compose.yml`, dependency manifest, optional shared helper) sit alongside the notebooks in
the cookbook directory (see [Cookbook Structure](#cookbook-structure)). The goal: a reader clones
the repo, runs one or two setup commands, opens the notebooks, and every cell runs.

### Runnable Setup

`docker-compose.yml` starts Valkey; the reader then installs the language deps, selects the kernel,
and runs the notebook. A typical flow:

```bash
cd cookbooks/framework-integrations/<language>/<name>
docker compose up -d --wait            # starts Valkey
# install language deps (for Python: `uv sync`), then open the
# notebook and select the cookbook's kernel — see the notebook's how-to-run section
```

If a cookbook needs anything beyond Valkey (an API key, a GPU, a proprietary model), keep a free,
runnable default path — mock or stub the paid/specialized parts — and document what any optional
part needs.

### Guidelines

- **Every cell must run** — verify the notebooks execute top-to-bottom before submitting
- **Pin dependency versions** — no open-ended version ranges
- **Show expected output** — the executed cells (or the surrounding prose) make success verifiable
- **Clean up resources** — document how to tear down (e.g., `docker compose down`)
- **Mock expensive dependencies when possible** — use local embedders, stub responses, or deterministic test data in the getting-started section
- **The default path must run for free** — no paid account, cloud credentials, or specialized
  hardware required to complete the core cookbook (this is the [Vendor Neutrality](#vendor-neutrality)
  rule applied to cookbooks). If a paid LLM (OpenAI, Anthropic, Bedrock, etc.) is shown, also include
  a working self-hosted equivalent (e.g., Ollama) so any reader can run it.
- **Paid or specialized capabilities are optional extensions, never the only path.** If some
  advanced part genuinely can't run for free (e.g., it needs a GPU or a paid API), scope it as a
  clearly-labeled optional section, keep the default path free and runnable, and state prominently
  what the optional part requires and where to find it.

### CI Validation

All cookbooks must pass CI before merge:

- **Notebook execution** — CI installs the cookbook's dependencies, starts Valkey via its
  `docker-compose.yml`, and executes every `.ipynb` end-to-end (e.g. `pytest --nbmake` or
  `jupyter nbconvert --execute` for Python; the equivalent kernel run for other languages). A cell
  that raises fails the build, so the code a reader runs is the code CI runs.
- **Version matrix** — CI runs against multiple Valkey versions (currently 8.1.x and 9.x) to ensure
  compatibility across supported releases
- **Lint check** — markdown (READMEs and notebook markdown cells) passes linting, links resolve

If a cookbook requires paid external services, guard those cells so the default CI path executes
without credentials (e.g. skip or use a local model when the key is absent).

CI runs on every pull request **and** on a weekly schedule to catch external dependency breakage
(e.g., upstream library releases that introduce incompatibilities). If a weekly run fails, a
maintainer will open an issue to track the fix.

---

## Cookbook Progression

A cookbook builds from a working baseline to the interesting result. In a single notebook this is the
arc of its sections; in a multi-notebook series it maps to the numbered notebooks:

| Stage | Difficulty | Content |
|-------|-----------|---------|
| Getting Started | Beginner | Connect, basic operation, verify it works |
| Core Feature | Intermediate | The main use case (RAG, caching, etc.) |
| Advanced / Production | Intermediate–Advanced | Scaling, security, deployment patterns |

Keep the opening achievable in ≤15 minutes with no paid dependencies.

---

## Demo Structure

Demos are focused, lightweight applications that demonstrate a single Valkey use case. They are not complete applications — include only the code necessary to illustrate the use case. A developer should be able to clone, run, and see the Valkey feature in action.

Demos live under `demos/` organized by language:

```
demos/
├── python/
│   ├── vector-search/
│   └── rate-limiting/
├── go/
│   └── pub-sub/
├── typescript/
│   └── session-cache/
└── java/
    └── cache-aside/
```

### Directory Naming

- Language directory: lowercase (e.g., `python`, `go`, `typescript`, `java`)
- Sample directory: lowercase, hyphenated use-case name (e.g., `vector-search`, `pub-sub`)
- Example path: `demos/python/vector-search/`

### Required Files

Every demo **must** include:

| File | Purpose |
|------|---------|
| `README.md` | Overview, prerequisites, how to run, expected output |
| `docker-compose.yml` | One-command run experience (starts Valkey + demo) |
| Dependency file | `pyproject.toml` + `uv.lock` (Python), `go.mod`, `package.json`, etc. |
| Source code | Minimal implementation demonstrating the use case |
| `.gitignore` | Exclude binaries, venvs, node_modules, etc. |

### Guidelines

- **Single use case** — each demo illustrates exactly one Valkey feature or pattern
- **Minimal code** — only what's necessary to demonstrate the concept
- **Runs in under 5 minutes** — quick to clone and execute
- **No UI scaffolding** — focus on the Valkey interaction, not application chrome
- **Self-contained** — no dependencies on other demos or shared libraries

---

## Sample App Structure

Sample apps are more complete applications showing how multiple Valkey use cases work together. They may include data loading utilities, admin functionality, and richer application logic. Sample apps **must** include documentation highlighting where Valkey-relevant code lives so readers can find the important parts quickly.

Sample apps live under `samples/` organized by language:

```
samples/
├── python/
│   └── ecommerce-recommendations/
├── typescript/
│   └── realtime-leaderboard/
└── go/
    └── chat-app/
```

### Directory Naming

- Language directory: lowercase (e.g., `python`, `go`, `typescript`, `java`)
- App directory: lowercase, hyphenated app name (e.g., `ecommerce-recommendations`)
- Example path: `samples/python/ecommerce-recommendations/`

### Required Files

Every sample app **must** include:

| File | Purpose |
|------|---------|
| `README.md` | Overview, architecture, prerequisites, how to run, **Valkey code locations** |
| `docker-compose.yml` | One-command run experience |
| Dependency file | `pyproject.toml` + `uv.lock` (Python), `go.mod`, `package.json`, etc. |
| `src/` | Source directory with application code |
| `.gitignore` | Exclude binaries, venvs, node_modules, etc. |

### Valkey Code Documentation

The README **must** include a section highlighting where Valkey-relevant code lives:

```markdown
## Where to Find the Valkey Code

| File | Valkey Feature |
|------|---------------|
| `src/cache.py` | Semantic caching with vector search |
| `src/session.py` | Session management with TTL |
| `src/pubsub.py` | Real-time notifications via Pub/Sub |
```

### Guidelines

- **Multiple use cases** — demonstrate how Valkey features compose in a real application
- **Production-like patterns** — connection pooling, error handling, retry logic
- **Clear architecture documentation** — readers should understand the overall design
- **Valkey code is findable** — don't bury it under layers of application framework code
- **Data loading utilities welcome** — include scripts to seed demo data

---

## Writing Style

- **Be concise** — respect the reader's time
- **Show, don't tell** — working code over lengthy explanations
- **Use consistent terminology** — "Valkey" (not "Redis"), "valkey-glide" (not "redis-py" or "ioredis")
- **Explain "why"** — briefly explain design choices, not just "what"
- **No vendor lock-in** — keep examples cloud-agnostic; if a cloud service is used, note alternatives
- **Cite quantitative claims** — if you state a performance number, link to the benchmark or methodology. Unsourced claims will be removed in review.

---

## Commit Messages

Use clear, descriptive commit messages. We recommend (but don't enforce) conventional commit format:

```
feat(langchain): add RAG pipeline cookbook
fix(eino): correct yourEmbedder call signature
docs: update framework-integrations README
```

**Always sign off:** `git commit -s`

---

## Questions?

- Open a [GitHub Discussion](https://github.com/valkey-io/Valkey-Samples/discussions) for questions
- Open an [Issue](https://github.com/valkey-io/Valkey-Samples/issues) for bugs or feature requests
- Join the [Valkey community](https://valkey.io/community/) for broader project discussion

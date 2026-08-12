# Contributing to Valkey-Samples

Thank you for contributing! This repository collects cookbooks, sample applications, and integrations that demonstrate Valkey capabilities. Contributions are welcome from everyone.

## Scope

See the [README](README.md) for this repository's audience and purpose. Contributions that fall outside that scope will be redirected during review.

### Out of Scope

The following content types do not belong in this repository:

- **Curated link lists** — collections of external URLs belong on the [Valkey website](https://valkey.io/) or documentation wiki, not in a samples repository.
- **Unreproducible builds** — if it depends on unreleased software, private artifacts, early-access tooling, or internal infrastructure, it is not ready for this repository.
- **Marketing content** — uncited performance claims, cost comparisons, and promotional language are rejected in review. State facts and link to benchmarks.
- **Single-vendor tutorials** — a tutorial that can only be completed with credentials from one specific cloud provider does not belong as the primary path.
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

- **Buildable from a clean clone** — no private dependencies, no unpublished branches, no local paths
- **Runs against stable Valkey** — use `valkey/valkey:latest` or `valkey/valkey-bundle:latest` (released stable tags). Never depend on `:unstable` or unreleased features.
- **Uses current stable client libraries** — use the latest published release of the official Valkey client for your language (valkey-glide, valkey-py, etc.)
- **Focused on Valkey** — the sample demonstrates Valkey features, not application scaffolding. Readers should be able to identify the Valkey patterns without excavating them from UI code.
- **Self-contained** — each sample directory is independently runnable with its own dependency file (`requirements.txt`, `go.mod`, `package.json`, etc.)
- **No internal references** — no private Jira links, local file paths, internal wiki references, or proprietary package names in any committed file
- **No marketing language** — no uncited performance claims ("60% cost reduction"), no promotional tone. State facts; link to benchmarks if making quantitative claims.

## Vendor Neutrality

Valkey is a community project under the Linux Foundation. Content in this repository must be vendor-neutral by default:

- **LLM/AI examples** use a widely accessible provider (e.g., OpenAI, Ollama for local) as the default path. Vendor-specific alternatives (AWS Bedrock, GCP Vertex AI, Azure OpenAI) are welcome as clearly labeled optional sections, not the primary walkthrough.
- **Production deployment** guidance must either cover at least two cloud providers equally (e.g., ElastiCache AND Memorystore AND self-hosted), OR remain generic and link to provider-specific documentation externally. A section that only covers one provider's deployment path will not be accepted.
- **Client libraries** use official Valkey clients. If a cloud-specific client wrapper is demonstrated, the generic equivalent must be shown first.
- **Integrations** are listed based on their relevance to Valkey, not their organizational origin. Disclose provenance where it's not obvious (e.g., "Strands Agents (Amazon)" alongside "CrewAI").

Contributions that route readers exclusively through one vendor's ecosystem will be asked to refactor during review.

## Pull Request Guidelines

- **One logical change per PR** — keep PRs focused and reviewable
- **Link related issues** — use "Fixes #N" or "Relates to #N" in the PR description
- **Stay responsive** — address review feedback promptly
- **Rebase on main** — keep your branch up to date before requesting review

## Review Process

Every PR requires **at least one maintainer approval** before merge. Reviewers evaluate each submission against this checklist:

- [ ] Builds and runs from a clean clone
- [ ] Runs against current stable Valkey Bundle (Valkey-JSON, Valkey-Search, and Valkey-Bloom content friendly)
- [ ] No private links, internal references, or local paths
- [ ] No marketing language or uncited claims
- [ ] Vendor-neutral by default (see [Vendor Neutrality](#vendor-neutrality))
- [ ] README explains concept, prerequisites, and how to run
- [ ] Dependencies pinned to specific versions
- [ ] CI validates the sample

PRs that do not pass CI will not be merged. Use this checklist as a pre-submit self-check before requesting review.

---

## Cookbook Structure

Cookbooks live under `cookbooks/` organized by category:

```
cookbooks/
├── framework-integrations/
│   └── <language>/
│       └── <framework-name>/
│           ├── README.md
│           ├── 01-getting-started.md
│           ├── 02-<topic>.md
│           ├── ...
│           └── sample/          (optional — runnable code)
└── use-cases/
    └── <language>/
        └── <use-case-name>/
            └── ...
```

### Directory Naming

- Language directory: lowercase (e.g., `python`, `go`, `typescript`, `java`)
- Sample directory: lowercase, hyphenated — match the canonical package/project name where possible
- Example paths: `cookbooks/framework-integrations/python/langchain/`, `cookbooks/use-cases/go/rate-limiting/`

### Required Files

Every cookbook **must** have:

| File | Purpose |
|------|---------|
| `README.md` | Overview with linked table of all cookbooks in the track |
| `01-getting-started.md` | First cookbook — always Beginner difficulty |

### Cookbook File Structure

Every numbered `.md` file follows this structure:

```markdown
# Title with Framework + Valkey

> One-sentence lead describing what the reader will build or learn.

**Difficulty** · Language · ~Time

[Optional 1–2 paragraph intro explaining why this matters]

## Prerequisites

- Docker or Podman installed
- Language/runtime version requirement
- Any API keys or accounts needed

## Step 1: Start Valkey

[Docker + Podman commands, security callout]

## Step 2: ...

[Progressive steps with code blocks]

## How It Works

[Table or diagram explaining the architecture]

## Configuration Reference

[Table of config options — required for any component with configurable params]

---

[← 01 - Previous](01-previous.md) | [03 - Next →](03-next.md)
```

### Mandatory Elements

| Element | Details |
|---------|---------|
| **Lead blockquote** | One sentence after the `# Title`, wrapped in `> ...` |
| **Difficulty badge line** | `**Difficulty** · Language · ~Time` |
| **Prerequisites section** | Explicit `## Prerequisites` with bullet list |
| **Step-based headings** | `## Step N: Title` — progressive, numbered |
| **Navigation footer** | `---` rule + prev/next links at bottom |
| **Security callout** | Required in the first cookbook (01) after the Valkey startup command |

### Security Callout (Required)

Every `01-getting-started.md` must include this after the Docker startup:

```markdown
> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).
```

### Valkey Startup

Use the appropriate image:

- `valkey/valkey-bundle` — when the Search module is needed
- `valkey/valkey` — for plain key-value operations

```markdown
```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```
```

> **Note:** All examples use `docker`. Substitute `podman` if that's your container runtime — the commands are identical.

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

## README.md Format

Each cookbook directory's README.md:

```markdown
# Framework with Valkey

> One-line description of the integration.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | What this cookbook covers. | Beginner, ~15 min, Python |
| 02 | <nobr>[Topic](02-topic.md)</nobr> | What this cookbook covers. | Intermediate, ~20 min, Python |
```

---

## Sample Code (Required When Feasible)

Every cookbook **should** include a `sample/` directory with code that can be built and run locally via Docker. The goal: a reviewer or reader can clone the repo, run one or two commands, and see it work.

### Runnable Container

If the sample has dependencies beyond Valkey (an API key, a GPU, a proprietary model), provide a `docker-compose.yml` or `Dockerfile` that runs the parts that *can* run locally. If the entire sample requires a paid/external service, document that clearly and provide a mock or stub mode where possible.

The ideal experience:

```bash
cd cookbooks/framework-integrations/python/<name>/sample
docker compose up        # starts Valkey + runs the sample
```

Or at minimum:

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
<language-specific run command>   # e.g. go run ., python main.py, npm start
```

### Required Files

| File | Purpose |
|------|---------|
| `README.md` | How to run, prerequisites, expected output |
| `Dockerfile` or `docker-compose.yml` | Preferred — one-command run experience |
| Build file | `go.mod`, `package.json`, `requirements.txt`, `pom.xml`, etc. |
| Source code | Minimal, self-contained implementation |
| `.gitignore` | Exclude binaries, venvs, node_modules |

### Guidelines

- **Must build and run locally** — a contributor should verify their sample works before submitting
- **Pin dependency versions** — no open-ended version ranges
- **Include expected output** — so readers can verify success
- **Clean up resources** — document how to tear down (e.g., `docker compose down`)
- **Mock expensive dependencies when possible** — use local embedders, stub API responses, or deterministic test data for the getting-started sample
- **If using a paid LLM (OpenAI, Anthropic, Bedrock, etc.)**, also include a working configuration or example using a self-hosted model (e.g., Ollama). This ensures any reader can run the sample without a paid account.
- **If it can't run without a paid service**, state that prominently in the sample README and explain what's needed

### CI Validation

All samples must pass CI before merge:

- **Build check** — dependency install and compilation succeed in a clean environment
- **Run check** — the sample executes successfully against a Valkey container (no external services required for the default path)
- **Lint check** — markdown files pass linting, links resolve

CI runs on every pull request **and** on a weekly schedule to catch external dependency breakage (e.g., upstream library releases that introduce incompatibilities). If a weekly run fails, a maintainer will open an issue to track the fix.

If your sample requires paid external services (API keys, cloud accounts), provide a mock/stub mode that CI can exercise without credentials.

---

## Cookbook Progression

A cookbook track should follow this progression:

| # | Title | Difficulty | Content |
|---|-------|-----------|---------|
| 01 | Getting Started | Beginner | Connect, basic operation, verify it works |
| 02 | Core Feature | Intermediate | The main use case (RAG, caching, etc.) |
| 03+ | Advanced / Production | Intermediate–Advanced | Scaling, security, deployment patterns |

The first cookbook should be achievable in ≤15 minutes with no paid dependencies.

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
| Dependency file | `requirements.txt`, `go.mod`, `package.json`, etc. |
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
| Dependency file | `requirements.txt`, `go.mod`, `package.json`, etc. |
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

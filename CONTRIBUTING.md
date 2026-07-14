# Contributing to Valkey-Samples

Thank you for contributing! This repository collects cookbooks, sample applications, and integrations that demonstrate Valkey capabilities. Contributions are welcome from everyone.

## Scope

See the [README](README.md) for this repository's audience and purpose. Contributions that fall outside that scope will be redirected during review.

### Out of Scope

The following do **not** belong in this repository:

- **Full applications** (>~500 LoC of non-Valkey code) — showcase apps deserve their own repo with their own maintenance commitment. Extract the Valkey-specific patterns into a focused sample instead.
- **Curated link lists** — belong on the [Valkey website](https://valkey.io) or documentation wiki where they can be maintained as living content.
- **Unreproducible builds** — anything requiring private artifacts, unreleased software, or local-only dependencies.
- **Marketing content** — uncited performance claims, promotional language, or product demos disguised as tutorials.
- **Single-vendor tutorials** — content that can only be completed with one cloud provider's credentials. The default path must be completable without any specific vendor account.

## Code of Conduct

This project follows the [Contributor Covenant v2.0](https://www.contributor-covenant.org/version/2/0/code_of_conduct/). By participating you agree to abide by its terms.

## License

All contributions are made under the [MIT License](LICENSE). By submitting a pull request, you agree that your contributions will be licensed under the same terms.

## Developer Certificate of Origin (DCO)

All commits **must** include a `Signed-off-by` trailer certifying you have the right to submit the contribution. This is mandatory across all `valkey-io` repositories.

```
Signed-off-by: Your Name <your.email@example.com>
```

Use `git commit -s` (or `--signoff`) to add this automatically. PRs that fail the DCO check will not be merged.

## Getting Started

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes
4. Ensure all commits are signed off
5. Open a pull request against `main`

For significant additions (new cookbooks, new sample apps, major restructuring), **open an issue first** to discuss the approach.

## Acceptance Criteria

Every contribution must meet these requirements to be merged:

- **Buildable from a clean clone** — all dependencies are publicly available and pinned to stable versions
- **Runs against stable Valkey** — use `valkey/valkey-bundle` with a pinned version tag (e.g., `valkey/valkey-bundle:8.1.7`). Never use `:latest` or `:unstable`. CI validates samples against a matrix of supported Valkey versions.
- **Uses current stable client libraries** — use the latest published release of the official Valkey client for your language (valkey-glide, valkey-py, etc.)
- **Focused on Valkey** — the sample demonstrates Valkey features, not application scaffolding. Readers should be able to identify the Valkey patterns without excavating them from UI code.
- **Self-contained** — each sample directory is independently runnable with its own dependency file (`requirements.txt`, `go.mod`, `package.json`, etc.)
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

## Cookbook Structure

Cookbooks live under `cookbooks/` organized by category:

```
cookbooks/
├── framework-integrations/
│   └── <framework-name>/
│       ├── README.md
│       ├── 01-getting-started.md
│       ├── 02-<topic>.md
│       ├── ...
│       └── sample/          (optional — runnable code)
└── use-cases/
    └── <use-case-name>/
        └── ...
```

### Directory Naming

- Lowercase, hyphenated: `betterdb-agent-cache`, `node-rate-limiter-flexible`
- Match the canonical package/project name where possible

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

**Who is this for:** [Target audience — e.g., "Python developers building RAG pipelines who want low-latency vector caching" or "Backend engineers adding rate limiting to an existing Express app"]

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
| **Audience line** | `**Who is this for:**` — one sentence identifying the target reader |
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

Prefer `valkey/valkey-bundle` — it includes the Search and JSON modules that most cookbooks need. Always pin a specific version tag; never use `:latest`.

````markdown
```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:8.1.7
```
````

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

If the sample has dependencies beyond Valkey (an API key, a GPU, a proprietary model), provide a `docker-compose.yml` or `Dockerfile` that runs the parts that *can* run locally.
If the entire sample requires a paid/external service, document that clearly and provide a mock or stub mode where possible.

The ideal experience:

```bash
cd cookbooks/framework-integrations/<name>/sample
docker compose up        # starts Valkey + runs the sample
```

Or at minimum:

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:8.1.7
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
- **Run check** — the sample executes successfully against `valkey/valkey-bundle` (no external services required for the default path)
- **Version matrix** — CI runs tests against multiple Valkey versions (currently 8.1.x and 9.x) to ensure compatibility across supported releases
- **Lint check** — markdown files pass linting, links resolve

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

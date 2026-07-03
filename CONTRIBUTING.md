# Contributing to Valkey-Samples

Thank you for contributing! This repository collects cookbooks, sample applications, and integrations that demonstrate Valkey capabilities. Contributions are welcome from everyone.

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

## Pull Request Guidelines

- **One logical change per PR** — keep PRs focused and reviewable
- **Link related issues** — use "Fixes #N" or "Relates to #N" in the PR description
- **Stay responsive** — address review feedback promptly
- **Rebase on main** — keep your branch up to date before requesting review

---

## Cookbook Structure

Cookbooks live under `cookbooks/` organized by category:

```
cookbooks/
├── framework-integrations/
│   └── <framework-name>/
│       ├── README.md
│       ├── meta.json
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
| `meta.json` | Machine-readable metadata for rendering and navigation |
| `01-getting-started.md` | First cookbook — always Beginner difficulty |

### meta.json Schema

```json
{
  "trackName": "Human-Readable Name",
  "language": "Python",
  "cookbooks": [
    {
      "num": "01",
      "source": "01-getting-started.md",
      "output": "01-getting-started.html",
      "title": "Getting Started with X + Valkey",
      "h1": "Getting Started with X + Valkey",
      "breadcrumb": "Getting Started",
      "lead": "One sentence describing what the reader will accomplish.",
      "difficulty": "Beginner",
      "time": "15 min",
      "next": { "file": "02-topic.html", "title": "02 - Topic" }
    }
  ]
}
```

**Required fields per entry:** `num`, `source`, `output`, `title`, `h1`, `breadcrumb`, `lead`, `difficulty`, `time`

**Navigation:** Include `prev`/`next` links on all entries except the first/last respectively.

**`language`:** Top-level field. One of: `Python`, `Go`, `Java`, `TypeScript`, `Rust`.

**`difficulty`:** One of: `Beginner`, `Intermediate`, `Advanced`.

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
cd cookbooks/framework-integrations/<name>/sample
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

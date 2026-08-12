## Description

<!-- Brief summary of what this PR adds or changes -->

## Related Issue

<!-- Link to the proposal issue. All new content requires a proposal. -->

Fixes #

## Content Type

<!-- Check one -->

- [ ] Cookbook
- [ ] Demo
- [ ] Sample App
- [ ] Repository infrastructure (CI, docs, templates)

## Upstream Dependency

<!-- REQUIRED for integration cookbooks/demos/samples.
     This enables dependency analysis before merge to ensure we don't release content
     before the upstream integration is available.

     Provide ONE of the following:
     - A URL to a released version of the upstream package that includes Valkey compatibility
       (e.g., https://github.com/mem0ai/mem0/releases/tag/v0.1.29)
     - A URL to an open PR in the upstream project that adds Valkey support
       (e.g., https://github.com/helicone/helicone/pull/1234)

     If the upstream support is already in a stable release, this PR can merge immediately.
     If the upstream PR is not yet merged/released, this PR will be blocked until it is.
-->

Upstream compatibility URL:

## Pre-Submit Checklist

<!-- Check all that apply before requesting review -->

- [ ] Builds and runs from a clean clone
- [ ] Runs against current stable Valkey Bundle (Valkey-JSON, Valkey-Search, and Valkey-Bloom content friendly)
- [ ] No private links, internal references, or local paths
- [ ] No marketing language or uncited claims
- [ ] Vendor-neutral by default
- [ ] README explains concept, prerequisites, and how to run
- [ ] Dependencies pinned to specific versions
- [ ] CI validates the sample
- [ ] All commits are signed off (`git commit -s`)

## Testing

<!-- How did you verify this works? -->

- [ ] Ran locally against Valkey Docker container
- [ ] Dependencies install cleanly
- [ ] Sample executes to completion
- [ ] Markdown passes linting

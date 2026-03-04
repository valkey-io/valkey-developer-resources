# Spec for Consolidation
This is the procedure for consolidation of the language-specific skills in order to reduce redundancy and improve token 
usage efficiency.

## Background
The language-specific skills "C#, Go, Java, JS, PHP, Python" are located as siblings to the 
`{cs,go,java,js,php,python}/PLAN.md` files as `<language>.md`.  These files contain some redundancy / excesses that can
benefit from consolidation.

## High-level Tasks
The following high-level tasks will be performed for each of the 6 languages, independently.

### Anti-Pattern Consolidation
Perform the following steps in order to extract anti-patterns into a separate `ANTI_PATTERNS.md` file located within
the language-specific sub-directory.  Do not create a separate language-agnostic `ANTI_PATTERNS_CONSOLIDATED.md` file in the parent directory.  
It is acceptable that some redundancy exist in the language-specific `ANTI_PATTERNS.md` files across languages if some similar pattern occurs in two or more languages.
The anti-pattern style and structure should be consistent for each language.
Perform the following steps for each language:
1. Isolate the anti-patterns documented in the language-specific Markdown file 
    - Use a combination of keyword and semantic search in order to find these patterns.
    - Identify anti-patterns by sections containing ✅ or ❌ emoji markers, not necessarily by heading text.
2. Extract these patterns moving them into an `ANTI_PATTERNS.md` file, from the language-specific skill Markdown file.
3. Document near the top of the language-specific Markdown file, near any other external resources reference links list, that the anti-patterns are located in `ANTI_PATTERNS.md`.
4. Update any external links that may link directly back into these anti-patterns by replacing them with a pointer to the centralized location in `ANTI_PATTERNS.md`.
5. Verify that no remaining anti-patterns are present in the language-specific Markdown file that were not previously identified.

### Package Selection Explanation Redundancies
There are redundant explanations within each skill's Markdown file for the package selection process and its importance as a developer.
These must be isolated and consolidated into the single top-level `SKILL.md` file.

#### Initial Collection Pass
This step will be performed for each language independently, within it's language-specific sub-directory, accumulating results from each language into a single file `REDUNDANT_PACKAGE_EXPL.md` located within the parent non-language-specific directory, sibling to `SKILL.md`:
1. Isolate the explanations documented in the language-specific Markdown file, search for a section similar to *"Package Selection"* as either keyword or semantic search in order to find the patterns.
2. Append these redundant pattern explanation lines to an interim `REDUNDANT_PACKAGE_EXPL.md` file in the parent non-language-specific directory.

#### Consolidation Pass
After all languages have completed the *"Initial Collection Pass"* process, perform a consolidation pass on this interim file:
1.  Analyze `REDUNDANT_PACKAGE_EXPL.md` and merge the explanations from each language into a single consolidated explanation that accounts for all 6 language-specific explanations.  Just store this consolidated explanation in your memory, do not create a new file.
2.  Update the section of the top-level `SKILL.md` file dedicated to package selection with this consolidated explanation and remove any redundant references from each individual skill Markdown file.  If the section does not exist, create it within a suitable position within the `SKILL.md` document for presentation clarity.
3.  Delete the `REDUNDANT_PACKAGE_EXPL.md` interim consolidation file as no longer required and confirm all language-specific skill Markdown files have been updated to reference this consolidated explanation.
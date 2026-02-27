---
name: brainstorm
description: >
  Use this skill for creative ideation, feature brainstorming, architecture exploration,
  and strategic planning. Triggers when users want to: (1) brainstorm new features or
  data sources, (2) explore trading strategy ideas, (3) design new pipeline components,
  (4) evaluate alternative approaches, (5) plan product direction, or (6) any creative
  thinking before implementation. Also use when users say things like "我想要...",
  "有沒有辦法...", "如果我們...", "怎麼做比較好", or ask open-ended "what if" questions.
---

# Brainstorm

Turn raw ideas into validated designs through structured creative dialogue.

This skill operates in **two modes** based on what the user needs:

- **Ideation Mode** — open-ended exploration, generating new ideas from scratch
- **Design Mode** — refining a specific idea into an actionable design

Ask which mode the user wants, or infer from context.

## Hard Rules

- Do NOT write code while brainstorming
- Do NOT skip to implementation
- Ask ONE question per message
- Prefer multiple-choice questions (use AskUserQuestion tool with 2-4 options)
- All assumptions must be stated explicitly

## Ideation Mode

For open-ended creative exploration ("what could we build?", "what's missing?").

### Step 1: Context Scan

Before generating ideas, review the current project state:
- Read `CLAUDE.md` for architecture overview
- Check `src/` for existing capabilities
- Check `data/data.db` schema for current data coverage
- Review `CONGRESS_AI_SOLUTION.md` for strategic direction

### Step 2: Seed Questions

Ask the user to narrow the exploration space. Example dimensions:

| Dimension | Examples |
|-----------|---------|
| Data sources | New data feeds? Alternative APIs? Cross-market data? |
| Signal quality | Better scoring? New sentiment models? Ensemble methods? |
| Automation | Scheduling? Alerts? Auto-execution? |
| Analysis | Backtesting? Sector analysis? Correlation studies? |
| User experience | Dashboard? Reports? Mobile notifications? |
| Risk management | Position sizing? Stop-loss logic? Drawdown limits? |

### Step 3: Idea Generation

Generate 5-8 ideas using these thinking frameworks (pick the most relevant):

**SCAMPER** (for improving existing features):
- **S**ubstitute — What data source/model/API could replace current ones?
- **C**ombine — What if we merged congress + 13F + social signals?
- **A**dapt — What works in other quant domains we could adapt?
- **M**odify — What if we changed the scoring scale or timing?
- **P**ut to other use — Can our scraper infrastructure serve other data?
- **E**liminate — What complexity can we remove?
- **R**everse — What if we did the opposite (short signals instead of long)?

**First Principles** (for novel approaches):
- What is the fundamental alpha source here?
- What assumptions are we making that might be wrong?
- What would this look like if we started from zero?

**Analogy Mapping** (for cross-domain inspiration):
- How do hedge funds solve this?
- How do news trading desks operate?
- What can we learn from sports betting / prediction markets?

### Step 4: Idea Evaluation

Present ideas in a comparison table:

| Idea | Impact | Effort | Risk | Data Available? |
|------|--------|--------|------|----------------|
| ... | H/M/L | H/M/L | H/M/L | Yes/No/Partial |

Recommend top 2-3 and explain reasoning.

### Step 5: Deep Dive

For the user's chosen idea(s), transition to **Design Mode**.

---

## Design Mode

For refining a specific idea into a concrete plan.

### Step 1: Understanding

Clarify through one-at-a-time questions:
- **What** — What exactly should this do?
- **Why** — What problem does it solve? What alpha does it generate?
- **Who** — Who uses the output? (automated system? human trader? dashboard?)
- **Constraints** — API limits? Cost? Latency requirements? Data availability?
- **Non-goals** — What is explicitly out of scope?

### Step 2: Understanding Lock

Before any design, present a summary:

> **Building**: [what]
> **Because**: [why]
> **For**: [who]
> **Constraints**: [list]
> **Non-goals**: [list]
> **Assumptions**: [list]

Ask: "Does this accurately reflect your intent?"

Do NOT proceed without confirmation.

### Step 3: Approaches

Propose 2-3 approaches. For each:
- Architecture sketch (text diagram)
- Key components and data flow
- Trade-offs: complexity / extensibility / cost / risk
- How it integrates with existing `src/` modules

Lead with your recommended option.

### Step 4: Incremental Design

Present design in sections (200-300 words each). After each section ask:
> "Does this look right so far?"

Cover as relevant:
- Data flow and pipeline integration
- Database schema changes
- AI/LLM prompt design
- External API dependencies
- Error handling and edge cases
- Testing strategy

### Step 5: Decision Log

Maintain throughout the discussion:

| Decision | Alternatives Considered | Rationale |
|----------|------------------------|-----------|
| ... | ... | ... |

### Step 6: Documentation

Save validated design to `docs/plans/YYYY-MM-DD-<topic>.md` with:
- Understanding summary
- Chosen approach with rationale
- Design details
- Decision log
- Next steps

---

## Domain-Specific Idea Triggers

When brainstorming for this project, consider these domain prompts. See `references/domain-prompts.md` for detailed exploration questions per category.

| Category | Key Question |
|----------|-------------|
| New data source | What data exists that correlates with congressional trading alpha? |
| Signal enhancement | How can we reduce false positives in impact scoring? |
| Timing optimization | Can we improve OPEN vs CLOSE execution timing? |
| Multi-signal fusion | How should congress + 13F + social signals be weighted? |
| Risk overlay | What position sizing makes sense for political alpha? |
| Monitoring | How do we know when our alpha is decaying? |

## Key Principles

- **YAGNI** — Remove unnecessary features from all designs
- **One question at a time** — Never overwhelm with multiple questions
- **Explore alternatives** — Always propose 2-3 approaches
- **Validate incrementally** — Get approval section by section
- **Prefer clarity over cleverness** — Simple > sophisticated
- **Be willing to go back** — Revisit earlier decisions if new info emerges

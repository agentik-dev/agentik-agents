# NICE_TO_HAVE: what agentik-agents leaves open that blocks nothing

One row per finding, in agentik-hq design/05 §2's table, held by `scripts/recordlint`: `id` is `n<k>`, never reused; `level` is S1 a reproduced harm or red gate, S2 blocks a first run, S3 the build order, S4 polish, and S4 when unsure; `area` a component or a backticked path; a row leaves when it lands. The items filed before 2026-11-01 are frozen, never edited, in `history/NICE-2026-11-01.md`: its five S3 items were all answered on main (a-s6, a-s8, a-s9 twice, a-s10), so none moved here, and its S4 items stay there, read by path when a packet touches their area.

## Open findings

| id | level | area | finding | evidence | from |
|---|---|---|---|---|---|
| n1 | S4 | `plugin/lib/claude-agents` | PRICES holds no claude-mythos-5-2 or claude-mythos-5-1: a helper on one reads cost `-`, named by the footer | Pricing page, 2026-11-10: Mythos 5.2 $8/$40, Mythos 5.1 $10/$50, cache hits 0.025x ($0.20, $0.25) | 2026-11-10, price-fable-5-2's build |
| n2 | S4 | `plugin/agents/local-*.md` | local-implement, local-review, local-summarize and local-test no longer say they run on the local model; a plain session's model may pick one and lose a call to the deny. Two words each (`Local: `) put the sum at 1,029 of 1,024 B, so they wait on room | p1 review N3; `scripts/plugin-description-bytes plugin` 1001 B at 6940dee | 2026-11-12, p1 review |
| n3 | S4 | `plugin/skills/local-delegation/SKILL.md` | the description's trigger "when the user asks for it" drops the body's second, keeping bulk retrieval, summaries and test runs off Claude (SKILL.md:8-11) | p1 review N3 | 2026-11-12, p1 review |
| n4 | S4 | `plugin/agents/scribe.md` | the description names a merge message but no longer says the scribe never merges | p1 review N3 | 2026-11-12, p1 review |
| n5 | S4 | `plugin/lib/agentik-tool.conf` | `/agents:install-cli`, now hidden, is the remedy printed in launcher refusals and doctor output (`agentik-tool.conf:3`, `agentik-agents:106`); a model that tries it is refused and should hand it to the owner | p1 review N4 | 2026-11-12, p1 review |
| n6 | S4 | `plugin/lib/claude-local` | in a local session the Explore override prefixes local-explore's description, so Explore carries the "Every agents:local-* type" sentence; harmless | p1 review N5; `claude-local:83-84` | 2026-11-12, p1 review |

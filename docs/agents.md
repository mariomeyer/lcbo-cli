# Use LCBO from an AI harness

The repository includes a portable [LCBO skill](skills/lcbo/SKILL.md) for agents
with shell access. It follows the [Agent Skills format](https://agentskills.io/specification):
a self-contained `SKILL.md` plus optional Codex UI metadata in
`agents/openai.yaml`. Other compatible harnesses can use the same instructions
without that UI metadata. No MCP server or API key is required.

## Load or install

Clone this repository, then copy the entire `docs/skills/lcbo/` folder into your
harness's configured skill directory, keeping the folder name `lcbo`. Consult
your harness's skill-loading instructions for the destination and reload steps;
this repository does not automatically install or enable skills on your machine.
The skill runs the published package with `uvx lcbo`, so it does not require
the repository after installation. uv, Python 3.11+, and permitted network access
are needed for live requests.

For a harness that can read files but does not discover skills automatically,
give it this instruction from a checkout:

> Read `docs/skills/lcbo/SKILL.md`, then use those instructions to find Guinness 0,
> check the current price, and report observed stock near the CN Tower coordinates
> 43.6426, -79.3871. Keep requests modest and explain any reduced coverage.

For a harness supporting named invocation, after installation:

> Use $lcbo to find Guinness 0 and compare observed availability near Toronto, ON.

The skill uses JSON for parsing, resolves product slugs and SKUs from real
results, and distinguishes observed inventory from complete store coverage.
It explains that candidate caps are source-order request limits, not nearest-N
filters. Human-facing tables remain available by omitting `--json`.

## Privacy and permissions

The skill is read-only: no purchases, accounts, or checkout. It does not grant
shell/network permissions, install tools globally, start servers, or record
captures automatically. When a user requests a city, address, or postal lookup,
the agent must explain that `--location` sends the query to Photon by default,
or to the provider configured in `LCBO_GEOCODER_URL`. Coordinates avoid that
geocoding request.

Personal locations and shopping queries must not enter shared artifacts.
Examples above use a public landmark and city, not user information. Review
any logs or output before sharing. Prices and stock are snapshots, not guarantees.

See the [CLI reference](reference.md) for all commands and data models.

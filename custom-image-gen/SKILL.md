---
name: custom-image-gen
description: Adapt the bundled system Image Gen skill to an OpenAI-compatible custom provider. Resolve CUSTOM_IMAGE_GEN_URL and CUSTOM_IMAGE_GEN_API_KEY from Codex image_auth.json, fall back to the active config.toml base_url and auth.json OPENAI_API_KEY only when custom values are absent, then run the system imagegen CLI with temporary OPENAI_BASE_URL and OPENAI_API_KEY mappings. Use only when the user explicitly invokes $custom-image-gen or requests system Image Gen through custom Codex credentials or endpoint configuration.
---

# Custom Image Gen

Use the bundled system `imagegen` Skill as the authoritative image workflow. This Skill is only a provider adapter; it must not duplicate or replace system guidance for prompting, generation versus editing, model parameters, transparency, output handling, visual inspection, or delivery.

## Load system Image Gen

Before generating or editing an image:

1. Locate the first existing system Skill file:
   - `$CODEX_HOME/skills/.system/imagegen/SKILL.md`
   - `~/.codex/skills/.system/imagegen/SKILL.md`
2. Read that `SKILL.md` completely and follow its current workflow.
3. Locate `scripts/image_gen.py` beside that system Skill.
4. Treat this custom-provider request as an explicit CLI/API-path request. Override the system Skill's default built-in-tool choice and use its bundled CLI; the platform-managed image tool cannot be redirected to an arbitrary Base URL.

If the system Skill or CLI is missing, stop and report the missing path. Do not create a replacement script.

## Resolve custom configuration

Use `${CODEX_HOME:-$HOME/.codex}` as the configuration directory.

Resolve URL in this order:

1. Nonblank top-level `CUSTOM_IMAGE_GEN_URL` from `image_auth.json`.
2. Active provider `model_providers.<model_provider>.base_url` from `config.toml`.

Resolve Key in this order:

1. Nonblank top-level `CUSTOM_IMAGE_GEN_API_KEY` from `image_auth.json`; when absent or blank, accept top-level `CUSTOM_IMAGE_GEN_TOKEN` from the same file as an alias.
2. Nonblank top-level `OPENAI_API_KEY` from `auth.json`.

Read image credentials only from `image_auth.json`; do not read `CUSTOM_IMAGE_GEN_URL` or the custom Key from `auth.json`. `auth.json` only supplies the `OPENAI_API_KEY` fallback.

Do not use existing environment variables, unrelated provider profiles, official defaults, or another host as configuration fallbacks. Never ask the user to paste a Key into chat.

Preserve the resolved URL exactly, including its existing `/v1` suffix or absence. Keep URL and Key only for the current operation. Never print, log, persist, or return the Key.

When the resolved host is not `api.openai.com`, warn once that prompts, input images, generated images, and the selected credential are sent to that third party.

## Run system Image Gen CLI

Map the resolved custom values only inside the CLI process:

```bash
(
  export OPENAI_BASE_URL="$resolved_url"
  export OPENAI_API_KEY="$resolved_key"
  python3 "$system_imagegen_cli" <generate|edit|generate-batch> <system-imagegen-cli-arguments>
)
```

Use the exact subcommand, arguments, prompt construction, model rules, size rules, transparency workflow, output conventions, and verification steps defined by the loaded system `imagegen` Skill. Always pass an explicit output path. Do not enable shell tracing.

Do not:

- call the platform-managed image tool for this custom-provider request;
- write a one-off SDK, Python, or `curl` image request;
- modify the bundled system CLI;
- require `/models` discovery before ordinary generation;
- silently change endpoint, provider, model, Key source, size, quality, or format.

## Failure handling overrides

Keep the system Image Gen failure workflow, with these provider-specific constraints:

- `401` or `403`: report authentication or permission failure. Try the second Key (`OPENAI_API_KEY` from `auth.json`) once only when it exists and the provider clearly did not create an image.
- `404` or `405`: report likely configured-path incompatibility. Do not append `/v1`, remove `/v1`, or switch hosts automatically.
- timeout or `5xx`: treat as provider/upstream failure. Do not automatically retry a paid image request or change local configuration.
- ambiguous completion: do not submit a second paid request.

Report the safe error, selected configuration sources, and saved artifact status without exposing credential values.

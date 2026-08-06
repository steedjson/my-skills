---
name: custom-image-gen
description: Generate or edit raster images through an OpenAI-compatible Image API using auth.json CUSTOM_IMAGE_GEN_URL when present, otherwise the active Codex config.toml Base URL, plus auth.json CUSTOM_IMAGE_GEN_API_KEY or OPENAI_API_KEY. Use only when the user explicitly invokes $custom-image-gen or asks for the built-in Image Gen workflow with a custom provider, custom endpoint, or Codex-managed credentials. This Skill is standalone and contains no scripts.
---

# Custom Image Gen

Follow the normal Image Gen workflow for raster image generation and editing, but execute through an OpenAI-compatible Image API selected from the user's Codex configuration. This Skill is standalone: do not import, call, or depend on another image Skill, bundled script, shell script, helper file, or persistent credential export.

## Configuration sources

The primary configuration changes from the normal Image Gen workflow are:

1. Read the top-level `CUSTOM_IMAGE_GEN_URL` from `$CODEX_HOME/auth.json` first; when it is absent or blank, read the active provider's `base_url` from `$CODEX_HOME/config.toml`. When `CODEX_HOME` is unset, use `~/.codex/auth.json` and `~/.codex/config.toml`.
2. Read the top-level `CUSTOM_IMAGE_GEN_API_KEY` value from `$CODEX_HOME/auth.json` first; when it is absent, use the top-level `OPENAI_API_KEY` value from the same file. When `CODEX_HOME` is unset, use `~/.codex/auth.json`.

Do not read `OPENAI_BASE_URL`, `OPENAI_API_KEY`, or `CUSTOM_IMAGE_GEN_API_KEY` environment variables, other provider profiles, or official defaults. Use `CUSTOM_IMAGE_GEN_URL` as the request URL when it is present; use `config.toml` only as the fallback URL source. Both candidate Keys must come from the same `auth.json`. If both auth-file Keys are missing, stop and explain which local configuration is missing; never ask the user to paste a Key into chat.

Because the platform-managed built-in image tool cannot be redirected to an arbitrary Base URL, an explicit `$custom-image-gen` request must use the Image API path at the resolved endpoint. Do not silently switch back to the platform-managed tool or to another provider.

## Resolve the endpoint safely

1. Read the top-level `CUSTOM_IMAGE_GEN_URL` from `auth.json`.
2. If that value is absent or blank, parse `model_provider` from `config.toml` and read `model_providers.<model_provider>.base_url`.
3. Read only the top-level `CUSTOM_IMAGE_GEN_API_KEY` and `OPENAI_API_KEY` strings from `auth.json`, preferring the former.
4. Keep the resolved request URL and candidate Keys in memory for the current request only. Never print, log, persist, or return a Key.
5. Send requests to the same host using `models`, `images/generations`, or `images/edits`.
6. If the resolved URL does not already end in `/v1`, a 404/405 may be retried once at the same host with `/v1`; never switch hosts or hide authentication and quota errors.

When the resolved host is not `api.openai.com`, warn once that the prompt, uploaded images, generated images, and selected credential are sent to that third party.

## API execution and Key fallback

Before selecting a default model, probe the same host's `/models` endpoint with `CUSTOM_IMAGE_GEN_API_KEY` first. Treat only an explicitly listed image model as confirmed. If the preferred Key returns 401/403 or does not have image capability, retry the probe once with `OPENAI_API_KEY` from the same `auth.json`. Keep the provider and resolved request URL unchanged.

For generation or editing, try `CUSTOM_IMAGE_GEN_API_KEY` first when present. Use `OPENAI_API_KEY` only for a clear authentication, permission, or image-capability failure. Do not retry with the second Key after invalid parameters, policy/content rejection, timeout, 5xx, or an ambiguous response that may already have completed. Never make a second paid image request when completion status is uncertain.

If `/models` is unavailable, do not claim model availability. Use a model only when the provider documents it or the user explicitly chooses it, and mark capability as unverified. If neither auth-file Key can authenticate, stop with a safe diagnostic that includes sources and status codes but never secret material.

## Choose the operation

Treat a request with no edit target as `generate`. Treat a request that asks to change an existing image while preserving parts of it as `edit`. Treat images supplied only for style, composition, or mood as references for generation.

For edits, preserve invariants aggressively. State them in the request: “change only X; keep Y, Z, framing, and text unchanged.” Never turn a failed edit into a fresh generation without telling the user.

Use one API call per distinct asset. Use variants only when the user requests variants of the same prompt; do not use a count parameter as a substitute for distinct prompts.

## Prompt construction

Normalize the user's request into a compact visual specification without adding unrelated creative requirements:

```text
Use case: <photorealistic-natural, product-mockup, illustration-story, stylized-concept, or other clear use>
Asset type: <where the image will be used>
Primary request: <user's request>
Input images: <role of each image, if any>
Scene/backdrop: <environment>
Subject: <main subject>
Style/medium: <photo, illustration, 3D, etc.>
Composition/framing: <orientation, view, placement>
Lighting/mood: <lighting and mood>
Color palette: <only when useful>
Text (verbatim): "<exact text>"
Constraints: <must keep and must avoid>
```

If the request is already specific, preserve it and only organize it. If it is generic, add only details that materially improve the result. Do not add brand names, slogans, extra characters, arbitrary palettes, or fixed left/right placement without support from the request.

For image text, quote the exact copy and verify it visually. Do not promise perfect typography. For recurring characters or brand elements, disclose that consistency can vary between generations.

## Use Image Gen prompt templates

Treat templates as prompt structures, not provider API parameters. Select the narrowest template that matches the user's asset and fill only the fields supported by the request. Do not force a template when a natural-language prompt is already specific.

### Website asset

```text
Use case: <photorealistic-natural|stylized-concept|product-mockup|infographic-diagram|ui-mockup>
Asset type: <hero image / section illustration / blog header>
Primary request: <short description>
Scene/backdrop: <environment or abstract backdrop>
Subject: <main subject>
Style/medium: <photo/illustration/3D>
Composition/framing: <wide/centered; usable negative space only when needed>
Lighting/mood: <soft/bright/neutral>
Color palette: <brand colors or neutral>
Constraints: no text; no logos; no watermark; leave room for UI if needed
```

### Game asset

```text
Use case: stylized-concept
Asset type: <environment concept / character concept / UI icon / tileable texture>
Primary request: <biome, scene, character, icon, or material>
Scene/backdrop: <location and set dressing>
Subject: <main focal element>
Style/medium: <realistic/stylized>; <concept art/render/icon/texture>
Composition/framing: <wide/establishing/top-down>; <camera angle>
Lighting/mood: <time of day and mood>
Constraints: no logos; no trademarks; no watermark
```

### Wireframe

```text
Use case: ui-mockup
Asset type: <website wireframe / mobile onboarding flow>
Primary request: <page or flow to sketch>
Style/medium: low-fi grayscale wireframe
Composition/framing: <landscape desktop, tablet, or portrait mobile>
Subject: <sections/screens in order; columns; key labels>
Constraints: label major blocks; no color; no logos; no real photos; no watermark
```

### Logo concept

```text
Use case: logo-brand
Asset type: logo concept
Primary request: <brand idea or symbol>
Style/medium: vector-friendly mark; flat colors; minimal
Composition/framing: centered mark; clear silhouette; generous margin
Color palette: <one or two colors>
Text (verbatim): "<exact name>"
Constraints: no gradients; no mockup; no 3D; no watermark
```

When the user names a template, preserve its field order and constraints while replacing placeholders with the user's details. If a template requires a missing decision that materially changes the result, ask one concise question; otherwise choose a conservative default and state it.

## Model and API parameters

Default to `gpt-image-2` for new API generation only when the resolved provider confirms it or the user explicitly requests it. Otherwise ask for a supported model or report that capability is unverified. Do not silently change the requested model.

Use `gpt-image-2` quality values `low`, `medium`, `high`, or `auto`; present them to beginners as “省钱快速 / 均衡推荐 / 高质量.” Omit `input_fidelity` for `gpt-image-2`, which processes image inputs at high fidelity. Use the Image API `images/generations` endpoint for new images and `images/edits` for edits.

Only send parameters documented for the selected model and provider. Preserve the user's requested quality, format, compression, moderation, background, mask, and input-image constraints. If the provider rejects a parameter, explain the rejection and ask before changing the request.

## Size handling

Keep three values distinct:

- `requested_size`: the exact final dimensions the user wants;
- `api_size`: the dimensions sent to the model;
- `final_size`: the verified dimensions of the delivered file.

For `gpt-image-2`, custom `api_size` values must satisfy the current API constraints: maximum edge 3840 px, both edges multiples of 16, aspect ratio no more than 3:1, and total pixels between 655,360 and 8,294,400. `auto` is allowed.

If a requested final size is not accepted directly, choose a valid API size and explicitly post-process to the exact final size using an available image operation. For example, `1920x1080` may require `1920x1088` followed by cropping 8 pixels from the height. If no safe post-processing operation is available, report that the exact size cannot be guaranteed rather than silently delivering a different size.

Do not silently crop, stretch, pad, upscale, lower quality, or change format. Report the API size, final size, and fit operation.

## Transparency

For ordinary opaque images, use the normal API generation flow. `gpt-image-2` does not support native transparent backgrounds. For a simple transparent request, first generate the subject on a perfectly flat chroma-key background, then remove that color with an available local image operation and verify alpha corners and edge quality. If no local image operation is available, stop and report that native transparency was not completed.

Do not silently downgrade to another model for native transparency. If the user specifically needs native transparency, explain the model requirement and obtain confirmation before changing models. For complex hair, fur, smoke, glass, liquids, reflections, or soft shadows, warn that chroma-key removal may damage edges.

## Input images and edits

For each input image, label its role as reference, edit target, or supporting insert. Preserve edit-target invariants. If a local image must be inspected before editing, load it with the available image viewer before sending it to the API.

Use masks only when the user requests a localized edit or when the target area is unambiguous. Never invent a mask or silently alter unrelated regions.

## Verification and delivery

After every generation or edit:

1. Confirm that the API response contains image data or a retrievable image URL.
2. Verify the file is readable, not corrupt, and has the expected format and final dimensions.
3. Check alpha behavior when transparency was requested.
4. Visually inspect subject, style, composition, text accuracy, unwanted text or watermark, cropping, and edit invariants.
5. Iterate with one targeted change when needed.
6. Save project-bound images inside the workspace and do not overwrite existing files unless explicitly requested.

Report the final saved path, model, API size, final size, fit operation, and verification result. Never report the Base URL's credential or any secret value.

## Failure handling

- `401` or `403`: try the second auth-file Key once for the same provider; if it fails, report authentication or permission failure and do not try another host.
- `404` or `405`: try the same-host `/v1` path once when appropriate; otherwise report that the provider may not implement the Image API.
- model unavailable: report the exact requested model failure; do not silently substitute.
- unsupported size or parameter: preserve the user's request and ask before changing it.
- timeout: do not retry by default; only retry a non-image probe or a request with a provider-supported idempotency key when the provider clearly reports that no image request completed.
- corrupt or wrong-sized output: do not deliver it as successful; retain the response for diagnosis and verify the repaired artifact.

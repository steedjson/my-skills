---
name: image-workbench
description: Generate, edit, resize, and verify raster images through OpenAI-compatible Image APIs while automatically reusing the user's active Codex provider configuration. Use for one-sentence beginner image requests, explicit image model/provider selection, custom Base URLs, exact user-defined output dimensions, image edits, transparent outputs, batch variants, provider diagnostics, or troubleshooting image API compatibility.
---

# Image Workbench

Turn a natural-language request into a verified image while keeping provider, model, and size controls optional. Reuse the user's existing configuration and never expose credentials.

## Choose the path

1. For a normal request, start in quick mode. Infer sensible defaults and ask only when purpose, orientation, or style is truly blocking.
2. Resolve the provider in this order: explicit request parameters, a complete environment-variable provider pair, active Codex `config.toml` paired with `auth.json`, then the official OpenAI Base URL. Never combine a Codex Base URL with an unrelated environment Key.
3. If an API key is available, use the bundled API scripts so the active Codex provider is honored.
4. If no API key is available and a built-in image generation tool exists, use that tool without requesting a key.
5. Use guided mode only when the user wants choices. Use advanced mode only when the user asks for provider, model, quality, transparency, format, compression, fit, or endpoint controls.

Never ask the user to paste an API key into chat. Never print a key, write it into the Skill, or forward Codex login/session tokens to a third-party provider.

## Quick mode

For a request such as “生成一张 1920×1080 的水彩城市夜景”:

1. Run `scripts/configure-provider.py --check` when this is the first API use or provider state may have changed.
2. Run `scripts/discover-models.py --json` to intersect currently documented official image models with models exposed by the active provider.
3. Select the newest compatible available model. Do not hardcode one model as the universal default.
4. Treat the user's dimensions as `requested_size`. Let `scripts/normalize-size.py` choose a compatible `api_size`, then restore the exact requested dimensions using the selected fit mode.
5. Generate with `scripts/generate-image.py`. Default to `fit=crop` only when the user requests exact dimensions and did not choose a fit strategy; state that crop fitting was used.
6. Run `scripts/verify-image.py` and visually inspect the result before delivery.

Keep raw model IDs hidden from beginners unless they ask. Present quality as “省钱快速 / 均衡推荐 / 高质量” and map them to `low` / `auto` / `high` when the selected model supports those values.

## Generate or edit

Generate:

```bash
python scripts/generate-image.py \
  --prompt "<request>" \
  --size "<WIDTHxHEIGHT or auto>" \
  --quality auto \
  --out "<output path>"
```

Edit:

```bash
python scripts/edit-image.py \
  --image "<input path>" \
  --prompt "<requested change and invariants>" \
  --size "<WIDTHxHEIGHT or auto>" \
  --out "<output path>"
```

Use `--dry-run` first when an explicit provider, model, transparency request, or unusual size makes compatibility uncertain. Use `--base-url` only when the user explicitly overrides the active configuration. Use `--api-key-env NAME` to select a credential variable; never accept a literal key argument.

For edits, repeat invariants such as “change only the background; preserve the subject, pose, text, and framing.” Do not turn a failed edit into regeneration without permission.

## Model discovery

Run `scripts/discover-models.py`. It fetches current image-model names from the official OpenAI image guide, probes the configured provider's `/models` endpoint, and reports:

- official models available from this provider;
- official models unavailable from this provider;
- provider-only image-like models with unverified capabilities;
- discovery failures and their source.

If live official discovery fails, disclose that bundled fallback knowledge was used. If provider discovery fails, do not claim that a model is available. In quick mode, a best-effort attempt may use the newest live-documented official model against the same provider while clearly marking availability as unverified; ask before selecting a provider-only or capability-unknown model.

Read `references/model-capabilities.md` when model selection, editing, transparency, or format support matters. Do not pass unsupported parameters merely because another model accepts them.

## Size and output

Keep these separate:

- `requested_size`: exact final dimensions the user wants;
- `api_size`: dimensions accepted by the chosen model;
- `fit`: `crop`, `contain`, `stretch`, or `none`.

Read `references/size-and-output.md` for fit behavior and model constraints. Never silently change the final requested size. Never silently remove transparency, lower quality, or convert the output format.

## Provider safety

Treat non-OpenAI Base URLs as third parties. Tell the user once that prompts, source images, and credentials are sent to that provider. Do not repeat the warning on every generation in the same task.

Read `references/provider-compatibility.md` for configuration precedence, Codex file handling, root-versus-`/v1` probing, and credential isolation. Read `references/troubleshooting.md` after authentication, endpoint, model, timeout, or malformed-image errors.

## Validation and delivery

After every final generation or edit:

1. Verify file integrity, actual dimensions, format, and alpha expectations with `scripts/verify-image.py`.
2. Visually inspect subject, composition, text accuracy, watermark/unwanted text, cropping, anatomy, and edit invariants.
3. Iterate with one targeted change when needed.
4. Save project-bound images inside the workspace. Do not overwrite an existing file unless the user asked.
5. Report provider category (official or third party), selected model, API size, final size, fit mode, output path, and whether verification passed. Never report credential values.

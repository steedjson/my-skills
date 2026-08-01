---
name: image-workbench-lite
description: Text-only image generation and editing workflow for quick, beginner-friendly requests and fair comparison with the full image-workbench Skill. Use when the user explicitly invokes $image-workbench-lite, asks for a no-script workflow, wants to use built-in image generation, or wants to compare built-in and OpenAI-compatible API image results.
---

# Image Workbench Lite

Use a lightweight, text-only workflow for image generation and editing. This Skill contains no scripts, dependencies, API keys, bundled assets, or provider-specific code. Keep it installed alongside `image-workbench`; it is a second path for comparison, not a replacement.

## Invocation and boundaries

Use this Skill when the user explicitly invokes `$image-workbench-lite`, asks for a pure-text workflow, or asks to compare image-generation approaches. Do not silently replace an explicit `$image-workbench` request.

Use the built-in image-generation capability by default. Use the existing `image-workbench` Skill when the user needs deterministic API operations that the built-in capability cannot expose, especially:

- a specific custom Base URL or provider endpoint;
- live provider model discovery and capability intersection;
- exact user-defined dimensions with explicit API-size normalization;
- repeatable format, compression, mask, or multipart edit controls;
- provider diagnostics, raw API errors, or machine-readable output verification.

Do not create a script to fill a gap in this Skill. Explain the limitation and hand off to `$image-workbench` when that is the appropriate path.

## Quick workflow

1. Interpret the request as either `generate` or `edit`.
2. Extract only the details needed to act: purpose, subject, style, composition, orientation, final size, exact text, input images, and things to avoid.
3. Preserve a specific prompt instead of inventing unrelated characters, brands, slogans, or story elements.
4. For a new image, use the built-in image tool. For an edit, preserve the user's stated invariants and change only the requested parts.
5. If the user names a model, provider, Base URL, quality, format, or exact API parameter, acknowledge that the text-only path may not control it and offer `$image-workbench`.
6. Inspect the result for subject accuracy, composition, text, watermarks, unwanted objects, edit invariants, and visible defects.
7. Report what actually happened: execution path, whether the requested size was guaranteed, output location, and any limitation. Do not claim API-level verification when only visual inspection occurred.

## Configuration behavior

For built-in generation, do not ask the user for an API key. For an explicit custom-provider request, respect the user's active Codex configuration when the current environment can access it:

1. pair an explicitly selected provider and credential;
2. otherwise use the active Codex provider from `config.toml` with its `auth.json` API key;
3. otherwise use a complete environment-variable provider pair;
4. otherwise use the official default path or the built-in image tool.

Never display, copy, or request a full API key in chat. Never use Codex session tokens as Image API credentials. Warn once when prompts or source images will be sent to a non-OpenAI provider.

Do not hardcode an image model list. When model choice matters, consult current official guidance through `$openai-docs` and the provider's advertised capabilities. Keep raw model IDs hidden from beginners unless they ask for them.

## Size and output honesty

Separate the user's requested final dimensions from whatever dimensions the active image tool actually accepts. If the built-in path cannot guarantee an exact custom size, say so before delivery and offer `$image-workbench` for explicit API-size normalization and post-processing.

Never silently:

- change the final dimensions;
- crop, stretch, or add padding;
- lower quality;
- remove transparency;
- change the output format;
- regenerate an edit as a new image.

For exact-size comparisons, use the same final dimensions, fit mode, prompt, and reference inputs in both paths. If one path cannot satisfy those conditions, label the comparison as non-equivalent instead of treating the images as a model benchmark.

## Fair comparison mode

When the user asks whether the two Skills achieve the same effect:

1. Normalize one prompt into a concise visual specification.
2. Run the same request once through the selected built-in/text-only path and once through `$image-workbench` when API access is available.
3. Keep model, provider, quality, size, reference images, and edit invariants identical wherever both paths support them.
4. Compare subject identity, style, composition, exact text, dimensions, crop behavior, transparency, latency, errors, and observed cost information only.
5. State the result as “equivalent for this request,” “visually similar but operationally different,” or “not comparable,” with the reason.

Do not promise pixel-identical output. Generative calls can differ even with the same prompt and model.

## Prompt shaping

For generic requests, add only useful production details:

```text
Use case: <purpose>
Primary request: <user's request>
Subject: <main subject>
Style/medium: <style>
Composition/framing: <framing and orientation>
Lighting/mood: <lighting and mood>
Text (verbatim): "<exact text>"
Constraints: <must keep and must avoid>
```

For edits, state invariants explicitly: “change only X; keep Y unchanged.” For text inside images, quote the exact text and verify it visually; do not imply that text rendering is guaranteed.

## Typical requests

- `使用 $image-workbench-lite 生成一张动漫风格的海报。`
- `用纯文本方式把这张图片背景换成白色，主体保持不变。`
- `用两个 Skill 分别生成同一张 1920×1080 图片，比较哪个更适合我。`


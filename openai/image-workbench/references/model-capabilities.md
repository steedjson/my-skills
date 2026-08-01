# Image model capabilities

Official guide checked: 2026-08-01, <https://developers.openai.com/api/docs/guides/image-generation>.

Always run live discovery before selection. This file is capability guidance and a fallback, not a fixed availability list.

| Model family | Generate | Edit | Size behavior | Quality | Transparent background | Input fidelity |
|---|---:|---:|---|---|---:|---|
| `gpt-image-2` | Yes | Yes | Custom constrained dimensions or `auto` | `low`, `medium`, `high`, `auto` | No | Always high; omit the parameter |
| `gpt-image-1.5` | Yes | Yes | Provider/API documented presets | Model/provider dependent | Supported for PNG/WebP when documented | Optional when supported |
| `gpt-image-1` | Yes | Yes | Provider/API documented presets | Model/provider dependent | Supported when documented | Optional when supported |
| `gpt-image-1-mini` | Yes | Yes | Provider/API documented presets | Model/provider dependent | Supported when documented | Optional when supported |

Current official guide names the GPT Image families above. Provider exposure is separate and must be checked through `/models`.

Treat provider-only image model names as unknown until the provider documents generation/edit endpoints, sizes, quality, transparency, formats, compression, and input fidelity. Do not infer capabilities from the name alone.

The Responses API image-generation tool and the Image API are distinct surfaces. This Skill's scripts use the OpenAI-compatible Image API endpoints `images/generations` and `images/edits`.


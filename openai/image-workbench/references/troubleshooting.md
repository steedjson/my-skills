# Troubleshooting

## No API key

Check, without displaying values:

1. the environment variable named by `--api-key-env`;
2. `OPENAI_API_KEY`;
3. top-level `OPENAI_API_KEY` in the active Codex `auth.json`.

If none exists, use the built-in image tool when available or ask the user to configure a key locally. Never ask for the full key in chat.

## 401 or 403

Stop. Confirm that the key belongs to the selected provider and that the provider grants image-model access. Do not try the same credential against a different host.

## 404 or 405

The scripts may try the same host with and without `/v1`. If both fail, the provider may not implement the Image API. Do not claim that a Responses API endpoint proves Image API compatibility.

## Model missing

Run `discover-models.py --json`. Distinguish official-but-unavailable, provider-only, and unknown-capability models. Never silently substitute another model.

## Unsupported size or parameter

Run `normalize-size.py`, then remove only parameters that the chosen model is documented not to accept. Preserve requested final dimensions through explicit post-processing.

## Timeout

Image generation can take up to several minutes. Retry once only when the failure is clearly transient and the provider did not return a completed image. Avoid automatic retries after ambiguous billing or completion states.

## Corrupt or wrong-sized output

Keep the source response for diagnosis, run `verify-image.py`, and do not deliver the file as successful. If post-processing is required, verify the final artifact again.


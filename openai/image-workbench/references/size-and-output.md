# Size and output handling

## Three size values

- `requested_size`: exact final width and height requested by the user.
- `api_size`: supported size sent to the model.
- actual source size: dimensions returned by the provider, which must be verified rather than assumed.

## Fit modes

- `crop`: resize proportionally and crop overflow from the center. Good for exact banners; may remove edge content.
- `contain`: resize proportionally and letterbox/pillarbox. Preserves all content; may add margins.
- `stretch`: force dimensions without preserving aspect ratio. Use only when explicitly requested.
- `none`: do not post-process. Fail exact-size delivery when the provider returns different dimensions.

For a request such as `1920x1080` with `gpt-image-2`, use an API-compatible size such as `1920x1088`, then crop to exactly `1920x1080`. Report both sizes.

## `gpt-image-2` constraints

According to the official guide checked on 2026-08-01:

- maximum edge: 3840 px;
- both edges: multiples of 16 px;
- aspect ratio: at most 3:1;
- total pixels: 655,360 through 8,294,400;
- `auto` is supported.

Other model families may accept only documented presets. Choose a compatible API size by aspect ratio, then post-process to the user's exact requested size.

Do not silently change final dimensions. If the requested final size is extreme enough to require upscaling, padding, or substantial cropping, disclose it before a costly generation when practical.


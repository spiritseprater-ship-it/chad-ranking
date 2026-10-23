# Scoring specification (v1)

`CHAD SCORE` is a **fictional entertainment score** for a friendly weekly
competition. It is not a measurement of attractiveness, health, skin, hair, bone
structure, ethnicity, perceived confidence in real life, or personal worth.

The Phase 1 implementation is a deterministic **browser heuristic**, not AI and
not a machine-learning model. It is deliberately documented so anyone can
reproduce the result.

Implementation: `src/services/scoring/localScoring.ts`
Version string: `local-heuristic-v1`

---

## 1. Categories and weights

| Category | Weight | What the image properties actually represent |
| --- | --- | --- |
| Pose & presentation | 30% | How visually different the three photos are (variety of poses/angles). |
| Expression & confidence | 25% | Tonal balance: absence of blown highlights/black crush, contrast, mid-tone exposure. |
| Photo creativity | 25% | Colourfulness, edge detail and contrast in the set. |
| Theme & styling | 20% | Palette consistency across the three photos plus moderate colour. |

These labels are competition flavour. The underlying metrics are generic image
statistics and nothing else.

---

## 2. Photo processing

For each of exactly three photos:

1. Accept JPG, PNG or WebP up to 8 MB.
2. Decode with `createImageBitmap` (fallback: `<img>`), honouring EXIF orientation.
3. Centre-crop to a square, downscale to 96 × 96 pixels with high-quality
   smoothing.
4. Read RGBA pixels. Compute:
   - luma `y = 0.2126r + 0.7152g + 0.0722b`
   - `brightness = mean(y)`
   - `contrast = clamp01(stddev(y) / 0.32)`
   - `sharpness = clamp01(mean neighbour |Δy| / 0.075)`
   - `saturation = clamp01(mean((max−min)/max) / 0.45)`
   - `exposure = 1 − fraction(y < 0.045 or y > 0.955)`
   - mean RGB (palette)

`clamp01` bounds a value to `[0, 1]`.

---

## 3. Quality gate (retake instead of inventing a score)

The analysis is rejected with a message when:

- any photo has mean brightness < 0.08 (**too dark**);
- any photo has mean brightness > 0.94 (**overexposed**);
- any photo has `sharpness < 0.06` (**blurry**);
- any pair of photos has mean absolute luma difference < 0.004
  (**duplicate photos**).

The UI asks the user to retake the affected photo. No score is generated.

---

## 4. Category formulas

Averaged across the three photos unless noted:

```text
variety      = clamp01( mean pairwise mean-abs-luma-difference / 0.12 )
colour       = clip01( mean saturation )
contrast     = clip01( mean contrast )
sharpness    = clip01( mean sharpness )
exposure     = clip01( mean exposure )
midTone      = clip01( 1 − |mean brightness − 0.55| / 0.4 )
consistency  = clip01( 1 − paletteSpread / 0.28 )   // spread = sum of channel std-dev

pose         = 55 + 40 × variety
expression   = 100 × (0.45·exposure + 0.35·contrast + 0.20·midTone)
creativity   = 100 × (0.40·colour + 0.30·sharpness + 0.30·contrast)
styling      = 100 × (0.60·consistency + 0.40·colour)
```

Each category is rounded to an integer. The final score:

```text
CHAD SCORE = clamp(round(
  0.30·pose + 0.25·expression + 0.25·creativity + 0.20·styling
), 0, 100)
```

There is **no randomness**. The same three images at the same decoder settings
always produce the same score. Browser image decoding can differ very slightly
between engines; the rounded integer is stable for normal inputs.

Typical well-lit, varied sets fall in the 70s–80s. Reaching the Top 10 requires a
strong set and a competitive week. The score is not calibrated against people or
celebrities.

---

## 5. What the system does not do

- It does not detect faces, jawlines, skin, body fat, hair, age, gender, race or
  health.
- It does not rank identity, personality or worth.
- It does not call an AI API.
- It does not use randomness, hidden boosts or paid ranking.
- It does not claim that a browser heuristic is a “sophisticated AI model”.

---

## 6. Confirmation and server validation (Phase 2)

Phase 1 stores only the provisional result in memory. Phase 2 must not simply
accept the browser's number. Planned approach:

1. The client sends the three compressed photos (or a strictly documented,
   privacy-reviewed alternative) to a trusted endpoint.
2. The endpoint validates the Firebase ID token, the active competition window,
   account status, the one-entry lock and rate limits.
3. It recomputes this exact formula using a server image decoder.
4. It writes the confirmed submission with a deterministic document ID
   (`{competitionId}_{uid}`), then derives the rank from authoritative data.
5. It discards the temporary images and returns score, rank and Top 10 status.
6. Administrators can correct a confirmed score only through a trusted, audited
   operation. Ranks are re-derived afterward.

If the chosen free plan cannot decode images server-side, the project must state
that limitation and cannot call the score server-verified. See
[`FIREBASE_PLAN.md`](FIREBASE_PLAN.md).

---

## 7. Privacy

- Raw photos remain in browser memory and are released after analysis, retake or
  navigation. Object URLs are revoked.
- No photo archive, thumbnails or metrics tied to a person are retained.
- The Privacy page explains that clearing memory is not a guarantee of erasing
  every browser, OS or network trace.
- Only the confirmed score and minimal metadata are stored.

---

## 8. Changing the rubric

Any change requires:

- a new version string (e.g. `local-heuristic-v2`);
- updated documentation and tests;
- a decision about whether scores can change mid-week (prefer no; score once,
  lock);
- server-side parity if confirmation re-analysis exists.

Never silently change weights or add randomness.

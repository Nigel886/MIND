# M20 DeepSeek Provider Envelope Remediation

## Diagnosis

The #258 live diagnostic reached the `envelope` telemetry stage with
`OTHER_CONTRACT_REJECTION`, before JSON parsing.  The live transport returns
the complete decoded OpenAI-compatible response mapping, while the M20 bridge
previously admitted only `model`, `choices`, and optional `usage`.  Standard
transport metadata (`id`, `object`, `created`, optional
`system_fingerprint`, and optional `service_tier`) was therefore rejected
before the bridge could traverse `choices[0].message.content`.

## Remediation and limits

The shared M20 DeepSeek proposal adapter now removes only that explicit,
documented metadata set before invoking the unchanged strict production
parser.  It accepts no unrecognised envelope fields and continues to
fail-closed for non-mappings, missing or empty choices, missing message or
content, unsupported content types, malformed objects, and transport errors.
Content is passed unchanged to the existing parser and #252 telemetry stages.

This does not alter the prompt, schema, action or payload semantics, admission
rules, retry semantics, or either condition's policy.  MIND-Adaptive and
MIND-Fixed use the same corrected adapter.

## Preservation and validation

Historical evidence was not modified: #250 remains 120 calibration records / 60
pairs and #258 remains two diagnostic records.  Issue #259 made zero real
provider calls and created zero diagnostic, pilot, calibration, or formal
records.

Focused provider-free validation passed (11 tests in 0.234s).  Full regression
passed: `python -m unittest` ran 780 tests in 486.754s (exit 0), and `pytest`
reported 780 passed in 441.25s (exit 0).  `git diff --check` passed.

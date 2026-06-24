# A1886 GEP Dataset Checker Algorithm Summary v01

Date: 2026.06.24

This note summarizes the red-line processing used in the browser viewer:

1. Deglitch function
2. Optional rule01 range-threshold function

The blue line is the raw `r0` data. The red line is the displayed processed range after deglitching and, when enabled, rule01.

## 1. Deglitch Function

Purpose: remove short abnormal spikes while preserving normal range movement.

Inputs:

- `r0[k]`: raw range value at frame `k`
- `median_win`: local median window size, default `9`
- `spike_TH`: spike threshold in meters, default `0.065 m`
- `jump_TH`: jump threshold in meters, default `0.253 m`

For each frame `k`:

1. Build a local window around `r0[k]`.
2. Compute the local median value.
3. Compare the current raw value with the local median.
4. Compare the current raw value with the previous accepted value.

Pseudocode:

```text
prev_valid = r0[0]

for each k:
    x = r0[k]
    med = median(local window around k)

    spike_flag = abs(x - med) > spike_TH

    jump_flag =
        abs(x - prev_valid) > jump_TH
        and abs(med - prev_valid) <= spike_TH

    if spike_flag or jump_flag:
        y = med
    else:
        y = x

    red_base[k] = y
    prev_valid = y
```

Brief explanation:

- `spike_flag` catches one-point or short noisy spikes far from the local trend.
- `jump_flag` catches sudden jumps away from the previous trusted value when the local median still agrees with the previous trusted value.
- The replacement value is the local median, so the red curve follows the nearby stable trend instead of the spike.

## 2. Optional Rule01 Function

Purpose: block processed values that jump into an untrusted high-range region.

Inputs:

- `red_base[k]`: result from the deglitch function
- `rule_base_range_TH`: untrusted range threshold, default `1.1 m`
- `Enable rule01`: checkbox that turns this rule on or off

Rule:

```text
old_r0 = r0{k}
new_r0 = r0{k+1}

if new_r0 >= rule_base_range_TH:
    r0{k+1} = r0{k}
```

Viewer behavior:

- Rule01 is applied after the deglitch function.
- The final red curve uses the rule01-corrected values.
- Any point changed by rule01 is marked with a green dot.

Pseudocode:

```text
red_final = copy(red_base)

if Enable rule01:
    for each k from 0 to N-2:
        old_r0 = red_final[k]
        new_r0 = red_final[k + 1]

        if new_r0 >= rule_base_range_TH:
            red_final[k + 1] = old_r0
            mark point k + 1 as rule01 affected
```

Brief explanation:

- If the next processed value is greater than or equal to `rule_base_range_TH`, it is treated as untrusted.
- The viewer keeps the previous processed value instead of accepting the high value.
- Green dots show where this rule changed the red curve.

## Processing Order

```text
raw r0
  -> deglitch function
  -> red_base
  -> optional rule01
  -> final red curve
```

## Current Defaults

```text
median_win          = 9
spike_TH            = 0.065 m
jump_TH             = 0.253 m
rule_base_range_TH  = 1.1 m
rule01              = off by default
```


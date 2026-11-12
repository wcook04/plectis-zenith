**Playbook**

1. **Start with degenerate structure.** Test empty input, one-element input, and all-identical input. For containers include `[]` and a singleton; for strings include `''`, one character, and a repeated character. Check exact return value and that empty input does not return the other argument or a singleton unchanged.

2. **Force numeric boundaries.** Include `0`, `1`, `-1`, all-negative data, mixed signs, and cases where `0` or `False` is the correct answer. Test equality exactly at thresholds (`x == t`, `need == remaining`, `number == need`), plus just below/at/above a stated minimum.

3. **Exercise branch precedence.** Use inputs where two rules overlap: zero remaining with already-enough versus not enough; empty versus singleton; maximum length tied; first versus last occurrence. These reveal wrong `if` ordering and early returns.

4. **Break duplicate/order assumptions.** Include repeated elements, repeated characters, overlapping occurrences, duplicate values in both inputs, and ties for “maximum” or “first.” Use an order where correct tie-breaking differs from input order. For strings, include repeated target characters and a target at both start/end.

5. **Use allowed type/domain edges.** If the specification permits, test booleans as integers, floats, negative numbers, punctuation/digits in strings, mixed case, non-ASCII letters, and non-letter characters. If it says “list of strings,” include `['']`; if “dictionary,” include empty and a key/value type that is still allowed by the spec.

6. **Test result shape.** Verify empty results are `[]`, not the original input; singleton results are not accidentally filtered; and no mutation/aliasing changes a later answer. Include a case where the correct result equals the input.

7. **Add one large performance probe.** Choose a large valid input whose answer should be decided early or quickly (e.g. a large prime/composite-like decision, large count, long repeated string). This exposes hidden loops, timeouts, and unnecessary exhaustive search.

Choose roughly 6–10 inputs total: one from each relevant category, combining where possible. Before running, write the expected result from the specification; if an input does not distinguish at least one plausible wrong implementation, replace it.

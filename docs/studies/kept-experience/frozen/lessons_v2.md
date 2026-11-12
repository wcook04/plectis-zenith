**Playbook**

1. **Match exact signature; always include empty and singleton.** Test the specified container/string/dict type, plus empty (`[]`, `''`, `{}`), one-element, and all-identical. Never substitute a scalar for a one-element list. Check empty does not index, sort, raise, mutate, or return the wrong sentinel—even when the spec seems to imply a minimum size.

2. **Probe zero/one and arithmetic extremes.** For arithmetic, counting, divisibility, GCD, or loops, include `0`, `1`, negatives, mixed signs, all-negative, and exact thresholds. Include `0` even when “positive” is stated: it often triggers modulo/division loops, timeouts, or infinite recursion. For ranges, include a valid answer strictly between two failing endpoints (odd,odd interval containing an even).

3. **Use adversarial large/recursive cases, not just large quick cases.** Make the performance probe worst-case for naive algorithms: large coprime/consecutive pairs for GCD, deeply recursive long lists, long repeated strings, huge numeric strings, values above hard-coded sentinels (`9999`), and beyond float precision. Check for timeout/recursion error and exact large-number rounding.

4. **Test strict parsing formats.** For parsed strings, include correct fields with wrong separators, extra/missing separators, missing zero-padding, empty fields, signs/decimals, spaces, and long digit strings. Permissive parsers accept these.

5. **Vary collection sizes and proportions.** When combining two collections, use unequal lengths, singleton vs many, surplus irrelevant elements, and exact counts at the decision boundary. For pair/sum problems include a lone `0` with no opposite, self-pair traps, duplicates, and no-pair negatives; enforce “distinct elements” by index, not value.

6. **Break sentinel/order/tie assumptions.** Include values larger than any sentinel, the maximum candidate first/last, skewed frequencies, and ties where correct choice is largest value/first index. Use an order where wrong tie-breaking differs from input order.

7. **Exercise overlapping rules, allowed edges, and result shape.** Combine empty vs singleton, zero remaining vs enough, equality at thresholds, max-length ties, first/last occurrence. If permitted, add booleans as ints, floats, non-ASCII, punctuation/digits, empty strings in lists, and `None`/heterogeneous elements when element type is unconstrained. Verify fresh results, no aliasing/mutation, and correct empty/sentinel for no-valid cases.

Choose 8–12 inputs total, combining categories. Before running, write the expected result from the spec; if it cannot distinguish a plausible wrong implementation (empty indexing, sentinel cap, self-pair, bad separator, naive-loop timeout), replace it.

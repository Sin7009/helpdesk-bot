## 2024-05-23 - [FAQ Loop Optimization]
**Learning:** For small-to-medium string collections (e.g., 100 FAQ triggers), Python's simple loop with `in` operator is faster than compiled Regex if allocations are minimized. Specifically, pre-calculating `.lower()` strings yielded a ~46% speedup (0.026s vs 0.032s best case, 0.6s vs 1.1s worst case for 100k iterations).
**Action:** Always benchmark "naive" loops against Regex for string matching. Pre-calculate transformations (like `.lower()`) outside hot loops.

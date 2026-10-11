# Benchmark Methodology & Evaluation Framework

## 1. Objectives & Scope
The goal of this benchmark is to evaluate the indexing speed, query latency, ranking quality, and memory scalability of the `AI-Knowledge-Architect` retrieval system under controlled, reproducible conditions across multiple scales (50, 500, and 5,000 documents).

---

## 2. Dataset Construction
To prevent evaluation bias and artificial keyword leakage:
- **Synthetic Corpus:** Multi-section technical specifications modeled on distributed systems, storage engines, cryptography, rate limiting, and event sourcing.
- **Query Set:** Separated into realistic natural language questions, technical synonym formulations, multi-term queries with stop-words, and negative unanswerable queries.
- **Negative Queries:** Include queries about topics completely absent from the knowledge base (e.g. quantum entanglement bus) to verify that the system correctly abstains rather than producing hallucinated matches.

---

## 3. Evaluation Metrics

### Retrieval Quality
- **Precision@k:** Proportion of the top-k retrieved documents that are relevant:
  $$\text{Precision@k} = \frac{|\text{Relevant} \cap \text{Top-k}|}{k}$$
- **Mean Reciprocal Rank (MRR):** Evaluates where the first relevant result appears in the ranking:
  $$\text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i}$$
- **nDCG@k:** Normalized Discounted Cumulative Gain measuring graded ranking quality:
  $$\text{DCG@k} = \sum_{i=1}^k \frac{2^{\text{rel}_i} - 1}{\log_2(i + 1)}$$

### Performance & Efficiency
- **Initial Indexing Throughput:** Documents processed per second during cold-start build.
- **Incremental Sync Latency:** Wall-clock time to detect 0 modifications (unchanged repository) and 1 modification.
- **Search Latency (p50, p95, p99):** Query execution times measured with high-resolution performance counters (`time.perf_counter()`).
- **Memory Footprint (RSS):** Peak resident set size of the Python process measured via `psutil`.

---

## 4. Execution Commands

```bash
# Execute multi-scale benchmark (50, 500, 5000 documents)
python benchmarks/rigorous_benchmark.py

# Inspect results JSON
cat benchmarks/multiscale_benchmark_results.json
```



# Confidence-Informed Architecture (CI) Implementation Manual

## 1. System Architecture Overview

### 1.1 Three-Tier Progressive Escalation Design

#### 1.1.1 Core Principle: Cost-Optimized Escalation

The **Confidence-Informed Architecture** implements a **three-tier progressive escalation** mechanism that fundamentally restructures how computational resources are allocated in query processing systems. The architecture's cardinal principle—**"绝不前置LLM" (never place LLM upfront)**—ensures that expensive large language model invocations are reserved only for queries that genuinely resist classification through cheaper methods. This design creates a **natural filtering pyramid**: approximately **60% of queries are hard-routed from Level 0**, **25-30% receive Level 1 verification**, and only **5-10% require full LLM arbitration at Level 2** .

The progressive escalation flow follows strict unidirectional progression with **escape gates** at each tier:

```
Query → Level 0 (XGBoost) ──σ<0.7──→ Level 1 (Hybrid Retrieval) ──σ<0.7──→ Level 2 (LLM) ──σ<0.7──→ Fallback
          │                              │                              │
          σ≥0.7                          σ≥0.7                          σ≥0.7
          ↓                              ↓                              ↓
      Hard Route to ABCD           Hard Route or C-Refinement      Refined Route
```

Each escape decision preserves **full provenance** from preceding levels, enabling downstream tiers to focus on specific uncertainty dimensions rather than redundant re-analysis.

#### 1.1.2 Escape Threshold Mechanism (α = 0.7)

The **unified escape threshold α = 0.7** serves as the architectural gatekeeper across all tiers. This value emerges from **calibration analysis** where predicted confidence correlates with approximately **85% empirical accuracy**—balancing false positive avoidance (premature routing) against false negative costs (unnecessary escalation). The threshold's constancy simplifies operational tuning while allowing **environment-specific overrides** through configuration .

The **conservative joint confidence** formula `sigma_joint = min(sigma_c, sigma_i)` implements pessimistic aggregation: **both complexity and information sufficiency must be confidently assessed** for hard routing. This prevents scenarios where high confidence in one dimension masks uncertainty in the other—a common failure mode in production systems.

#### 1.1.3 Hard Routing vs. Escalation Decision Points

| Decision Point | Condition                                | Action                           | Latency    |
| -------------- | ---------------------------------------- | -------------------------------- | ---------- |
| Level 0 Exit   | `sigma_joint >= 0.7`                     | Route to ABCD zone               | **<1ms**   |
| Level 0 Escape | `sigma_joint < 0.7`                      | Pass to Level 1 with context     | ~1ms       |
| Level 1 Exit   | `sigma_joint >= 0.7`                     | Route with possible C-refinement | **~50ms**  |
| Level 1 Escape | `sigma_joint < 0.7` or conflict detected | Pass to Level 2 arbitration      | ~50ms      |
| Level 2 Exit   | `sigma >= 0.7`                           | Final refined routing            | **~100ms** |
| Level 2 Escape | `sigma < 0.7`                            | Trigger fallback strategy        | ~100ms+    |

### 1.2 Latency and Cost Budgets

#### 1.2.1 Level 0: <1ms CPU-Based Screening

Level 0 operates under an **aggressive sub-millisecond budget** achieved through **zero-token feature engineering**—no neural network forward passes, no tokenization beyond whitespace splitting, and no external dependencies. The **12-dimensional feature vector** is computed entirely through string operations and arithmetic that modern CPUs execute with near-single-cycle throughput .

**Cost structure**: Pure compute time on standard cloud instances (e.g., AWS c6i.large), approximately **$0.000001 per query** with no network egress or API charges. This enables **edge deployment** and **serverless scaling** without GPU provisioning complexity.

#### 1.2.2 Level 1: ~50ms Hybrid Retrieval Verification

Level 1's expanded budget accommodates **three parallel retrieval modalities**:

| Modality               | Typical Latency | Cost Driver                                  |
| ---------------------- | --------------- | -------------------------------------------- |
| Vector semantic search | 15-25ms         | FAISS index hosting, embedding cache         |
| Structured data query  | 10-30ms         | Database connection pooling, query execution |
| Keyword inverted index | 5-10ms          | Memory-resident index, CPU traversal         |

The **~50ms total** assumes **parallel execution** with result fusion as the synchronization point. Cost increases to **$0.001-0.005 per query** primarily from infrastructure (vector database, SQL replicas) rather than per-query compute .

#### 1.2.3 Level 2: ~100ms LLM Semantic Refinement

Level 2 represents the **premium tier** with strict constraints:

| Parameter         | Value                      | Rationale                                             |
| ----------------- | -------------------------- | ----------------------------------------------------- |
| Latency budget    | ~100ms                     | API round-trip + generation                           |
| Token consumption | **100-150 tokens**         | Sufficient for structured analysis, minimal verbosity |
| Temperature       | 0.1-0.3                    | Deterministic confidence estimation                   |
| Model selection   | Configurable via `litellm` | Cost-quality trade-offs per deployment                |

At typical pricing ($0.002/1K tokens), Level 2 costs **$0.0002-0.0003 per invocation**—acceptable only because **<10% of queries reach this tier** .

### 1.3 Module Organization and Code Structure

#### 1.3.1 Core Package: `ci_architecture/`

```
ci_architecture/
├── __init__.py                 # Package version and exports
├── config.py                   # Centralized configuration (Pydantic models)
├── orchestrator.py             # Main CI pipeline and escalation logic
├── metrics.py                  # Online monitoring and calibration tracking
├── level0/                     # Zero-token XGBoost classification
│   ├── features.py             # 12-dim feature extraction
│   ├── classifier.py           # Dual XGBoost inference
│   └── router.py               # Hard routing and escape logic
├── level1/                     # Hybrid retrieval verification
│   ├── vector_retriever.py     # sentence-transformers + FAISS
│   ├── keyword_retriever.py    # jieba + inverted index
│   ├── structured_retriever.py # SQL/KG with intent recognition
│   ├── fusion.py               # Multi-source confidence fusion
│   └── c_calibrator.py         # Complexity verification and adjustment
├── level2/                     # LLM semantic refinement
│   ├── llm_client.py           # litellm wrapper
│   ├── prompt_builder.py       # Context assembly
│   ├── response_parser.py      # Structured output extraction
│   └── dual_probe.py           # Consistency validation
├── routing/                    # ABCD zone execution
│   ├── abcd_mapper.py          # CI to zone mapping
│   └── execution_planner.py    # Resource allocation per zone
└── fallback/                   # Ultimate fallback strategies
    ├── conservative.py         # Forced Zone B routing
    ├── rejection.py            # Query refusal with guidance
    └── hitl.py                 # Human escalation protocol
```

#### 1.3.2 Level-Specific Submodules

Each level exposes a **standardized interface**:

```python
class CILevel(Protocol):
    def process(self, query: str, context: CIContext) -> CIResult:
        """Process query and return CI estimate with confidence."""
        ...

    def should_escalate(self, result: CIResult) -> bool:
        """Determine if result warrants next-level processing."""
        ...
```

This design enables **independent testing**, **A/B deployment**, and **graceful degradation** (e.g., skipping Level 1 if vector DB unavailable).

#### 1.3.3 Shared Utilities and Configuration

**Configuration hierarchy** (later overrides earlier):

1. `config/defaults.yaml` — baseline parameters
2. `config/{environment}.yaml` — environment-specific overrides
3. Environment variables — runtime secrets and endpoints
4. Runtime parameters — dynamic threshold adjustment

Key configurable parameters:

| Parameter          | Default                                   | Description                             |
| ------------------ | ----------------------------------------- | --------------------------------------- |
| `ALPHA`            | 0.7                                       | Universal escape threshold              |
| `LEVEL0_MODEL_C`   | `"models/xgb_c.json"`                     | Complexity classifier path              |
| `LEVEL0_MODEL_I`   | `"models/xgb_i.json"`                     | Information sufficiency classifier path |
| `VECTOR_MODEL`     | `"paraphrase-multilingual-MiniLM-L12-v2"` | Embedding model                         |
| `FAISS_INDEX_PATH` | `"indexes/corpus.faiss"`                  | Vector index location                   |
| `LLM_MODEL`        | `"gpt-4"`                                 | Level 2 arbitration model               |
| `FUSION_WEIGHTS`   | `[0.4, 0.5, 0.1]`                         | Vector/SQL/Keyword weights              |

---

## 2. Level 0: Zero-Token XGBoost Classifier

### 2.1 Feature Engineering (12-Dimensional Input)

#### 2.1.1 Length Features: `len_char`, `len_word`

The most fundamental features capture **query scale** with strong complexity correlation. **`len_char`** provides language-agnostic measurement, while **`len_word`** (whitespace-split tokens) offers semantic density indication. Their ratio implicitly encodes **average word length** useful for language detection.

Empirical distributions reveal **non-linear relationships**: queries below 10 words show >80% low-complexity probability; 20-50 words exhibit **multimodal ambiguity** requiring deeper analysis; >100 words often indicate **query overloading** or **pasted content** rather than genuine complexity .

#### 2.1.2 Entropy Features: `char_entropy`, `word_entropy` (Shannon Entropy)

**Shannon entropy** detects randomness, encoding corruption, and linguistic anomaly:

$$H(X) = -\sum_{i} p(x_i) \log_2 p(x_i)$$

| Entropy Range                            | Interpretation                          | Typical Action                                |
| ---------------------------------------- | --------------------------------------- | --------------------------------------------- |
| `char_entropy < 2.0`                     | Repetitive/templated content            | Elevate confidence in simple classification   |
| `char_entropy > 4.5` (CN) / `> 3.5` (EN) | Random/encoded/adversarial input        | Flag for special handling, degrade confidence |
| `word_entropy > 5.0`                     | High vocabulary diversity, domain-mixed | Signal potential complexity                   |

These features excel at **out-of-distribution detection** without semantic analysis .

#### 2.1.3 Domain Complexity Proxy: `domain_switch_cnt`

**Lightweight lexicon-based domain detection** counts transitions between semantic fields. Implementation maintains ~50 domain keyword sets (technology, finance, medicine, legal, etc.) and increments counter when query spans multiple domains.

A query like *"分析某医药公司的Kubernetes部署合规性"* registers switches: **medicine → technology → legal** → `domain_switch_cnt = 2`, signaling **cross-domain complexity** despite simple syntax.

#### 2.1.4 Syntactic Markers: `has_question`, `digit_ratio`

| Feature        | Detection                                   | CI Signal                                                            |
| -------------- | ------------------------------------------- | -------------------------------------------------------------------- |
| `has_question` | Question particles (吗, 什么, how, why) or `?` | Information-seeking intent, typically higher I requirements          |
| `digit_ratio`  | `sum(c.isdigit()) / len(query)`             | Quantitative precision needs (elevated → structured data preference) |

**Interaction effects**: high `digit_ratio` + `has_question` = 0 strongly suggests **identifier lookup** (high I potential); low `digit_ratio` + `has_question` = 1 indicates **open-ended inquiry** (complex response needs).

#### 2.1.5 Historical Context: `user_historical_freq`

Personalization through **query pattern frequency**—implemented via **locality-sensitive hashing** of feature vectors for privacy-preserving similarity estimation. High-frequency patterns from established users may have **cached responses** or **predictable handling**, effectively reducing information sufficiency requirements despite objective complexity.

### 2.2 Dual XGBoost Model Design

#### 2.2.1 Model C: Complexity Binary Classifier

**Training objective**: distinguish queries requiring **multi-step reasoning, domain expertise, or ambiguity handling** (High C) from **direct lookup or simple transformation** (Low C). Labels derived from **downstream task success metrics**—queries requiring Level 2 or producing low satisfaction when routed to simple pipelines.

**Architecture constraints** for <1ms inference:

- `max_depth = 6`
- `n_estimators = 100-150`
- `tree_method = 'hist'` (histogram-based splitting)
- `predictor = 'cpu_predictor'`

#### 2.2.2 Model I: Information Sufficiency Binary Classifier

**Training objective**: predict whether **available knowledge sources contain adequate information** for satisfactory response without external retrieval. Labels from **retrieval success analysis**—queries answerable from cached knowledge vs. requiring RAG supplementation.

Model I shows **stronger dependence on historical features** and **domain-specific indicators**, as information sufficiency is inherently **relative to knowledge base state** rather than query-intrinsic.

#### 2.2.3 Conservative Joint Confidence: `sigma_joint = min(sigma_c, sigma_i)`

The **minimum operation** implements architectural conservatism:

| Scenario                         | sigma_c | sigma_i | sigma_joint | Outcome            |
| -------------------------------- | ------- | ------- | ----------- | ------------------ |
| Clear complexity, ambiguous info | 0.95    | 0.55    | **0.55**    | Escape to Level 1  |
| Ambiguous complexity, clear info | 0.60    | 0.90    | **0.60**    | Escape to Level 1  |
| Both clear                       | 0.92    | 0.88    | **0.88**    | Hard route to ABCD |
| Both ambiguous                   | 0.65    | 0.70    | **0.65**    | Escape to Level 1  |

This prevents **confident errors** where certainty in one dimension masks uncertainty in the other .

### 2.3 Implementation with xgboost Library

#### 2.3.1 Model Training Pipeline

```python
# Training pipeline with calibration focus
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.calibration import CalibratedClassifierCV

def train_ci_classifier(X, y_c, y_i, output_dir):
    """
    Train dual XGBoost classifiers with calibration.
    """
    # Temporal split for realistic evaluation
    split_idx = int(len(X) * 0.8)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_c_train, y_c_val = y_c[:split_idx], y_c[split_idx:]
    y_i_train, y_i_val = y_i[:split_idx], y_i[split_idx:]

    # Model C: Complexity
    model_c = xgb.XGBClassifier(
        max_depth=6,
        n_estimators=150,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective='binary:logistic',
        eval_metric='logloss',
        tree_method='hist'
    )
    model_c.fit(
        X_train, y_c_train,
        eval_set=[(X_val, y_c_val)],
        early_stopping_rounds=20,
        verbose=False
    )

    # Calibrate on validation set
    calibrated_c = CalibratedClassifierCV(model_c, cv='prefit', method='isotonic')
    calibrated_c.fit(X_val, y_c_val)

    # Model I: Information Sufficiency (analogous)
    model_i = xgb.XGBClassifier(...)  # Similar configuration
    model_i.fit(X_train, y_i_train, ...)
    calibrated_i = CalibratedClassifierCV(model_i, cv='prefit', method='isotonic')
    calibrated_i.fit(X_val, y_i_val)

    # Save with version metadata
    model_c.save_model(f"{output_dir}/xgb_c_v{VERSION}.json")
    model_i.save_model(f"{output_dir}/xgb_i_v{VERSION}.json")

    return calibrated_c, calibrated_i
```

#### 2.3.2 Inference and Probability Extraction

```python
import xgboost as xgb
import numpy as np

class Level0Classifier:
    def __init__(self, model_c_path: str, model_i_path: str, alpha: float = 0.7):
        self.model_c = xgb.Booster()
        self.model_c.load_model(model_c_path)
        self.model_i = xgb.Booster()
        self.model_i.load_model(model_i_path)
        self.alpha = alpha

        # Pre-allocated DMatrix buffer for efficiency
        self._dmatrix_buffer = None

    def predict(self, features: np.ndarray) -> dict:
        """
        Execute dual inference with conservative confidence aggregation.
        Target: <1ms end-to-end on modern CPU.
        """
        # Ensure 2D array
        if features.ndim == 1:
            features = features.reshape(1, -1)

        # Zero-copy DMatrix when possible
        dmatrix = xgb.DMatrix(features)

        # Probability extraction: [P(Low), P(High)]
        proba_c = self.model_c.predict(dmatrix)
        proba_i = self.model_i.predict(dmatrix)

        # Handle output format (XGBoost may return 1D for binary)
        if proba_c.ndim == 1:
            proba_c = np.column_stack([1 - proba_c, proba_c])
        if proba_i.ndim == 1:
            proba_i = np.column_stack([1 - proba_i, proba_i])

        # Discrete hard decisions
        C = 1 if proba_c[0, 1] > 0.5 else 0
        I = 1 if proba_i[0, 1] > 0.5 else 0

        # Conservative confidence
        sigma_c = float(np.max(proba_c[0]))
        sigma_i = float(np.max(proba_i[0]))
        sigma_joint = min(sigma_c, sigma_i)

        return {
            'C_discrete': C,
            'I_discrete': I,
            'C_continuous': float(proba_c[0, 1]),
            'I_continuous': float(proba_i[0, 1]),
            'sigma_c': sigma_c,
            'sigma_i': sigma_i,
            'sigma_joint': sigma_joint,
            'escalate': sigma_joint < self.alpha
        }
```

#### 2.3.3 Discrete CI Hard Decision Logic

The **0.5 threshold** for discrete classification is arbitrary—any value could be used, with 0.5 representing **maximum uncertainty**. The architectural conservatism derives from **joint confidence aggregation**, not this discretization point. Continuous probabilities are preserved for Level 1 consumption, enabling **nuanced confidence fusion** rather than binary information loss.

### 2.4 Escape Condition and Routing

#### 2.4.1 Threshold Comparison: `sigma_joint < ALPHA`

The escape decision implements **strict inequality**—threshold-exact confidence (0.7000...) triggers escalation, acknowledging that confidence scores are **estimates with inherent uncertainty**. This boundary treatment prevents **overconfident routing** at the margin.

#### 2.4.2 Direct ABCD Routing on High Confidence

| C   | I   | Zone  | Execution Strategy                                    |
| --- | --- | ----- | ----------------------------------------------------- |
| 0   | 0   | **D** | Precision single-point RAG, tight constraints         |
| 0   | 1   | **C** | Direct chunk output, minimal generation               |
| 1   | 0   | **B** | Parallel RAG with external completion                 |
| 1   | 1   | **A** | Structured adversarial generation, internal reasoning |

Routing is **immediate and stateless**—no additional processing, enabling **sub-millisecond response initiation**.

#### 2.4.3 Escalation Trigger to Level 1

Escalation passes **full provenance**:

```python
level1_context = {
    'query': original_query,
    'level0_result': {
        'C_0': C, 'I_0': I,
        'sigma_c': sigma_c, 'sigma_i': sigma_i,
        'sigma_joint': sigma_joint,
        'features': features.tolist(),
        'proba_c': proba_c.tolist(),
        'proba_i': proba_i.tolist()
    }
}
```

This enables **targeted verification**—if `sigma_c` was high but `sigma_i` low, Level 1 prioritizes **information sufficiency retrieval** over complexity re-evaluation.

---

## 3. Level 1: Multi-Source Hybrid Retrieval

### 3.1 Vector Memory Retrieval (Semantic Search)

#### 3.1.1 Framework Selection: sentence-transformers + FAISS

After evaluating alternatives (including the mem0 framework mentioned in original specifications), the implementation selects **`sentence-transformers`** for embedding generation paired with **`faiss-cpu`** for vector search. This combination provides **optimal quality-efficiency trade-offs** for production deployment:

| Criterion | sentence-transformers + FAISS      | mem0 (evaluated)                    |
| --------- | ---------------------------------- | ----------------------------------- |
| Latency   | 15-25ms embedding + search         | 100ms+ (includes LLM calls)         |
| Cost      | Compute only                       | LLM API charges per operation       |
| Control   | Full over index structure, metrics | Abstracted, limited metric exposure |
| Maturity  | Production-proven, extensive docs  | Emerging, rapid API evolution       |

The **mem0 framework** offers sophisticated LLM-as-memory capabilities with automatic fact extraction and contradiction resolution, but these features introduce **substantial token overhead** (2+ LLM calls per operation) that conflicts with Level 1's **50ms latency budget** . The `sentence-transformers` + `FAISS` combination delivers **equivalent semantic retrieval** with **deterministic performance** and **full control over confidence metrics**.

#### 3.1.2 Embedding Model: `paraphrase-multilingual-MiniLM-L12-v2`

| Attribute       | Specification                 | Rationale                                     |
| --------------- | ----------------------------- | --------------------------------------------- |
| Architecture    | 12-layer MiniLM               | Balance of quality and speed                  |
| Dimensions      | 384                           | Memory-efficient, fast similarity computation |
| Sequence length | 256 tokens                    | Accommodates typical queries with headroom    |
| Languages       | 50+ including Chinese-English | Cross-lingual code-switching support          |
| Inference speed | ~5,000 queries/sec (CPU)      | Meets latency budget with batching            |

Alternative models for specific scenarios:

- **`all-MiniLM-L6-v2`**: English-only, 2x faster, slightly lower quality
- **`paraphrase-multilingual-mpnet-base-v2`**: Higher quality, 2x slower, 768-dim

#### 3.1.3 FAISS Index Construction: `IndexFlatL2` or `IndexIVFFlat`

| Collection Size | Index Type                   | Build Time | Search Latency | Recall |
| --------------- | ---------------------------- | ---------- | -------------- | ------ |
| < 100K          | `IndexFlatL2`                | Instant    | 1-2ms          | 100%   |
| 100K - 10M      | `IndexIVFFlat` (nlist=√N)    | Minutes    | 5-10ms         | >99%   |
| 10M - 100M      | `IndexIVFPQ` (m=16, nbits=8) | Hours      | 10-20ms        | ~95%   |
| > 100M          | `IndexHNSW` + `IndexIVF`     | Hours      | 5-15ms         | ~98%   |

**Default production configuration**: `IndexIVFFlat` with `nlist = 4 * sqrt(N)` clusters and `nprobe = 16` probes at query time.

```python
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

class VectorMemoryRetriever:
    def __init__(self, 
                 model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2',
                 index_path: str = None,
                 documents: List[Dict] = None):
        self.encoder = SentenceTransformer(model_name)
        self.dim = self.encoder.get_sentence_embedding_dimension()

        if index_path and os.path.exists(index_path):
            self.index = faiss.read_index(index_path)
            self.documents = self._load_doc_store(index_path.replace('.faiss', '.docs'))
        elif documents:
            self.documents = documents
            self.index = self._build_index([d['content'] for d in documents])
        else:
            raise ValueError("Provide index_path or documents")

    def _build_index(self, texts: List[str], use_ivf: bool = True) -> faiss.Index:
        """Build FAISS index with appropriate type for scale."""
        print(f"Encoding {len(texts)} documents...")
        embeddings = self.encoder.encode(texts, show_progress_bar=True)
        faiss.normalize_L2(embeddings)  # For cosine similarity via inner product

        if use_ivf and len(texts) > 100000:
            nlist = int(4 * np.sqrt(len(texts)))
            quantizer = faiss.IndexFlatIP(self.dim)
            index = faiss.IndexIVFFlat(quantizer, self.dim, nlist, faiss.METRIC_INNER_PRODUCT)
            index.train(embeddings)
        else:
            index = faiss.IndexFlatIP(self.dim)

        index.add(embeddings)
        return index

    def search(self, query: str, k: int = 10) -> Dict:
        """Retrieve with confidence-relevant metrics."""
        # Encode and normalize
        query_emb = self.encoder.encode([query])
        faiss.normalize_L2(query_emb)

        # Search
        scores, indices = self.index.search(query_emb, k)
        scores, indices = scores[0], indices[0]

        # Filter valid results
        valid = indices >= 0
        scores, indices = scores[valid], indices[valid]

        if len(scores) == 0:
            return {'sim_max': 0.0, 'gap': 0.0, 'entropy': 1.0, 'results': []}

        # Core metrics for confidence estimation
        sim_max = float(scores[0])  # Already cosine similarity (inner product of normalized)
        gap = float(scores[0] - scores[1]) if len(scores) > 1 else 0.0

        # Normalized entropy of similarity distribution
        probs = np.exp(scores - np.max(scores))  # Softmax for stability
        probs = probs / probs.sum()
        entropy = -np.sum(probs * np.log(probs + 1e-10)) / np.log(len(scores))

        # Retrieve document metadata including complexity annotations
        results = []
        for idx, score in zip(indices[:5], scores[:5]):  # Top-5 for downstream
            doc = self.documents[idx]
            results.append({
                'doc_id': int(idx),
                'content': doc['content'][:200],
                'similarity': float(score),
                'complexity': doc.get('metadata', {}).get('complexity', 0.5),
                'source': doc.get('metadata', {}).get('source', 'unknown')
            })

        return {
            'sim_max': sim_max,
            'gap': gap,
            'entropy': float(entropy),
            'results': results,
            'raw_scores': scores.tolist()
        }
```

#### 3.1.4 Retrieved Metrics: `sim_max`, `gap` (Top-1 vs Top-2), `entropy`

| Metric    | Computation                | Confidence Interpretation                                                             |
| --------- | -------------------------- | ------------------------------------------------------------------------------------- |
| `sim_max` | `max(cosine_similarities)` | **High (>0.9)**: strong semantic match; **Low (<0.5)**: knowledge gap                 |
| `gap`     | `sim_1 - sim_2`            | **Large (>0.2)**: clear best match; **Small (<0.05)**: ambiguous, multiple candidates |
| `entropy` | `H(p) / H_max` over top-K  | **Low (<0.3)**: concentrated relevance; **High (>0.7)**: diffuse, uncertain focus     |

These metrics feed directly into **calibrated confidence estimation** for information sufficiency.

### 3.2 Keyword/Sparse Retrieval (Inverted Index)

#### 3.2.1 Tokenization: jieba for Chinese Text Segmentation

**`jieba`** provides the de facto standard for Chinese text segmentation with three modes:

- **Precise mode** (default): Most accurate, suitable for analysis
- **Full mode**: Fast, finds all possible words, higher recall
- **Search engine mode**: Precise + long word segmentation, optimized for search

Level 1 uses **search engine mode** for indexing and **precise mode** for querying to balance recall and precision.

```python
import jieba
import jieba.posseg as pseg

# Load custom dictionary for domain terms
jieba.load_userdict('custom_dict.txt')

def tokenize(text: str, for_search: bool = True) -> List[str]:
    """Tokenize Chinese text with appropriate mode."""
    if for_search:
        return list(jieba.cut_for_search(text))
    return list(jieba.cut(text, cut_all=False))
```

#### 3.2.2 Inverted Index Data Structure: `Dict[str, List[DocID]]`

Core data structure with positional information for phrase queries:

```python
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict, Set, Tuple

@dataclass
class Posting:
    doc_id: int
    term_freq: int
    positions: List[int]  # For phrase queries and proximity scoring

class InvertedIndex:
    def __init__(self):
        self.index: Dict[str, List[Posting]] = defaultdict(list)
        self.doc_lengths: Dict[int, int] = {}
        self.doc_count: int = 0
        self.total_doc_length: int = 0

    def add_document(self, doc_id: int, text: str):
        """Index a document with positional information."""
        tokens = tokenize(text, for_search=True)
        self.doc_lengths[doc_id] = len(tokens)
        self.doc_count += 1
        self.total_doc_length += len(tokens)

        # Build position map
        term_positions: Dict[str, List[int]] = defaultdict(list)
        for pos, token in enumerate(tokens):
            term_positions[token].append(pos)

        # Create postings
        for term, positions in term_positions.items():
            self.index[term].append(Posting(
                doc_id=doc_id,
                term_freq=len(positions),
                positions=positions
            ))

    def get_postings(self, term: str) -> List[Posting]:
        """Retrieve posting list for term."""
        return self.index.get(term, [])
```

#### 3.2.3 TF-IDF and BM25 Scoring Implementation

```python
import math

class BM25Scorer:
    def __init__(self, index: InvertedIndex, k1: float = 1.5, b: float = 0.75):
        self.index = index
        self.k1 = k1
        self.b = b
        self.avg_doc_length = (index.total_doc_length / index.doc_count 
                              if index.doc_count > 0 else 0)
        self.idf_cache: Dict[str, float] = {}

    def idf(self, term: str) -> float:
        """Compute IDF with caching."""
        if term not in self.idf_cache:
            df = len(self.index.get_postings(term))
            # BM25 IDF with smoothing
            self.idf_cache[term] = math.log(
                (self.index.doc_count - df + 0.5) / (df + 0.5) + 1.0
            )
        return self.idf_cache[term]

    def score(self, doc_id: int, term: str, term_freq: int) -> float:
        """Compute BM25 score for single term-document pair."""
        idf = self.idf(term)
        doc_len = self.index.doc_lengths.get(doc_id, self.avg_doc_length)

        # BM25 term frequency saturation
        tf_component = (term_freq * (self.k1 + 1)) / (
            term_freq + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_length)
        )

        return idf * tf_component

    def score_query(self, query: str, doc_id: int) -> float:
        """Score document for full query."""
        query_tokens = tokenize(query)
        query_term_counts = {}
        for t in query_tokens:
            query_term_counts[t] = query_term_counts.get(t, 0) + 1

        total_score = 0.0
        for term, qtf in query_term_counts.items():
            # Find term frequency in document
            doc_tf = 0
            for posting in self.index.get_postings(term):
                if posting.doc_id == doc_id:
                    doc_tf = posting.term_freq
                    break

            if doc_tf > 0:
                total_score += self.score(doc_id, term, doc_tf) * qtf

        return total_score
```

#### 3.2.4 Boolean and Phrase Query Support

```python
def boolean_search(self, query_terms: List[str], operator: str = 'AND') -> Set[int]:
    """Execute Boolean retrieval."""
    result_sets = []
    for term in query_terms:
        doc_ids = {p.doc_id for p in self.index.get_postings(term)}
        result_sets.append(doc_ids)

    if not result_sets:
        return set()

    if operator == 'AND':
        return set.intersection(*result_sets)
    else:  # OR
        return set.union(*result_sets)

def phrase_search(self, phrase: str) -> List[int]:
    """Exact phrase search with positional verification."""
    phrase_tokens = tokenize(phrase)
    if not phrase_tokens:
        return []

    # Get candidate documents containing all terms
    candidates = boolean_search(self, phrase_tokens, 'AND')

    # Verify phrase adjacency
    results = []
    for doc_id in candidates:
        # Get positions for each term in document
        term_positions = []
        for term in phrase_tokens:
            for posting in self.index.get_postings(term):
                if posting.doc_id == doc_id:
                    term_positions.append(posting.positions)
                    break

        if len(term_positions) != len(phrase_tokens):
            continue

        # Check for consecutive positions
        for start_pos in term_positions[0]:
            is_phrase = True
            for i, positions in enumerate(term_positions[1:], 1):
                if start_pos + i not in positions:
                    is_phrase = False
                    break
            if is_phrase:
                results.append(doc_id)
                break

    return results
```

### 3.3 Structured Data Retrieval (SQL/KG)

#### 3.3.1 Intent Recognition Module Design

The intent recognition subsystem classifies queries into **structured access patterns** and extracts parameters for query generation. Implementation combines **pattern matching** for common templates with **lightweight classification** for ambiguous cases.

```python
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, List, Dict
import re

class StructuredIntent(Enum):
    FACT_LOOKUP = auto()      # "What is X's Y?" → SELECT Y FROM table WHERE id=X
    AGGREGATION = auto()      # "Average sales by region" → GROUP BY with AVG
    COMPARISON = auto()       # "Compare A and B" → Multiple lookups + computation
    TEMPORAL = auto()         # "Trend over last N months" → Time-series query
    RELATIONAL = auto()       # "Employees in department X" → JOIN traversal
    UNSUPPORTED = auto()      # No structured mapping possible

@dataclass
class IntentResult:
    intent: StructuredIntent
    confidence: float
    entities: Dict[str, any]  # Extracted parameters
    table_candidates: List[str]
    missing_slots: List[str]

class IntentRecognizer:
    """Rule-based intent recognition with confidence scoring."""

    # Intent-specific patterns with capture groups
    PATTERNS = {
        StructuredIntent.FACT_LOOKUP: [
            r'(?:什么是|查询|查找)\s*(\w+)的(\w+)',
            r'(\w+)的(\w+)(?:是|为)?多少',
            r'(\w+)(?:的)?(\w+)(?:是什么|是多少)',
        ],
        StructuredIntent.AGGREGATION: [
            r'(?:总共|合计|总和|总计|sum|total)',
            r'(?:平均|均值|average|avg|mean)',
            r'(?:最大|最高|最多|maximum|max)',
            r'(?:最小|最低|最少|minimum|min)',
            r'按(\w+)(?:统计|分组|group)',
        ],
        StructuredIntent.COMPARISON: [
            r'(?:比较|对比|versus|vs|compare)',
            r'(\w+)和(\w+)(?:的)?(?:区别|差异|比较)',
        ],
        StructuredIntent.TEMPORAL: [
            r'(?:20\d{2})[年/-](\d{1,2})[月/-]?(\d{1,2})?',
            r'(?:去年|今年|明年|last year|this year|next year)',
            r'(?:上|本|下)(?:季度|月|周)',
        ],
    }

    def __init__(self, schema: Dict):
        self.schema = schema  # Database schema for validation
        self.entity_patterns = self._compile_entity_patterns()

    def recognize(self, query: str) -> IntentResult:
        """Classify query intent with confidence."""
        query_lower = query.lower().strip()

        # Score each intent category
        intent_scores = {intent: 0.0 for intent in StructuredIntent}

        for intent, patterns in self.PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, query_lower)
                for match in matches:
                    # Confidence based on match length and specificity
                    match_score = len(match.group(0)) / len(query_lower)
                    intent_scores[intent] = max(intent_scores[intent], 
                                               0.3 + 0.7 * match_score)

        # Entity extraction for slot filling
        entities = self._extract_entities(query_lower)

        # Schema-based validation
        table_candidates = self._infer_tables(entities)

        # Select primary intent
        if max(intent_scores.values()) < 0.3:
            primary_intent = StructuredIntent.UNSUPPORTED
            confidence = 0.9  # High confidence that we can't handle it
        else:
            primary_intent = max(intent_scores, key=intent_scores.get)
            confidence = intent_scores[primary_intent]

        # Determine missing required slots
        required_slots = self._get_required_slots(primary_intent)
        missing_slots = [s for s in required_slots if s not in entities]

        return IntentResult(
            intent=primary_intent,
            confidence=confidence,
            entities=entities,
            table_candidates=table_candidates,
            missing_slots=missing_slots
        )

    def _extract_entities(self, query: str) -> Dict[str, any]:
        """Extract named entities, numbers, dates from query."""
        entities = {}

        # Number extraction
        numbers = re.findall(r'\d+(?:\.\d+)?', query)
        if numbers:
            entities['numbers'] = [float(n) for n in numbers]

        # Date patterns
        date_patterns = [
            r'(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})[日]?',
            r'(20\d{2})(\d{2})(\d{2})',  # YYYYMMDD
        ]
        dates = []
        for pattern in date_patterns:
            for match in re.finditer(pattern, query):
                dates.append({
                    'year': int(match.group(1)),
                    'month': int(match.group(2)),
                    'day': int(match.group(3)) if match.lastindex >= 3 else None
                })
        if dates:
            entities['dates'] = dates

        # Quoted strings as exact match candidates
        quoted = re.findall(r'"([^"]+)"', query)
        if quoted:
            entities['quoted_terms'] = quoted

        return entities

    def _infer_tables(self, entities: Dict) -> List[str]:
        """Map entity types to database tables using schema."""
        candidates = []
        for table, info in self.schema.get('tables', {}).items():
            # Simple heuristic: check if entity keys match column names
            for entity_key in entities.keys():
                if any(entity_key in col['name'] for col in info.get('columns', [])):
                    candidates.append(table)
                    break
        return list(set(candidates))

    def _get_required_slots(self, intent: StructuredIntent) -> List[str]:
        """Define required parameters for each intent type."""
        required = {
            StructuredIntent.FACT_LOOKUP: ['entity_id', 'attribute'],
            StructuredIntent.AGGREGATION: ['metric', 'dimension'],
            StructuredIntent.COMPARISON: ['entity_a', 'entity_b'],
            StructuredIntent.TEMPORAL: ['start_date', 'end_date'],
            StructuredIntent.RELATIONAL: ['entity_type', 'relationship'],
        }
        return required.get(intent, [])
```

#### 3.3.2 Schema-Aware SQL Query Generator

```python
class SQLQueryGenerator:
    """Generate executable SQL from recognized intent."""

    def __init__(self, schema: Dict, db_connection):
        self.schema = schema
        self.conn = db_connection

    def generate(self, intent_result: IntentResult) -> Optional[Dict]:
        """Generate SQL with execution plan and confidence metrics."""
        if intent_result.intent == StructuredIntent.UNSUPPORTED:
            return None

        # Build query components
        select_clause = self._build_select(intent_result)
        from_clause = self._build_from(intent_result)
        where_clause = self._build_where(intent_result)
        group_clause = self._build_group_by(intent_result)

        # Assemble query
        sql_parts = [f"SELECT {select_clause}", f"FROM {from_clause}"]
        if where_clause:
            sql_parts.append(f"WHERE {where_clause}")
        if group_clause:
            sql_parts.append(f"GROUP BY {group_clause}")

        sql = " ".join(sql_parts)

        # Validate against schema
        validation = self._validate_query(sql)

        return {
            'sql': sql,
            'parameters': [],  # For prepared statement
            'expected_schema': validation['columns'],
            'confidence': validation['match_score']
        }

    def _build_select(self, intent: IntentResult) -> str:
        """Construct SELECT clause based on intent."""
        if intent.intent == StructuredIntent.AGGREGATION:
            # Detect aggregation function from query patterns
            if any(kw in str(intent.entities) for kw in ['平均', 'avg', 'average', 'mean']):
                return "AVG({}) as result, {}".format(
                    self._infer_metric_column(intent),
                    intent.entities.get('dimension', '*')
                )
            elif any(kw in str(intent.entities) for kw in ['总共', 'sum', 'total']):
                return "SUM({}) as result".format(self._infer_metric_column(intent))
            else:
                return "COUNT(*) as result"

        elif intent.intent == StructuredIntent.FACT_LOOKUP:
            attr = intent.entities.get('attribute', '*')
            return attr if attr != '*' else ', '.join(
                c['name'] for c in self._get_columns(intent.table_candidates[0])[:5]
            )

        return "*"

    def _build_from(self, intent: IntentResult) -> str:
        """Determine target table(s)."""
        if intent.table_candidates:
            primary = intent.table_candidates[0]
            # Add joins if relational intent
            if intent.intent == StructuredIntent.RELATIONAL and len(intent.table_candidates) > 1:
                joins = self._infer_joins(primary, intent.table_candidates[1:])
                return f"{primary} {joins}"
            return primary
        return "unknown_table"  # Will fail validation

    def _build_where(self, intent: IntentResult) -> Optional[str]:
        """Construct WHERE clause from extracted entities."""
        conditions = []

        if 'numbers' in intent.entities:
            # Infer numeric filter from context
            for num in intent.entities['numbers'][:2]:  # Limit to first 2
                col = self._infer_numeric_column(intent.table_candidates[0])
                if col:
                    conditions.append(f"{col} = {num}")

        if 'dates' in intent.entities:
            for date in intent.entities['dates'][:1]:
                col = self._infer_date_column(intent.table_candidates[0])
                if col:
                    conditions.append(f"{col} >= '{date['year']}-{date['month']:02d}-01'")

        if 'quoted_terms' in intent.entities:
            for term in intent.entities['quoted_terms']:
                text_col = self._infer_text_column(intent.table_candidates[0])
                if text_col:
                    conditions.append(f"{text_col} LIKE '%{term}%'")

        return " AND ".join(conditions) if conditions else None

    def execute_with_metrics(self, query_spec: Dict) -> Dict:
        """Execute generated query and compute quality metrics."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(query_spec['sql'])

            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            # Compute metrics
            return {
                'success': True,
                'row_count': len(rows),
                'null_ratio': self._compute_null_ratio(rows),
                'schema_match_rate': query_spec['confidence'],
                'sample_data': [dict(zip(columns, row)) for row in rows[:5]],
                'execution_time_ms': None  # Would measure in production
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'schema_match_rate': query_spec['confidence'] * 0.5,
                'row_count': 0,
                'null_ratio': 1.0
            }

    def _compute_null_ratio(self, rows: List[tuple]) -> float:
        """Compute fraction of null values in result set."""
        if not rows:
            return 1.0

        total_cells = len(rows) * len(rows[0])
        null_cells = sum(1 for row in rows for cell in row if cell is None)
        return null_cells / total_cells
```

#### 3.3.3 Knowledge Graph Traversal for Entity Linking

```python
import networkx as nx

class KnowledgeGraphRetriever:
    """Traverse knowledge graphs for relational queries."""

    def __init__(self, graph: nx.Graph):
        self.G = graph
        self.entity_index = self._build_entity_index()

    def _build_entity_index(self) -> Dict[str, List[str]]:
        """Index nodes by name/alias for fast lookup."""
        index = {}
        for node, data in self.G.nodes(data=True):
            names = [data.get('name', '')] + data.get('aliases', [])
            for name in names:
                index.setdefault(name.lower(), []).append(node)
        return index

    def link_entity(self, mention: str) -> Optional[str]:
        """Link text mention to graph node."""
        # Exact match
        if mention.lower() in self.entity_index:
            candidates = self.entity_index[mention.lower()]
            return candidates[0] if len(candidates) == 1 else None  # Disambiguate if needed

        # Fuzzy match (simplified—production would use embeddings)
        # ...
        return None

    def traverse(self, start_entity: str, 
                 relation_type: Optional[str] = None,
                 depth: int = 2) -> Dict:
        """Traverse graph from entity with optional relation filter."""
        start_node = self.link_entity(start_entity)
        if not start_node:
            return {'found': False, 'reachable_nodes': 0, 'subgraph': None}

        # BFS traversal with depth limit
        visited = {start_node}
        frontier = {start_node}
        current_depth = 0

        while frontier and current_depth < depth:
            next_frontier = set()
            for node in frontier:
                for neighbor in self.G.neighbors(node):
                    if neighbor not in visited:
                        edge_data = self.G.get_edge_data(node, neighbor)
                        if relation_type is None or edge_data.get('relation') == relation_type:
                            next_frontier.add(neighbor)
                            visited.add(neighbor)
            frontier = next_frontier
            current_depth += 1

        # Extract subgraph
        subgraph = self.G.subgraph(visited)

        return {
            'found': True,
            'start_node': start_node,
            'reachable_nodes': len(visited) - 1,  # Exclude start
            'traversal_depth': current_depth,
            'subgraph': subgraph,
            'central_entities': self._rank_by_centrality(subgraph, start_node)
        }

    def _rank_by_centrality(self, subgraph: nx.Graph, 
                           start_node: str) -> List[Dict]:
        """Rank entities by relevance to start node."""
        # Simple degree centrality—production would use personalized PageRank
        centrality = nx.degree_centrality(subgraph)
        ranked = sorted(
            [(n, c) for n, c in centrality.items() if n != start_node],
            key=lambda x: x[1],
            reverse=True
        )
        return [{'node': n, 'centrality': c, 
                'name': self.G.nodes[n].get('name', n)} 
               for n, c in ranked[:10]]
```

#### 3.3.4 Return Metrics: Schema Match Rate, Row Count, Null Ratio

| Metric                | Range  | Interpretation                                | Confidence Signal                                               |
| --------------------- | ------ | --------------------------------------------- | --------------------------------------------------------------- |
| **Schema match rate** | [0, 1] | Fraction of query elements mappable to schema | Higher = better query understanding                             |
| **Row count**         | 0 to ∞ | Result set size                               | 0 = no information; 1 = precise fact; many = requires synthesis |
| **Null ratio**        | [0, 1] | Fraction of null values in results            | Higher = data quality concerns, degrade confidence              |

### 3.4 Multi-Source Confidence Fusion

#### 3.4.1 Source-Specific Calibration (Isotonic Regression)

```python
from sklearn.isotonic import IsotonicRegression
import numpy as np

class CalibratedScorer:
    """Transform raw retrieval scores to calibrated probabilities."""

    def __init__(self):
        self.vector_calibrator = IsotonicRegression(out_of_bounds='clip')
        self.structured_calibrator = IsotonicRegression(out_of_bounds='clip')
        self.fitted = False

    def fit(self, 
            vector_scores: np.ndarray, vector_accuracies: np.ndarray,
            struct_scores: np.ndarray, struct_accuracies: np.ndarray):
        """Fit calibrators on validation data with relevance judgments."""
        self.vector_calibrator.fit(vector_scores, vector_accuracies)
        self.structured_calibrator.fit(struct_scores, struct_accuracies)
        self.fitted = True

    def calibrate_vector(self, sim_max: float, gap: float, entropy: float) -> float:
        """Calibrate vector retrieval confidence."""
        if not self.fitted:
            # Fallback: heuristic calibration
            return sim_max * (1 - entropy) * (0.5 + 0.5 * gap)

        # Primary signal: max similarity
        base_conf = self.vector_calibrator.predict([sim_max])[0]

        # Adjust for distribution quality
        quality_factor = (1 - entropy) * (0.5 + 0.5 * min(gap * 5, 1))

        return base_conf * quality_factor

    def calibrate_structured(self, schema_match: float, row_count: int,
                            null_ratio: float, execution_success: bool) -> float:
        """Calibrate structured retrieval confidence."""
        if not execution_success:
            return 0.1  # Heavy penalty for execution failure

        if not self.fitted:
            # Fallback heuristic
            specificity = 1 / (1 + np.log1p(row_count))
            completeness = 1 - null_ratio
            return schema_match * specificity * completeness

        base_conf = self.structured_calibrator.predict([schema_match])[0]
        specificity = 1 / (1 + np.log1p(max(row_count, 1)))
        completeness = 1 - null_ratio

        return base_conf * specificity * completeness
```

#### 3.4.2 Weighted Bayesian Fusion: Vector (0.4), SQL (0.5), Keyword (0.1)

```python
class ConfidenceFusion:
    """Fuse multi-source signals into unified I estimate."""

    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or {
            'vector': 0.4,
            'structured': 0.5,
            'keyword': 0.1
        }
        self.calibrator = CalibratedScorer()
        self.conflict_threshold = 0.5
        self.conflict_penalty = 0.6

    def fuse(self, sources: Dict[str, Dict]) -> Tuple[float, float]:
        """
        Fuse sources into I_mean and sigma_I.

        Args:
            sources: {
                'vector': {'sim_max': ..., 'gap': ..., 'entropy': ...},
                'structured': {'schema_match': ..., 'row_count': ..., ...},
                'keyword': {'score_max': ..., 'coverage': ...}
            }

        Returns:
            (I_mean, sigma_I)
        """
        # Calibrate each source
        conf_vector = self.calibrator.calibrate_vector(
            sources['vector']['sim_max'],
            sources['vector']['gap'],
            sources['vector']['entropy']
        ) if 'vector' in sources else 0.0

        conf_structured = self.calibrator.calibrate_structured(
            sources['structured'].get('schema_match_rate', 0),
            sources['structured'].get('row_count', 0),
            sources['structured'].get('null_ratio', 0.5),
            sources['structured'].get('success', False)
        ) if 'structured' in sources else 0.0

        # Keyword: simple scaling (less reliable)
        conf_keyword = sources['keyword'].get('score_max', 0) * 0.5 \
                      if 'keyword' in sources else 0.0

        # Collect available sources
        available = {}
        if 'vector' in sources:
            available['vector'] = conf_vector
        if 'structured' in sources:
            available['structured'] = conf_structured
        if 'keyword' in sources:
            available['keyword'] = conf_keyword

        if not available:
            return 0.0, 0.0  # No valid sources

        # Normalize weights for available sources
        total_weight = sum(self.weights.get(s, 0) for s in available)
        normalized_weights = {
            s: self.weights.get(s, 0) / total_weight 
            for s in available
        }

        # Weighted mean
        I_mean = sum(
            conf * normalized_weights[s] 
            for s, conf in available.items()
        )

        # Conflict detection
        conf_values = list(available.values())
        max_diff = max(conf_values) - min(conf_values)

        sigma_penalty = self.conflict_penalty if max_diff > self.conflict_threshold else 1.0

        # Final confidence: vector entropy-based with conflict penalty
        vector_entropy = sources.get('vector', {}).get('entropy', 0.5)
        sigma_I = (1 - vector_entropy) * sigma_penalty

        return I_mean, sigma_I
```

#### 3.4.3 Conflict Detection: Cross-Source Divergence Penalty

**Conflict triggers**:

- **Numerical divergence**: `max(conf_vector, conf_structured) - min(conf_vector, conf_structured) > 0.5`
- **Qualitative mismatch**: one source strongly positive (>0.8), another strongly negative (<0.3)

**Penalty application**: `sigma_I *= 0.6`, typically forcing `sigma_joint < 0.7` and escalation to Level 2.

#### 3.4.4 Final I Estimation and `sigma_I` Computation

The fusion output `I_mean` represents **expected information sufficiency** on [0,1], while `sigma_I` captures **epistemic uncertainty** about that estimate. These feed into joint confidence recalculation with complexity verification results.

### 3.5 C Verification and Fine-Tuning

#### 3.5.1 Historical Complexity Retrieval from mem0 Metadata

**Note on mem0 integration**: While the original specification referenced mem0 for vector memory with complexity metadata, the production implementation uses **FAISS with custom metadata fields**. The equivalent functionality stores `complexity` annotations in document metadata during index construction:

```python
# During document indexing
documents = [
    {
        'content': text,
        'metadata': {
            'complexity': compute_complexity(text),  # Historical label
            'source': 'training_data',
            'timestamp': '2024-01-15'
        }
    }
    for text in corpus
]
```

#### 3.5.2 Bounded Adjustment: `delta ∈ [-0.2, +0.2]`

```python
class ComplexityVerifier:
    """Verify and refine Level 0 complexity estimate."""

    def __init__(self, max_adjustment: float = 0.2, 
                 damping: float = 0.3):
        self.max_adjustment = max_adjustment
        self.damping = damping  # Gain factor for historical influence

    def verify(self, c0: float, sigma0: float,
               retrievals: List[Dict]) -> Tuple[float, float]:
        """
        Refine complexity using high-confidence historical matches.

        Returns:
            (c1, sigma_c1)
        """
        # Extract complexity from high-similarity retrievals
        hist_c = [
            doc['metadata']['complexity']
            for doc in retrievals
            if doc.get('similarity', 0) > 0.9 and 'complexity' in doc.get('metadata', {})
        ]

        if not hist_c:
            # No reliable historical evidence
            return c0, sigma0

        hist_mean = np.mean(hist_c)

        # Compute damped, bounded adjustment
        raw_delta = self.damping * (hist_mean - c0)
        clipped_delta = np.clip(raw_delta, -self.max_adjustment, self.max_adjustment)
        c1 = c0 + clipped_delta

        # Confidence boost with ceiling
        sigma_c1 = min(0.95, sigma0 * 1.1)

        return c1, sigma_c1
```

#### 3.5.3 Conflict-Triggered Confidence Degradation

```python
# Within verify() method
CONFLICT_THRESHOLD = 0.3
MIN_SIGMA_FOR_CONFLICT = 0.8

if abs(hist_mean - c0) > CONFLICT_THRESHOLD and sigma0 < MIN_SIGMA_FOR_CONFLICT:
    # Strong disagreement with moderate original confidence
    # Degrade and escalate rather than risk wrong adjustment
    return c0, sigma0 * 0.5  # 50% confidence penalty
```

#### 3.5.4 Updated `sigma_c1` with Post-Correction Boost

The **1.1x confidence boost** reflects information gain from successful verification, capped at **0.95** to maintain epistemic humility. This prevents artificial certainty inflation while rewarding productive refinement.

### 3.6 Level 1 Escape Decision

#### 3.6.1 Joint Confidence Recalculation

```python
def level1_decision(c0: float, sigma0: float,
                    vector_result: Dict,
                    structured_result: Dict,
                    keyword_result: Dict) -> Dict:
    """Execute full Level 1 pipeline and decision."""

    # Fuse information sufficiency
    fusion = ConfidenceFusion()
    I_mean, sigma_I = fusion.fuse({
        'vector': vector_result,
        'structured': structured_result,
        'keyword': keyword_result
    })

    # Verify complexity
    verifier = ComplexityVerifier()
    c1, sigma_c1 = verifier.verify(
        c0, sigma0, 
        vector_result.get('results', [])
    )

    # Joint confidence
    sigma_joint = min(sigma_c1, sigma_I)

    # Check for source conflict in fusion
    conflict_detected = (max([vector_result.get('sim_max', 0),
                             structured_result.get('schema_match_rate', 0)]) -
                        min([v for v in [vector_result.get('sim_max', 1),
                                        structured_result.get('schema_match_rate', 1)]
                            if v > 0])) > 0.5

    return {
        'C': c1,
        'I': I_mean,
        'sigma_c': sigma_c1,
        'sigma_i': sigma_I,
        'sigma_joint': sigma_joint,
        'escalate': sigma_joint < 0.7 or conflict_detected,
        'conflict_detected': conflict_detected,
        'level': 1
    }
```

#### 3.6.2 Source Conflict as Escalation Trigger

**Explicit conflict detection** ensures that fundamentally contradictory signals—regardless of numerical confidence—receive human-level semantic analysis. This captures cases where:

- Vector search finds highly similar documents (high I potential)
- Structured query returns empty results (low I evidence)
- Or vice versa: no semantic matches but precise schema hit

#### 3.6.3 Handoff to Level 2 Arbitration

Escalation passes **comprehensive context**:

```python
level2_context = {
    'query': original_query,
    'level0': level0_result,
    'level1': {
        'C': c1, 'I': I_mean,
        'sigma_c': sigma_c1, 'sigma_i': sigma_I,
        'vector_results': vector_result,
        'structured_results': structured_result,
        'fusion_metadata': {
            'weights_used': fusion.weights,
            'conflict_detected': conflict_detected
        }
    }
}
```

---

## 4. Level 2: LLM Semantic Refinement

### 4.1 LLM Interaction Framework

#### 4.1.1 Library Selection: litellm for Unified API

**`litellm`** provides **provider-agnostic LLM access** with OpenAI-compatible interface, enabling seamless model substitution and fallback chains:

| Feature                      | Benefit for CI Architecture                    |
| ---------------------------- | ---------------------------------------------- |
| Unified `completion()` API   | Single integration point for 100+ models       |
| Automatic retry with backoff | Resilience to transient API failures           |
| Cost tracking integration    | Per-query cost attribution for optimization    |
| Streaming support            | Future extension for progressive responses     |
| Async support                | Concurrent probe execution for dual validation |

Installation: `pip install litellm>=1.0.0`

#### 4.1.2 Model-Agnostic Completion Interface

```python
import litellm
import os
from typing import List, Dict, Optional

class LLMInterface:
    """Unified LLM interface with provider abstraction."""

    def __init__(self, 
                 primary_model: str = "gpt-4",
                 fallback_models: List[str] = None,
                 temperature: float = 0.1,
                 max_tokens: int = 500):
        self.primary_model = primary_model
        self.fallback_models = fallback_models or ["gpt-3.5-turbo", "claude-3-haiku-20240307"]
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Configure from environment or explicit keys
        litellm.set_verbose = False

    def complete(self, 
                 messages: List[Dict[str, str]],
                 model: Optional[str] = None,
                 temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None,
                 response_format: Optional[Dict] = None) -> Dict:
        """
        Execute completion with fallback chain.

        Returns standardized response regardless of provider.
        """
        model = model or self.primary_model
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        models_to_try = [model] + self.fallback_models

        for m in models_to_try:
            try:
                response = litellm.completion(
                    model=m,
                    messages=messages,
                    temperature=temp,
                    max_tokens=tokens,
                    response_format=response_format,
                    timeout=30  # Seconds
                )

                return {
                    'success': True,
                    'model_used': m,
                    'content': response.choices[0].message.content,
                    'usage': {
                        'prompt_tokens': response.usage.prompt_tokens,
                        'completion_tokens': response.usage.completion_tokens,
                        'total_tokens': response.usage.total_tokens
                    },
                    'finish_reason': response.choices[0].finish_reason
                }

            except Exception as e:
                last_error = str(e)
                continue  # Try next fallback

        # All models failed
        return {
            'success': False,
            'error': last_error,
            'models_attempted': models_to_try
        }
```

#### 4.1.3 Message Format: OpenAI-Compatible Chat Structure

```python
def build_messages(system_prompt: Optional[str] = None,
                   user_prompt: str) -> List[Dict[str, str]]:
    """Construct OpenAI-compatible message list."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    return messages
```

### 4.2 Structured Prompt Engineering

#### 4.2.1 Context Assembly: Level 0/1 Results + Retrieval Evidence

```python
class PromptBuilder:
    """Assemble comprehensive context for Level 2 arbitration."""

    def build(self, query: str, level0: Dict, level1: Dict) -> str:
        """Construct evidence-rich prompt with structured output instruction."""

        # Extract retrieval summaries
        vector_summary = self._summarize_vector(level1.get('vector_results', {}))
        structured_summary = self._summarize_structured(level1.get('structured_results', {}))

        prompt = f"""You are an expert query analyzer for an intelligent routing system. Your task is to assess query complexity (C) and information sufficiency (I) based on all available evidence from previous processing stages.

## Original Query
"{query}"

## Level 0 Analysis (Fast Classifier)
- Complexity estimate (C₀): {level0.get('C_continuous', level0.get('C_discrete', 0.5)):.2f}
- Information sufficiency (I₀): {level0.get('I_continuous', level0.get('I_discrete', 0.5)):.2f}
- Confidence: σ_c={level0.get('sigma_c', 0):.2f}, σ_i={level0.get('sigma_i', 0):.2f}
- Key features: length={level0.get('features', [0])[0]:.0f}, entropy={level0.get('features', [0]*3)[2]:.2f}

## Level 1 Retrieval Evidence
### Semantic Search (Vector Memory)
{vector_summary}

### Structured Data (SQL/KG)
{structured_summary}

### Fusion Analysis
- Combined I estimate: {level1.get('I', 0):.2f}
- Source conflict detected: {"YES" if level1.get('conflict_detected') else "NO"}

## Your Assessment Task
Based on ALL evidence above, provide your final CI assessment in **strict JSON format**:

```json
{{
  "C": 0.00-1.00,           // Query complexity: 0=simple lookup, 1=multi-step reasoning
  "I": 0.00-1.00,           // Information sufficiency: 0=major gaps, 1=fully answerable
  "confidence": 0.00-1.00,  // Your certainty in this assessment
  "missing_info": ["..."],  // Specific information needed if I < 0.5, else []
  "reasoning": "..."        // 1-2 sentence analysis of key factors
}}
```

Guidelines:

- **C > 0.7**: Requires multi-step reasoning, domain synthesis, or careful ambiguity handling

- **I > 0.7**: Retrieved sources contain sufficient information for complete answer

- Be **well-calibrated**: confidence should reflect genuine uncertainty, not optimism

- If sources conflict, acknowledge this and adjust confidence downward
  """
  
        return prompt
  
    def _summarize_vector(self, result: Dict) -> str:
  
        """Create human-readable vector retrieval summary."""
        if not result or not result.get('results'):
            return "- No relevant documents found (sim_max: 0.00)"
      
        lines = [
            f"- Top similarity: {result.get('sim_max', 0):.3f}",
            f"- Result distinctness (gap): {result.get('gap', 0):.3f}",
            f"- Distribution entropy: {result.get('entropy', 1):.3f}",
            "- Top matches:"
        ]
        for i, doc in enumerate(result.get('results', [])[:3], 1):
            lines.append(f"  {i}. [{doc.get('similarity', 0):.3f}] {doc.get('content', '')[:80]}...")
      
        return '\n'.join(lines)
  
    def _summarize_structured(self, result: Dict) -> str:
  
        """Create human-readable structured retrieval summary."""
        if not result or not result.get('success'):
            return f"- Query execution failed: {result.get('error', 'unknown error')}"
      
        lines = [
            f"- Schema match rate: {result.get('schema_match_rate', 0):.2f}",
            f"- Result rows: {result.get('row_count', 0)}",
            f"- Data completeness: {1 - result.get('null_ratio', 0.5):.2f}"
        ]
        if result.get('sample_data'):
            lines.append("- Sample results:")
            for row in result['sample_data'][:2]:
                lines.append(f"  {str(row)[:100]}")
      
        return '\n'.join(lines)
  
  ```
  
  ```

#### 4.2.2 Forced JSON Output Schema: `C`, `I`, `confidence`, `missing_info`, `reasoning`

| Field          | Type      | Range         | Description                                                                                   |
| -------------- | --------- | ------------- | --------------------------------------------------------------------------------------------- |
| `C`            | float     | [0, 1]        | **Complexity**: 0=direct lookup, 0.3-0.7=moderate reasoning, 1=multi-step synthesis           |
| `I`            | float     | [0, 1]        | **Information sufficiency**: 0=major gaps, 0.3-0.7=partial coverage, 1=complete answerability |
| `confidence`   | float     | [0, 1]        | **Self-assessed certainty**: well-calibrated probability of expert agreement                  |
| `missing_info` | list[str] | [] or ["..."] | Specific facts/knowledge gaps if I < 0.5; empty list otherwise                                |
| `reasoning`    | string    | 1-2 sentences | Brief analysis highlighting key evidence and uncertainty sources                              |

#### 4.2.3 Continuous Value Ranges: C ∈ [0,1], I ∈ [0,1]

Continuous outputs enable **soft routing at boundaries**—e.g., C=0.65 triggers 60% Zone A + 40% Zone C resource allocation—rather than sharp discrete transitions.

### 4.3 Confidence Computation and Validation

#### 4.3.1 Direct LLM Self-Reported Confidence

The `confidence` field elicits **calibrated self-assessment** through careful framing:

> *"How confident are you that a human expert would agree with your C and I assessment?"*

This **second-order judgment** (confidence in correctness) typically yields better calibration than raw certainty reports.

#### 4.3.2 Dual-Probe Consistency Check (Jaccard > 0.8)

```python
class DualProbeValidator:
    """Validate LLM assessment consistency through independent probes."""

    def __init__(self, llm: LLMInterface, consistency_threshold: float = 0.8):
        self.llm = llm
        self.threshold = consistency_threshold

    def validate(self, query: str, level0: Dict, level1: Dict,
                 n_probes: int = 2) -> Dict:
        """Execute multiple probes and measure response consistency."""

        # Build base prompt
        builder = PromptBuilder()
        base_prompt = builder.build(query, level0, level1)

        # Add variation for independent sampling
        prompts = []
        for i in range(n_probes):
            variant = base_prompt + f"\n\n[Assessment variant {i+1}/{n_probes}]"
            prompts.append(variant)

        # Execute probes with slight temperature variation
        responses = []
        for i, prompt in enumerate(prompts):
            result = self.llm.complete(
                build_messages(user_prompt=prompt),
                temperature=0.1 + i * 0.05  # 0.1, 0.15, ...
            )
            if result['success']:
                parsed = self._parse_json_safe(result['content'])
                responses.append(parsed)

        if len(responses) < 2:
            return {
                'consistency': 0.0,
                'confidence_adjustment': 0.7,  # Degrade for insufficient probes
                'parsed_responses': responses
            }

        # Compute Jaccard-like similarity on discrete elements
        discrete_sims = []
        for i in range(len(responses)):
            for j in range(i+1, len(responses)):
                sim = self._compute_similarity(responses[i], responses[j])
                discrete_sims.append(sim)

        avg_similarity = np.mean(discrete_sims)

        # Confidence adjustment based on consistency
        if avg_similarity >= self.threshold:
            adjustment = 1.1  # Boost for strong agreement
        elif avg_similarity >= 0.5:
            adjustment = 0.9  # Slight degrade for moderate agreement
        else:
            adjustment = 0.6  # Strong degrade for disagreement

        return {
            'consistency': avg_similarity,
            'confidence_adjustment': adjustment,
            'parsed_responses': responses,
            'recommend_retry': avg_similarity < 0.5
        }

    def _compute_similarity(self, r1: Dict, r2: Dict) -> float:
        """Compute response similarity across key fields."""
        # Zone agreement (discrete)
        zone1 = (1 if r1.get('C', 0.5) >= 0.7 else 0, 
                1 if r1.get('I', 0.5) >= 0.7 else 0)
        zone2 = (1 if r2.get('C', 0.5) >= 0.7 else 0,
                1 if r2.get('I', 0.5) >= 0.7 else 0)
        zone_match = 1.0 if zone1 == zone2 else 0.0

        # Continuous value correlation
        c_diff = abs(r1.get('C', 0.5) - r2.get('C', 0.5))
        i_diff = abs(r1.get('I', 0.5) - r2.get('I', 0.5))
        value_sim = 1.0 - (c_diff + i_diff) / 2

        # Missing info overlap
        m1 = set(r1.get('missing_info', []))
        m2 = set(r2.get('missing_info', []))
        if not m1 and not m2:
            info_sim = 1.0
        else:
            info_sim = len(m1 & m2) / len(m1 | m2) if (m1 | m2) else 0.0

        # Weighted combination
        return 0.4 * zone_match + 0.4 * value_sim + 0.2 * info_sim
```

#### 4.3.3 Cross-Validation with Retrieval Results

Final confidence is **constrained by agreement with Level 1 evidence**:

```python
def cross_validate(llm_result: Dict, level1: Dict) -> float:
    """Adjust LLM confidence based on retrieval agreement."""

    # Check I estimate consistency
    llm_i = llm_result.get('I', 0.5)
    level1_i = level1.get('I', 0.5)

    if abs(llm_i - level1_i) > 0.3:
        # Substantial disagreement with empirical retrieval
        agreement_penalty = 0.8
    else:
        agreement_penalty = 1.0

    base_confidence = llm_result.get('confidence', 0.5)

    return min(0.95, base_confidence * agreement_penalty)
```

### 4.4 Response Parsing and Extraction

#### 4.4.1 Regex-Based Field Extraction Fallback

```python
import re
import json

class ResponseParser:
    """Robust JSON extraction with regex fallback."""

    def parse(self, content: str) -> Dict:
        """Extract structured fields with multiple strategies."""

        # Strategy 1: Direct JSON parsing
        try:
            # Find JSON block if embedded in markdown
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Regex field extraction
        result = {}

        # Numeric field patterns
        patterns = {
            'C': r'"?C"?\s*[:=]\s*([0-9.]+)',
            'I': r'"?I"?\s*[:=]\s*([0-9.]+)',
            'confidence': r'(?:confidence|置信度)"?\s*[:=]\s*([0-9.]+)'
        }

        for field, pattern in patterns.items():
            match = re.search(pattern, content, re.I)
            result[field] = float(match.group(1)) if match else 0.5

        # List extraction for missing_info
        list_match = re.search(r'"missing_info"\s*:\s*\[(.*?)\]', content, re.DOTALL)
        if list_match:
            items = re.findall(r'"([^"]+)"', list_match.group(1))
            result['missing_info'] = items
        else:
            result['missing_info'] = []

        # Reasoning extraction
        reasoning_match = re.search(r'"reasoning"\s*:\s*"([^"]+)"', content)
        result['reasoning'] = reasoning_match.group(1) if reasoning_match else "Extracted via fallback"

        # Validate ranges
        for field in ['C', 'I', 'confidence']:
            result[field] = max(0.0, min(1.0, result.get(field, 0.5)))

        return result
```

#### 4.4.2 Structured Output Validation

```python
def validate_output(parsed: Dict) -> Tuple[bool, str]:
    """Validate extracted fields and return status."""
    required = ['C', 'I', 'confidence', 'missing_info', 'reasoning']

    missing = [f for f in required if f not in parsed]
    if missing:
        return False, f"Missing required fields: {missing}"

    for field in ['C', 'I', 'confidence']:
        if not isinstance(parsed[field], (int, float)):
            return False, f"Field {field} must be numeric"
        if not 0 <= parsed[field] <= 1:
            return False, f"Field {field} out of range [0,1]"

    if not isinstance(parsed['missing_info'], list):
        return False, "missing_info must be a list"

    # Consistency check: missing_info should be non-empty iff I < 0.5
    if parsed['I'] < 0.5 and not parsed['missing_info']:
        return False, "I < 0.5 requires non-empty missing_info"
    if parsed['I'] >= 0.5 and parsed['missing_info']:
        # Warning, not error—may indicate conservative assessment
        pass

    return True, "Valid"
```

#### 4.4.3 Final CI Discretization for ABCD Mapping

```python
def discretize_ci(C: float, I: float, threshold: float = 0.7) -> Tuple[int, int, str]:
    """Convert continuous CI to discrete zone."""
    C_d = 1 if C >= threshold else 0
    I_d = 1 if I >= threshold else 0

    zone_map = {(0,0): 'D', (0,1): 'C', (1,0): 'B', (1,1): 'A'}
    zone = zone_map[(C_d, I_d)]

    return C_d, I_d, zone
```

---

## 5. Ultimate Fallback Strategies

### 5.1 Forced Conservative Default (Zone B)

#### 5.1.1 Trigger Condition: `sigma < ALPHA` after Level 2

When all three processing tiers fail to achieve confident assessment, the system enters **maximum uncertainty mode**.

#### 5.1.2 Parameter Forcing: `C=1.0`, `I=0.0`

```python
def forced_conservative_fallback() -> Dict:
    """Maximum uncertainty routing to safest execution path."""
    return {
        'C': 1.0,           # Assume maximum complexity
        'I': 0.0,           # Assume information deficiency
        'zone': 'B',        # Parallel RAG with multi-source verification
        'strategy': 'CONSERVATIVE',
        'resource_allocation': {
            'parallel_rag_streams': 4,
            'verification_rounds': 2,
            'max_tokens': 2048,
            'require_citations': True
        },
        'note': 'MAX_UNCERTAINTY_FORCED_B',
        'escalation_reason': 'Insufficient confidence after full CI pipeline'
    }
```

#### 5.1.3 Resource Allocation: Parallel RAG + Multi-Source Verification

**Zone B's conservative strategy** activates:

- **4 parallel retrieval streams** (vector variants, structured, web if available)
- **2 verification rounds** with cross-attention checking
- **Explicit uncertainty acknowledgment** in responses ("Based on limited information...")

### 5.2 Query Rejection

#### 5.2.1 Ambiguity Detection Threshold

Rejection triggers when:

- Level 2 confidence `< 0.3`, **or**
- Dual-probe consistency `< 0.3`, **or**
- Parse failure after 3 retry attempts

#### 5.2.2 User Guidance for Query Refinement

```python
def reject_with_guidance(reason: str, context: Dict) -> Dict:
    """Constructive rejection with actionable feedback."""

    suggestions = []

    # Analyze failure mode for targeted guidance
    if context.get('level2', {}).get('parse_failures', 0) >= 3:
        suggestions.append("Rephrase your query with clearer structure")

    if context.get('level1', {}).get('conflict_detected'):
        suggestions.append("Specify which aspect you're most interested in")

    if context.get('level0', {}).get('features', [0])[4] > 3:  # High domain switches
        suggestions.append("Break into separate questions for each topic")

    return {
        'action': 'REJECT',
        'reason': reason,
        'suggestions': suggestions or ["Please rephrase with more specific details"],
        'retry_encouraged': True,
        'hitl_available': True  # Enterprise option
    }
```

### 5.3 Human-in-the-Loop (HITL)

#### 5.3.1 Enterprise-Grade Escalation Protocol

```python
def hitl_escalation(query: str, full_context: Dict) -> Dict:
    """Queue for human expert review with complete provenance."""

    return {
        'action': 'HITL_ESCALATION',
        'queue_priority': compute_priority(full_context),  # Business impact
        'sla_hours': 4,  # Service level agreement
        'context_package': {
            'original_query': query,
            'ci_pipeline_output': full_context,
            'retrieved_evidence': extract_evidence(full_context),
            'system_recommendation': 'UNCERTAIN'  # No confident automated decision
        },
        'user_communication': {
            'immediate': "Your query has been forwarded to our specialist team",
            'follow_up': "Expected response within 4 hours"
        }
    }
```

#### 5.3.2 Context Preservation for Human Review

The **context package** includes:

- Complete feature vectors and model outputs
- All retrieval results with similarity scores
- LLM probe responses and consistency analysis
- Timestamp and version metadata for reproducibility

---

## 6. ABCD Routing and Execution Mapping

### 6.1 Discrete Zone Classification

| Zone  | C    | I    | Characteristics        | Execution Strategy                                            | Token Budget | Latency Target |
| ----- | ---- | ---- | ---------------------- | ------------------------------------------------------------- | ------------ | -------------- |
| **A** | ≥0.7 | ≥0.7 | Complex, well-covered  | Structured adversarial generation with retrieval verification | 2048         | 2-3s           |
| **B** | ≥0.7 | <0.3 | Complex, under-covered | Parallel RAG streams with external completion                 | 3072         | 3-5s           |
| **C** | <0.3 | ≥0.7 | Simple, well-covered   | Direct chunk output, minimal generation                       | 512          | <500ms         |
| **D** | <0.3 | <0.3 | Simple, under-covered  | Precision single-point RAG with tight constraints             | 1024         | 1-2s           |

### 6.2 Soft Routing at Boundaries

#### 6.2.1 Continuous CI Blending (e.g., 60% A + 40% B)

```python
def soft_route(C: float, I: float) -> Dict[str, float]:
    """Compute zone membership probabilities for boundary blending."""

    # Distance to zone centers
    zones = {
        'A': (0.85, 0.85), 'B': (0.85, 0.15),
        'C': (0.15, 0.85), 'D': (0.15, 0.15)
    }

    # Inverse distance weighting
    weights = {}
    for z, (cz, iz) in zones.items():
        dist = np.sqrt((C - cz)**2 + (I - iz)**2)
        weights[z] = 1.0 / (dist + 0.01)  # Avoid division by zero

    # Normalize to probabilities
    total = sum(weights.values())
    return {z: w/total for z, w in weights.items()}
```

#### 6.2.2 Confidence-Weighted Resource Allocation

```python
def allocate_resources(zone_probs: Dict[str, float], 
                      base_confidence: float) -> Dict:
    """Compute blended resource allocation."""

    # Base allocations per zone
    base_allocations = {
        'A': {'tokens': 2048, 'retrieval_streams': 2, 'verification': True},
        'B': {'tokens': 3072, 'retrieval_streams': 4, 'verification': True},
        'C': {'tokens': 512, 'retrieval_streams': 1, 'verification': False},
        'D': {'tokens': 1024, 'retrieval_streams': 2, 'verification': True}
    }

    # Weighted blend
    blended = {}
    for resource in ['tokens', 'retrieval_streams']:
        blended[resource] = int(sum(
            zone_probs[z] * base_allocations[z][resource]
            for z in zone_probs
        ))

    # Confidence scaling: reduce allocation when uncertain
    confidence_factor = 0.5 + 0.5 * base_confidence  # [0.5, 1.0]
    blended['tokens'] = int(blended['tokens'] * confidence_factor)

    return blended
```

### 6.3 Execution Strategy Selection

#### 6.3.1 Internal Reasoning vs. External Retrieval Balance

| I Level       | Internal Reasoning  | External Retrieval     | Citation Requirement      |
| ------------- | ------------------- | ---------------------- | ------------------------- |
| I ≥ 0.7       | Primary             | Verification only      | Optional                  |
| 0.3 ≤ I < 0.7 | Guided by retrieval | Substantial            | Required                  |
| I < 0.3       | Minimal             | Primary with synthesis | Required, with gaps noted |

#### 6.3.2 Token Budget and Latency Constraints per Zone

Implemented through **dynamic generation parameters**:

```python
execution_params = {
    'zone_A': {'max_tokens': 2048, 'temperature': 0.3, 'top_p': 0.9},
    'zone_B': {'max_tokens': 3072, 'temperature': 0.4, 'top_p': 0.95},
    'zone_C': {'max_tokens': 512, 'temperature': 0.1, 'top_p': 0.85},
    'zone_D': {'max_tokens': 1024, 'temperature': 0.2, 'top_p': 0.9}
}
```

---

## 7. Key Implementation Libraries and Dependencies

### 7.1 Core ML and NLP Stack

| Library                   | Version | Purpose                     | Key APIs                                                                        |
| ------------------------- | ------- | --------------------------- | ------------------------------------------------------------------------------- |
| **xgboost**               | ≥2.0.0  | Level 0 dual classification | `XGBClassifier`, `Booster.predict_proba()`, `save_model()`/`load_model()`       |
| **sentence-transformers** | ≥2.2.0  | Semantic embeddings         | `SentenceTransformer.encode()`, `util.cos_sim()`                                |
| **faiss-cpu**             | ≥1.7.0  | Efficient vector search     | `IndexFlatIP`, `IndexIVFFlat`, `index.search()`, `write_index()`/`read_index()` |
| **jieba**                 | ≥0.42.1 | Chinese tokenization        | `cut()`, `cut_for_search()`, `load_userdict()`                                  |
| **numpy**                 | ≥1.24.0 | Numerical operations        | Array operations, entropy computation, vectorized scoring                       |
| **scipy**                 | ≥1.10.0 | Statistical functions       | `stats.entropy`, sparse matrix operations                                       |

### 7.2 LLM Integration

| Library     | Version | Purpose                        | Configuration                                                                |
| ----------- | ------- | ------------------------------ | ---------------------------------------------------------------------------- |
| **litellm** | ≥1.0.0  | Unified multi-provider LLM API | `completion()`, `acompletion()`, environment-based API keys, fallback chains |

**Key capabilities exploited**:

- **Provider abstraction**: Single interface for OpenAI, Anthropic, Azure, local models
- **Retry logic**: Exponential backoff with jitter for transient failures
- **Cost tracking**: Per-query attribution for optimization analysis
- **Response format**: Native JSON mode support where available

### 7.3 Structured Data and Calibration

| Library                          | Version   | Purpose                         | Application                                                  |
| -------------------------------- | --------- | ------------------------------- | ------------------------------------------------------------ |
| **sqlite3**                      | (builtin) | Lightweight SQL for prototyping | Schema-aware query generation, result metrics                |
| **sklearn** (IsotonicRegression) | ≥1.3.0    | Confidence calibration          | Source-specific score-to-probability mapping                 |
| **NetworkX**                     | ≥3.0      | Knowledge graph traversal       | Entity linking, path finding, centrality analysis (optional) |

---

## 8. Monitoring and Feedback Loop

### 8.1 Online Metrics

#### 8.1.1 Escalation Rate Pyramid: L0 > L1 > L2

| Metric              | Target                | Interpretation                         | Action Trigger                                               |
| ------------------- | --------------------- | -------------------------------------- | ------------------------------------------------------------ |
| L0 → L1 escape rate | 30-40%                | Moderate filtering, not too aggressive | >50%: Level 0 too conservative; <20%: potential over-routing |
| L1 → L2 escape rate | 20-30% of L1 arrivals | Effective retrieval verification       | >40%: retrieval quality issues or miscalibration             |
| L2 → Fallback rate  | <10% of L2 arrivals   | LLM arbitration generally sufficient   | >20%: prompt engineering or model selection review           |

**Pyramid health check**: L0_escape > L1_escape > L2_escape should hold; inversions indicate tier-specific degradation.

#### 8.1.2 Calibration Error (ECE < 0.05 Target)

**Expected Calibration Error** computed by binning predictions by confidence and measuring average absolute deviation from empirical accuracy:

```python
def compute_ece(confidences: np.ndarray, 
                accuracies: np.ndarray,
                n_bins: int = 10) -> float:
    """Compute Expected Calibration Error."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0

    for i in range(n_bins):
        in_bin = (confidences > bin_boundaries[i]) & (confidences <= bin_boundaries[i+1])
        prop_in_bin = in_bin.mean()

        if prop_in_bin > 0:
            avg_confidence = confidences[in_bin].mean()
            avg_accuracy = accuracies[in_bin].mean()
            ece += np.abs(avg_confidence - avg_accuracy) * prop_in_bin

    return ece
```

**Target ECE < 0.05** ensures confidence values are meaningfully interpretable for routing decisions.

#### 8.1.3 C Correction Rate at Level 1 (< 20% Threshold)

The fraction of queries where `|c1 - c0| > 0.1` indicates how often Level 0's complexity estimate is revised.

| Correction Rate | Interpretation                                             | Action                            |
| --------------- | ---------------------------------------------------------- | --------------------------------- |
| < 10%           | Level 0 well-calibrated, Level 1 appropriately subordinate | Maintain current configuration    |
| 10-20%          | Healthy refinement, some genuine ambiguity                 | Monitor for trends                |
| 20-30%          | Level 0 feature inadequacy or distribution shift           | Feature engineering review        |
| > 30%           | Fundamental Level 0 degradation                            | Retraining or architecture review |

### 8.2 Continuous Optimization

#### 8.2.1 Level 0: Feature Importance Monitoring, Threshold Tuning

- **Feature importance**: XGBoost `get_booster().get_score()` tracked weekly; features with <1% importance flagged for removal
- **Online threshold tuning**: Multi-armed bandit (Thompson sampling) experiments with α ∈ [0.6, 0.8] to optimize cost-quality Pareto frontier

#### 8.2.2 Level 1: Periodic Isotonic Regression Recalibration

- **Recalibration schedule**: Weekly for high-volume deployments, monthly for stable corpora
- **Trigger conditions**: ECE degradation >0.02, or >10% new document ingestion

#### 8.2.3 Level 2: Prompt A/B Testing, Probe Consistency Threshold Tuning

- **Prompt variants**: Test 2-3 alternative formulations monthly; select by calibration quality and consistency rates
- **Dual-probe threshold**: Grid search over [0.6, 0.9] to optimize escalation precision; current default 0.8 validated on held-out ambiguity set

---

This implementation manual provides comprehensive technical specifications for deploying the Confidence-Informed Architecture in production environments. The three-tier progressive escalation design—**zero-token XGBoost screening**, **hybrid retrieval verification**, and **LLM semantic refinement**—achieves **cost-precision-latency Pareto optimality** through conservative confidence aggregation, bounded complexity refinement, and multi-source Bayesian fusion with explicit conflict detection. The specified library stack (`xgboost`, `sentence-transformers`, `FAISS`, `jieba`, `litellm`) enables rapid deployment with proven production reliability.

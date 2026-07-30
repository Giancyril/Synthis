# AI Research Assistant

An intelligent, grounded AI Research Assistant pipeline powered by **Tavily API** (search & retrieval) and **Google Gemini API** (synthesis).

## Core Principle: Zero-Hallucination Grounding

Gemini **never** writes claims from its internal training knowledge alone. Every substantive assertion in the final report traces directly back to a Tavily-retrieved web source via inline `[S1]`, `[S2]` citation markers.

---

## Pipeline Architecture

```
User Topic
   │
   ▼
[1] Query Planning       — Gemini breaks topic into 3-6 distinct search queries
   │
   ▼
[2] Retrieval             — Tavily API runs queries & fetches web sources
   │
   ▼
[3] Source Filtering       — Deduplication, domain limits & relevance filtering
   │
   ▼
[4] Source Summarization   — Gemini summarizes each source grounded strictly in text
   │
   ▼
[5] Report Synthesis       — Gemini synthesizes takeaways + report sections with [S#] citations
   │
   ▼
[6] Citation Mapping        — Validates citations, strips invalid markers, flags ungrounded sections
   │
   ▼
Structured Output (.md / .json)
```

---

## Quick Start

### 1. Prerequisites & Environment Setup

Create a `.env` file in the project root with your API keys:

```env
TAVILY_API_KEY=tvly-your_key_here
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run a Research Query via CLI

```bash
python src/main.py "Quantum Computing in 2026" --output output/quantum.md
```

Export as JSON:

```bash
python src/main.py "Solid state battery technology progress" --output output/battery.json --format json
```

---

## Running Tests

Run the full unit test suite (15 offline unit tests using mocks):

```bash
pytest
```

To run end-to-end integration tests against real live APIs:

```bash
RUN_INTEGRATION_TESTS=1 pytest tests/test_integration.py
```

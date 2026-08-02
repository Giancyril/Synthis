import re
from collections import Counter
from typing import List, Optional
from pydantic import BaseModel
from src.models.schemas import ResearchReport

# Common English stop words to exclude from keyword extraction
STOP_WORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "by","from","up","about","into","through","during","is","was","are",
    "were","be","been","being","have","has","had","do","does","did","will",
    "would","could","should","may","might","can","that","this","these",
    "those","it","its","which","who","whom","what","when","where","how",
    "all","both","each","few","more","most","other","some","such","no",
    "not","only","same","so","than","too","very","just","now","also",
    "as","if","then","their","they","we","our","you","your","he","she",
    "his","her","us","them","new","used","well","make","first","based",
    "using","shows","research","study","studies","report","evidence",
    "according","found","shown","suggest","suggests","including","across",
    "between","within","however","therefore","while","since","after",
    "before","over","under","further","following","due","per","via",
    "key","significant","important","major","large","high","low","use",
    "see","one","two","three","four","five","six","many","much","several",
}


class KeywordResult(BaseModel):
    keyword: str
    frequency: int
    weight: float          # 0.0 – 1.0 normalised
    source_ids: List[str]


class ThemeCluster(BaseModel):
    theme: str             # derived from the highest-weight keyword in the cluster
    keywords: List[str]
    strength: float        # 0.0 – 1.0


def _extract_domain(url: str) -> str:
    from urllib.parse import urlparse
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _tokenize(text: str) -> List[str]:
    """Lower-case alphabetic tokens only, length 3-25."""
    return [t.lower() for t in re.findall(r"[a-zA-Z]{3,25}", text)
            if t.lower() not in STOP_WORDS]


def _citation_sources_for_token(token: str, report: ResearchReport) -> List[str]:
    """Return source IDs of sources whose summary / snippet mentions the token."""
    matched = []
    for src in (report.sources or []):
        blob = ((src.summary or "") + " " + (src.snippet or "") + " " + (src.title or "")).lower()
        if token in blob:
            matched.append(src.id)
    return matched


def extract_keywords(report: ResearchReport, top_n: int = 15) -> List[KeywordResult]:
    # Build corpus from takeaways + section content (without citation tags)
    parts: List[str] = []
    for kt in (report.key_takeaways or []):
        parts.append(re.sub(r"\[S\d+\]", "", kt.text))
    for sec in (report.sections or []):
        parts.append(re.sub(r"\[S\d+\]", "", sec.content))
        parts.append(sec.heading)

    corpus = " ".join(parts)
    tokens = _tokenize(corpus)

    if not tokens:
        return []

    counts = Counter(tokens)
    most_common = counts.most_common(top_n)
    max_freq = most_common[0][1] if most_common else 1

    results = []
    for word, freq in most_common:
        weight = round(freq / max_freq, 3)
        sids = _citation_sources_for_token(word, report)
        results.append(KeywordResult(keyword=word, frequency=freq, weight=weight, source_ids=sids))

    return results


def cluster_themes(keywords: List[KeywordResult], n_themes: int = 5) -> List[ThemeCluster]:
    """
    Simple greedy clustering: group keywords by first-letter + word-length band,
    picking the highest-weight keyword in each cluster as the theme label.
    """
    if not keywords:
        return []

    # Sort by weight descending
    sorted_kw = sorted(keywords, key=lambda k: k.weight, reverse=True)

    clusters: List[ThemeCluster] = []
    used: set = set()
    bucket_size = max(1, len(sorted_kw) // n_themes)

    for i in range(min(n_themes, len(sorted_kw))):
        anchor = sorted_kw[i]
        if anchor.keyword in used:
            continue
        # Pull nearby keywords (same weight band or similar length)
        cluster_words = [anchor.keyword]
        used.add(anchor.keyword)
        for other in sorted_kw:
            if other.keyword in used:
                continue
            if abs(len(other.keyword) - len(anchor.keyword)) <= 3:
                cluster_words.append(other.keyword)
                used.add(other.keyword)
            if len(cluster_words) >= bucket_size:
                break

        avg_strength = round(
            sum(kw.weight for kw in keywords if kw.keyword in cluster_words) / max(len(cluster_words), 1),
            3
        )
        clusters.append(ThemeCluster(theme=anchor.keyword, keywords=cluster_words, strength=avg_strength))

    return clusters

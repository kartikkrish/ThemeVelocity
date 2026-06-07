"""Lightweight candidate phrase extractor — no spaCy dependency.

Extracts bigrams and trigrams from plain text. These become the raw
term vocabulary fed into the discovery engine's velocity tracker.
"""
from __future__ import annotations

import re

_STOPWORDS = frozenset({
    # English function words
    'the','a','an','and','or','but','in','on','at','to','for','of','with',
    'by','from','is','are','was','were','be','been','have','has','had',
    'do','does','did','will','would','could','should','may','might','can',
    'this','that','these','those','it','its','as','not','no','we','they',
    'he','she','our','their','his','her','also','than','into','up','over',
    'all','one','two','three','new','old','said','such','about','which',
    'when','if','then','so','what','how','who','per','via','each','any',
    'some','just','very','too','more','most','many','much','few','less',
    'after','before','during','since','while','although','however',
    'yet','still','already','now','then','here','there','where',
    'both','either','neither','whether','though','because','since',
    # Finance / news boilerplate
    'company','market','year','quarter','percent','share','stock','price',
    'revenue','growth','report','fiscal','financial','business','product',
    'service','total','result','net','gross','use','used','using',
    'including','based','due','related','other','following','said',
    'says','according','reuters','bloomberg','inc','corp','llc','ltd',
    'sec','filing','form','pursuant','exhibit','item','section',
    'million','billion','thousand','hundred','first','second','third',
    'annual','quarterly','monthly','weekly','daily','period','date',
    'current','prior','previous','next','last','recent','future',
})

_TOKEN = re.compile(r"[a-zA-Z][a-zA-Z0-9\-]*")


def extract_phrases(text: str, max_ngram: int = 3) -> list[str]:
    """Extract candidate bigrams and trigrams from text.

    Returns unique lowercased phrases, trigrams before bigrams (more specific first).
    Only adjacent meaningful tokens (at most 1 stopword between them) qualify.
    """
    if not text:
        return []

    tokens = _TOKEN.findall(text.lower())
    # (original_position, word) — only meaningful, min-length-3 tokens
    meaningful = [
        (i, t) for i, t in enumerate(tokens)
        if t not in _STOPWORDS and len(t) >= 3 and not t.isdigit()
    ]

    trigrams: list[str] = []
    bigrams:  list[str] = []
    seen: set[str] = set()

    for j, (idx1, w1) in enumerate(meaningful):
        if j + 1 >= len(meaningful):
            break
        idx2, w2 = meaningful[j + 1]
        # bigram: positions within 2 (one stopword gap allowed)
        if idx2 - idx1 <= 2:
            bg = f"{w1} {w2}"
            if bg not in seen:
                seen.add(bg)
                bigrams.append(bg)
            # trigram
            if max_ngram >= 3 and j + 2 < len(meaningful):
                idx3, w3 = meaningful[j + 2]
                if idx3 - idx1 <= 4:
                    tg = f"{w1} {w2} {w3}"
                    if tg not in seen:
                        seen.add(tg)
                        trigrams.append(tg)

    return trigrams + bigrams

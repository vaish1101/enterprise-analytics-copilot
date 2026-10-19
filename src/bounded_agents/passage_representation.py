"""Application-owned views; never change canonical content or evidence identity."""
import re


def representation(record, *, budget):
    """A contiguous prefix of complete sentences, never a partial number/word.

    Oversized indivisible passages are omitted, not silently sliced. Consumers
    receive explicit coverage metadata and can fail closed if full context is
    required. The registry remains the sole owner of the complete passage.
    """
    if budget < 1:
        raise ValueError('Positive passage budget required')
    text = record.text
    end = len(text)
    if end > budget:
        boundaries = [m.end() for m in re.finditer(r'[.!?](?=\s|$)', text)
                      if m.end() <= budget]
        end = max(boundaries, default=0)
    return {'id': record.evidence_unit_id, 'text': text[:end],
            'shortened': end < len(text), 'canonical_characters': len(text),
            'start': 0, 'end': end, 'source_id': record.source_id,
            'content_hash': record.content_hash}

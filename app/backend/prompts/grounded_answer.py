"""Grounded answer prompt templates with strict evidence rules."""

GROUNDED_ANSWER_SYSTEM_PROMPT = """\
You are a knowledge base assistant that answers questions strictly from \
the provided evidence. You must follow these rules:

1. Answer ONLY from the provided evidence. Do not use any external knowledge.
2. Cite your sources using [1], [2], [3] notation matching the evidence items.
3. If the evidence does not contain enough information, say so explicitly.
4. Do not invent, guess, or extrapolate facts not present in the evidence.
5. Distinguish between explicit statements in the evidence and your own \
inferences. Mark inferences with "Based on the evidence, it appears..."
6. If evidence items conflict, acknowledge the conflict and present both sides.
7. Never claim confidence that the evidence does not support.
8. If evidence is from OCR or low-confidence extraction, mention that the \
text may contain errors.
"""

GROUNDED_ANSWER_USER_TEMPLATE = """\
## Question
{query}

## Evidence
{evidence_text}

## Instructions
Answer the question using ONLY the evidence above. Cite each claim with \
the corresponding evidence number [N]. If the evidence is insufficient to \
answer the question fully, state what you can answer and what remains \
uncertain.

Format your answer with clear citations like this:
- Make a claim [1]
- Support it with another piece of evidence [2]

If you cannot answer based on the available evidence, respond:
"Based on the available evidence, I cannot provide a complete answer to \
this question."
"""

ABSTENTION_RESPONSE = (
    "Based on the available evidence, I cannot provide a complete answer "
    "to this question. The retrieved evidence does not contain sufficient "
    "information to address your query confidently."
)


def build_evidence_text(items: list[dict]) -> str:
    """Build the evidence section for the prompt.

    Args:
        items: List of evidence items, each with text_content, title,
               section_path, page_number, modality, confidence.

    Returns:
        Formatted evidence text with numbered references.
    """
    parts = []
    for i, item in enumerate(items, 1):
        source_parts = [f"**Source {i}:**"]
        if item.get("document_title"):
            source_parts.append(item["document_title"])
        if item.get("section_path"):
            source_parts.append(f"Section: {item['section_path']}")
        if item.get("page_number") is not None:
            source_parts.append(f"Page {item['page_number']}")
        if item.get("modality") and item["modality"] != "text":
            source_parts.append(f"({item['modality']})")
        if item.get("confidence") and item["confidence"] < 1.0:
            source_parts.append(f"[confidence: {item['confidence']:.0%}]")

        header = " ".join(source_parts)
        content = item.get("text_content", "")
        parts.append(f"{header}\n{content}")

    return "\n\n---\n\n".join(parts)
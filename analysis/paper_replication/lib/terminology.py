"""Consistent terminology at the paper's LaTeX rendering boundary."""

from __future__ import annotations

import re


def normalize_latex_terminology(text: str) -> str:
    """Normalize prose without changing identifiers or verbatim replication code."""
    protected: list[str] = []

    def hold(match: re.Match[str]) -> str:
        protected.append(match.group())
        return f"@@PAPER_LITERAL_{len(protected) - 1}@@"

    text = re.sub(
        r"\\begin\{(Verbatim|verbatim|lstlisting|minted)\}.*?\\end\{\1\}"
        r"|\\(?:input|includegraphics|label|ref|citep|citet|url|texttt)"
        r"(?:\[[^\]]*\])?\{[^}]*\}",
        hold,
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"\b(?:synthetic[- ](?:difference-in-differences|DID)|SDID)\b",
        "SDiD", text, flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bcontinuous[- ](?:difference-in-differences|DID)\b",
        "CDiD", text, flags=re.IGNORECASE,
    )
    text = re.sub(r"\b(?:ContDID|ContDiD|cont[- ]DID|CDID|CDiD)\b", "CDiD", text)
    text = re.sub(r"\b(?:DID|DiD|diD)\b", "DiD", text)
    text = re.sub(r"\bUS\b", "U.S.", text)
    text = re.sub(r"\bfixed[- ]effects\b", "FE", text, flags=re.IGNORECASE)
    for index, literal in enumerate(protected):
        text = text.replace(f"@@PAPER_LITERAL_{index}@@", literal)
    return text

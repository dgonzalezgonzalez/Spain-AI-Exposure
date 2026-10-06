from unittest import TestCase

from analysis.paper_replication.lib.terminology import normalize_latex_terminology


class PaperTerminologyTests(TestCase):
    def test_prose_normalization_preserves_numbers_and_english_verbs(self):
        text = "US payroll; DID; Synthetic DiD; continuous-DiD; ContDID; did not change 0.1169."
        self.assertEqual(
            normalize_latex_terminology(text),
            "U.S. payroll; DiD; SDiD; CDiD; CDiD; did not change 0.1169.",
        )

    def test_literal_code_paths_and_cross_references_are_preserved(self):
        text = (
            r"\input{US/ContDID.tex} \label{SDID} \texttt{contdid} "
            r"\url{https://example.org/US/DID} "
            r"\begin{Verbatim}US SDID did not change\end{Verbatim}"
        )
        self.assertEqual(normalize_latex_terminology(text), text)

    def test_repeated_rendering_is_stable(self):
        text = r"SDiD and CDiD; U.S.; \(\widehat{\tau}_{SDID}\)."
        rendered = normalize_latex_terminology(text)
        self.assertEqual(rendered, normalize_latex_terminology(rendered))
        self.assertIn(r"\widehat{\tau}_{SDiD}", rendered)

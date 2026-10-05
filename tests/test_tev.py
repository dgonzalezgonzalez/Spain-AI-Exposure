from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import pandas as pd

from src.tev import (MODEL, TevClient, build_hierarchy, joint_probabilities,
                     pack_requests, string_question)
from src.jev_questions import tier_question


class TevTests(unittest.TestCase):
    def test_exhaustive_hierarchy_preserves_probability_mass_and_singletons(self):
        codes = [f"11-{1000+i:04d}" for i in range(31)] + ["13-2011"]
        catalogue = pd.DataFrame({"occ_code": codes, "title": codes,
                                  "onet_description": ["Duties"] * len(codes),
                                  "observed_exposure": [0.2] * len(codes)})
        nodes, paths = build_hierarchy(catalogue)
        self.assertEqual(set(paths), set(codes))
        self.assertTrue(all(2 <= len(node["criteria"]) <= 24 for node in nodes.values()))
        answers = {}
        for key, node in nodes.items():
            probabilities = {option: 1 / len(node["criteria"]) for option in node["criteria"]}
            answers[key] = {"type": "choice", "choice": next(iter(probabilities)),
                            "confidence": 0, "probabilities": probabilities}
        result = joint_probabilities(answers, nodes, paths)
        self.assertAlmostEqual(sum(result.values()), 1)
        self.assertAlmostEqual(result["13-2011"], 0.5)
        self.assertAlmostEqual(sum(result[code] for code in codes[:-1]), 0.5)

    def test_cache_pins_candidate_order_and_offline_replays_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            client = TevClient(cache, {"digest": "fixed"})
            question = {"type": "choice", "instructions": "Pick", "criteria": {"a": "A", "b": "B"}}
            payload = {"model": MODEL, "state": "State", "questions": {"q": question}}
            result = {"model": MODEL, "answers": {"q": {
                "type": "choice", "choice": "a", "probabilities": {"a": 0.7, "b": 0.3}, "confidence": 0.1}},
                "usage": {"input_tokens": 5, "output_tokens": 1}}
            response = Mock(status_code=200)
            response.json.return_value = result
            client.session.post = Mock(return_value=response)
            _, first_key, cached = client.evaluate(payload)
            self.assertFalse(cached)
            offline = TevClient(cache, {"digest": "fixed"}, offline=True)
            offline.session.post = Mock(side_effect=AssertionError("Network used"))
            self.assertEqual(offline.evaluate(payload), (result, first_key, True))
            reversed_payload = {**payload, "questions": {"q": {**question, "criteria": {"b": "B", "a": "A"}}}}
            with self.assertRaises(FileNotFoundError):
                offline.evaluate(reversed_payload)
            changed = TevClient(cache, {"digest": "different"}, offline=True)
            with self.assertRaises(FileNotFoundError):
                changed.evaluate(payload)

    def test_structured_tiers_are_serialized_without_losing_definitions(self):
        question = string_question(tier_question())
        self.assertTrue(all(isinstance(value, str) for value in question["criteria"].values()))
        self.assertIn("central source of value", question["criteria"]["3"])
        batches = pack_requests({"occupation": "test"}, {"tier": question})
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0]["questions"]["tier"], question)

    def test_oversized_question_after_a_full_batch_is_never_silently_accepted(self):
        small = {"type": "choice", "instructions": "Pick", "criteria": {"a": "A", "b": "B"}}
        huge = {**small, "instructions": "x" * 60001}
        with self.assertRaisesRegex(ValueError, "no truncation"):
            pack_requests({"occupation": "test"}, {"small": small, "huge": huge})


if __name__ == "__main__":
    unittest.main()

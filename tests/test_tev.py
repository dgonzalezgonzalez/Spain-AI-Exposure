import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "code"))
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import pandas as pd

from lib.tev import (MODEL, TevClient,
                     pack_requests, string_question, validate_response)
from lib.jev_questions import tier_question


class TevTests(unittest.TestCase):
    def test_noul_rejects_invalid_probabilities_and_missing_answers(self):
        payload = {'model': MODEL, 'state': 'test', 'questions': {'wrong': {
            'type': 'noul', 'instructions': 'Wrong match?', 'criteria': {'true': 'Wrong', 'false': 'Valid'}}}}
        response = {'model': MODEL, 'answers': {'wrong': {'type': 'noul', 'noul': .5}},
                    'usage': {'input_tokens': 1, 'output_tokens': 1}}
        validate_response(response, payload)
        for invalid in (True, -0.1, 1.1, float('nan'), None):
            with self.assertRaises(ValueError):
                validate_response({**response, 'answers': {'wrong': {'type': 'noul', 'noul': invalid}}}, payload)
        with self.assertRaises(ValueError):
            validate_response({**response, 'answers': {}}, payload)

    def test_shortlist_production_shape_is_complete_and_isolates_direct_score(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code/acquisition'))
        import run_tev
        spanish, catalogue, _, screens, candidates = run_tev.sources()
        batches = run_tev.payloads_for(
            spanish.iloc[0].to_dict(), screens, catalogue, candidates)
        self.assertEqual(set(batches[0]['questions']), {'tier', 'direct_exposure'})
        self.assertEqual(set(batches[0]['state']), {'occupation'})
        self.assertNotIn('proposed_us_match', batches[0]['state'])
        self.assertEqual(set(batches[1]['questions']['match']['criteria']), set(candidates[str(spanish.iloc[0].CNO4)]))
        self.assertEqual(len(batches), 2)
        self.assertEqual(sum(len(p['questions']) for p in batches), 5)
        self.assertEqual(len(batches[1]['questions']['match']['criteria']), 24)

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

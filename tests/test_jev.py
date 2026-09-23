import json
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile
from unittest import TestCase
from unittest.mock import Mock, patch

import pandas as pd

from src.jev import (
    JevClient, archive_cache, choice_label_disagrees, choice_probabilities, combine_probabilities,
    direct_exposure_record, direct_exposure_state, fingerprint, matching_questions,
    merge_sepe_file, pack_questions, restore_cache_archive, score_probabilities,
    summarize, validate_catalogue,
)
from src.jev_questions import direct_exposure_question


def choice(probabilities, confidence=0.8):
    return {"type": "choice", "choice": max(probabilities, key=probabilities.get),
            "probabilities": probabilities, "confidence": confidence}


def catalogue():
    return pd.DataFrame({
        "occ_code": ["11-1011", "11-1021", "13-2011"],
        "title": ["Chief executives", "Operations managers", "Accountants"],
        "onet_description": ["Lead organizations", "Manage operations", "Prepare accounts"],
        "observed_exposure": [0.1, 0.9, 0.4],
    })


def answers():
    return {"soc_group": choice({"11": 0.6, "13": 0.4}),
            "soc_11": choice({"11-1011": 0.51, "11-1021": 0.49}),
            "soc_13": choice({"13-2011": 1.0}),
            "tier": choice({"1": 0.1, "2": 0.2, "3": 0.7})}


class JevTests(TestCase):
    def test_global_argmax_not_greedy_group_and_full_weighted_average(self):
        record, distribution = summarize({"CNO4": "1211", "occupation_title": "Finance"}, answers(), catalogue())
        # Winning leaf belongs to the SECOND most probable group.
        self.assertEqual(record["jev_matched_occ_code"], "13-2011")
        self.assertAlmostEqual(record["observed_exposure_jev_nearest"], 0.4)
        self.assertAlmostEqual(record["observed_exposure_jev_weighted"], 0.306 * 0.1 + 0.294 * 0.9 + 0.4 * 0.4)
        self.assertEqual(len(distribution), 3)
        self.assertAlmostEqual(sum(distribution.values()), 1)
        self.assertEqual(record["jev_tier"], 3)

    def test_zero_probability_groups_still_require_every_leaf(self):
        data = answers()
        data["soc_group"] = choice({"11": 1.0, "13": 0.0})
        self.assertEqual(combine_probabilities(data, catalogue())["13-2011"], 0)
        del data["soc_13"]
        with self.assertRaises(KeyError):
            combine_probabilities(data, catalogue())

    def test_ties_use_lexicographic_code(self):
        data = answers()
        data["soc_group"] = choice({"11": 1.0, "13": 0.0})
        data["soc_11"] = choice({"11-1021": 0.5, "11-1011": 0.5})
        record, _ = summarize({"CNO4": "11", "occupation_title": "Military"}, data, catalogue())
        self.assertEqual(record["jev_matched_occ_code"], "11-1011")
        self.assertTrue(record["jev_no_military_category"])
        self.assertTrue(record["jev_match_review"])

    def test_reject_invalid_or_incomplete_probabilities(self):
        for probabilities in ({"a": 0.8}, {"a": 0.5, "b": 0.4}, {"a": 1.1, "b": -0.1},
                              {"a": float("nan"), "b": 0.0}, {"a": True, "b": 0.0}):
            with self.subTest(probabilities=probabilities), self.assertRaises(ValueError):
                choice_probabilities(choice(probabilities), ["a", "b"])
        bad = choice({"a": 0.8, "b": 0.2})
        bad["choice"] = "absent"
        with self.assertRaises(ValueError):
            choice_probabilities(bad, ["a", "b"])

    def test_api_label_disagreement_keeps_probabilities_and_flags_review(self):
        data = answers()
        data["tier"]["choice"] = "2"
        self.assertTrue(choice_label_disagrees(data["tier"]))
        record, _ = summarize({"CNO4": "1211", "occupation_title": "Finance"}, data, catalogue())
        self.assertEqual(record["jev_tier"], 3)
        self.assertEqual(record["jev_api_label_disagreement_count"], 1)
        self.assertTrue(record["jev_tier_api_label_disagreement"])
        self.assertTrue(record["jev_tier_review"])

    def test_bounded_hundredth_rounding_is_normalized(self):
        normalized = choice_probabilities(choice({"a": 0.47, "b": 0.47, "c": 0.05}), ["a", "b", "c"])
        self.assertAlmostEqual(normalized["a"], 0.47 / 0.99)
        self.assertAlmostEqual(sum(normalized.values()), 1)
        with self.assertRaises(ValueError):
            choice_probabilities(choice({"a": 0.4731, "b": 0.4731, "c": 0.05}), ["a", "b", "c"])

    def test_direct_score_measures_degree_and_preserves_raw_distribution(self):
        levels = direct_exposure_question()["criteria"]
        answer = {"type": "score", "score": 6.75, "confidence": 0.6,
                  "legend": {str(index): level for index, level in enumerate(levels)},
                  "probabilities": {str(index): (0.25 if index == 0 else 0.75 if index == 9 else 0.0)
                                    for index in range(10)}}
        self.assertAlmostEqual(sum(score_probabilities(answer, levels).values()), 1)
        record, distribution = direct_exposure_record("0011", answer)
        self.assertAlmostEqual(record["observed_exposure_jev_direct"], 0.75)
        self.assertEqual(record["jev_direct_raw_score"], 6.75)
        self.assertEqual(distribution["level_0"], 0.25)
        self.assertEqual(distribution["level_9"], 0.75)
        answer["probabilities"]["9"] = 0.65
        with self.assertRaises(ValueError):
            score_probabilities(answer, levels)

    def test_direct_prompt_omits_us_outcomes_matches_and_tier(self):
        row = {"CNO4": "0011", "occupation_title": "Armed forces officers",
               "cno_structured_text_es": "Lead military units"}
        state = direct_exposure_state(row)
        self.assertEqual(state["occupation"]["country"], "Spain")
        self.assertEqual(state["occupation"]["cno4"], "0011")
        payload = pack_questions(state, {"direct_exposure": direct_exposure_question()})[0]
        self.assertEqual(list(payload["questions"]), ["direct_exposure"])
        self.assertNotIn("observed_exposure", state["occupation"])

    def test_catalogue_rejects_missing_descriptions_duplicate_codes_and_exposure(self):
        for column, value in (("onet_description", None), ("observed_exposure", float("inf")), ("title", "")):
            data = catalogue()
            data.loc[0, column] = value
            with self.subTest(column=column), self.assertRaises(ValueError):
                validate_catalogue(data)
        with self.assertRaises(ValueError):
            validate_catalogue(pd.concat([catalogue(), catalogue()]))

    def test_questions_do_not_leak_exposure_and_cover_all_categories(self):
        first = matching_questions(catalogue())
        changed = catalogue()
        changed["observed_exposure"] = 0.99
        self.assertEqual(first, matching_questions(changed))
        leaves = {code for key, q in first.items() if key.startswith("soc_") and key != "soc_group" for code in q["criteria"]}
        self.assertEqual(leaves, set(catalogue().occ_code))

    def test_packing_keeps_every_question_and_rejects_oversized_input(self):
        questions = matching_questions(catalogue())
        with patch("src.jev.MAX_REQUEST_BYTES", 5000):
            batches = pack_questions({}, questions)
        self.assertGreater(len(batches), 1)
        self.assertEqual({key for batch in batches for key in batch["questions"]}, set(questions))
        with self.assertRaises(ValueError):
            pack_questions({"text": "x" * 31_000}, questions)

    def test_request_fingerprint_changes_for_model_description_or_rubric(self):
        payload = pack_questions({}, matching_questions(catalogue()))[0]
        baseline = fingerprint(payload)
        for key, value in (("model", "other-model"), ("state", {"description": "different"}),
                           ("questions", {"different": "rubric"})):
            altered = {**payload, key: value}
            self.assertNotEqual(baseline, fingerprint(altered))

    def test_client_caches_valid_response_offline_needs_no_key(self):
        payload = {"model": "jev-1.13.0", "state": {}, "questions": {"q": {"type": "choice", "criteria": {"a": "A", "b": "B"}}}}
        result = {"model": "jev-1.13.0", "answers": {"q": choice({"a": 0.8, "b": 0.2})},
                  "usage": {"input_tokens": 100, "output_tokens": 20}}
        session = Mock()
        session.post.return_value = Mock(status_code=200, json=lambda: result)
        with tempfile.TemporaryDirectory() as directory:
            client = JevClient(Path(directory), session=session)
            with patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-secret"}):
                self.assertFalse(client.evaluate(payload)[2])
            with patch.dict(os.environ, {}, clear=True):
                offline = JevClient(Path(directory), offline=True, session=session)
                self.assertTrue(offline.evaluate(payload)[2])
                with self.assertRaises(FileNotFoundError):
                    offline.evaluate({**payload, "state": "new"})
            self.assertEqual(session.post.call_count, 1)
            saved = next(Path(directory).glob("*.json")).read_text()
            self.assertNotIn("test-secret", saved)

    def test_tracked_archive_restores_raw_response_for_offline_replay(self):
        payload = {"model": "jev-1.13.0", "state": {}, "questions": {"q": {"type": "choice", "criteria": {"a": "A", "b": "B"}}}}
        response = {"model": "jev-1.13.0", "answers": {"q": choice({"a": 0.8, "b": 0.2})},
                    "usage": {"input_tokens": 100, "output_tokens": 20}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / "source", root / "restored"
            source.mkdir()
            key = fingerprint(payload)
            (source / f"{key}.json").write_text(json.dumps({"request_sha256": key, "response": response}))
            archive = root / "cache.zip"
            archive_cache(source, [key], archive)
            self.assertEqual(restore_cache_archive(archive, destination), 1)
            self.assertEqual(restore_cache_archive(archive, destination), 0)
            self.assertEqual(JevClient(destination, offline=True).evaluate(payload)[0], response)
            rebuilt = root / "rebuilt.zip"
            archive_cache(destination, [key], rebuilt)
            self.assertEqual(archive.read_bytes(), rebuilt.read_bytes())
            bad_archive = root / "bad.zip"
            with ZipFile(bad_archive, "w") as file:
                file.writestr("../escape.json", "{}")
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                restore_cache_archive(bad_archive, destination)

    def test_client_retries_rate_limit_but_not_auth_failure(self):
        session = Mock()
        session.post.return_value = Mock(status_code=401)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"TYPESAFE_API_KEY": "secret"}):
            with self.assertRaisesRegex(RuntimeError, "HTTP 401"):
                JevClient(Path(directory), session=session).evaluate({"state": {}})
            self.assertEqual(session.post.call_count, 1)
            session.post.reset_mock()
            session.post.return_value = Mock(status_code=429, headers={"Retry-After": "0"})
            with patch("src.jev.time.sleep"), self.assertRaisesRegex(RuntimeError, "after retries"):
                JevClient(Path(directory), session=session, attempts=2).evaluate({"state": {}})
            self.assertEqual(session.post.call_count, 2)

    def test_sepe_merge_preserves_grain_and_leading_zeros(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination = Path(directory) / "in.csv", Path(directory) / "out.csv"
            pd.DataFrame({"cno4": ["0011", "1211", "1211"], "period": ["2020-01"] * 3,
                          "dimension": ["total", "age", "total"]}).to_csv(source, index=False)
            estimates = pd.DataFrame({"cno4": ["0011", "1211"], "occupation_title": ["Military", "Finance"],
                                      "observed_exposure_jev_nearest": [0.2, 0.5]})
            stats = merge_sepe_file(source, destination, estimates)
            self.assertEqual(stats, {"rows": 3, "cno4_count": 2})
            merged = pd.read_csv(destination, dtype={"cno4": str})
            self.assertEqual(merged.cno4.tolist(), ["0011", "1211", "1211"])
            self.assertEqual(merged.observed_exposure_jev_nearest.tolist(), [0.2, 0.5, 0.5])
            with self.assertRaises(ValueError):
                merge_sepe_file(source, destination, estimates.iloc[:1])
            self.assertEqual(len(pd.read_csv(destination)), 3)
            with self.assertRaises(ValueError):
                merge_sepe_file(source, source, estimates)

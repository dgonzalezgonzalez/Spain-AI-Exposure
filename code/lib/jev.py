"""Exhaustive SOC hierarchy, probability-weighted exposure, and Jev API caching."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pandas as pd
import requests

from .jev_questions import (
    DIRECT_REVIEW_MIN_CONFIDENCE, MATCH_INSTRUCTIONS, MODEL, REVIEW_MIN_MARGIN,
    REVIEW_MIN_PROBABILITY, SOC_GROUPS, direct_exposure_question, tier_question,
)

API_URL = "https://api.typesafe.ai/v1/systemone"
# UTF-8 bytes are a deliberately conservative token upper bound for these texts.
MAX_STATE_QUESTION_BYTES = 31_000
MAX_REQUEST_BYTES = 60_000


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def archive_cache(cache_dir: Path, request_hashes: list[str], target: Path) -> None:
    """Bundle every successful raw response used by published results."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for key in sorted(set(request_hashes)):
                if not re.fullmatch(r"[0-9a-f]{64}", key):
                    raise ValueError("Invalid Jev request hash")
                source = cache_dir / f"{key}.json"
                if not source.is_file():
                    raise FileNotFoundError(f"Missing raw Jev response for {key}")
                record = json.loads(source.read_text(encoding="utf-8"))
                if record.get("request_sha256") != key or "response" not in record:
                    raise ValueError(f"Invalid raw Jev response for {key}")
                info = ZipInfo(f"{key}.json", date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, source.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
        temporary.replace(target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def restore_cache_archive(archive_path: Path, cache_dir: Path) -> int:
    """Restore only content-addressed JSON; reject unsafe or duplicate ZIP names."""
    if not archive_path.is_file():
        return 0
    count = 0
    cache_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate cache archive members")
        for name in names:
            if not re.fullmatch(r"[0-9a-f]{64}\.json", name):
                raise ValueError(f"Unsafe cache archive member: {name}")
            target = cache_dir / name
            if target.exists():
                continue
            data = archive.read(name)
            record = json.loads(data)
            if record.get("request_sha256") != name[:-5] or "response" not in record:
                raise ValueError(f"Invalid archived Jev response for {name}")
            target.write_bytes(data)
            count += 1
    return count


def validate_catalogue(frame: pd.DataFrame) -> pd.DataFrame:
    required = ["occ_code", "title", "onet_description", "observed_exposure"]
    if not set(required).issubset(frame):
        raise ValueError(f"US catalogue requires {required}")
    out = frame[required].copy()
    if out.isna().any().any():
        raise ValueError("US catalogue contains missing titles, descriptions, codes or exposures")
    for column in required[:-1]:
        out[column] = out[column].astype(str).str.strip()
        if out[column].eq("").any():
            raise ValueError(f"Empty US {column}")
    if out.occ_code.duplicated().any():
        raise ValueError("US occupation codes must be unique")
    if not out.occ_code.str.fullmatch(r"\d{2}-\d{4}(?:\.\d{2})?").all():
        raise ValueError("Invalid US occupation code")
    out["observed_exposure"] = pd.to_numeric(out.observed_exposure, errors="raise")
    if not out.observed_exposure.between(0, 1).all():
        raise ValueError("US observed exposure must be finite and in [0, 1]")
    unknown = set(out.occ_code.str[:2]) - SOC_GROUPS.keys()
    if unknown:
        raise ValueError(f"Unknown SOC major groups: {sorted(unknown)}")
    return out.sort_values("occ_code").reset_index(drop=True)


def occupation_state(row: dict) -> dict:
    code = str(row["CNO4"]).zfill(4)
    title = row["occupation_title"]
    description = row["cno_structured_text_es"]
    if not re.fullmatch(r"\d{4}", code) or not isinstance(title, str) or not title.strip():
        raise ValueError("Invalid CNO4 code/title")
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f"Missing Spanish description for {code}")
    return {"occupation": {"cno4": code, "title": title, "description_and_tasks": description}}


def matching_questions(catalogue: pd.DataFrame) -> dict:
    """One major-group Choice and every conditional leaf Choice, with no pruning."""
    root = {}
    leaves = {}
    for group, rows in catalogue.groupby(catalogue.occ_code.str[:2], sort=True):
        root[group] = SOC_GROUPS[group]
        criteria = {
            row.occ_code: {"title": row.title, "description": row.onet_description}
            for row in rows.itertuples(index=False)
        }
        if len(criteria) > 255:
            raise ValueError(f"SOC {group} exceeds Jev's 255-option limit")
        leaves[f"soc_{group}"] = {
            "type": "choice",
            "instructions": (
                MATCH_INSTRUCTIONS + f" Conditional on its best US equivalent belonging "
                f"to SOC major group {group} ({SOC_GROUPS[group]}), which occupation "
                "within this group is the closest equivalent? This premise applies "
                "even if another major group would be a better overall fit."
            ),
            "criteria": criteria,
        }
    questions = {
        "soc_group": {
            "type": "choice",
            "instructions": MATCH_INSTRUCTIONS + " Which SOC major group contains its closest available US equivalent?",
            "criteria": root,
        },
        "tier": tier_question(),
    }
    questions.update(leaves)
    return questions


def pack_questions(state: dict, questions: dict, model: str = MODEL) -> list[dict]:
    """Batch independent questions without truncating descriptions or choices."""
    batches = []
    current = {}
    for name, question in questions.items():
        single = {"model": model, "state": state, "questions": {name: question}}
        if len(canonical_json(single).encode("utf-8")) > MAX_STATE_QUESTION_BYTES:
            raise ValueError(f"Question {name} exceeds conservative context budget; no text was truncated")
        candidate = {"model": model, "state": state, "questions": {**current, name: question}}
        if current and len(canonical_json(candidate).encode("utf-8")) > MAX_REQUEST_BYTES:
            batches.append({"model": model, "state": state, "questions": current})
            current = {}
        current[name] = question
    if current:
        batches.append({"model": model, "state": state, "questions": current})
    return batches


def choice_probabilities(answer: dict, options) -> dict[str, float]:
    expected = set(options)
    probabilities = answer.get("probabilities", {})
    if answer.get("type") != "choice" or set(probabilities) != expected:
        raise ValueError("Choice response must contain every expected category exactly once")
    if not expected:
        raise ValueError("Empty Choice")
    result = {}
    for key, value in probabilities.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Invalid category probability")
        result[key] = float(value)
    total = math.fsum(result.values())
    # Live Jev 1.13 serializes probabilities at 0.01 resolution. Permit only
    # small drift consistent with that rounding, while requiring EVERY option.
    rounded_to_hundredths = all(abs(value * 100 - round(value * 100)) < 1e-8 for value in result.values())
    tolerance = min(0.05, 0.005 * len(result)) if rounded_to_hundredths else 1e-5
    if total <= 0 or abs(total - 1) > tolerance + 1e-10:
        raise ValueError(f"Probabilities do not sum to one: {total}")
    confidence = answer.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("Invalid Choice confidence")
    selected = answer.get("choice")
    if selected not in expected:
        raise ValueError("Selected category is absent from expected options")
    # Correct bounded API rounding, never omitted categories or arbitrary scores.
    return {key: value / total for key, value in result.items()}


def choice_label_disagrees(answer: dict) -> bool:
    probabilities = answer["probabilities"]
    return probabilities[answer["choice"]] < max(probabilities.values()) - 1e-10


def score_probabilities(answer: dict, levels: list) -> dict[str, float]:
    """Return validated, normalized level probabilities; retain raw Score in cache."""
    expected = {str(index) for index in range(len(levels))}
    probabilities = answer.get("probabilities", {})
    if answer.get("type") != "score" or set(probabilities) != expected:
        raise ValueError("Score response must contain every expected level exactly once")
    if not 2 <= len(levels) <= 10:
        raise ValueError("Jev Score requires two to ten levels")
    result = {}
    for key, value in probabilities.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Invalid Score level probability")
        result[key] = float(value)
    total = math.fsum(result.values())
    rounded_to_hundredths = all(abs(value * 100 - round(value * 100)) < 1e-8 for value in result.values())
    tolerance = min(0.05, 0.005 * len(result)) if rounded_to_hundredths else 1e-5
    if total <= 0 or abs(total - 1) > tolerance + 1e-10:
        raise ValueError(f"Score probabilities do not sum to one: {total}")
    score = answer.get("score")
    confidence = answer.get("confidence")
    for name, value, maximum in (("score", score, len(levels) - 1), ("confidence", confidence, 1)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= maximum:
            raise ValueError(f"Invalid Score {name}")
    legend = answer.get("legend")
    if not isinstance(legend, dict) or set(legend) != expected or any(legend[str(i)] != level for i, level in enumerate(levels)):
        raise ValueError("Score legend differs from requested levels")
    return {key: value / total for key, value in result.items()}


def validate_response(response: dict, payload: dict) -> None:
    if response.get("model") != payload["model"]:
        raise ValueError("Response model differs from pinned request model")
    answers = response.get("answers", {})
    if set(answers) != set(payload["questions"]):
        raise ValueError("Response question IDs differ from request")
    for key, question in payload["questions"].items():
        if question["type"] == "choice":
            choice_probabilities(answers[key], question["criteria"])
        elif question["type"] == "score":
            score_probabilities(answers[key], question["criteria"])
        else:
            raise ValueError(f"Unsupported Jev question type: {question['type']}")
    usage = response.get("usage", {})
    for key in ("input_tokens", "output_tokens"):
        if isinstance(usage.get(key), bool) or not isinstance(usage.get(key), int) or usage[key] < 0:
            raise ValueError("Missing or invalid token usage")


class JevClient:
    def __init__(self, cache_dir: Path, *, offline: bool = False, attempts: int = 6, session=None):
        self.cache_dir = cache_dir
        self.offline = offline
        self.attempts = attempts
        self.session = session or requests.Session()

    def evaluate(self, payload: dict) -> tuple[dict, str, bool]:
        key = fingerprint(payload)
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("request_sha256") != key:
                raise ValueError("Cache request hash mismatch")
            validate_response(record["response"], payload)
            return record["response"], key, True
        if self.offline:
            raise FileNotFoundError(f"Offline Jev cache miss: {key}")
        api_key = os.environ.get("TYPESAFE_API_KEY")
        if not api_key:
            raise RuntimeError("Set TYPESAFE_API_KEY in the process environment")
        for attempt in range(self.attempts):
            try:
                response = self.session.post(
                    API_URL, json=payload,
                    headers={"Authorization": f"Bearer {api_key}"}, timeout=(15, 120),
                )
            except requests.RequestException:
                if attempt + 1 == self.attempts:
                    raise RuntimeError("Jev transport failed after retries") from None
                time.sleep(min(2 ** attempt, 30))
                continue
            if response.status_code in {408, 429, 500, 502, 503, 504, 529}:
                if attempt + 1 == self.attempts:
                    raise RuntimeError(f"Jev HTTP {response.status_code} after retries")
                try:
                    delay = float(response.headers.get("Retry-After", 2 ** attempt))
                except ValueError:
                    delay = 2 ** attempt
                time.sleep(max(0, min(delay, 60)))
                continue
            if response.status_code != 200:
                # Never echo request headers, credentials, or server-provided request bodies.
                raise RuntimeError(f"Jev HTTP {response.status_code}; request {key}")
            result = response.json()
            try:
                validate_response(result, payload)
            except ValueError as error:
                write_json(self.cache_dir / "invalid" / f"{key}.json", {
                    "request_sha256": key, "request": payload, "response": result,
                    "validation_error": str(error),
                })
                raise ValueError(f"Invalid Jev response {key}: {error}") from None
            write_json(path, {
                "request_sha256": key,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "response": result,
            })
            return result, key, False
        raise RuntimeError("Jev retry attempts must be positive")


def combine_probabilities(answers: dict, catalogue: pd.DataFrame) -> dict[str, float]:
    groups = sorted(set(catalogue.occ_code.str[:2]))
    root = choice_probabilities(answers["soc_group"], groups)
    result = {}
    for group, rows in catalogue.groupby(catalogue.occ_code.str[:2], sort=True):
        conditional = choice_probabilities(answers[f"soc_{group}"], rows.occ_code)
        result.update({code: root[group] * conditional[code] for code in rows.occ_code})
    if set(result) != set(catalogue.occ_code) or not math.isclose(math.fsum(result.values()), 1, abs_tol=1e-10):
        raise ValueError("Incomplete or invalid joint distribution")
    return result


def summarize(row: dict, answers: dict, catalogue: pd.DataFrame) -> tuple[dict, dict]:
    probabilities = combine_probabilities(answers, catalogue)
    ranking = sorted(probabilities, key=lambda code: (-probabilities[code], code))
    winner = ranking[0]
    us = catalogue.set_index("occ_code")
    tier = choice_probabilities(answers["tier"], ("1", "2", "3"))
    tier_rank = sorted(tier, key=lambda code: (-tier[code], code))
    record = {
        "cno4": str(row["CNO4"]).zfill(4),
        "occupation_title": row["occupation_title"],
        "jev_matched_occ_code": winner,
        "jev_matched_title": us.at[winner, "title"],
        "observed_exposure_jev_nearest": float(us.at[winner, "observed_exposure"]),
        "observed_exposure_jev_weighted": math.fsum(
            probabilities[code] * float(us.at[code, "observed_exposure"]) for code in ranking
        ),
        "jev_match_probability": probabilities[winner],
        "jev_match_margin": probabilities[winner] - probabilities[ranking[1]] if len(ranking) > 1 else 1.0,
        "jev_match_entropy": -math.fsum(p * math.log(p) for p in probabilities.values() if p > 0),
        "jev_soc_group_confidence": answers["soc_group"]["confidence"],
        "jev_conditional_match_confidence": answers[f"soc_{winner[:2]}"]["confidence"],
        "jev_tier": int(tier_rank[0]),
        "jev_tier_probability": tier[tier_rank[0]],
        "jev_tier_margin": tier[tier_rank[0]] - tier[tier_rank[1]],
        "jev_tier_confidence": answers["tier"]["confidence"],
        "jev_api_label_disagreement_count": sum(choice_label_disagrees(answer) for answer in answers.values()),
        "jev_match_api_label_disagreement": choice_label_disagrees(answers["soc_group"]) or choice_label_disagrees(answers[f"soc_{winner[:2]}"]),
        "jev_tier_api_label_disagreement": choice_label_disagrees(answers["tier"]),
        **{f"jev_tier_{key}_probability": value for key, value in sorted(tier.items())},
    }
    # Review heuristics, not calibrated correctness or exclusion rules.
    record["jev_match_review"] = record["jev_match_probability"] < REVIEW_MIN_PROBABILITY or record["jev_match_margin"] < REVIEW_MIN_MARGIN
    record["jev_tier_review"] = record["jev_tier_probability"] < REVIEW_MIN_PROBABILITY or record["jev_tier_margin"] < REVIEW_MIN_MARGIN
    record["jev_no_military_category"] = record["cno4"].startswith("0")
    record["jev_match_review"] |= record["jev_no_military_category"] or record["jev_match_api_label_disagreement"]
    record["jev_tier_review"] |= record["jev_tier_api_label_disagreement"]
    return record, probabilities


def classify_occupations(spanish: pd.DataFrame, catalogue: pd.DataFrame, cache_dir: Path,
                         *, workers: int = 4, offline: bool = False, progress=print) -> tuple[pd.DataFrame, pd.DataFrame, list]:
    if workers < 1 or spanish.empty or spanish.CNO4.duplicated().any():
        raise ValueError("Need positive workers and nonempty, unique Spanish occupations")
    catalogue = validate_catalogue(catalogue)
    questions = matching_questions(catalogue)
    rows = spanish.sort_values("CNO4").to_dict("records")
    # Preflight the entire run before spending any API tokens.
    payloads = [pack_questions(occupation_state(row), questions) for row in rows]

    def classify(item):
        row, batches = item
        client = JevClient(cache_dir, offline=offline)
        answers, requests_used = {}, []
        try:
            for payload in batches:
                response, key, cached = client.evaluate(payload)
                answers.update(response["answers"])
                requests_used.append({
                    "cno4": str(row["CNO4"]), "request_sha256": key,
                    "question_ids": list(payload["questions"]), "model": response["model"],
                    "cached": cached, **response["usage"],
                    "raw_probability_sums": {key: math.fsum(answer["probabilities"].values())
                                             for key, answer in response["answers"].items()},
                    "api_choice_disagreements": {
                        key: {"api_choice": answer["choice"],
                              "api_choice_probability": answer["probabilities"][answer["choice"]],
                              "max_probability": max(answer["probabilities"].values())}
                        for key, answer in response["answers"].items() if choice_label_disagrees(answer)
                    },
                })
        finally:
            client.session.close()
        record, probabilities = summarize(row, answers, catalogue)
        return record, {"cno4": record["cno4"], **probabilities}, requests_used

    records, distributions, audit = [], [], []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(classify, item) for item in zip(rows, payloads)]
        try:
            for future in as_completed(futures):
                record, probabilities, requests_used = future.result()
                records.append(record)
                distributions.append(probabilities)
                audit.extend(requests_used)
                progress(f"Jev {len(records)}/{len(rows)}: CNO4 {record['cno4']}")
        except BaseException:
            for future in futures:
                future.cancel()
            raise
    return (
        pd.DataFrame(records).sort_values("cno4").reset_index(drop=True),
        pd.DataFrame(distributions)[["cno4", *catalogue.occ_code]].sort_values("cno4").reset_index(drop=True),
        sorted(audit, key=lambda item: (item["cno4"], item["request_sha256"])),
    )


def direct_exposure_state(row: dict) -> dict:
    """Semantic occupation evidence only: no observed outcomes, crosswalk or tier."""
    state = occupation_state(row)["occupation"]
    return {"occupation": {
        "country": "Spain", "cno4": state["cno4"],
        "title": state["title"], "description_and_tasks": state["description_and_tasks"],
    }}


def direct_exposure_record(code: str, answer: dict) -> tuple[dict, dict]:
    probabilities = score_probabilities(answer, direct_exposure_question()["criteria"])
    estimate = math.fsum(int(level) * value for level, value in probabilities.items()) / 9
    raw_score = float(answer["score"])
    record = {
        "cno4": code, "observed_exposure_jev_direct": estimate,
        "jev_direct_raw_score": raw_score,
        "jev_direct_confidence": float(answer["confidence"]),
        "jev_direct_score_discrepancy": abs(estimate - raw_score / 9),
        "jev_direct_review": answer["confidence"] < DIRECT_REVIEW_MIN_CONFIDENCE,
    }
    return record, {"cno4": code, **{f"level_{level}": value for level, value in sorted(probabilities.items())}}


def classify_direct_exposure(spanish: pd.DataFrame, cache_dir: Path,
                             *, workers: int = 4, offline: bool = False, progress=print) -> tuple[pd.DataFrame, pd.DataFrame, list]:
    if workers < 1 or spanish.empty or spanish.CNO4.duplicated().any():
        raise ValueError("Need positive workers and nonempty, unique Spanish occupations")
    rows = spanish.sort_values("CNO4").to_dict("records")
    items = [(str(row["CNO4"]).zfill(4), direct_exposure_state(row)) for row in rows]
    return classify_direct_exposure_states(items, cache_dir, workers=workers, offline=offline, progress=progress)


def classify_direct_exposure_states(items: list[tuple[str, dict]], cache_dir: Path,
                                    *, workers: int = 4, offline: bool = False, progress=print) -> tuple[pd.DataFrame, pd.DataFrame, list]:
    if workers < 1 or not items or len({code for code, _ in items}) != len(items):
        raise ValueError("Need positive workers and nonempty, unique occupation states")
    question = {"direct_exposure": direct_exposure_question()}
    payloads = [(code, pack_questions(state, question)[0]) for code, state in items]

    def classify(item):
        code, payload = item
        client = JevClient(cache_dir, offline=offline)
        try:
            response, key, cached = client.evaluate(payload)
        finally:
            client.session.close()
        record, distribution = direct_exposure_record(code, response["answers"]["direct_exposure"])
        audit = {
            "cno4": code, "request_sha256": key, "question_ids": ["direct_exposure"],
            "model": response["model"], "cached": cached, **response["usage"],
            "raw_probability_sums": {"direct_exposure": math.fsum(response["answers"]["direct_exposure"]["probabilities"].values())},
        }
        return record, distribution, audit

    records, distributions, audit = [], [], []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(classify, item) for item in payloads]
        try:
            for future in as_completed(futures):
                record, distribution, request = future.result()
                records.append(record)
                distributions.append(distribution)
                audit.append(request)
                progress(f"Jev direct {len(records)}/{len(items)}: {record['cno4']}")
        except BaseException:
            for future in futures:
                future.cancel()
            raise
    return (
        pd.DataFrame(records).sort_values("cno4").reset_index(drop=True),
        pd.DataFrame(distributions)[["cno4", *[f"level_{i}" for i in range(10)]]].sort_values("cno4").reset_index(drop=True),
        sorted(audit, key=lambda item: item["cno4"]),
    )


def merge_sepe_file(source: Path, destination: Path, classifications: pd.DataFrame) -> dict:
    """Stream a many-to-one merge; fail on missing codes and preserve row counts."""
    if source.resolve() == destination.resolve():
        raise ValueError("SEPE destination must differ from source")
    if classifications.cno4.duplicated().any():
        raise ValueError("Duplicate CNO4 classifications")
    additions = classifications.drop(columns="occupation_title")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    count = 0
    codes = set()
    try:
        for chunk in pd.read_csv(source, dtype={"cno4": "string"}, chunksize=100_000):
            chunk["cno4"] = chunk.cno4.str.zfill(4)
            if chunk.cno4.isna().any():
                raise ValueError("SEPE has missing CNO4 codes")
            missing = set(chunk.cno4) - set(additions.cno4)
            if missing:
                raise ValueError(f"SEPE occupations missing Jev classification: {sorted(missing)}")
            collisions = set(chunk) & (set(additions) - {"cno4"})
            if collisions:
                raise ValueError(f"SEPE already contains Jev columns: {sorted(collisions)}")
            merged = chunk.merge(additions, on="cno4", how="left", validate="many_to_one", sort=False)
            if len(merged) != len(chunk):
                raise ValueError("SEPE merge changed row count")
            merged.to_csv(temporary, mode="w" if count == 0 else "a", header=count == 0, index=False)
            count += len(chunk)
            codes.update(chunk.cno4)
        if not count:
            raise ValueError("Empty SEPE input")
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return {"rows": count, "cno4_count": len(codes)}

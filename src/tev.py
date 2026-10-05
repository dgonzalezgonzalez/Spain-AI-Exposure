"""Local exhaustive TEV classification with pinned inference and exact cache replay."""
from __future__ import annotations

import json
import math
from pathlib import Path
import time

import pandas as pd
import requests

from .jev import (choice_probabilities, direct_exposure_record, fingerprint,
                  occupation_state, direct_exposure_state, validate_catalogue,
                  validate_response, write_json)
from .jev_questions import MATCH_INSTRUCTIONS, SOC_GROUPS, tier_question, direct_exposure_question

MODEL = "tev-occupation-reproducible:4b"
BASE_MODEL = "tev1:4b"
BASE_DIGEST = "9b5bb969e46c"
OLLAMA_VERSION = "0.35.1"
API = "http://127.0.0.1:11435"
MAX_OPTIONS = 24  # Within TEV's training range; API limit is 26.
RUNTIME_OPTIONS = {"num_ctx": 32768, "num_batch": 128, "num_thread": 4,
                   "num_gpu": 999, "seed": 20261005, "temperature": 0,
                   "top_k": 1, "top_p": 1, "min_p": 0, "repeat_penalty": 1}


def string_question(question: dict) -> dict:
    """Ollama requires string criteria; preserve all original structured content."""
    out = dict(question)
    if isinstance(out["criteria"], dict):
        out["criteria"] = {
            key: value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            for key, value in out["criteria"].items()
        }
    return out


def build_hierarchy(catalogue: pd.DataFrame) -> tuple[dict, dict]:
    """Split oversized SOC groups by successively finer official code prefixes."""
    catalogue = validate_catalogue(catalogue)
    nodes, paths = {}, {}

    def descend(rows: pd.DataFrame, prefix: str, path: list[tuple[str, str]]) -> None:
        if len(rows) == 1:
            paths[str(rows.iloc[0].occ_code)] = path
            return
        name = "soc_" + prefix.replace("-", "_") if prefix else "soc_group"
        if len(rows) <= MAX_OPTIONS and prefix:
            groups = [(str(row.occ_code), pd.DataFrame([row._asdict()]))
                      for row in rows.itertuples(index=False)]
            criteria = {str(row.occ_code): json.dumps(
                {"title": row.title, "description": row.onet_description}, ensure_ascii=False)
                for row in rows.itertuples(index=False)}
        else:
            # Major, minor, broad, then detailed SOC; skip single-child levels.
            lengths = [2, 4, 6, 7, 10]
            length = next((n for n in lengths if n > len(prefix)
                           and rows.occ_code.str[:n].nunique() > 1), None)
            if length is None:
                raise ValueError("Cannot partition unique SOC codes")
            groups = list(rows.groupby(rows.occ_code.str[:length], sort=True))
            if len(groups) > MAX_OPTIONS:
                raise ValueError(f"SOC partition exceeds {MAX_OPTIONS} options: {prefix}")
            criteria = {str(code): (SOC_GROUPS[str(code)] if length == 2 else
                        "Occupational group containing: " + "; ".join(group.title))
                        for code, group in groups}
        instructions = MATCH_INSTRUCTIONS + (
            " Which SOC major group contains its closest available US equivalent?" if not prefix else
            f" Conditional on its closest equivalent belonging to SOC group {prefix}, "
            "which listed occupation or occupational subgroup contains the closest equivalent? "
            "This premise applies even if another group would be a better overall fit.")
        nodes[name] = {"type": "choice", "instructions": instructions, "criteria": criteria}
        for code, group in groups:
            descend(group, str(code), [*path, (name, str(code))])

    descend(catalogue, "", [])
    if set(paths) != set(catalogue.occ_code):
        raise ValueError("Incomplete hierarchy")
    return nodes, paths


def joint_probabilities(answers: dict, nodes: dict, paths: dict) -> dict[str, float]:
    distributions = {key: choice_probabilities(answers[key], node["criteria"])
                     for key, node in nodes.items()}
    probabilities = {code: math.prod(distributions[node][option] for node, option in path)
                     for code, path in paths.items()}
    total = math.fsum(probabilities.values())
    if not math.isclose(total, 1, abs_tol=1e-10):
        raise ValueError(f"Hierarchy probability mass differs from one: {total}")
    return {code: probability / total for code, probability in probabilities.items()}


def pack_requests(state: dict, questions: dict) -> list[dict]:
    """Pin shared-schema batches, allowing Ollama's recurrent prefix checkpoint."""
    batches, current = [], {}
    for name, question in questions.items():
        candidate = {"model": MODEL, "state": state,
                     "questions": {**current, name: question}, "keep_alive": "30m"}
        size = len(json.dumps(candidate, ensure_ascii=False).encode("utf-8"))
        if size > 60000 or len(candidate["questions"]) > 64:
            if not current:
                raise ValueError("TEV question exceeds context budget; no truncation allowed")
            batches.append({"model": MODEL, "state": state, "questions": current, "keep_alive": "30m"})
            current = {}
            single = {"model": MODEL, "state": state, "questions": {name: question}, "keep_alive": "30m"}
            if len(json.dumps(single, ensure_ascii=False).encode("utf-8")) > 60000:
                raise ValueError("TEV question exceeds context budget; no truncation allowed")
        current[name] = question
    if current:
        batches.append({"model": MODEL, "state": state, "questions": current, "keep_alive": "30m"})
    return batches


def runtime_provenance() -> dict:
    version = requests.get(API + "/api/version", timeout=15).json()["version"]
    tags = requests.get(API + "/api/tags", timeout=15).json()["models"]
    models = {model["name"]: model for model in tags}
    if version != OLLAMA_VERSION or not models[BASE_MODEL]["digest"].startswith(BASE_DIGEST):
        raise ValueError("Ollama version or TEV base weights differ from pinned runtime")
    details = requests.post(API + "/api/show", json={"model": MODEL}, timeout=30).json()
    # Endpoint does not accept options. Validate parameters embedded in model.
    actual = dict(line.split(None, 1) for line in details["parameters"].splitlines())
    for key, value in RUNTIME_OPTIONS.items():
        if key not in actual or float(actual[key]) != float(value):
            raise ValueError(f"Pinned TEV parameter differs: {key}")
    return {"ollama_version": version, "model": MODEL,
            "model_digest": models[MODEL]["digest"],
            "base_model": BASE_MODEL, "base_digest": models[BASE_MODEL]["digest"],
            "runtime_options": RUNTIME_OPTIONS,
            "server": {"endpoint": API, "backend": "Vulkan", "device": 0,
                       "parallel_requests": 1, "flash_attention": False,
                       "kv_cache_type": "f16", "cloud": False,
                       "reset_before_uncached_request": True},
            "scoring": "candidate logits and softmax; no random sampling; thinking disabled by endpoint",
            "model_show_sha256": fingerprint(details)}


class TevClient:
    def __init__(self, cache_dir: Path, provenance: dict, *, offline: bool = False):
        self.cache_dir, self.provenance, self.offline = cache_dir, provenance, offline
        self.session = requests.Session()

    def evaluate(self, payload: dict, *, fresh: bool = False) -> tuple[dict, str, bool]:
        # Explicit serialized request pins key order, which assigns candidate letters.
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        key = fingerprint({"serialized_request": serialized, "runtime": self.provenance})
        path = self.cache_dir / f"{key}.json"
        if path.exists() and not fresh:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["request_sha256"] != key or record["request"] != payload:
                raise ValueError("TEV cache identity mismatch")
            validate_response(record["response"], payload)
            return record["response"], key, True
        if self.offline:
            raise FileNotFoundError(f"Offline TEV cache miss: {key}")
        started = time.monotonic()
        if self.provenance.get("server", {}).get("reset_before_uncached_request"):
            # Eliminate any dependence on prefixes retained from earlier requests.
            reset = self.session.post(API + "/api/generate",
                                      json={"model": MODEL, "keep_alive": 0}, timeout=(15, 120))
            reset.raise_for_status()
        response = self.session.post(API + "/v1/systemone", data=serialized.encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, timeout=(15, 1800))
        if response.status_code != 200:
            raise RuntimeError(f"TEV HTTP {response.status_code}: {response.text[:400]}")
        result = response.json()
        validate_response(result, payload)
        if not fresh:
            write_json(path, {"request_sha256": key, "request": payload, "runtime": self.provenance,
                             "response": result, "elapsed_seconds": time.monotonic() - started})
        return result, key, False


def classify(spanish: pd.DataFrame, catalogue: pd.DataFrame, cache_dir: Path,
             provenance: dict, *, offline: bool = False, progress=print) -> tuple:
    catalogue = validate_catalogue(catalogue)
    nodes, paths = build_hierarchy(catalogue)
    questions = {**nodes, "tier": string_question(tier_question()),
                 "direct_exposure": direct_exposure_question()}
    client = TevClient(cache_dir, provenance, offline=offline)
    records, distributions, scores, audit = [], [], [], []
    us = catalogue.set_index("occ_code")
    started = time.monotonic()
    try:
        for row in spanish.sort_values("CNO4").to_dict("records"):
            code = str(row["CNO4"])
            answers = {}
            # Direct Score has its own state, excluding every occupation match.
            payloads = pack_requests(direct_exposure_state(row), {"direct_exposure": questions["direct_exposure"]})
            payloads += pack_requests(occupation_state(row), {k: v for k, v in questions.items() if k != "direct_exposure"})
            for number, payload in enumerate(payloads, start=1):
                response, key, cached = client.evaluate(payload)
                answers.update(response["answers"])
                audit.append({"cno4": code, "question_ids": list(payload["questions"]), "request_sha256": key,
                              "cached": cached, **response["usage"]})
                progress(f"TEV CNO4 {code}: batch {number}/{len(payloads)} ({'cache' if cached else 'fresh'})")
            probabilities = joint_probabilities(answers, nodes, paths)
            winner = min(probabilities, key=lambda item: (-probabilities[item], item))
            tier = choice_probabilities(answers["tier"], ("1", "2", "3"))
            direct, score = direct_exposure_record(code, answers["direct_exposure"])
            direct = {key.replace("jev", "tev"): value for key, value in direct.items()}
            record = {"cno4": code, "occupation_title": row["occupation_title"],
                      "tev_matched_occ_code": winner, "tev_matched_title": us.at[winner, "title"],
                      "observed_exposure_tev_nearest": float(us.at[winner, "observed_exposure"]),
                      "observed_exposure_tev_weighted": math.fsum(probabilities[i] * us.at[i, "observed_exposure"] for i in sorted(probabilities)),
                      "tev_match_probability": probabilities[winner],
                      "tev_tier": int(min(tier, key=lambda item: (-tier[item], item))),
                      **{f"tev_tier_{i}_probability": tier[i] for i in sorted(tier)}, **direct}
            records.append(record)
            distributions.append({"cno4": code, **probabilities})
            scores.append(score)
            # Persist completed occupation immediately as well as every request.
            write_json(cache_dir / "completed" / f"{code}.json", record)
            progress(f"TEV completed {len(records)}/{len(spanish)} occupations; {time.monotonic()-started:.0f}s")
    finally:
        client.session.close()
    return pd.DataFrame(records), pd.DataFrame(distributions), pd.DataFrame(scores), audit, questions, paths

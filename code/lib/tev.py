"""Local TEV decisions with pinned inference and exact cache replay."""
from __future__ import annotations

import json
from pathlib import Path
import time

import requests

from .jev import fingerprint, validate_response as validate_jev_response, write_json

MODEL = "tev-replication:4b-q4-cpu4"
BASE_MODEL = "tev1:4b-q4_K_M"
BASE_DIGEST = "608e3a13eec386ad34b657b1dcefe89e98c489f0cd6a3287ac2bb613db2f93da"
OLLAMA_VERSION = "0.40.13"
API = "http://127.0.0.1:11436"
MAX_OPTIONS = 24  # Within TEV's training range; API limit is 26.
RUNTIME_OPTIONS = {"num_ctx": 8192, "num_batch": 128, "num_thread": 4,
                   "num_gpu": 0, "seed": 20261030, "temperature": 0,
                   "top_k": 1, "top_p": 1, "min_p": 0, "repeat_penalty": 1}


def validate_response(response: dict, payload: dict) -> None:
    if set(response.get('answers', {})) != set(payload['questions']):
        raise ValueError('Response question IDs differ from request')
    ordinary = {k: q for k, q in payload['questions'].items() if q['type'] != 'noul'}
    validate_jev_response({**response, 'answers': {k: response['answers'][k] for k in ordinary}},
                          {**payload, 'questions': ordinary})
    for key, question in payload['questions'].items():
        if question['type'] == 'noul':
            answer = response['answers'][key]
            value = answer.get('noul')
            if answer.get('type') != 'noul' or isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                raise ValueError(f'Invalid Noul probability: {key}')


def string_question(question: dict) -> dict:
    """Ollama requires string criteria; preserve all original structured content."""
    out = dict(question)
    if isinstance(out["criteria"], dict):
        out["criteria"] = {
            key: value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            for key, value in out["criteria"].items()
        }
    return out


def pack_requests(state: dict, questions: dict) -> list[dict]:
    """Group independent questions without truncation, pinning their order."""
    batches, current = [], {}
    for name, question in questions.items():
        if question["type"] == "choice" and len(question["criteria"]) > MAX_OPTIONS:
            raise ValueError("TEV Choice exceeds the 24-option training range")
        candidate = {"model": MODEL, "state": state,
                     "questions": {**current, name: question}, "keep_alive": "30m"}
        size = len(json.dumps(candidate, ensure_ascii=False).encode("utf-8"))
        if size > 22000 or len(candidate["questions"]) > 16:
            if not current:
                raise ValueError("TEV question exceeds context budget; no truncation allowed")
            batches.append({"model": MODEL, "state": state, "questions": current, "keep_alive": "30m"})
            current = {}
            single = {"model": MODEL, "state": state, "questions": {name: question}, "keep_alive": "30m"}
            if len(json.dumps(single, ensure_ascii=False).encode("utf-8")) > 22000:
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
            "server": {"endpoint": API, "backend": "CPU", "device": None,
                       "parallel_requests": 1, "flash_attention": False,
                       "kv_cache_type": "f16", "cloud": False,
                       "reset_before_uncached_request": True},
            "scoring": "candidate logits and softmax; no random sampling; thinking disabled by endpoint",
            # Ollama prints parameter/modelfile lines from unordered Go maps.
            "model_show_sha256": fingerprint({'parameters': actual,
                                              'model_info': details.get('model_info'),
                                              'template': details.get('template')})}


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
        record = {"request_sha256": key, "request": payload, "runtime": self.provenance,
                  "response": result, "elapsed_seconds": time.monotonic() - started}
        write_json(path if not fresh else self.cache_dir / 'audit' / f'{key}-{time.time_ns()}.json', record)
        return result, key, False


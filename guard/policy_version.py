import os
import hashlib


def compute_file_hash(filepath: str) -> str:
    if not os.path.exists(filepath):
        return ""
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def compute_corpus_hash(policy_data_dir: str = "policy-data") -> str:
    if not os.path.exists(policy_data_dir):
        return ""
    combined = []
    for root, _, files in sorted(os.walk(policy_data_dir)):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            combined.append(compute_file_hash(fpath))
    corpus_combined = "".join(combined)
    return hashlib.sha256(corpus_combined.encode("utf-8")).hexdigest()


def get_policy_version(
    rules_path: str = "policies/rules.yaml",
    limits_path: str = "policies/limits.yaml",
    thresholds_path: str = "policies/thresholds.yaml",
    policy_data_dir: str = "policy-data",
) -> str:
    rules_hash = compute_file_hash(rules_path)
    limits_hash = compute_file_hash(limits_path)
    thresholds_hash = compute_file_hash(thresholds_path)
    corpus_hash = compute_corpus_hash(policy_data_dir)

    combined = f"{rules_hash}:{limits_hash}:{thresholds_hash}:{corpus_hash}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()

#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module

task = load_module("rb_task", ROOT / "brain" / "task.py")
learning = load_module("rb_learning", ROOT / "brain" / "learning.py")
validation = load_module("rb_validation", ROOT / "brain" / "validation_memory.py")

class TaskTests(unittest.TestCase):
    def test_terms_drop_noise(self):
        self.assertEqual(task.terms("Continue fix purchase billing"), ["purchase", "billing"])

    def test_dynamic_budget_high_confidence(self):
        ranked = [
            {"score": 45, "matched_terms": ["purchase", "billing"], "reasons": ["search-index"]},
            {"score": 20, "matched_terms": ["purchase"], "reasons": ["search-index"]},
        ]
        budget = task.choose_context_budget(ranked, 12)
        self.assertEqual(budget["max_files"], 3)
        self.assertEqual(budget["confidence"], "high")

    def test_dynamic_budget_low_confidence(self):
        ranked = [{"score": 5, "matched_terms": [], "reasons": []}]
        budget = task.choose_context_budget(ranked, 12)
        self.assertEqual(budget["max_files"], 12)

class LearningTests(unittest.TestCase):
    def test_learning_scores_are_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            old = learning.LEARNING
            learning.LEARNING = Path(td) / "routing-learning.json"
            try:
                for _ in range(20):
                    learning.learn("purchase billing", ["A.kt"], ["B.kt"], ["T.kt"])
                data = json.loads(learning.LEARNING.read_text())
                self.assertEqual(data["term_file_scores"]["purchase"]["A.kt"], 40)
                self.assertEqual(data["term_file_scores"]["purchase"]["B.kt"], -20)
                self.assertEqual(data["term_test_scores"]["purchase"]["T.kt"], 40)
                self.assertLessEqual(len(data["examples"]), 64)
            finally:
                learning.LEARNING = old

class ValidationTests(unittest.TestCase):
    def test_validation_scores_pass_and_fail(self):
        with tempfile.TemporaryDirectory() as td:
            old = validation.VALIDATION
            validation.VALIDATION = Path(td) / "validation-memory.json"
            try:
                validation.record("purchase billing", "T.kt", "passed")
                validation.record("purchase billing", "T.kt", "failed")
                data = json.loads(validation.VALIDATION.read_text())
                self.assertEqual(data["term_test_scores"]["purchase"]["T.kt"], 1)
                self.assertEqual(len(data["records"]), 2)
            finally:
                validation.VALIDATION = old

if __name__ == "__main__":
    unittest.main()

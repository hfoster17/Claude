"""Tests for model schema validation."""

import json
import copy
import pytest

from model_manager import validate_model_dict, load_model_file, CURRENT_SCHEMA_VERSION


class TestSchemaValidation:
    def test_valid_model(self, sample_model):
        error = validate_model_dict(sample_model)
        assert error is None

    def test_missing_field(self, sample_model):
        for field in ["schema_version", "symbol", "k", "initial_probs",
                       "transition_matrix", "means", "variances",
                       "feature_mean", "feature_std", "regime_labels", "metadata"]:
            model = copy.deepcopy(sample_model)
            del model[field]
            error = validate_model_dict(model)
            assert error is not None, f"Should fail for missing {field}"
            assert field in error

    def test_wrong_schema_version(self, sample_model):
        model = copy.deepcopy(sample_model)
        model["schema_version"] = 99
        error = validate_model_dict(model)
        assert error is not None
        assert "version" in error.lower()

    def test_unknown_symbol(self, sample_model):
        model = copy.deepcopy(sample_model)
        model["symbol"] = "INVALID"
        error = validate_model_dict(model)
        assert error is not None
        assert "symbol" in error.lower()

    def test_dimension_mismatch_initial_probs(self, sample_model):
        model = copy.deepcopy(sample_model)
        model["initial_probs"] = [0.5, 0.5]  # k=3 but only 2 probs
        error = validate_model_dict(model)
        assert error is not None

    def test_dimension_mismatch_transition(self, sample_model):
        model = copy.deepcopy(sample_model)
        model["transition_matrix"] = [[0.5, 0.5], [0.5, 0.5]]  # k=3 but 2x2
        error = validate_model_dict(model)
        assert error is not None

    def test_dimension_mismatch_means(self, sample_model):
        model = copy.deepcopy(sample_model)
        model["means"] = [[0.0] * 6, [0.0] * 6]  # k=3 but only 2 rows
        error = validate_model_dict(model)
        assert error is not None

    def test_dimension_mismatch_feature_mean(self, sample_model):
        model = copy.deepcopy(sample_model)
        model["feature_mean"] = [0.0, 0.0]  # n_features=6 but only 2
        error = validate_model_dict(model)
        assert error is not None

    def test_load_model_file(self, sample_model_file):
        model = load_model_file(sample_model_file)
        assert model is not None
        assert model.symbol == "NQ"
        assert model.k == 3

    def test_load_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json")
        model = load_model_file(str(path))
        assert model is None

    def test_load_nonexistent(self):
        model = load_model_file("/nonexistent/path.json")
        assert model is None

    def test_all_supported_symbols(self, sample_model):
        for sym in ["NQ", "ES", "CL", "NG", "GC", "SI", "ZB", "UB"]:
            model = copy.deepcopy(sample_model)
            model["symbol"] = sym
            error = validate_model_dict(model)
            assert error is None, f"Failed for {sym}: {error}"

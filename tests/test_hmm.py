"""Tests for hmm_inference.py — HMM filter and Viterbi."""

import numpy as np
import pytest

from hmm_inference import HMMModel, HMMFilter, viterbi


class TestHMMModel:
    def test_load_valid(self, sample_model):
        model = HMMModel(sample_model)
        assert model.k == 3
        assert model.n_features == 6
        assert model.symbol == "NQ"
        assert model.initial_probs.shape == (3,)
        assert model.transition_matrix.shape == (3, 3)
        assert model.means.shape == (3, 6)
        assert model.variances.shape == (3, 6)

    def test_variance_floor(self, sample_model):
        sample_model["variances"][0][0] = 0.0
        model = HMMModel(sample_model)
        assert model.variances[0, 0] >= 1e-6


class TestHMMFilter:
    def test_initial_probs(self, sample_model):
        model = HMMModel(sample_model)
        filt = HMMFilter(model)
        np.testing.assert_allclose(filt.state_probs, model.initial_probs, atol=1e-10)

    def test_probs_sum_to_one(self, sample_model, sample_features):
        model = HMMModel(sample_model)
        filt = HMMFilter(model)

        for i in range(50):
            probs, state, conf = filt.update(sample_features[i])
            total = np.sum(probs)
            assert abs(total - 1.0) < 1e-6, f"Probs sum to {total} at step {i}"

    def test_dominant_state_valid(self, sample_model, sample_features):
        model = HMMModel(sample_model)
        filt = HMMFilter(model)

        for i in range(50):
            probs, state, conf = filt.update(sample_features[i])
            assert 0 <= state < model.k
            assert conf == probs[state]

    def test_confidence_bounded(self, sample_model, sample_features):
        model = HMMModel(sample_model)
        filt = HMMFilter(model)

        for i in range(50):
            _, _, conf = filt.update(sample_features[i])
            assert 0 <= conf <= 1.0

    def test_reset(self, sample_model, sample_features):
        model = HMMModel(sample_model)
        filt = HMMFilter(model)

        for i in range(20):
            filt.update(sample_features[i])

        filt.reset()
        np.testing.assert_allclose(filt.state_probs, model.initial_probs, atol=1e-10)

    def test_batch_forward(self, sample_model, sample_features):
        model = HMMModel(sample_model)
        filt = HMMFilter(model)

        all_probs = filt.batch_forward(sample_features[:50])
        assert all_probs.shape == (50, 3)

        for i in range(50):
            assert abs(np.sum(all_probs[i]) - 1.0) < 1e-6

    def test_deterministic(self, sample_model, sample_features):
        model = HMMModel(sample_model)

        filt1 = HMMFilter(model)
        filt2 = HMMFilter(model)

        for i in range(50):
            p1, s1, c1 = filt1.update(sample_features[i])
            p2, s2, c2 = filt2.update(sample_features[i])
            np.testing.assert_allclose(p1, p2, atol=1e-12)
            assert s1 == s2
            assert c1 == c2

    def test_extreme_observation(self, sample_model):
        model = HMMModel(sample_model)
        filt = HMMFilter(model)

        # Very extreme observation
        extreme = np.array([100.0, 100.0, 100.0, 100.0, 100.0, 100.0])
        probs, state, conf = filt.update(extreme)

        # Should not crash, probs should still sum to 1
        assert abs(np.sum(probs) - 1.0) < 1e-6
        assert not np.any(np.isnan(probs))


class TestViterbi:
    def test_output_shape(self, sample_model, sample_features):
        model = HMMModel(sample_model)
        states = viterbi(model, sample_features[:50])
        assert states.shape == (50,)

    def test_valid_states(self, sample_model, sample_features):
        model = HMMModel(sample_model)
        states = viterbi(model, sample_features[:50])
        for s in states:
            assert 0 <= s < model.k

    def test_deterministic(self, sample_model, sample_features):
        model = HMMModel(sample_model)
        s1 = viterbi(model, sample_features[:50])
        s2 = viterbi(model, sample_features[:50])
        np.testing.assert_array_equal(s1, s2)

"""Soak and stress tests — verify stability under sustained load."""

import time
import numpy as np
import pytest

from hmm_inference import HMMModel, HMMFilter
from server import InferenceServer
from model_manager import ModelManager


class TestSoakInference:
    def test_1000_sequential_inferences(self, sample_model):
        """Run 1000 inferences and verify no degradation."""
        model = HMMModel(sample_model)
        filt = HMMFilter(model)

        np.random.seed(42)
        latencies = []

        for i in range(1000):
            obs = np.random.randn(6)
            start = time.perf_counter()
            probs, state, conf = filt.update(obs)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

            # Verify invariants
            assert abs(np.sum(probs) - 1.0) < 1e-6
            assert 0 <= state < model.k
            assert 0 <= conf <= 1.0
            assert not np.any(np.isnan(probs))

        avg_ms = np.mean(latencies) * 1000
        p99_ms = np.percentile(latencies, 99) * 1000
        assert avg_ms < 10.0, f"Average latency too high: {avg_ms:.3f}ms"
        assert p99_ms < 50.0, f"P99 latency too high: {p99_ms:.3f}ms"

    def test_1000_server_messages(self, sample_model_dir):
        """Run 1000 infer requests through the server."""
        mm = ModelManager(sample_model_dir)
        mm.load_all()
        server = InferenceServer(mm)

        np.random.seed(42)
        latencies = []

        for i in range(1000):
            features = np.random.randn(6).tolist()
            start = time.perf_counter()
            resp = server.handle_message({
                "type": "infer",
                "symbol": "NQ",
                "timestamp": "2026-02-21T14:30:00Z",
                "features": features,
            })
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

            assert resp["type"] == "result"

        assert server.stats.total_requests == 1000
        assert server.stats.total_errors == 0

        avg_ms = np.mean(latencies) * 1000
        assert avg_ms < 10.0

    def test_memory_stability(self, sample_model):
        """Verify no memory growth over many iterations."""
        import sys

        model = HMMModel(sample_model)
        filt = HMMFilter(model)

        np.random.seed(42)

        # Warm up
        for _ in range(100):
            filt.update(np.random.randn(6))

        # Measure baseline
        baseline_size = sys.getsizeof(filt._alpha)

        for _ in range(5000):
            filt.update(np.random.randn(6))

        final_size = sys.getsizeof(filt._alpha)
        assert final_size == baseline_size, "Memory grew during inference"

    def test_alternating_symbols(self, sample_model_dir):
        """Test server handles alternating symbol requests."""
        mm = ModelManager(sample_model_dir)
        mm.load_all()
        server = InferenceServer(mm)

        np.random.seed(42)
        symbols = ["NQ", "ES"]

        for i in range(500):
            sym = symbols[i % len(symbols)]
            resp = server.handle_message({
                "type": "infer",
                "symbol": sym,
                "timestamp": "2026-02-21T14:30:00Z",
                "features": np.random.randn(6).tolist(),
            })
            assert resp["type"] == "result"

        assert server.stats.per_symbol_requests["NQ"] == 250
        assert server.stats.per_symbol_requests["ES"] == 250

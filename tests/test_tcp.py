"""Tests for TCP server — protocol integration tests."""

import asyncio
import json
import struct
import pytest

from server import InferenceServer, EngineStats
from model_manager import ModelManager


def encode_message(msg: dict) -> bytes:
    """Encode a message with 4-byte length prefix."""
    payload = json.dumps(msg).encode("utf-8")
    return struct.pack(">I", len(payload)) + payload


def decode_message(data: bytes) -> dict:
    """Decode a length-prefixed message."""
    if len(data) < 4:
        return {}
    msg_len = struct.unpack(">I", data[:4])[0]
    payload = data[4:4 + msg_len]
    return json.loads(payload.decode("utf-8"))


class TestEngineStats:
    def test_initial_state(self):
        stats = EngineStats()
        assert stats.total_requests == 0
        assert stats.total_errors == 0
        assert stats.avg_latency_ms == 0.0

    def test_record_request(self):
        stats = EngineStats()
        stats.record_request("NQ", 0.001)
        assert stats.total_requests == 1
        assert stats.per_symbol_requests["NQ"] == 1
        assert stats.avg_latency_ms > 0


class TestInferenceServer:
    @pytest.fixture
    def server(self, sample_model_dir):
        mm = ModelManager(sample_model_dir)
        mm.load_all()
        return InferenceServer(mm)

    def test_heartbeat(self, server):
        resp = server.handle_message({"type": "heartbeat"})
        assert resp["type"] == "heartbeat_ack"
        assert "uptime_s" in resp
        assert "models_loaded" in resp

    def test_status(self, server):
        resp = server.handle_message({"type": "status"})
        assert resp["type"] == "status_response"
        assert "models" in resp
        assert "total_requests" in resp

    def test_infer_valid(self, server):
        resp = server.handle_message({
            "type": "infer",
            "symbol": "NQ",
            "timestamp": "2026-02-21T14:30:00Z",
            "features": [0.1, -0.5, 0.3, 0.2, 1.1, -0.3],
        })
        assert resp["type"] == "result"
        assert resp["symbol"] == "NQ"
        assert len(resp["state_probs"]) == 3
        assert 0 <= resp["state"] < 3
        assert 0 <= resp["confidence"] <= 1.0

    def test_infer_missing_model(self, server):
        resp = server.handle_message({
            "type": "infer",
            "symbol": "ZB",
            "timestamp": "2026-02-21T14:30:00Z",
            "features": [0.1, -0.5, 0.3, 0.2, 1.1, -0.3],
        })
        assert resp["type"] == "error"
        assert resp["code"] == "MODEL_NOT_FOUND"

    def test_infer_wrong_feature_count(self, server):
        resp = server.handle_message({
            "type": "infer",
            "symbol": "NQ",
            "timestamp": "2026-02-21T14:30:00Z",
            "features": [0.1, 0.2],  # Too few
        })
        assert resp["type"] == "error"
        assert resp["code"] == "INVALID_FEATURES"

    def test_unknown_message_type(self, server):
        resp = server.handle_message({"type": "unknown"})
        assert resp["type"] == "error"
        assert resp["code"] == "INVALID_REQUEST"

    def test_multiple_inferences(self, server):
        """Test sequential inferences maintain state."""
        features = [0.1, -0.5, 0.3, 0.2, 1.1, -0.3]
        results = []
        for _ in range(10):
            resp = server.handle_message({
                "type": "infer",
                "symbol": "NQ",
                "timestamp": "2026-02-21T14:30:00Z",
                "features": features,
            })
            assert resp["type"] == "result"
            results.append(resp)

        assert server.stats.total_requests == 10

    def test_probs_sum_to_one(self, server):
        resp = server.handle_message({
            "type": "infer",
            "symbol": "NQ",
            "timestamp": "2026-02-21T14:30:00Z",
            "features": [0.1, -0.5, 0.3, 0.2, 1.1, -0.3],
        })
        total = sum(resp["state_probs"])
        assert abs(total - 1.0) < 0.01


class TestMessageEncoding:
    def test_round_trip(self):
        msg = {"type": "heartbeat"}
        encoded = encode_message(msg)
        decoded = decode_message(encoded)
        assert decoded == msg

    def test_infer_round_trip(self):
        msg = {
            "type": "infer",
            "symbol": "NQ",
            "timestamp": "2026-02-21T14:30:00Z",
            "features": [0.1, -0.5, 0.3, 0.2, 1.1, -0.3],
        }
        encoded = encode_message(msg)
        decoded = decode_message(encoded)
        assert decoded == msg

"""
TCP Inference Server — serves HMM regime classifications to NT8 clients.

Protocol: 4-byte big-endian length prefix + UTF-8 JSON payload.
See contracts/tcp_protocol.md for full specification.
"""

import asyncio
import json
import logging
import struct
import time
from typing import Dict, Optional

import numpy as np

from hmm_inference import HMMFilter, HMMModel
from model_manager import ModelManager

logger = logging.getLogger(__name__)

MAX_MSG_SIZE = 65536
HEADER_SIZE = 4


class EngineStats:
    """Track server-wide statistics."""

    def __init__(self):
        self.start_time = time.time()
        self.total_requests = 0
        self.total_errors = 0
        self.latency_sum = 0.0
        self.per_symbol_requests: Dict[str, int] = {}

    @property
    def uptime_s(self) -> float:
        return time.time() - self.start_time

    @property
    def avg_latency_ms(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.latency_sum / self.total_requests) * 1000

    def record_request(self, symbol: str, latency: float) -> None:
        self.total_requests += 1
        self.latency_sum += latency
        self.per_symbol_requests[symbol] = self.per_symbol_requests.get(symbol, 0) + 1

    def record_error(self) -> None:
        self.total_errors += 1


class InferenceServer:
    """Async TCP server for HMM inference."""

    def __init__(self, model_manager: ModelManager, host: str = "127.0.0.1", port: int = 5555):
        self.model_manager = model_manager
        self.host = host
        self.port = port
        self.stats = EngineStats()
        self._filters: Dict[str, HMMFilter] = {}
        self._server: Optional[asyncio.AbstractServer] = None

    def _get_filter(self, symbol: str) -> Optional[HMMFilter]:
        """Get or create an HMM filter for a symbol."""
        model = self.model_manager.get_model(symbol)
        if model is None:
            return None

        if symbol not in self._filters:
            self._filters[symbol] = HMMFilter(model)
        else:
            # Check if model changed (hot reload)
            current_filter = self._filters[symbol]
            if current_filter.model is not model:
                self._filters[symbol] = HMMFilter(model)
                logger.info("Replaced filter for %s with reloaded model", symbol)

        return self._filters[symbol]

    def _handle_infer(self, msg: Dict) -> Dict:
        """Handle an inference request."""
        symbol = msg.get("symbol", "")
        features = msg.get("features", [])
        timestamp = msg.get("timestamp", "")

        filt = self._get_filter(symbol)
        if filt is None:
            return {
                "type": "error",
                "symbol": symbol,
                "message": f"Model not loaded for symbol {symbol}",
                "code": "MODEL_NOT_FOUND",
            }

        if len(features) != filt.model.n_features:
            return {
                "type": "error",
                "symbol": symbol,
                "message": f"Expected {filt.model.n_features} features, got {len(features)}",
                "code": "INVALID_FEATURES",
            }

        obs = np.array(features, dtype=np.float64)
        state_probs, state, confidence = filt.update(obs)

        return {
            "type": "result",
            "symbol": symbol,
            "state_probs": [round(p, 6) for p in state_probs.tolist()],
            "state": int(state),
            "confidence": round(float(confidence), 6),
            "version": filt.model.schema_version,
            "model_timestamp": filt.model.metadata.get("trained_at", "unknown"),
        }

    def _handle_heartbeat(self, msg: Dict) -> Dict:
        return {
            "type": "heartbeat_ack",
            "uptime_s": round(self.stats.uptime_s, 1),
            "models_loaded": self.model_manager.loaded_symbols,
            "request_count": self.stats.total_requests,
        }

    def _handle_status(self, msg: Dict) -> Dict:
        models_info = {}
        for sym in self.model_manager.loaded_symbols:
            model = self.model_manager.get_model(sym)
            if model:
                models_info[sym] = {
                    "version": model.schema_version,
                    "trained_at": model.metadata.get("trained_at", "unknown"),
                    "request_count": self.stats.per_symbol_requests.get(sym, 0),
                }

        return {
            "type": "status_response",
            "uptime_s": round(self.stats.uptime_s, 1),
            "models": models_info,
            "total_requests": self.stats.total_requests,
            "total_errors": self.stats.total_errors,
            "avg_latency_ms": round(self.stats.avg_latency_ms, 3),
        }

    def handle_message(self, msg: Dict) -> Dict:
        """Route a message to the appropriate handler."""
        msg_type = msg.get("type", "")
        start = time.time()

        if msg_type == "infer":
            response = self._handle_infer(msg)
            elapsed = time.time() - start
            symbol = msg.get("symbol", "unknown")
            if response.get("type") == "result":
                self.stats.record_request(symbol, elapsed)
            else:
                self.stats.record_error()
            return response
        elif msg_type == "heartbeat":
            return self._handle_heartbeat(msg)
        elif msg_type == "status":
            return self._handle_status(msg)
        else:
            return {
                "type": "error",
                "message": f"Unknown message type: {msg_type}",
                "code": "INVALID_REQUEST",
            }

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a single TCP client connection."""
        addr = writer.get_extra_info("peername")
        logger.info("Client connected: %s", addr)

        try:
            while True:
                # Read 4-byte length header
                header = await reader.readexactly(HEADER_SIZE)
                msg_len = struct.unpack(">I", header)[0]

                if msg_len > MAX_MSG_SIZE:
                    logger.warning("Message too large (%d bytes) from %s", msg_len, addr)
                    break

                # Read payload
                payload = await reader.readexactly(msg_len)
                msg = json.loads(payload.decode("utf-8"))

                # Process (stats tracked inside handle_message)
                response = self.handle_message(msg)

                # Send response
                resp_bytes = json.dumps(response).encode("utf-8")
                writer.write(struct.pack(">I", len(resp_bytes)))
                writer.write(resp_bytes)
                await writer.drain()

        except asyncio.IncompleteReadError:
            logger.info("Client disconnected: %s", addr)
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON from %s: %s", addr, e)
        except Exception as e:
            logger.error("Error handling client %s: %s", addr, e)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            logger.info("Client connection closed: %s", addr)

    async def start(self) -> None:
        """Start the TCP server."""
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        logger.info("Inference server listening on %s:%d", self.host, self.port)

        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        """Stop the server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("Inference server stopped")

    def get_status_dict(self) -> Dict:
        """Get current server status as a dict (for dashboard)."""
        return {
            "uptime_s": round(self.stats.uptime_s, 1),
            "total_requests": self.stats.total_requests,
            "total_errors": self.stats.total_errors,
            "avg_latency_ms": round(self.stats.avg_latency_ms, 3),
            "models_loaded": self.model_manager.loaded_symbols,
            "per_symbol_requests": dict(self.stats.per_symbol_requests),
        }


def write_status_file(server: InferenceServer, path: str = "engine_status.json") -> None:
    """Write server status to a JSON file for dashboard consumption."""
    status = server.get_status_dict()
    try:
        with open(path, "w") as f:
            json.dump(status, f, indent=2)
    except Exception as e:
        logger.error("Failed to write status file: %s", e)


async def status_writer_loop(server: InferenceServer, path: str, interval: float = 5.0):
    """Periodically write status to file."""
    while True:
        write_status_file(server, path)
        await asyncio.sleep(interval)

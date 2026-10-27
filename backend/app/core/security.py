"""
AetherGrid Zero-Trust Telemetry Attestation
===========================================
Every telemetry packet from a crate carries:
  - hsm_serial       : Hardware Security Module unique ID (per crate)
  - seq_number       : Monotonic counter (anti-replay, anti-drop detection)
  - ts               : Unix timestamp (signed by HSM)
  - hsm_signature    : HMAC-SHA256 over (batch_id | truck_id | seq | ts | lat | lng | T | h | E)

On the backend:
  1. Look up the registered truck's HSM secret.
  2. Verify the signature matches.
  3. Reject packets older than ATTESTATION_TOLERANCE_SEC.
  4. Ensure seq_number strictly increases for that truck (replay defense).
  5. In production: enforce mTLS client certificate whose CN matches hsm_serial.

This is a SIMULATION of mTLS+HSM — a real deployment would use
ATECC608A/OPTIGA TPM chips per crate + SPIFFE/SPIRE for identity.

Author: Praveen Sudireddy
"""
from __future__ import annotations
import hashlib, hmac, time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .config import settings


@dataclass
class AttestationResult:
    ok: bool
    reason: str = ""


# In-memory replica of last-seen sequence per truck (in production: Redis)
_last_seq: Dict[str, int] = {}
_hsm_keys: Dict[str, bytes] = {}


def register_hsm(hsm_serial: str, secret: Optional[str] = None) -> None:
    """Register a crate/truck HSM at provisioning time."""
    _hsm_keys[hsm_serial] = (secret or (settings.HSM_SECRET + "|" + hsm_serial)).encode()


def _signing_payload(batch_id: str, truck_id: str, seq: int, ts: int,
                     lat: float, lng: float, temp_c: float,
                     humidity_pct: float, ethylene_ppm: float) -> bytes:
    msg = f"{batch_id}|{truck_id}|{seq}|{ts}|{lat:.5f}|{lng:.5f}|{temp_c:.2f}|{humidity_pct:.1f}|{ethylene_ppm:.2f}"
    return msg.encode()


def sign_packet(hsm_serial: str, batch_id: str, truck_id: str, seq: int, ts: int,
                lat: float, lng: float, temp_c: float,
                humidity_pct: float, ethylene_ppm: float) -> str:
    if hsm_serial not in _hsm_keys:
        register_hsm(hsm_serial)
    key = _hsm_keys[hsm_serial]
    payload = _signing_payload(batch_id, truck_id, seq, ts, lat, lng, temp_c, humidity_pct, ethylene_ppm)
    return "HSM-" + hmac.new(key, payload, hashlib.sha256).hexdigest()[:24]


def verify_packet(hsm_serial: str, signature: str, batch_id: str, truck_id: str,
                  seq: int, ts: int, lat: float, lng: float, temp_c: float,
                  humidity_pct: float, ethylene_ppm: float,
                  last_sequence: Optional[int] = None, advance_memory: bool = True) -> AttestationResult:
    if settings.MTLS_REQUIRED:
        # 1. Unknown HSM
        if hsm_serial not in _hsm_keys:
            return AttestationResult(False, f"unknown_hsm:{hsm_serial}")
        # 2. Replay / ordering check
        prev_seq = _last_seq.get(truck_id, -1) if last_sequence is None else last_sequence
        if seq <= prev_seq:
            return AttestationResult(False, f"replay:seq={seq}<=prev={prev_seq}")
        # 3. Time freshness
        now = int(time.time())
        if abs(now - ts) > settings.ATTESTATION_TOLERANCE_SEC:
            return AttestationResult(False, f"stale:now={now} ts={ts} delta={abs(now-ts)}s")
        # 4. Signature verification
        expected = sign_packet(hsm_serial, batch_id, truck_id, seq, ts, lat, lng,
                               temp_c, humidity_pct, ethylene_ppm)
        if not hmac.compare_digest(expected, signature):
            return AttestationResult(False, "bad_signature")
        if advance_memory: _last_seq[truck_id] = seq
    return AttestationResult(True, "ok")


def _v2_payload(packet: dict) -> bytes:
    """Versioned canonical model covers ALL accepted telemetry fields, not raw extras."""
    import json
    from ..api.schemas import TelemetryIn
    normalized = TelemetryIn.model_validate(dict(packet, signature_version=2, hsm_signature="placeholder")).model_dump(exclude={"hsm_signature"})
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sign_packet_v2(packet: dict) -> str:
    serial=packet["hsm_serial"]
    if serial not in _hsm_keys: register_hsm(serial)
    return "AG2-"+hmac.new(_hsm_keys[serial],_v2_payload(packet),hashlib.sha256).hexdigest()


def verify_packet_v2(packet:dict,last_sequence:int) -> AttestationResult:
    if packet["hsm_serial"] not in _hsm_keys:return AttestationResult(False,"unknown_serial")
    if packet["seq"]<=last_sequence:return AttestationResult(False,"replay")
    if abs(time.time()-packet["ts"])>settings.ATTESTATION_TOLERANCE_SEC:return AttestationResult(False,"stale")
    if not hmac.compare_digest(sign_packet_v2(packet),packet["hsm_signature"]):return AttestationResult(False,"bad_signature_v2")
    return AttestationResult(True,"ok")

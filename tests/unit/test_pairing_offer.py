"""Unit tests for PairingOfferManager security contract."""

import json
import time
from cache_vault.core.mobile.pairing_offer import PairingOfferManager, PAIRING_OFFER_TTL_SECONDS


def test_create_pairing_offer():
    mgr = PairingOfferManager(ttl_seconds=300)
    offer = mgr.create_offer(host="192.168.0.16", port=8742)
    assert offer.token is not None
    assert len(offer.token) >= 32
    assert offer.host == "192.168.0.16"
    assert offer.port == 8742
    assert not offer.consumed
    assert not offer.is_expired
    assert offer.is_valid

    payload_json = offer.to_qr_payload()
    data = json.loads(payload_json)
    assert data["v"] == 1
    assert data["host"] == "192.168.0.16"
    assert data["port"] == 8742
    assert data["token"] == offer.token
    # Permanent credentials must NOT be in QR payload
    assert "device_id" not in data
    assert "device_token" not in data


def test_pairing_offer_single_use_consumption():
    mgr = PairingOfferManager(ttl_seconds=300)
    offer = mgr.create_offer(host="192.168.0.16", port=8742)
    token = offer.token

    ok, reason = mgr.consume_offer(token)
    assert ok is True
    assert reason == "ok"

    # Second consumption attempt must fail (replay protection)
    ok2, reason2 = mgr.consume_offer(token)
    assert ok2 is False
    assert reason2 == "offer_already_used"


def test_pairing_offer_expiration():
    mgr = PairingOfferManager(ttl_seconds=1)  # 1 second TTL
    offer = mgr.create_offer(host="192.168.0.16", port=8742)
    token = offer.token

    time.sleep(1.1)
    ok, reason = mgr.consume_offer(token)
    assert ok is False
    assert reason == "offer_expired"

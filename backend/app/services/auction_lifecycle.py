"""Transactional demo auction lifecycle. No bank or insurer integration.

Reservations live in buyer capacity and a simulated cash ledger. State transitions
are serialized with BEGIN IMMEDIATE on SQLite before reading eligibility/state.
This deliberately supports one SQLite writer, not a distributed production lock.
"""
import datetime as dt
import uuid
from sqlalchemy import text
from ..core.database import (FlashAuction, AuctionControl, AuctionBid, CargoBatch,
    BuyerAuthorization, RegisteredBuyer, CargoEvent)
from ..core.config import settings


def lock_writer(db):
    if db.bind.dialect.name == 'sqlite':
        # Endpoint/service entry only: callers must not have pending writes.
        db.execute(text('BEGIN IMMEDIATE'))


def control_for(db, auction):
    control = db.get(AuctionControl, auction.id)
    if control is None:
        control = AuctionControl(auction_id=auction.id, attempt=0)
        db.add(control); db.flush()
    return control


def release_reservation(db, auction):
    bid = db.get(AuctionBid, auction.winning_bid_id) if auction.winning_bid_id else None
    if bid:
        buyer = db.get(RegisteredBuyer, bid.buyer_id)
        auth = db.get(BuyerAuthorization, bid.buyer_id)
        if buyer: buyer.capacity_kg += bid.kg_requested
        if auth: auth.simulated_escrow_inr += bid.price_inr_per_kg * bid.kg_requested
    auction.winning_bid_id = None


def fail_and_retry(db, auction, now, reason):
    """Call under writer lock; only active auctions can release/retry once."""
    if auction.status not in ('Open', 'AwaitingConfirmation'): return None
    control = control_for(db, auction)
    if auction.status == 'AwaitingConfirmation': release_reservation(db, auction)
    auction.status = 'Expired'
    batch = db.get(CargoBatch, auction.batch_id)
    db.add(CargoEvent(batch_id=auction.batch_id, kind='auction_expired', severity='warn',
        description=f'{reason}; simulated reservations released if present.'))
    if not batch or batch.status != 'DistressedLiquidation': return None
    # Conservative current thermal budget; never grant a new RVH budget on retry.
    elapsed = max(0, (now - auction.opened_at).total_seconds()/3600)
    remaining = max(0, min(auction.trigger_rvh_hours or 0, batch.rvh_hours or 0) - elapsed)
    if control.attempt >= settings.MAX_REAUCTIONS or remaining <= .25 or (batch.life_consumed_pct or 0) >= 100:
        db.add(CargoEvent(batch_id=batch.id, kind='manual_intervention_required', severity='critical',
            description='Automatic retries exhausted or insufficient heuristic thermal budget. No rescue claimed.'))
        return None
    child = FlashAuction(id='F-'+uuid.uuid4().hex[:8].upper(), batch_id=batch.id,
        status='Open', opened_at=now, closes_at=now+dt.timedelta(seconds=settings.REAUCTION_WINDOW_SEC),
        trigger_lat=batch.current_lat if batch.current_lat is not None else auction.trigger_lat,
        trigger_lng=batch.current_lng if batch.current_lng is not None else auction.trigger_lng,
        trigger_rvh_hours=remaining, trigger_temp_c=batch.current_temp_c or auction.trigger_temp_c,
        trigger_life_pct=batch.life_consumed_pct)
    db.add(child)
    db.add(AuctionControl(auction_id=child.id, attempt=control.attempt+1, parent_auction_id=auction.id))
    db.add(CargoEvent(batch_id=batch.id, kind='auction_reopened', severity='warn',
        description=f'Timed fallback attempt {control.attempt+1}: {child.id}. No radius widening.'))
    return child


def expire_due(db, now=None):
    """One atomic sweep; safe for restart (deadlines persisted in SQLite)."""
    now = now or dt.datetime.utcnow()
    lock_writer(db)
    changed=[]
    for auction in db.query(FlashAuction).filter(FlashAuction.status.in_(['Open','AwaitingConfirmation'])).all():
        control = control_for(db, auction)
        deadline = control.confirmation_deadline if auction.status == 'AwaitingConfirmation' else auction.closes_at
        batch = db.get(CargoBatch, auction.batch_id)
        invalid = not batch or batch.status != 'DistressedLiquidation'
        if invalid or (deadline and deadline <= now):
            child = fail_and_retry(db, auction, now, 'Batch unavailable' if invalid else 'Deadline elapsed')
            changed.append({'expired':auction.id, 'reopened':child.id if child else None})
    db.commit()
    return changed

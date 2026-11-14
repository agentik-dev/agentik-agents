"""The fan-out's budget pool, ported from the old fan-out (d8ca583) as it was.

design/21 item 25. A shard's grant is min(max_shard_usd or budget/shards,
free); its CLI ceiling is the grant over OVERSHOOT. A grant under FLOOR_USD is
not started: the floor is judged on the ceiling the grant buys, not on the
grant, since a shard that trips a tiny ceiling returns nothing and still costs.
"""
import threading

# A shard's ceiling is checked between requests, so the request that trips it
# still completes; measured overshoot was 1.2x on a $0.01 cap.
OVERSHOOT = 1.35
# Below this ceiling a shard cannot do useful work.
MIN_VIABLE_SHARD_USD = 0.05
# The grant it takes to fund a viable ceiling: 0.05 * 1.35 == 0.0675 in floats.
FLOOR_USD = MIN_VIABLE_SHARD_USD * OVERSHOOT


class BudgetPool:
    """Hard aggregate ceiling. Reserve before launch, settle after."""

    def __init__(self, total):
        self.total = total
        self._settled = 0.0
        self._reserved = 0.0
        self._lock = threading.Lock()

    @property
    def available(self):
        with self._lock:
            return self.total - self._settled - self._reserved

    @property
    def settled(self):
        with self._lock:
            return self._settled

    def reserve(self, want):
        """Take up to `want` from the pool. Returns 0.0 if nothing viable."""
        with self._lock:
            free = self.total - self._settled - self._reserved
            grant = min(want, free)
            if grant < FLOOR_USD:
                return 0.0
            self._reserved += grant
            return grant

    def settle(self, reserved, actual):
        """Release a reservation and book what was actually spent.

        Actual spend counts even when it exceeded the reservation: the pool
        reflects money that left, not money that was meant to.
        """
        with self._lock:
            self._reserved -= reserved
            self._settled += max(0.0, actual)


def want(max_shard_usd, budget_usd, count):
    """What one shard asks of the pool."""
    return max_shard_usd or budget_usd / count


def skip_reason(asked, free):
    """Why a shard the pool would not fund is skipped: `floor` when its own
    ask is under the floor, else `budget`, the pool having too little left."""
    if asked < FLOOR_USD and free >= asked:
        return "floor"
    return "budget"

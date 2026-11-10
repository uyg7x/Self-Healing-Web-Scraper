import asyncio
import math
import random


class HumanDelay:
    def __init__(
        self,
        base: float = 1.8,
        sigma: float = 0.65,
        hard_min: float = 0.9,
        hard_max: float = 90.0,
        long_pause_chance: float = 0.12,
        long_pause_range: tuple[float, float] = (3.0, 9.0),
        coffee_break_range: tuple[int, int] = (7, 12),
        coffee_duration: tuple[float, float] = (15.0, 45.0),
        session_gap_range: tuple[float, float] = (30.0, 90.0),
    ):
        self.base = base
        self.initial_base = base
        self.sigma = sigma
        self.hard_min = hard_min
        self.hard_max = hard_max
        self.long_pause_chance = long_pause_chance
        self.long_pause_range = long_pause_range
        self.coffee_break_range = coffee_break_range
        self.coffee_duration = coffee_duration
        self.session_gap_range = session_gap_range

        self.page_count = 0
        self.failure_count = 0
        self.next_break_at = random.randint(*coffee_break_range)

    def _sample(self) -> float:
        raw = random.lognormvariate(math.log(self.base), self.sigma)
        return max(self.hard_min, min(self.hard_max, raw))

    async def page_load(self, actual_seconds: float) -> float:
        buffer = random.uniform(0.5, 1.5)
        total = max(1.0, actual_seconds + buffer)
        await asyncio.sleep(total)
        return total

    async def page_turn(self) -> float:
        self.page_count += 1
        delay = self._sample()

        if random.random() < self.long_pause_chance:
            delay += random.uniform(*self.long_pause_range)

        if self.page_count >= self.next_break_at:
            delay += random.uniform(*self.coffee_duration)
            self.next_break_at = self.page_count + random.randint(*self.coffee_break_range)

        if self.failure_count > 0:
            delay += min((2 ** self.failure_count) * 5, 120.0)

        delay = min(delay, self.hard_max)
        await asyncio.sleep(delay)
        return delay

    async def micro_pause(self) -> float:
        d = max(0.08, random.lognormvariate(math.log(0.35), 0.5))
        await asyncio.sleep(d)
        return d

    async def scroll_pause(self) -> float:
        d = random.uniform(0.8, 2.5)
        await asyncio.sleep(d)
        return d

    async def typing_delay(self) -> float:
        return random.uniform(0.05, 0.15)

    async def session_gap(self) -> float:
        d = random.uniform(*self.session_gap_range)
        await asyncio.sleep(d)
        return d

    async def between_sites(self) -> float:
        return await self.session_gap()

    async def after_block(self) -> float:
        d = random.uniform(20.0, 55.0)
        await asyncio.sleep(d)
        return d

    def register_failure(self) -> None:
        self.failure_count += 1
        self.base = min(self.base * 1.45, 6.0)

    def register_success(self) -> None:
        self.failure_count = 0
        self.base = max(self.base * 0.97, self.initial_base * 0.7)

    punish = register_failure
    reward = register_success

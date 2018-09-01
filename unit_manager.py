from functools import reduce
from .build_manager import BuildBuilding, BuildManager
from sc2.constants import *

class BuildUnit(BuildBuilding):
    """ Base for training units for zerg """

    def __init__(self, bot):
        self.bot = bot
        self.under_construction = 0

    async def build(self, bot):
        """ Override building build function """
        if bot.can_afford(self.unit) and bot.can_feed(self.unit) and bot.units(LARVA).exists:
            await bot.do(bot.units(LARVA).random.train(self.unit))

    @property
    def priority(self):
        return -1


class Overlord(BuildUnit):
    unit = OVERLORD
    unit_type = ['supply']

    @property
    def priority(self):
        return 0.1 # ALWAYS build this first

    def prefered_amount(self, bot):
        """ Make sure we always have supply, but don't make too many in the beginning """
        return 1 + (bot.supply_used-4) // 8

class Drone(BuildUnit):
    unit = DRONE
    unit_type = ['gathering']

    @property
    def priority(self):
        return 1.1

    def prefered_amount(self, bot):
        """ Build always and change priority if we have many """
        return min(70, reduce(lambda tot, base: base.ideal_harvesters + tot, bot.townhalls, 0))


class Zergling(BuildUnit):
    unit = ZERGLING
    requirements = [SPAWNINGPOOL]
    unit_type = ['war']

    @property
    def priority(self):
        return 1 - self.bot.diff_army_value

    def prefered_amount(self, bot):
        """ We have currently a roach rush, but make some lings to defend """
        return 6

class Roach(BuildUnit):
    unit = ROACH
    requirements = [ROACHWARREN]
    unit_type = ['war', 'tank']

    @property
    def priority(self):
        priority = 2
        if self.bot.units(HYDRALISK).amount > 0:
            # Change the value by a tiny bit
            priority -= (self.bot.units(ROACH).amount / self.bot.units(HYDRALISK).amount - self.bot.roachHydraRatio) * 0.01
        return priority

    def prefered_amount(self, bot):
        """ Build always and change priority if we have many """
        return 200

class Hydralisk(BuildUnit):
    unit = HYDRALISK
    requirements = [HYDRALISKDEN]
    unit_type = ['war', 'artillery']

    @property
    def priority(self):
        priority = 2
        if self.bot.units(HYDRALISK).amount > 0:
            # Change the value by a tiny bit
            priority += (self.bot.units(ROACH).amount / self.bot.units(HYDRALISK).amount - self.bot.roachHydraRatio) * 0.01
        return priority

    def prefered_amount(self, bot):
        """ Build always and change priority if we have many """
        return 100


class UnitBuildManager(BuildManager):
    def __init__(self, bot):
        self.bot = bot
        self.units = [Overlord(bot), Drone(bot), Zergling(bot), Roach(bot), Hydralisk(bot)]


    async def build(self, logging=False):
        """ Choses what unit to build based on priority and diff army value """
        units = self.units
        if self.bot.diff_army_value > 0:
            units = filter(lambda unit: 'war' in unit.unit_type or 'supply', units)

        for unit in sorted(units, key=lambda unit: unit.priority):
            if await unit.would_build(self.bot):
                if await unit.can_build(self.bot):
                    await unit.build(self.bot)

                    if logging:
                        print('Building ', unit.__class__.__name__, ' at ', self.bot.supply_used)
                return

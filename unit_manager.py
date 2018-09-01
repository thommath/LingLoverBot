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

    @property
    def priority(self):
        return 0.1 # ALWAYS build this first

    def prefered_amount(self, bot):
        """ Make sure we always have supply, but don't make too many in the beginning """
        return 1 + (bot.supply_used-4) // 8

class Drone(BuildUnit):
    unit = DRONE

    @property
    def priority(self):
        return 1.1

    def prefered_amount(self, bot):
        """ Build always and change priority if we have many """
        return min(70, reduce(lambda tot, base: base.ideal_harvesters + tot, bot.townhalls, 0))


class Zergling(BuildUnit):
    unit = ZERGLING
    requirements = [SPAWNINGPOOL]

    @property
    def priority(self):
        return 1 - self.bot.diff_army_value

    def prefered_amount(self, bot):
        """ We have currently a roach rush, but make some lings to defend """
        return 6

class Roach(BuildUnit):
    unit = ROACH
    requirements = [ROACHWARREN]

    @property
    def priority(self):
        priority = 2
        if self.bot.units(HYDRALISK).amount > 0:
            # Change the value by a tiny bit
            priority -= (self.bot.units(ROACH).amount / self.bot.units(HYDRALISK).amount - self.bot.roachHydraRatio) * 0.01
        return priority - self.bot.diff_army_value

    def prefered_amount(self, bot):
        """ Build always and change priority if we have many """
        return 200

class Hydralisk(BuildUnit):
    unit = HYDRALISK
    requirements = [HYDRALISKDEN]

    @property
    def priority(self):
        priority = 2
        if self.bot.units(HYDRALISK).amount > 0:
            # Change the value by a tiny bit
            priority += (self.bot.units(ROACH).amount / self.bot.units(HYDRALISK).amount - self.bot.roachHydraRatio) * 0.01
        return priority - self.bot.diff_army_value

    def prefered_amount(self, bot):
        """ Build always and change priority if we have many """
        return 100


class UnitBuildManager(BuildManager):
    def __init__(self, bot):
        self.bot = bot
        self.units = [Overlord(bot), Drone(bot), Zergling(bot), Roach(bot), Hydralisk(bot)]


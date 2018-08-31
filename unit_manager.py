from functools import reduce
from build_manager import BuildBuilding, BuildManager
from sc2.constants import *

class BuildUnit(BuildBuilding):
    """ Base for training units for zerg """

    async def build(self, bot):
        """ Override building build function """
        if bot.can_afford(self.unit) and bot.can_feed(self.unit) and bot.units(LARVA).exists:
            await bot.do(bot.units(LARVA).random.train(self.unit))


class Overlord(BuildUnit):
    unit = OVERLORD
    priority = 0.1 # ALWAYS build this first

    def prefered_amount(self, bot):
        """ Make sure we always have supply, but don't make too many in the beginning """
        return 1 + (bot.supply_used-4) // 8

class Drone(BuildUnit):
    unit = DRONE
    priority = 1.1

    def prefered_amount(self, bot):
        """ Build always and change priority if we have many """
        return min(70, reduce(lambda tot, base: base.ideal_harvesters + tot, bot.townhalls, 0))


class Zergling(BuildUnit):
    unit = ZERGLING
    priority = 1
    requirements = [SPAWNINGPOOL]

    def prefered_amount(self, bot):
        """ We have currently a roach rush, but make some lings to defend """
        return 6


class Roach(BuildUnit):
    unit = ROACH
    requirements = [ROACHWARREN]
    priority = 2

    def prefered_amount(self, bot):
        """ Build always and change priority if we have many """
        return 200

class Hydralisk(BuildUnit):
    unit = HYDRALISK
    priority = 2
    requirements = [HYDRALISKDEN]

    def prefered_amount(self, bot):
        """ Build always and change priority if we have many """
        return 100


class UnitBuildManager(BuildManager):
    def __init__(self, bot):
        self.bot = bot
        self.units = [Overlord(), Drone(), Zergling(), Roach(), Hydralisk()]


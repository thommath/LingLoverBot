from sc2.constants import *
from functools import reduce
import math
import json

priorities = {}

with open('./LingLover/settings.json') as f:
    priorities = json.load(f)


class BuildBuilding():
    requirements = []
    unit = 0
    name = ''

    def __init__(self, bot):
        self.bot = bot
        self.under_construction = 0

    @property
    def priority(self):
        return priorities[self.name]['priority']
    
    def prefered_amount(self, bot):
        return 1

    async def build(self, bot):
        if bot.can_afford(self.unit):
            await bot.build(self.unit, near=bot.townhalls.first)
    
    async def can_build(self, bot):
        if not bot.can_afford(self.unit).__bool__():
            return False

        if len(self.requirements) > 0:
            for id in self.requirements:
                if not bot.units(id).ready.exists:
                    return False

        return True


    # Would if I could
    async def would_build(self, bot):
        if len(self.requirements) > 0:
            for id in self.requirements:
                if not bot.units(id).ready.exists:
                    return False
                    
        pending = max(self.under_construction, 0)
        if pending == 0 and bot.already_pending(self.unit):
            pending = 1

        return self.prefered_amount(bot) > bot.units(self.unit).amount + pending


class Hatchery(BuildBuilding):
    name = 'HATCHERY'
    unit = HATCHERY

    @property
    def priority(self):
        return priorities[self.name]['priority'] + 10 * (self.bot.townhalls.amount - 1)
    
    def prefered_amount(self, bot):
        useful_hatcheries = bot.bases.filter(lambda base: base.ideal_harvesters > 8)

        return max(1 + 1/12 * bot.units(DRONE).amount + (bot.bases.amount - useful_hatcheries.amount), bot.bases.amount + bot.minerals // 800)

    async def build(self, bot):
        location = await bot.get_next_expansion()

        if bot.can_afford(self.unit):
            await bot.build(self.unit, near=location, max_distance=10, random_alternative=False, placement_step=1)
            self.under_construction += 1
            return True
        return False
    
    async def can_build(self, bot):
        if not bot.can_afford(self.unit):
            return False

        # Must have a valid exp location
        location = await bot.get_next_expansion()
        if not location:
            return False

        # Must not have enemies nearby
        if bot.remembered_enemy_units.closer_than(10, location).exists:
            return False

        # Must be able to find a valid building position
        if bot.can_afford(self.unit):
            position = await bot.find_placement(self.unit, location.rounded, max_distance=10, random_alternative=False, placement_step=1)
            if not position:
                return False
        return True

    # Would if I could
    async def would_build(self, bot):

        return self.prefered_amount(bot) > bot.bases.amount + bot.already_pending(self.unit)


class Spawningpool(BuildBuilding):
    name = 'SPAWNINGPOOL'
    unit = SPAWNINGPOOL

class Roachwarren(BuildBuilding):
    name = 'ROACHWARREN'
    unit = ROACHWARREN
    requirements = [SPAWNINGPOOL]

class Hydraliskden(BuildBuilding):
    name = 'HYDRALISKDEN'
    unit = HYDRALISKDEN
    requirements = [SPAWNINGPOOL, LAIR]

class Evolutionchamber(BuildBuilding):
    name = 'EVOLUTIONCHAMBER'
    unit = EVOLUTIONCHAMBER
    requirements = [SPAWNINGPOOL, LAIR]

class Lair(BuildBuilding):
    name = 'LAIR'
    unit = LAIR
    requirements = [HATCHERY, QUEEN]

    async def build(self, bot):
        if bot.can_afford(self.unit):
            await bot.do(bot.hq.build(self.unit))

class Extractor(BuildBuilding):
    name = 'EXTRACTOR'
    unit = EXTRACTOR
    requirements = []

    def prefered_amount(self, bot):
        if not (bot.already_pending(SPAWNINGPOOL) or bot.units(SPAWNINGPOOL).exists) or bot.units(DRONE).amount <= 15 + 10 * bot.units(EXTRACTOR).amount:
            return 0

        return math.floor(1.45 * bot.bases.amount) // 2

    async def build(self, bot):
        if bot.can_afford(EXTRACTOR):
            target = bot.state.vespene_geyser.closest_to(bot.bases.ready.random)
            drone = bot.workers.gathering.closest_to(target)
            await bot.do(drone.build(EXTRACTOR, target))




#######
# UNITS
#######

class BuildUnit(BuildBuilding):
    """ Base for training units for zerg """

    async def build(self, bot):
        """ Override building build function """
        if bot.can_afford(self.unit) and bot.can_feed(self.unit) and bot.units(LARVA).exists:
            await bot.do(bot.units(LARVA).random.train(self.unit))



class Overlord(BuildUnit):
    name = 'OVERLORD'
    unit = OVERLORD
    unit_type = ['supply']

    def prefered_amount(self, bot):
        """ Make sure we always have supply, but don't make too many in the beginning """
        return min(1 + (bot.supply_used - 5) // 9, 1 + 200 // 8)

class Drone(BuildUnit):
    name = 'DRONE'
    unit = DRONE
    unit_type = ['gathering']

    @property
    def priority(self):
        return self.bot.units(self.unit).amount

    def prefered_amount(self, bot):
        """ Build always and change priority if we have many """
        #return min(70, 12 + bot.army.amount * bot.droneArmyRatio , reduce(lambda tot, base: base.ideal_harvesters + tot, bot.townhalls, 0))
        return 80


class Zergling(BuildUnit):
    name = 'ZERGLING'
    unit = ZERGLING
    requirements = [SPAWNINGPOOL]
    unit_type = ['war']

    @property
    def priority(self):
        return 24

    def prefered_amount(self, bot):
        """ We have currently a roach rush, but make some lings to defend """
        return 6

class Roach(BuildUnit):
    name = 'ROACH'
    unit = ROACH
    requirements = [ROACHWARREN]
    unit_type = ['war', 'tank']

    @property
    def priority(self):
        priority = 35
        if self.bot.units(HYDRALISK).amount > 0:
            # Change the value by a tiny bit
            priority += ((self.bot.units(ROACH).amount / self.bot.units(HYDRALISK).amount) - self.bot.roachHydraRatio) * 0.01
        return priority

    def prefered_amount(self, bot):
        """ Build always and change priority if we have many """
        return self.bot.remembered_enemy_units.amount

class Hydralisk(BuildUnit):
    name = 'HYDRALISK'
    unit = HYDRALISK
    requirements = [HYDRALISKDEN]
    unit_type = ['war', 'artillery']

    @property
    def priority(self):
        priority = 70
        if self.bot.units(HYDRALISK).amount > 0:
            # Change the value by a tiny bit
            priority -= ((self.bot.units(ROACH).amount / self.bot.units(HYDRALISK).amount) - self.bot.roachHydraRatio) * 0.01
        return priority

    def prefered_amount(self, bot):
        """ Build always and change priority if we have many """
        return self.bot.remembered_enemy_units.amount



class BuildManager():
    def __init__(self, bot):
        self.bot = bot
        self.units = [Hatchery(bot), Spawningpool(bot), Roachwarren(bot), Hydraliskden(bot), Extractor(bot), Lair(bot), Evolutionchamber(bot), \
                    Overlord(bot), Drone(bot), Zergling(bot), Roach(bot), Hydralisk(bot)]

    async def build(self, logging=False):
        for unit in sorted(self.units, key=lambda unit: unit.priority):
            if await unit.would_build(self.bot):
                if await unit.can_build(self.bot):
                    await unit.build(self.bot)

                    if logging:
                        print('Building ', unit.__class__.__name__, ' at ', self.bot.supply_used)
                return


    async def get_stats(self):
        response = ''
        for unit in self.units:
            response += unit.__class__.__name__ + ': \nPriority: ' + str(unit.priority) + '\nPref amount: ' + str(unit.prefered_amount(self.bot))
            response += '\n'
        return response
        
    def building_done(self, building_id):
        for building in self.units:
            if building.unit == building_id:
                building.under_construction -= 1
                return True
        return False



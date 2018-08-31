from sc2.constants import *
import math

class BuildUnit():
    requirements = []
    priority = -1
    unit = 0

    def __init__(self):
        self.under_construction = 0
    
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


class Hatchery(BuildUnit):
    priority = 2
    unit = HATCHERY
    
    def prefered_amount(self, bot):
        return 1 + 1/16 * bot.units(DRONE).amount

    async def build(self, bot):
        location = await bot.get_next_expansion()

        if bot.can_afford(self.unit):
            await bot.build(self.unit, near=location, max_distance=10, random_alternative=False, placement_step=1)
            self.priority += 0.7 # Make it less priority over time
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
        pending = self.under_construction
        if pending == 0 and bot.already_pending(self.unit):
            pending = 1

        return self.prefered_amount(bot) > bot.bases.amount + pending


class Spawningpool(BuildUnit):
    unit = SPAWNINGPOOL
    priority = 1

class Roachwarren(BuildUnit):
    unit = ROACHWARREN
    requirements = [SPAWNINGPOOL]
    priority = 3

class Hydraliskden(BuildUnit):
    unit = HYDRALISKDEN
    requirements = [SPAWNINGPOOL, LAIR]
    priority = 4

class Evolutionchamber(BuildUnit):
    unit = EVOLUTIONCHAMBER
    requirements = [SPAWNINGPOOL, LAIR]
    priority = 3.5

class Lair(BuildUnit):
    unit = LAIR
    requirements = [HATCHERY, QUEEN]
    priority = 2

    async def build(self, bot):
        if bot.can_afford(self.unit):
            await bot.do(bot.hq.build(self.unit))

class Extractor(BuildUnit):
    unit = EXTRACTOR
    requirements = []
    priority = 3

    def prefered_amount(self, bot):
        if not (bot.already_pending(SPAWNINGPOOL) or bot.units(SPAWNINGPOOL).exists) or bot.units(DRONE).amount <= 15 + 10 * bot.units(EXTRACTOR).amount:
            return 0

        return math.floor(1.45 * bot.bases.amount)

    async def build(self, bot):
        if bot.can_afford(EXTRACTOR):
            target = bot.state.vespene_geyser.closest_to(bot.bases.ready.random)
            drone = bot.workers.gathering.closest_to(target)
            await bot.do(drone.build(EXTRACTOR, target))



class BuildManager():
    def __init__(self, bot):
        self.bot = bot
        self.buildings = [Hatchery(), Spawningpool(), Roachwarren(), Hydraliskden(), Lair(), Extractor(), Evolutionchamber()]

    async def build(self):
        priority = None

        for building in self.buildings:
            if await building.would_build(self.bot) and (priority == None or priority.priority > building.priority):
                priority = building

        # print(priority)

        if priority != None and await priority.can_build(self.bot):
            print('Building ', priority.__class__.__name__)   
            await priority.build(self.bot)
        
    def building_done(self, building_id):
        for building in self.buildings:
            if building.unit == building_id:
                building.under_construction -= 1
                return True
        return False



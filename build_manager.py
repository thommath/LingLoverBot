from sc2.constants import *
import math

class BuildBuilding():
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


class Hatchery(BuildBuilding):
    unit = HATCHERY
    priority = 2
    
    def prefered_amount(self, bot):
        useful_hatcheries = bot.bases.filter(lambda base: base.ideal_harvesters > 8)

        return max(1 + 1/12 * bot.units(DRONE).amount + (bot.bases.amount - useful_hatcheries.amount), bot.bases.amount + bot.minerals // 800)

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

        return self.prefered_amount(bot) > bot.bases.amount + bot.already_pending(self.unit)


class Spawningpool(BuildBuilding):
    unit = SPAWNINGPOOL
    priority = 1

class Roachwarren(BuildBuilding):
    unit = ROACHWARREN
    requirements = [SPAWNINGPOOL]
    priority = 3

class Hydraliskden(BuildBuilding):
    unit = HYDRALISKDEN
    requirements = [SPAWNINGPOOL, LAIR]
    priority = 4

class Evolutionchamber(BuildBuilding):
    unit = EVOLUTIONCHAMBER
    requirements = [SPAWNINGPOOL, LAIR]
    priority = 3.5

class Lair(BuildBuilding):
    unit = LAIR
    requirements = [HATCHERY, QUEEN]
    priority = 2

    async def build(self, bot):
        if bot.can_afford(self.unit):
            await bot.do(bot.hq.build(self.unit))

class Extractor(BuildBuilding):
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
        self.units = [Hatchery(), Spawningpool(), Roachwarren(), Hydraliskden(), Lair(), Extractor(), Evolutionchamber()]

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



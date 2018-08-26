from functools import reduce
from operator import or_
import random

import sc2
from sc2 import Race, Difficulty
from sc2.constants import *
from sc2.player import Bot, Computer
from sc2.data import race_townhalls

import enum

class LingLoverBot(sc2.BotAI):

    roachHydraRatio = 0.7 # 70% roaches


    def select_target(self):
        if self.known_enemy_structures.exists:
            return random.choice(self.known_enemy_structures).position

        return self.enemy_start_locations[0]

    async def on_step(self, iteration):
        # If base exusts update ref
        if not self.townhalls.exists:
            self.hq = self.townhalls.first

        if iteration == 0:
            await self.startUp()

        await self.trainUnits()
        await self.handleBase()

        await self.attack()
        await self.handleQueen()

#        print(self.state.score)

    async def startUp(self):
        if not self.townhalls.exists:
            for unit in self.units(DRONE) | self.units(QUEEN) | forces:
                await self.do(unit.attack(self.enemy_start_locations[0]))
            return
        else:
            self.hq = self.townhalls.first

    async def attack(self):
        forces = self.units(ZERGLING) | self.units(HYDRALISK)

        if self.units(HYDRALISK).amount > 10 and iteration % 50 == 0:
            for unit in forces.idle:
                await self.do(unit.attack(self.select_target()))

    def can_feed(self, unit_type: UnitTypeId) -> bool:
        """ Checks if you have enough free supply to build the unit """
        return self.supply_left >= self._game_data.units[unit_type.value]._proto.food_required

    async def trainUnits(self):
        larvae = self.units(LARVA)

        if self.supply_left < 2 + self.supply_used*0.1 and self.supply_cap < 200:
            if self.can_afford(OVERLORD) and larvae.exists:
                await self.do(larvae.random.train(OVERLORD))

        if self.hq.assigned_harvesters < self.hq.ideal_harvesters and self.units(DRONE).amount < 70: # Not working propperly needs to be for each hatchery 
            if self.can_afford(DRONE) and larvae.exists and self.can_feed(DRONE):
                await self.do(larvae.random.train(DRONE))
                return
        
        if self.units(SPAWNINGPOOL).ready and self.can_feed(ZERGLING) and not self.units(ROACHWARREN).ready:
            if larvae.exists and self.can_afford(ZERGLING):
                await self.do(larvae.random.train(ZERGLING))
                return


        if self.units(ROACHWARREN).ready:
            if self.can_afford(ROACH) and larvae.exists and self.can_feed(ROACH) and self.units(HYDRALISK).amount > 0 and self.units(ROACH).amount/self.units(HYDRALISK).amount > roachHydraRatio:
                await self.do(larvae.random.train(ROACH))
                return

        if self.units(HYDRALISKDEN).ready:
            if self.can_afford(HYDRALISK) and larvae.exists and self.can_feed(HYDRALISK) and self.units(HYDRALISK).amount > 0 and self.units(ROACH).amount/self.units(HYDRALISK).amount <= roachHydraRatio:
                await self.do(larvae.random.train(HYDRALISK))
                return


    async def on_unit_created(self, unit):
        """ Override this in your bot class. """
        pass

    async def on_building_construction_complete(self, unit):
        """ Override this in your bot class. """
        pass

    async def handleQueen(self):

        if self.units(SPAWNINGPOOL).ready and self.units(QUEEN).amount < self.units(HATCHERY).amount and self.units(HATCHERY).exists and self.units(HATCHERY)[-1].noqueue and self.can_feed(QUEEN):
            if self.can_afford(QUEEN):
                await self.do(self.units(HATCHERY)[-1].train(QUEEN))
                return

        for queen in self.units(QUEEN).idle:
            abilities = await self.get_available_abilities(queen)
            if AbilityId.EFFECT_INJECTLARVA in abilities:
                await self.do(queen(EFFECT_INJECTLARVA, self.units(HATCHERY).closest_to(queen)))


    async def handleBase(self):

        # Handle extractors
        for a in self.units(EXTRACTOR):
            if a.assigned_harvesters < a.ideal_harvesters:
                w = self.workers.closer_than(20, a)
                if w.exists:
                    await self.do(w.random.gather(a))

        # Handle expanding
        if not self.already_pending(HATCHERY) and self.units(HATCHERY).amount < 3 and self.can_afford(HATCHERY) and self.units(DRONE).amount > 15*self.units(HATCHERY).amount:
            await self.expand_now()

        
        if not (self.units(SPAWNINGPOOL).exists or self.already_pending(SPAWNINGPOOL)):
            if self.can_afford(SPAWNINGPOOL):
                await self.build(SPAWNINGPOOL, near=self.hq)
                
        if (self.already_pending(SPAWNINGPOOL) or self.units(SPAWNINGPOOL).exists) and self.units(EXTRACTOR).amount < 2 and not self.already_pending(EXTRACTOR):
            if self.can_afford(EXTRACTOR):
                target = self.state.vespene_geyser.closest_to(self.hq)
                drone = self.workers.closest_to(target)
                err = await self.do(drone.build(EXTRACTOR, target))

        if self.units(SPAWNINGPOOL).ready and not (self.units(ROACHWARREN).exists or self.already_pending(ROACHWARREN)):
            if self.can_afford(ROACHWARREN):
                await self.build(ROACHWARREN, near=self.hq)


        if self.units(QUEEN).amount > 0 and not (self.units(LAIR).exists or self.already_pending(LAIR)):
            if self.can_afford(LAIR):
                await self.do(self.hq.build(LAIR))


        if self.units(LAIR).ready and not (self.units(HYDRALISKDEN).exists or self.already_pending(HYDRALISKDEN)):
            if self.can_afford(HYDRALISKDEN):
                await self.build(HYDRALISKDEN, near=self.hq)


        await self.distribute_workers()


    async def a():

        if not (self.units(SPAWNINGPOOL).exists or self.already_pending(SPAWNINGPOOL)):
            if self.can_afford(SPAWNINGPOOL):
                await self.build(SPAWNINGPOOL, near=self.hq)

        if self.units(SPAWNINGPOOL).ready.exists:
            if not self.units(LAIR).exists and self.hq.noqueue:
                if self.can_afford(LAIR):
                    await self.do(self.hq.build(LAIR))

        if self.units(LAIR).ready.exists:
            if not (self.units(HYDRALISKDEN).exists or self.already_pending(HYDRALISKDEN)):
                if self.can_afford(HYDRALISKDEN):
                    await self.build(HYDRALISKDEN, near=self.hq)

        if self.units(EXTRACTOR).amount < 2 and not self.already_pending(EXTRACTOR):
            if self.can_afford(EXTRACTOR):
                drone = self.workers.random
                target = self.state.vespene_geyser.closest_to(drone.position)
                err = await self.do(drone.build(EXTRACTOR, target))

        if self.units(SPAWNINGPOOL).ready.exists:
            if not self.units(QUEEN).exists and self.hq.is_ready and self.hq.noqueue:
                if self.can_afford(QUEEN):
                    await self.do(self.hq.train(QUEEN))

    def get_game_center_random(self, offset_x=50, offset_y=50):
        x = self.game_info.map_center.x
        y = self.game_info.map_center.y

        rand = random.random()
        if rand < 0.2:
            x += offset_x
        elif rand < 0.4:
            x -= offset_x
        elif rand < 0.6:
            y += offset_y
        elif rand < 0.8:
            y -= offset_y

    def get_base_build_location(self, base, min_distance=10, max_distance=20):
        return base.position.towards(self.get_game_center_random(), random.randrange(min_distance, max_distance))



        # Approximate army value by adding unit health+shield
    def friendly_army_value(self, position, distance=10):
        value = 0

        for unit in self.units.not_structure.filter(lambda unit: unit.type_id not in self.units_to_ignore).closer_than(distance, position):
            value += unit.health + unit.shield

        # Count nearby cannons
        for unit in self.units(PHOTONCANNON).closer_than(10, position):
            value += unit.health # Skip shield, to not overestimate

        # Count nearby bunkers
        for unit in self.units(BUNKER).ready.closer_than(10, position):
            value += unit.health

        # Count nearby spine crawlers
        for unit in self.units(SPINECRAWLER).ready.closer_than(10, position):
            value += unit.health

        return value

    # Approximate army value by adding unit health+shield
    def enemy_army_value(self, position, distance=10):
        value = 0

        for unit in self.remembered_enemy_units.ready.not_structure.filter(lambda unit: unit.type_id not in self.units_to_ignore).closer_than(distance, position):
            value += unit.health + unit.shield

            # Add extra army value for marine/marauder, to not under-estimate
            if unit.type_id in [MARINE, MARAUDER]:
                value += 20

        # Count nearby cannons
        for unit in self.remembered_enemy_units(PHOTONCANNON).ready.closer_than(10, position):
            value += unit.health # Skip shield, to not overestimate

        # Count nearby bunkers
        for unit in self.remembered_enemy_units(BUNKER).ready.closer_than(10, position):
            value += unit.health

        # Count nearby spine crawlers
        for unit in self.remembered_enemy_units(SPINECRAWLER).ready.closer_than(10, position):
            value += unit.health

        return value

def main():
    sc2.run_game(sc2.maps.get("Abyssal Reef LE"), [
        Bot(Race.Zerg, LingLoverBot()),
        Computer(Race.Terran, Difficulty.Medium)
    ], realtime=False, save_replay_as="ZvT.SC2Replay")

if __name__ == '__main__':
    main()


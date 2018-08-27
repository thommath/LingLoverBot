from functools import reduce
from operator import or_
import random, math, asyncio
from typing import List, Dict, Set, Tuple, Any, Optional, Union # mypy type checking
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.ids.upgrade_id import UpgradeId
from sc2.units import Units
import sc2
from sc2 import Race, Difficulty
from sc2.constants import *
from sc2.player import Bot, Computer
from sc2.data import race_townhalls
from sc2.unit import Unit
from base_bot import BaseBot
from sc2.position import Point2, Point3
import enum

##
## Inspired by Cannon lover bot 
##

###
#
# Todos 
# Start with only one overlord 
# Upgrades
# Invis units
# Improve focus and kiting back and forth 
# Fight units on higher ground
# On lost base build army to withstand another attack
# If at home, attack
#
###



class LingLoverBot(BaseBot):

    units_to_ignore = [DRONE, SCV, PROBE, EGG, LARVA, OVERLORD, OVERSEER, OBSERVER, BROODLING, INTERCEPTOR, MEDIVAC, CREEPTUMOR, CREEPTUMORBURROWED, CREEPTUMORQUEEN, CREEPTUMORMISSILE]
    roachHydraRatio = 0.6 # 70% roaches
    droneArmyRatio = 0.4
    army_size_minimum = 20
    start_location = None


    def select_target(self):
        if self.known_enemy_structures.exists:
            return random.choice(self.known_enemy_structures).position

        return self.enemy_start_locations[0]

    async def on_step(self, iteration):
        self.combinedActions = []
        # If base exusts update ref
        if not self.townhalls.exists:
            self.hq = self.townhalls.first

        self.bases = self.units(HATCHERY) | self.units(LAIR)
        self.army = self.units(ZERGLING) | self.units(ROACH) | self.units(HYDRALISK)


        self.remember_enemy_units()
        self.remember_friendly_units()
        await self.cancel_buildings() # Make sure to cancel buildings under construction that are under attack
        
        if iteration == 0:
            await self.startUp()

        if iteration % 25 == 0:
            await self.distribute_workers()

        self.trainUnits()
        await self.handleBase()

        await self.handleQueen()
        
        self.move_army()

        await self.do_actions(self.combinedActions)


#        print(self.state.score)


    # Only run once at game start
    async def startUp(self):
        # Say hello!
        await self.chat_send("(probe)(pylon)(cannon)(cannon)(gg)")

        # Save base locations for later
        self.start_location = self.units(HATCHERY).first.position
        self.enemy_natural = await self.find_enemy_natural()

        self.bases_under_construction = 0
        self.combinedActions = []

        self.hq = self.townhalls.first


    def can_feed(self, unit_type: UnitTypeId) -> bool:
        """ Checks if you have enough free supply to build the unit """
        return self.supply_left >= self._game_data.units[unit_type.value]._proto.food_required


    def trainUnits(self):
        larvae = self.units(LARVA)

        if larvae.exists:
            # Make sure we have supply 
            if self.supply_left < 2 + self.supply_used*0.1 and self.already_pending(OVERLORD) < 2 and self.supply_cap < 200:
                if self.can_afford(OVERLORD) and larvae.exists:
                    self.combinedActions.append(larvae.random.train(OVERLORD))
                    return

            # Make drone if we have sufficently large army
            if self.units(DRONE).amount < 70 and self.units(DRONE).amount < self.bases.amount * 16 and self.army.amount + 10 >= self.units(DRONE).amount * self.droneArmyRatio:
                if self.can_afford(DRONE) and self.can_feed(DRONE):
                    self.combinedActions.append(larvae.random.train(DRONE))

            # Make lings until roaches are available
            elif self.units(SPAWNINGPOOL).ready and self.can_feed(ZERGLING) and not self.units(ROACHWARREN).ready:
                if larvae.exists and self.can_afford(ZERGLING):
                    self.combinedActions.append(larvae.random.train(ZERGLING))

            # Make roaches until hydra is possible or the ratio is in favor of hydra
            elif self.units(ROACHWARREN).ready and (not self.units(HYDRALISKDEN).ready or self.units(HYDRALISK).amount > 0 and self.units(ROACH).amount/self.units(HYDRALISK).amount > self.roachHydraRatio):
                if self.can_afford(ROACH) and self.can_feed(ROACH):
                    self.combinedActions.append(larvae.random.train(ROACH))

            elif self.units(HYDRALISKDEN).ready and (self.units(HYDRALISK).amount <= 0 or self.units(ROACH).amount/self.units(HYDRALISK).amount <= self.roachHydraRatio):
                if self.can_afford(HYDRALISK) and self.can_feed(HYDRALISK):
                    self.combinedActions.append(larvae.random.train(HYDRALISK))



    async def handleQueen(self):
        if self.units(SPAWNINGPOOL).ready and self.units(QUEEN).amount < self.units(HATCHERY).amount and self.units(HATCHERY).exists and self.units(HATCHERY)[-1].noqueue and self.can_feed(QUEEN):
            if self.can_afford(QUEEN):
                self.combinedActions.append(self.units(HATCHERY)[-1].train(QUEEN))
                return

        for queen in self.units(QUEEN).idle:
            abilities = await self.get_available_abilities(queen)
            if AbilityId.EFFECT_INJECTLARVA in abilities:
                self.combinedActions.append(queen(EFFECT_INJECTLARVA, self.bases.closest_to(queen)))

    def on_building_construction_complete(self, unit):
        if unit.type_id == HATCHERY:
            self.bases_under_construction -= 1
            print('base done')
        print(unit.type_id)


    async def handleBase(self):

        expand_every = 2.5 * 60 # Seconds
        prefered_base_count = 1 + int(math.floor(self.get_game_time() / expand_every))
        prefered_base_count = max(prefered_base_count, 2) # Take natural ASAP (i.e. minimum 2 bases)
        current_base_count = self.bases.ready.filter(lambda unit: unit.ideal_harvesters >= 10).amount + self.bases_under_construction# Only count bases as active if they have at least 10 ideal harvesters (will decrease as it's mined out)

        # Handle extractors
        for a in self.units(EXTRACTOR):
            if a.assigned_harvesters < a.ideal_harvesters:
                w = self.workers.closer_than(20, a)
                if w.exists:
                    self.combinedActions.append(w.random.gather(a))
        
        # manage idle drones, would be taken care by distribute workers aswell
        if self.townhalls.exists:
            for w in self.workers.idle:
                th = self.townhalls.closest_to(w)
                mfs = self.state.mineral_field.closer_than(10, th)
                if mfs:
                    mf = mfs.closest_to(w)
                    self.combinedActions.append(w.gather(mf))

        # Also add an extra expansion if minerals get too high
        if self.minerals > 800:
            prefered_base_count += 1
        
        # Handle expanding
        if current_base_count < prefered_base_count and await self.can_take_expansion():
            if self.can_afford(HATCHERY):
                print('expanding')
                self.bases_under_construction += 1
                await self.expand_now()
        
        # Make spawnpool
        elif not (self.units(SPAWNINGPOOL).exists or self.already_pending(SPAWNINGPOOL)):
            if self.can_afford(SPAWNINGPOOL):
                await self.build(SPAWNINGPOOL, near=self.hq)
        
        # Make extractors
        elif (self.already_pending(SPAWNINGPOOL) or self.units(SPAWNINGPOOL).exists) and self.units(EXTRACTOR).amount < math.floor(1.5 * self.bases.amount) and not self.already_pending(EXTRACTOR) and self.units(DRONE).amount > 15:
            if self.can_afford(EXTRACTOR):
                target = self.state.vespene_geyser.closest_to(self.bases.random)
                drone = self.workers.closest_to(target)
                err = self.combinedActions.append(drone.build(EXTRACTOR, target))

        # Make roachwarren
        elif self.units(SPAWNINGPOOL).ready and not (self.units(ROACHWARREN).exists or self.already_pending(ROACHWARREN)):
            if self.can_afford(ROACHWARREN):
                await self.build(ROACHWARREN, near=self.hq)

        # Make lair if we have one queen
        elif self.units(QUEEN).amount > 0 and not (self.units(LAIR).exists or self.already_pending(LAIR)) and self.units(ROACH).amount > 10:
            if self.can_afford(LAIR):
                self.combinedActions.append(self.hq.build(LAIR))

        # Make hydra den if we have lair
        elif self.units(LAIR).ready and not (self.units(HYDRALISKDEN).exists or self.already_pending(HYDRALISKDEN)):
            if self.can_afford(HYDRALISKDEN):
                await self.build(HYDRALISKDEN, near=self.hq)


    async def expand_now(self, building: UnitTypeId=None, max_distance: Union[int, float]=10, location: Optional[Point2]=None):
        """Takes new expansion."""

        if not building:
            # self.race is never Race.Random
            start_townhall_type = {Race.Protoss: UnitTypeId.NEXUS, Race.Terran: UnitTypeId.COMMANDCENTER, Race.Zerg: UnitTypeId.HATCHERY}
            building = start_townhall_type[self.race]

        assert isinstance(building, UnitTypeId)

        if not location:
            location = await self.get_next_expansion()

        if self.can_afford(building):
            await self.build(building, near=location, max_distance=max_distance, random_alternative=False, placement_step=1)


    async def can_take_expansion(self):
        # Must have a valid exp location
        location = await self.get_next_expansion()
        if not location:
            return False

        # Must not have enemies nearby
        if self.remembered_enemy_units.closer_than(10, location).exists:
            return False

        # Must be able to find a valid building position
        if self.can_afford(HATCHERY):
            position = await self.find_placement(HATCHERY, location.rounded, max_distance=10, random_alternative=False, placement_step=1)
            if not position:
                return False

        return True


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


    # Movement and micro for army
    def move_army(self):
        army_units = self.units(ZERGLING).ready | self.units(ROACH).ready | self.units(HYDRALISK).ready | self.units(ULTRALISK).ready
        army_count = army_units.amount
        home_location = self.start_location
        focus_fire_target = None
        attack_random_exp = False
        attack_location = None

        # Determine attack location
        if army_count < self.army_size_minimum:
            # We have less than self.army_size_minimum army in total. Just gather at rally point
            attack_location = self.get_rally_location()

        ## TODO Only attack if the enemy is close to our structures or we have a bug army 

        if self.remembered_enemy_units.filter(lambda unit: unit.type_id not in self.units_to_ignore).exists:
            # We have large enough army and have seen an enemy. Attack closest enemy to home
            attack_location = self.remembered_enemy_units.filter(lambda unit: unit.type_id not in self.units_to_ignore).closest_to(home_location).position
        else:
            # We have not seen an enemy
            #if random.random() < 0.8:
                # Try move to random enemy start location 80% of time
            #    attack_location = random.choice(self.enemy_start_locations) #self.enemy_start_locations[0]
            #else:
                # As a last resort, scout different expansions with army units
            attack_random_exp = True

        for unit in army_units:
            nearby_enemy_units = self.remembered_enemy_units.not_structure.filter(lambda unit: unit.type_id not in self.units_to_ignore).closer_than(15, unit)

            # If we don't have any nearby enemies
            if not nearby_enemy_units.exists:
                # If we don't have an attack order, cast one now
                if not self.has_order(ATTACK, unit) or (self.known_enemy_units.exists and not self.has_target(attack_location, unit)):
                    if attack_random_exp:
                        # If we're attacking a random exp, find one now
                        random_exp_location = random.choice(list(self.expansion_locations.keys()))
                        self.combinedActions.append(unit.attack(random_exp_location))
                        #print("Attack random exp")
                    elif unit.distance_to(attack_location) > 10:
                        self.combinedActions.append(unit.attack(attack_location))
                        #print("Attack no enemy nearby")
                
                continue # Do no further micro
                
            
            friendly_army_value = self.friendly_army_value(unit, 10) #20
            enemy_army_value = self.enemy_army_value(nearby_enemy_units.closest_to(unit), 10) #30
            army_advantage = friendly_army_value - enemy_army_value

            # If our shield is low, escape a little backwards
#            if unit.is_taking_damage and unit.shield < 20 and unit.type_id not in [ZEALOT]:
#                escape_location = unit.position.towards(home_location, 4)
#                if has_blink:
#                    # Stalkers can blink
#                    await self.order(unit, EFFECT_BLINK_STALKER, escape_location)
#                else:
                    # Others can move normally
#                    if not self.has_order(MOVE, unit):
#                        self.combinedActions.append(unit.move(escape_location))

#                continue

            # Do we have an army advantage?
            if army_advantage > 0:
                # We have a larger army. Engage enemy
                attack_position = nearby_enemy_units.closest_to(unit).position

                # If not already attacking, attack
                if not self.has_order(ATTACK, unit) or not self.has_target(attack_position, unit):
                    self.combinedActions.append(unit.attack(attack_position))
                
                # Activate guardian shield for sentries (if enemy army value is big enough)
#                if has_guardianshield and enemy_army_value > 200:
#                    await self.order(unit, GUARDIANSHIELD_GUARDIANSHIELD)
            else:
                # Others can move normally
                if not self.has_order(MOVE, unit):
                    self.combinedActions.append(unit.move(home_location))

    async def micro():
        # Micro for each individual army unit
        for unit in army_units:
            # Find nearby enemy units
            nearby_enemy_units = self.remembered_enemy_units.not_structure.filter(lambda unit: unit.type_id not in self.units_to_ignore).closer_than(15, unit)

            # If we don't have any nearby enemies
            if not nearby_enemy_units.exists:
                # If we don't have an attack order, cast one now
                if not self.has_order(ATTACK, unit) or (self.known_enemy_units.exists and not self.has_target(attack_location, unit)):
                    if attack_random_exp:
                        # If we're attacking a random exp, find one now
                        random_exp_location = random.choice(list(self.expansion_locations.keys()))
                        self.combinedActions.append(unit.attack(random_exp_location))
                        #print("Attack random exp")
                    elif unit.distance_to(attack_location) > 10:
                        self.combinedActions.append(unit.attack(attack_location))
                        #print("Attack no enemy nearby")
                
                continue # Do no further micro

            # Calculate friendly vs enemy army value
            friendly_army_value = self.friendly_army_value(unit, 10) #20
            enemy_army_value = self.enemy_army_value(nearby_enemy_units.closest_to(unit), 10) #30
            army_advantage = friendly_army_value - enemy_army_value

            # If our shield is low, escape a little backwards
#            if unit.is_taking_damage and unit.shield < 20 and unit.type_id not in [ZEALOT]:
#                escape_location = unit.position.towards(home_location, 4)
#                if has_blink:
#                    # Stalkers can blink
#                    await self.order(unit, EFFECT_BLINK_STALKER, escape_location)
#                else:
                    # Others can move normally
#                    if not self.has_order(MOVE, unit):
#                        self.combinedActions.append(unit.move(escape_location))

#                continue

            # Do we have an army advantage?
            if army_advantage > 0:
                # We have a larger army. Engage enemy
                attack_position = nearby_enemy_units.closest_to(unit).position

                # If not already attacking, attack
                if not self.has_order(ATTACK, unit) or not self.has_target(attack_position, unit):
                    self.combinedActions.append(unit.attack(attack_position))
                
                # Activate guardian shield for sentries (if enemy army value is big enough)
#                if has_guardianshield and enemy_army_value > 200:
#                    await self.order(unit, GUARDIANSHIELD_GUARDIANSHIELD)
            else:
                # Others can move normally
                if not self.has_order(MOVE, unit):
                    self.combinedActions.append(unit.move(home_location))



    def get_rally_location(self):
        if self.units(HATCHERY).ready.exists:
            rally_location = self.units(HATCHERY).center
        else:
            rally_location = self.start_location
        return rally_location


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
            if unit.type_id in [MARINE, MARAUDER, SIEGETANK]:
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
        Computer(Race.Protoss, Difficulty.VeryHard)
    ], realtime=False, save_replay_as="ZvT.SC2Replay")

if __name__ == '__main__':
    main()


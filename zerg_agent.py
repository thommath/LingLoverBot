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
from sc2.position import Point2, Point3
import enum

from .base_bot import BaseBot
from .build_manager import *
from .unit_manager import *

##
## Inspired by Cannon lover bot 
##

###
#
# Todos 
# Start with only one overlord 
# Invis units
# Fight units on higher ground
# On lost base build army to withstand another attack
# Scout
# If early aggression decrese droneArmyRatio #important #machineLearning
# Implement 70-30 attack for when maxed out 
# Bring overlords into fights for vision
# Add more units it can build
# Don't walk past enemies
# Cheese defence
#
# Kind of done
# Upgrades
# 
# Done
# Improve focus and kiting back and forth 
# If at home, attack
###



class LingLoverBot(BaseBot):

    units_to_ignore = [DRONE, SCV, PROBE, EGG, LARVA, OVERLORD, OVERSEER, OBSERVER, BROODLING, INTERCEPTOR, MEDIVAC, CREEPTUMOR, CREEPTUMORBURROWED, CREEPTUMORQUEEN, CREEPTUMORMISSILE]
    roachHydraRatio = 0.7 # 70% roaches
    droneArmyRatio = 1 # Risk level
    army_size_minimum = 20
    start_location = None
    min_enemy_army_value = 0

    async def on_step(self, iteration):
        if iteration == 0:
            await self.startUp()

        self.combinedActions = []

        # If base exusts update ref
        if not self.hq:
            self.hq = self.townhalls.first

        self.bases = self.units(HATCHERY) | self.units(LAIR)
        self.army = self.units(ZERGLING) | self.units(ROACH) | self.units(HYDRALISK)


        self.remember_enemy_units()
        self.min_enemy_army_value = self.enemy_army_value()
        self.remember_friendly_units()
        self.our_army_value = self.friendly_army_value()
        self.diff_army_value = self.min_enemy_army_value - self.our_army_value

        await self.cancel_buildings() # Make sure to cancel buildings under construction that are under attack
        

        if iteration % 25 == 0:
            await self.distribute_workers()
#            print(list(map(lambda unit: unit.__class__.__name__ + ' ' + str(unit.priority), sorted(self.unit_build_manager.units, key=lambda unit: unit.priority))))


        await self.unit_build_manager.build()

        await self.handleBase()
        await self.build_manager.build(logging=True)

        await self.handleQueen()
        
        await self.handleUpgrades()

        await self.scout()

        self.move_army()
        await self.do_actions(self.combinedActions)


    # Only run once at game start
    async def startUp(self):
        # Say hello!
        #await self.chat_send("(drone)(roach)(roach)(roach)(roach)(roach)(roach)(roach)(roach)(roach)(roach)(gg)")

        # Save base locations for later
        self.start_location = self.units(HATCHERY).first.position
        self.enemy_natural = await self.find_enemy_natural()

        self.bases_under_construction = 0
        self.combinedActions = []
        self.diff_army_value = 0
        self.unit_build_manager = UnitBuildManager(self)
        self.build_manager = BuildManager(self)

        self.hq = self.townhalls.first


    async def scout(self):
        if self.units(OVERLORD).amount == 1 and self.units(OVERLORD).first.is_idle:
            self.combinedActions.append(self.units(OVERLORD).first.move(self._game_info.start_locations[0]))


    async def handleQueen(self):
        if self.units(SPAWNINGPOOL).ready and self.units(QUEEN).amount < self.units(HATCHERY).amount and self.units(HATCHERY).exists and self.units(HATCHERY)[-1].noqueue and self.can_feed(QUEEN):
            if self.can_afford(QUEEN):
                self.combinedActions.append(self.units(HATCHERY)[-1].train(QUEEN))
                return

        for queen in self.units(QUEEN).idle:
            abilities = await self.get_available_abilities(queen)
            if AbilityId.EFFECT_INJECTLARVA in abilities:
                self.combinedActions.append(queen(EFFECT_INJECTLARVA, self.bases.closest_to(queen)))


    async def handleBase(self):

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
    

    async def handleUpgrades(self):
        if self.units(EVOLUTIONCHAMBER).ready.exists:
            evo = self.units(EVOLUTIONCHAMBER).first
            abilities = await self.get_available_abilities(evo)
            
            if evo.noqueue and len(abilities) > 0 and RESEARCH_ZERGGROUNDARMORLEVEL1  in abilities:
                if self.can_afford(RESEARCH_ZERGGROUNDARMORLEVEL1):
                    self.combinedActions.append(evo(RESEARCH_ZERGGROUNDARMORLEVEL1))
            
            elif evo.noqueue and len(abilities) > 0 and RESEARCH_ZERGMISSILEWEAPONSLEVEL1 in abilities:
                if self.can_afford(RESEARCH_ZERGMISSILEWEAPONSLEVEL1):
                    self.combinedActions.append(evo(RESEARCH_ZERGMISSILEWEAPONSLEVEL1))
            
            elif evo.noqueue and len(abilities) > 0 and RESEARCH_ZERGGROUNDARMORLEVEL2 in abilities:
                if self.can_afford(RESEARCH_ZERGGROUNDARMORLEVEL2):
                    self.combinedActions.append(evo(RESEARCH_ZERGGROUNDARMORLEVEL2))
            
            elif evo.noqueue and len(abilities) > 0 and RESEARCH_ZERGMISSILEWEAPONSLEVEL2 in abilities:
                if self.can_afford(RESEARCH_ZERGMISSILEWEAPONSLEVEL2):
                    self.combinedActions.append(evo(RESEARCH_ZERGMISSILEWEAPONSLEVEL2))
            
            elif evo.noqueue and len(abilities) > 0 and RESEARCH_ZERGGROUNDARMORLEVEL3 in abilities:
                if self.can_afford(RESEARCH_ZERGGROUNDARMORLEVEL3):
                    self.combinedActions.append(evo(RESEARCH_ZERGGROUNDARMORLEVEL3))
            
            elif evo.noqueue and len(abilities) > 0 and RESEARCH_ZERGMISSILEWEAPONSLEVEL3 in abilities:
                if self.can_afford(RESEARCH_ZERGMISSILEWEAPONSLEVEL3):
                    self.combinedActions.append(evo(RESEARCH_ZERGMISSILEWEAPONSLEVEL3))
        
        # Overlord speed



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
            if army_advantage > 0 or unit.distance_to(home_location) < 6:
                # We have a larger army. Engage enemy
                attack_position = nearby_enemy_units.closest_to(unit).position
                possible_targets = nearby_enemy_units.in_attack_range_of(unit)
                targets = possible_targets.sorted(lambda u: u.ground_dps + 10/u.health_percentage, True)

                # Only micro kite inwards if x% bigger army
                if unit.weapon_cooldown > 0 and friendly_army_value - enemy_army_value * 1.10 > 0:
                    if len(targets) > 0:
                        self.combinedActions.append(unit.move(targets[0].position))
                    else:
                        self.combinedActions.append(unit.move(attack_position))

                else:

                    if len(targets) > 0:
                        self.combinedActions.append(unit.attack(targets[0]))

                    # If not already attacking, attack
                    elif not self.has_order(ATTACK, unit) or not self.has_target(attack_position, unit):
                        self.combinedActions.append(unit.attack(attack_position))
                    
            else:
                # Others can move normally
                if not self.has_order(MOVE, unit):
                    self.combinedActions.append(unit.move(home_location))



    def on_building_construction_complete(self, unit):
        if not self.build_manager.building_done(unit.type_id):
            print('Building not recognized', unit.type_id)

    def get_rally_location(self):
        if self.units(HATCHERY).ready.exists:
            rally_location = self.units(HATCHERY).center
        else:
            rally_location = self.start_location
        return rally_location


        # Approximate army value by adding unit health+shield
    def friendly_army_value(self, position=None, distance=10):
        value = 0

        units = self.units(ZERGLING).ready | self.units(ROACH).ready | self.units(HYDRALISK).ready | self.units(ULTRALISK).ready
        if position:
            units = units.closer_than(distance, position)

        for unit in units:
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
    def enemy_army_value(self, position=None, distance=10):
        value = 0

        units = self.remembered_enemy_units.ready.not_structure.filter(lambda unit: unit.type_id not in self.units_to_ignore)
        if position:
            units = units.closer_than(distance, position)

        for unit in units:
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


    def can_feed(self, unit_type: UnitTypeId) -> bool:
        """ Checks if you have enough free supply to build the unit """
        return self.supply_left >= self._game_data.units[unit_type.value]._proto.food_required


def main():
    sc2.run_game(sc2.maps.get("Abyssal Reef LE"), [
        Bot(Race.Zerg, LingLoverBot()),
        Computer(Race.Protoss, Difficulty.VeryHard)
    ], realtime=False, save_replay_as="ZvT.SC2Replay")

if __name__ == '__main__':
    main()


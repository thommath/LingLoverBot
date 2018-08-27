import json
import sc2
from sc2.constants import *
from sc2.data import Race
import random
from sc2.position import Point2
import itertools

FLOAT_DIGITS = 8
EPSILON = 10**(-FLOAT_DIGITS)
def eq(self, other):
    if not isinstance(other, tuple):
        return False
    return all(abs(a - b) < EPSILON for a, b in itertools.zip_longest(self, other, fillvalue=0))

sc2.position.Pointlike.__eq__ = eq

def get_unitlist(enemyrace):
    data = {
        'Race.Terran':  'builds/unitlist_pvt.json',
        'Race.Protoss':  'builds/unitlist_pvp.json',
        'Race.Zerg':  'builds/unitlist_pvz.json',
        'Race.Random':  'builds/unitlist_pvr.json'
    }

    with open(data.get(enemyrace)) as src:
        return json.load(src)

def get_buildorder(enemyrace):
    data = {
        'Race.Terran':  'builds/buildorder_pvt.json',
        'Race.Protoss':  'builds/buildorder_pvp.json',
        'Race.Zerg':  'builds/buildorder_pvz.json',
        'Race.Random':  'builds/buildorder_pvr.json'
    }

    with open(data.get(enemyrace)) as src:
        return json.load(src)
    
    
class m1ndb0t(sc2.BotAI):
    def __init__(self):
        self.warpgate_started = False
        self.blink_started = False
        self.blink_done = False
        
        self.exlance_started = False

        self.shield_built = False
        self.unitInfo = {}
        self.fightstarted = False
        self.enemyrace = "Unknown"
        self.enemy_id = 3
        self.attacked = False
        self.microActions = []
        self.targetunits = []
        self.coreboosted = False
        self.ramp_built = False
        self.ramp_location = False
        
        self.cheese_towerrush = False
        
        self.forcewarpprismraid = False
        self.prismready = False
        
        self.keepminerals = False
        self.keepgas = False
        self.keepminerals_amount = 0
        self.keepgas_amount = 0
        
        self.buildaproxy = False
        self.proxy_built = False
        
        self.pylonthreshold = 7
        
        self.attack_count = 20
        self.retreat_count = 5

        self.my_armypower = 0
        self.enemy_armypower = 0
        self.enemy_income = 0

    async def do_actions(self, actions):     
        for action in actions:
            cost = self._game_data.calculate_ability_cost(action.ability)
            self.minerals -= cost.minerals
            self.vespene -= cost.vespene

        r = await self._client.actions(actions, game_data=self._game_data)
        return r


    async def racecheck(self):
        if self.player_id == 1:
            self.enemy_id = 2
        else:
            self.enemy_id = 1
        self.enemyrace = Race(self._game_info.player_races[self.enemy_id])

        if self.enemyrace == "Race.Terran":
            self.buildaproxy = False
            self.attack_count = 20
            self.retreat_count = 5
        elif self.enemyrace == "Race.Protoss":
            self.buildaproxy = True
            self.attack_count = 20
            self.retreat_count = 5
        elif self.enemyrace == "Race.Zerg":
            self.buildaproxy = False
            self.attack_count = 8
            self.retreat_count = 2
        elif (self.enemyrace == "Race.Random") or (self.enemyrace == "Unknown"):
            self.buildaproxy = True
            self.attack_count = 20
            self.retreat_count = 5


    async def buildatramp(self):
        if self.can_afford(UnitTypeId.PYLON) and not self.ramp_built:
            pos = self.main_base_ramp.top_center.position
            nx = self.units(UnitTypeId.NEXUS).ready.first.position
            p = pos.towards(nx, 1)
            await self.build(UnitTypeId.PYLON, near=p)
            self.ramp_built = True
            self.ramp_location = p
            return


    async def buildproxy(self):
        if self.units(UnitTypeId.CYBERNETICSCORE).amount >= 1 and not self.proxy_built and self.can_afford(UnitTypeId.PYLON):
            p = self.game_info.map_center.towards(self.enemy_start_locations[0], random.randrange(25, 30))
            await self.build(UnitTypeId.PYLON, near=p)
            self.proxy_built = True
            return


    async def prismraid(self):
        if self.units(UnitTypeId.WARPPRISM):
            self.forcewarpprismraid = False
            
            self.keepminerals = True
            self.keepgas = True
            self.keepminerals_amount = (self.units(UnitTypeId.WARPGATE).amount * 150)
            self.keepgas_amount = (self.units(UnitTypeId.WARPGATE).amount * 50)
    
            if ((self.keepminerals_amount > self.minerals) and (self.keepgas_amount > self.vespene)):
                self.prismready = True
            
        if self.units(UnitTypeId.WARPPRISM).ready.idle:
            p = self.enemy_start_locations[0].towards(self.game_info.map_center, random.randrange(1, 10))
            for u in self.units(UnitTypeId.WARPPRISM).ready.idle:
                distance = u.position.distance_to(self.enemy_start_locations[0])
                if distance < 30:
                    self.microActions.append(u.move(p.position))
                else:
                    #if self.prismready:
                    await self.do(u(AbilityId.MORPH_WARPPRISMPHASINGMODE))


    async def scoutroutine(self):
        observers = self.units(UnitTypeId.OBSERVER).ready
        if not observers:
            return
        
        for observer in observers:
            scoutqueue = len(observer.orders)
            if scoutqueue == 0:
                await self.do(observer.move(self.enemy_start_locations[0], queue=True))
            if scoutqueue < 2:
                await self.do(observer.move(self.state.mineral_field.random.position, queue=True))
            elif scoutqueue > 3:
                break


    async def dtattack(self):
        dts = self.units(UnitTypeId.DARKTEMPLAR).ready
        if not dts:
            return

        for dt in dts:
            enemies = self.known_enemy_units.closer_than(30, dt)
            if enemies:
                for enemy in enemies:
                    if (enemy.name == 'Probe') or (enemy.name == 'SCV') or (enemy.name == 'Drone'):
                        self.microActions.append(dt.attack(enemy.position))
            else:
                structures = self.known_enemy_structures
                if not structures:
                    break
                
                self.microActions.append(dt.move(structures.first.position))

 
    async def workerroutine(self):
        for hq in self.units(UnitTypeId.NEXUS).ready:
            if hq.assigned_harvesters > hq.ideal_harvesters:
                toomuch = hq.assigned_harvesters - hq.ideal_harvesters
                harvesters = self.units(UnitTypeId.PROBE).ready
                harvesters_pool = []
                
                harvesters_pool.extend(harvesters.random_group_of(toomuch))
                if harvesters_pool:
                    for harvester in harvesters_pool:
                        for checkhq in self.units(UnitTypeId.NEXUS).ready:
                            if checkhq.assigned_harvesters < checkhq.ideal_harvesters:
                                mineral = self.state.mineral_field.closest_to(checkhq)
                                #await self.do(harvester.gather(mineral))
                                self.microActions.append(harvester.gather(mineral))

        if self.units(UnitTypeId.NEXUS):
            nx = self.units(UnitTypeId.NEXUS).ready.first

        # Assign workers to assimilators
        if self.units(UnitTypeId.ASSIMILATOR).ready.exists:
            for gasstation in self.units(UnitTypeId.ASSIMILATOR):
                workers = self.units(UnitTypeId.PROBE)
                assigned = gasstation.assigned_harvesters
                ideal = gasstation.ideal_harvesters
                needed = ideal - assigned
    
                worker_pool = []
                for x in range(0, needed):
                    worker_pool.extend(workers.random_group_of(min(needed, len(workers))))
                    if worker_pool:
                        w = worker_pool.pop()
                        if len(w.orders) == 1 and w.orders[0].ability.id in [AbilityId.HARVEST_RETURN]:
                            self.microActions.append(w.move(gasstation))
                            self.microActions.append(w.return_resource(queue=True))
                        else:
                            self.microActions.append(w.gather(gasstation))
                    
        # Distribute idle workers
        for lazy in self.workers.idle:
            await self.do(lazy.move(self.units(UnitTypeId.NEXUS).ready.random.position, queue=True))
        for lazyathq in self.workers.idle:
            if nx:
                mineral = self.state.mineral_field.closest_to(nx)
                await self.do(lazyathq.gather(mineral, queue=True))
            else:
                break

        # Build Workers
        for hq in self.units(UnitTypeId.NEXUS).ready:
            neededharvesters = (hq.ideal_harvesters - hq.assigned_harvesters) - 2

            if hq.assigned_harvesters > hq.ideal_harvesters:
                return

            if neededharvesters < 0:
                return

            if self.already_pending(UnitTypeId.PROBE):
                return

            if hq.noqueue and self.can_afford(UnitTypeId.PROBE):
                await self.do(hq.train(UnitTypeId.PROBE))
                return


    async def estimate(self):
        self.my_armypower = self.units.not_structure.ready.amount - self.workers.ready.amount
        self.enemy_armypower =  self.known_enemy_units.not_structure.amount
        self.enemy_income = 0
        for mineral in self.state.mineral_field:
            enemies = self.known_enemy_units.closer_than(2, mineral)
            for enemy in enemies:
                if (enemy.name == 'Probe') or (enemy.name == 'SCV') or (enemy.name == 'Drone'):
                    self.enemy_income = self.enemy_income + 1
                    self.enemy_armypower = self.enemy_armypower - 1
                    if self.enemy_armypower < 0:
                        self.enemy_armypower = 0
                    break

    async def cheesedetection_towerrush(self):
        if not self.units(UnitTypeId.NEXUS).ready:
            return
        nx = self.units(UnitTypeId.NEXUS).ready.first
        enemies = self.known_enemy_units.closer_than(30, nx)

        if enemies:
            for enemy in enemies:
                if (enemy.name == 'Probe') or (enemy.name == 'Pylon') or (enemy.name == 'PhotonCannon'):
                    self.cheese_towerrush = True
                    self.probecount = 0
                    
                    for probe in self.workers:
                        if self.probecount < 3:
                            self.microActions.append(probe.attack(enemy.position))
                            self.probecount = self.probecount + 1
                            break
        else:
            self.cheese_towerrush = False


    async def defendroutine(self):
        hqs = self.units(UnitTypeId.NEXUS)
        for hq in hqs:
            enemies = self.known_enemy_units.closer_than(25, hq)
            
            if enemies:
                self.attacked = True

                sentries = self.units(UnitTypeId.SENTRY).ready.idle
                for sentrie in sentries:
                    next_enemy = self.known_enemy_units.closest_to(sentrie)
                    self.microActions.append(sentrie.attack(next_enemy.position))
                
                stalkers = self.units(UnitTypeId.STALKER).ready.idle
                for stalker in stalkers:
                    next_enemy = self.known_enemy_units.closest_to(stalker)
                    self.microActions.append(stalker.attack(next_enemy.position))

                colossuses = self.units(UnitTypeId.COLOSSUS).ready.idle
                for colossus in colossuses:
                    next_enemy = self.known_enemy_units.closest_to(colossus)
                    self.microActions.append(colossus.attack(next_enemy.position))

                immortals = self.units(UnitTypeId.IMMORTAL).ready.idle
                for immortal in immortals:
                    next_enemy = self.known_enemy_units.closest_to(immortal)
                    self.microActions.append(immortal.attack(next_enemy.position))
                    
                zealots = self.units(UnitTypeId.ZEALOT).ready.idle
                for zealot in zealots:
                    next_enemy = self.known_enemy_units.closest_to(zealot)
                    self.microActions.append(zealot.attack(next_enemy.position))
                    
                adepts = self.units(UnitTypeId.ADEPT).ready.idle
                for adept in adepts:
                    next_enemy = self.known_enemy_units.closest_to(adept)
                    self.microActions.append(adept.attack(next_enemy.position))
            else:
                self.attacked = False


    async def microroutine(self):
        stalkers = self.units(UnitTypeId.STALKER).ready
        adepts = self.units(UnitTypeId.ADEPT).ready
        immortals = self.units(UnitTypeId.IMMORTAL).ready
        zealots = self.units(UnitTypeId.ZEALOT).ready
        colossuses = self.units(UnitTypeId.COLOSSUS).ready
        #warpprisms = self.units(UnitTypeId.WARPPRISM).ready
        observers = self.units(UnitTypeId.OBSERVER).ready
        sentries = self.units(UnitTypeId.SENTRY).ready
        workers = self.workers.ready

        if zealots:
            for zealot in zealots:
                enemies = self.known_enemy_units.closer_than(15, zealot)
                
                if enemies:
                    for e in enemies:
                        if e.is_flying:
                            enemies.remove(e)
                        #elif e in self.targetunits:
                        #    self.microActions.append(zealot.attack(e))
                        else:
                            self.targetunits.append(e)
                            break

        if observers:
            for observer in observers:
                enemies = self.known_enemy_units.closer_than(15, observer)
                if enemies:
                    if enemies.amount > 10:
                        #await self.do(observer(AbilityId.MORPH_SURVEILLANCEMODE))
                        break
                                
        if workers:
            for worker in workers:
                distance = worker.position.distance_to(self.game_info.map_center.position)
                if distance < 30:
                    nx = self.units(UnitTypeId.NEXUS).ready.closest_to(worker)
                    if not nx:
                        break
                    self.microActions.append(worker.move(nx.position))
                
                
        if stalkers:
            for stalker in stalkers:
                enemies = self.known_enemy_units.closer_than(10, stalker)
                
                if enemies:
                    next_enemy = self.known_enemy_units.closest_to(stalker)
                    distance = stalker.position.distance_to(next_enemy.position)

                    nx = self.units(UnitTypeId.NEXUS).ready.closest_to(stalker)
                    if not nx:
                        break

                    nxdistance = stalker.position.distance_to(nx.position)
                    if nxdistance < 10:
                        break

                    # buggy
                    #if next_enemy.is_structure and (distance > 5):
                    #    #if next_enemy_unit and (unit_distance > 6):
                    #    self.microActions.append(stalker.move(stalker.position.towards(next_enemy.position, 1)))
                    
                    if distance < 2:
                        break                
                                
                    if distance < 6:
                        if self.blink_done:
                            blinkposition = stalker.position.to2.towards(nx.position, 2)
                            if not blinkposition:
                                break
                        
                            await self.do(stalker(AbilityId.EFFECT_BLINK_STALKER, blinkposition))
                            break
                        else:
                            moveposition = stalker.position.to2.towards(nx.position, 2)
                            if not moveposition:
                                break
                            
                            self.microActions.append(stalker.move(moveposition))

        if immortals:
            for immortal in immortals:
                enemies = self.known_enemy_units.closer_than(10, immortal)
                
                for e in enemies:
                    if e.is_flying:
                        enemies.remove(e)
                
                if enemies:
                    next_enemy = self.known_enemy_units.closest_to(immortal)
                    distance = immortal.position.distance_to(next_enemy.position)

                    nx = self.units(UnitTypeId.NEXUS).ready.closest_to(immortal)
                    if not nx:
                        break

                    nxdistance = immortal.position.distance_to(nx.position)
                    if nxdistance < 10:
                        break

                    if distance < 2:
                        break                
                    
                    if distance < 5:
                        moveposition = immortal.position.to2.towards(nx.position, 2)
                        if not moveposition:
                            break
                        
                        self.microActions.append(immortal.move(moveposition))

        if colossuses:
            for colossus in colossuses:
                enemies = self.known_enemy_units.closer_than(10, colossus)
                
                if enemies:
                    next_enemy = self.known_enemy_units.closest_to(colossus)
                    distance = colossus.position.distance_to(next_enemy.position)

                    nx = self.units(UnitTypeId.NEXUS).ready.closest_to(colossus)
                    if not nx:
                        break

                    nxdistance = colossus.position.distance_to(nx.position)
                    if nxdistance < 5:
                        break
                    
                    if distance < 1:
                        break                

                    if distance < 9:
                        moveposition = colossus.position.to2.towards(nx.position, 1)
                        if not moveposition:
                            break
                        
                        self.microActions.append(colossus.move(moveposition))

        if adepts:
            for adept in adepts:
                enemies = self.known_enemy_units.closer_than(10, adept)
                
                if enemies:
                    next_enemy = self.known_enemy_units.closest_to(adept)
                    distance = adept.position.distance_to(next_enemy.position)

                    nx = self.units(UnitTypeId.NEXUS).ready.closest_to(adept)
                    if not nx:
                        break

                    nxdistance = adept.position.distance_to(nx.position)
                    if nxdistance < 10:
                        break
                    
                    if distance < 2:
                        break                

                    if distance < 4:
                        moveposition = adept.position.to2.towards(nx.position, 2)
                        if not moveposition:
                            break
                        
                        self.microActions.append(adept.move(moveposition))

        if sentries:
            for sentry in sentries:
                enemies = self.known_enemy_units.closer_than(10, sentry)
                
                if enemies:
                    next_enemy = self.known_enemy_units.closest_to(sentry)
                    distance = sentry.position.distance_to(next_enemy.position)

                    if not sentry.has_buff(BuffId.GUARDIANSHIELD):
                        if sentry.energy > 75:
                            if distance < 10:
                                if (not next_enemy.name == 'Probe') or (not next_enemy.name == 'SCV') or (not next_enemy.name == 'Drone'):
                                    await self.do(sentry(AbilityId.GUARDIANSHIELD_GUARDIANSHIELD))
                                    break
                    else:
                        nx = self.units(UnitTypeId.NEXUS).ready.closest_to(sentry)
                        if not nx:
                            break
    
                        nxdistance = sentry.position.distance_to(nx.position)
                        if nxdistance < 10:
                            break

                        if distance < 2:
                            break                

                        if distance < 8:
                            moveposition = sentry.position.to2.towards(nx.position, 2)
                            if not moveposition:
                                break

                            self.microActions.append(sentry.move(moveposition))


    async def fightroutine(self):
        zealots = self.units(UnitTypeId.ZEALOT).ready.idle
        adepts = self.units(UnitTypeId.STALKER).ready.idle
        stalkers = self.units(UnitTypeId.STALKER).ready.idle
        allstalkers = self.units(UnitTypeId.STALKER).ready.amount
        immortals = self.units(UnitTypeId.IMMORTAL).ready.idle
        colossuses = self.units(UnitTypeId.COLOSSUS).ready.idle
        warpprisms = self.units(UnitTypeId.WARPPRISM).ready.idle
        sentries = self.units(UnitTypeId.SENTRY).ready
        ramp = self.main_base_ramp.top_center.position
                
        # Target
        if self.known_enemy_structures:
            target = random.choice(self.known_enemy_structures).position
        elif self.known_enemy_units:
            target = random.choice(self.known_enemy_units).position
        else:
            target = None
        
        
        # Guard Pool
        guard_pool = []
        if zealots:
            guard_pool.extend(zealots)
                    
        # Fighter Pool
        fighter_pool = []
        if adepts:
            fighter_pool.extend(adepts)
        if stalkers:
            fighter_pool.extend(stalkers)
        if immortals:
            fighter_pool.extend(immortals)
        if colossuses:
            fighter_pool.extend(colossuses)
        if sentries:
            fighter_pool.extend(sentries)
                
        # Proxy Pool
        proxy_pool = []
        if warpprisms:
            proxy_pool.extend(warpprisms)


        if allstalkers < self.retreat_count:
            self.fightstarted = False
        
        if self.fightstarted == False:
            fighteramount = self.attack_count
        else:
            fighteramount = 0


        if self.fightstarted == False:
            waitingunits_adepts = self.units(UnitTypeId.ADEPT).ready.idle
            rallyunits_adepts = self.state.units(UnitTypeId.ADEPT).ready.idle.closer_than(25, ramp)
            for wuad in waitingunits_adepts:
                if wuad not in rallyunits_adepts:
                    self.microActions.append(wuad.attack(ramp))

            waitingunits_sentries = self.units(UnitTypeId.SENTRY).ready.idle
            rallyunits_sentries = self.state.units(UnitTypeId.SENTRY).ready.idle.closer_than(25, ramp)
            for wuss in waitingunits_sentries:
                if wuss not in rallyunits_sentries:
                    self.microActions.append(wuss.attack(ramp))
                    
            waitingunits_stalker = self.units(UnitTypeId.STALKER).ready.idle
            rallyunits_stalker = self.state.units(UnitTypeId.STALKER).ready.idle.closer_than(25, ramp)
            for wus in waitingunits_stalker:
                if wus not in rallyunits_stalker:
                    self.microActions.append(wus.attack(ramp))
                    
            waitingunits_immortal = self.units(UnitTypeId.IMMORTAL).ready.idle
            rallyunits_immortal = self.state.units(UnitTypeId.IMMORTAL).ready.idle.closer_than(25, ramp)
            for wui in waitingunits_immortal:
                if wui not in rallyunits_immortal:
                    self.microActions.append(wui.attack(ramp))

            waitingunits_colossus = self.units(UnitTypeId.COLOSSUS).ready.idle
            rallyunits_colossus = self.state.units(UnitTypeId.COLOSSUS).ready.idle.closer_than(25, ramp)
            for wuc in waitingunits_colossus:
                if wuc not in rallyunits_colossus:
                    self.microActions.append(wuc.attack(ramp))

            
        if len(proxy_pool) != 0:
            for u in proxy_pool:
                if target:
                    self.microActions.append(u.attack(target))
                else:
                    await self.prismraid()

        for g in guard_pool:
            nexus = self.units(UnitTypeId.NEXUS).ready.random.position
            if target and self.fightstarted:
                self.microActions.append(g.attack(target))
            else:
                enemies = self.known_enemy_units.closer_than(30, nexus)
                for e in enemies:
                    if e.is_flying:
                        enemies.remove(e)
                    
                gqueue = 0
                while True:
                    location = await self.get_next_expansion()
                    pos = nexus.towards(location.position, random.randrange(1, 25))
                    self.microActions.append(g.attack(pos, queue=True))
                    gqueue = gqueue + 1
                    if gqueue > 2:
                        break
                
       
        if len(fighter_pool) > fighteramount:
            for i in fighter_pool:
                if target:
                    self.microActions.append(i.attack(target))
                    self.fightstarted = True
                else:
                    break


    async def trainroutine(self):
        if self.supply_used == self.supply_cap:
            return            

        unitlist = get_unitlist(str(self.enemyrace))
        for i in unitlist['unit']:
            unitname = (unitlist['unit'][i]['name'])
            buildstructure = (unitlist['unit'][i]['structure'])
            buildrequirement = (unitlist['unit'][i]['requirement'])
            unitcount = (unitlist['unit'][i]['count']) * self.units(UnitTypeId.NEXUS).amount
            
            # Spawn observer when needed
            if self.known_enemy_structures and unitname == 'OBSERVER':
                break

            # what does this button do?
            if self.forcewarpprismraid:
                if unitname != 'WARPPRISM':
                    break

            if self.keepminerals and self.keepgas and unitname != 'WARPPRISM':
                break

            # the unit train routine
            if self.units(UnitTypeId[unitname]).amount < unitcount:
                if not self.already_pending(UnitTypeId[unitname]):
                    
                    if buildrequirement:
                        if not self.units(UnitTypeId[buildrequirement]).ready.exists:
                            break
                        
                    if self.units(UnitTypeId[buildstructure]).ready.exists:
                        if self.can_afford(UnitTypeId[unitname]):
                            for structure in self.units(UnitTypeId[buildstructure]).ready.idle:
                                
                                if buildstructure == 'WARPGATE':
                                    abilities = await self.get_available_abilities(structure)
                                    if AbilityId.WARPGATETRAIN_STALKER in abilities:
                                        if not self.fightstarted:
                                            ramp = self.main_base_ramp.top_center.position
                                            proxy = self.units(UnitTypeId.PYLON).closest_to(ramp)
                                        elif self.fightstarted:
                                            proxy = self.units(UnitTypeId.PYLON).closest_to(self.enemy_start_locations[0])
    
                                        pos = proxy.position.to2.random_on_distance(4)
                                        placement = await self.find_placement(AbilityId.WARPGATETRAIN_STALKER, pos, placement_step=1)
                                        if placement is None:
                                            break
                                        
                                        if self.units(UnitTypeId.WARPPRISM).ready:
                                            for prism in self.units(UnitTypeId.WARPPRISM).ready:
                                                abilities = await self.get_available_abilities(prism)
                                                if AbilityId.MORPH_WARPPRISMPHASINGMODE in abilities:
                                                    print("found prism")
                                                        
                                                        
                                        await self.do(structure.warp_in(UnitTypeId[unitname], placement))
                                        break
                                    
                                    elif AbilityId.GATEWAYTRAIN_STALKER in abilities:
                                        await self.do(structure.train(UnitTypeId[unitname]))
                                        break
                                    
                                else:
                                    await self.do(structure.train(UnitTypeId[unitname]))
                                    break


    async def buffroutine(self):
        for hq in self.units(UnitTypeId.NEXUS).ready:
               
            # SHIELDBATTERY
            if self.units(UnitTypeId.SHIELDBATTERY).ready.exists:
                for sb in self.units(UnitTypeId.SHIELDBATTERY).ready:
                    if sb.energy < 3:
                        break
                    sbabilities = await self.get_available_abilities(sb)
                    if AbilityId.EFFECT_RESTORE in sbabilities:
                        shield_pool = []                        
                        nearunits = self.units.ready.not_structure.closer_than(7, sb)
                        
                        for helpunit in nearunits:
                            if helpunit.shield < helpunit.shield_max:
                                shield_pool.append(helpunit)

                        if shield_pool:
                            attackedunit = shield_pool.pop()
                            if attackedunit:
                                if not attackedunit.has_buff(BuffId.RESTORESHIELDS):
                                    await self.do(sb(AbilityId.EFFECT_RESTORE, attackedunit))
                                    break

            
            # Boost Cyber Core
            if self.units(UnitTypeId.CYBERNETICSCORE).ready.exists and not self.coreboosted:
                ccore = self.units(UnitTypeId.CYBERNETICSCORE).ready.first
                if not ccore.has_buff(BuffId.CHRONOBOOSTENERGYCOST):
                        abilities = await self.get_available_abilities(hq)
                        if AbilityId.EFFECT_CHRONOBOOSTENERGYCOST in abilities:
                            await self.do(hq(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, ccore))
                            self.coreboosted = True
                            return

            # Boost Gateway
            if self.units(UnitTypeId.GATEWAY).ready.exists and self.units(UnitTypeId.CYBERNETICSCORE).ready.exists:
                gw = self.units(UnitTypeId.GATEWAY).ready.first
                if not gw.has_buff(BuffId.CHRONOBOOSTENERGYCOST):
                        abilities = await self.get_available_abilities(hq)
                        if AbilityId.EFFECT_CHRONOBOOSTENERGYCOST in abilities:
                            await self.do(hq(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, gw))
                            return

            # Boost Warpgate
            if self.units(UnitTypeId.WARPGATE).ready.exists and self.units(UnitTypeId.CYBERNETICSCORE).ready.exists:
                warps = self.units(UnitTypeId.WARPGATE).ready.first
                if not warps.has_buff(BuffId.CHRONOBOOSTENERGYCOST):
                        abilities = await self.get_available_abilities(hq)
                        if AbilityId.EFFECT_CHRONOBOOSTENERGYCOST in abilities:
                            await self.do(hq(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, warps))
                            return
                
    
            # WARPGATE
            if self.units(UnitTypeId.CYBERNETICSCORE).ready.exists and self.can_afford(AbilityId.RESEARCH_WARPGATE) and not self.warpgate_started:
                ccore = self.units(UnitTypeId.CYBERNETICSCORE).ready.first
                await self.do(ccore(AbilityId.RESEARCH_WARPGATE))
                self.warpgate_started = True
                return
                
            for gateway in self.units(UnitTypeId.GATEWAY).ready:
                abilities = await self.get_available_abilities(gateway)
                if AbilityId.MORPH_WARPGATE in abilities and self.can_afford(AbilityId.MORPH_WARPGATE):
                    await self.do(gateway(AbilityId.MORPH_WARPGATE))
                    return

            # Blink
            if self.units(UnitTypeId.TWILIGHTCOUNCIL).ready.exists and self.can_afford(AbilityId.RESEARCH_BLINK) and not self.blink_started:
                tc = self.units(UnitTypeId.TWILIGHTCOUNCIL).ready.first
                await self.do(tc(AbilityId.RESEARCH_BLINK))
                self.blink_started = True
                return
            
            if self.units(UnitTypeId.STALKER).ready and not self.blink_done:
                stalker = self.units(UnitTypeId.STALKER).ready.first
                abilities = await self.get_available_abilities(stalker)
                if AbilityId.EFFECT_BLINK_STALKER in abilities:
                    self.blink_done = True

            # Extended Thermal Lance
            if self.units(UnitTypeId.COLOSSUS).amount > 1:
                if self.units(UnitTypeId.ROBOTICSBAY).ready.exists and self.can_afford(AbilityId.RESEARCH_EXTENDEDTHERMALLANCE) and not self.exlance_started:
                    tc = self.units(UnitTypeId.ROBOTICSBAY).ready.first
                    await self.do(tc(AbilityId.RESEARCH_EXTENDEDTHERMALLANCE))
                    self.exlance_started = True
                    return
            

    async def buildroutine(self):
        if self.keepminerals and self.keepgas:
            return
        
        # Nexus Loop
        for hq in self.units(UnitTypeId.NEXUS).ready:            
            # add some tags to each hq
            if hq.tag not in self.unitInfo:
                self.unitInfo[hq.tag] = {'phase': 1, 'warpgates': 0}
            
            # Read unitInfo
            for unitTag, unitInfo in self.unitInfo.items():
                unitImLookingFor = self.units.find_by_tag(unitTag)
            
            currentphase = str(unitInfo['phase'])
            buildorder = get_buildorder(str(self.enemyrace))
            buildproject = buildorder['phase'][currentphase]['name']
            buildrequirement = buildorder['phase'][currentphase]['requirement']
            buildsupply = buildorder['phase'][currentphase]['supply']

            # PYLONS
            if self.supply_left < self.pylonthreshold:
                if not self.already_pending(UnitTypeId.PYLON) and self.can_afford(UnitTypeId.PYLON):
                    worker = self.select_build_worker(hq.position)
                    if worker:
                        pylonnexus = hq.position
                        pylonposition = pylonnexus.random_on_distance(random.randrange(6, 12))
                        if not self.state.psionic_matrix.covers(pylonposition):
                            await self.build(UnitTypeId.PYLON, near=pylonposition)
                            return

            # NEXUS                
            if self.already_pending(UnitTypeId.NEXUS):
                break
            if self.can_afford(UnitTypeId.NEXUS) and self.supply_cap > 60:
                location = await self.get_next_expansion()
                err = await self.build(UnitTypeId.NEXUS, near=location)
                if not err:
                    break                
                
            # This HQ is done
            if buildproject == 'END':
                return
               
            # Raise the phase if build is pending
            for buildinprogress in self.units(UnitTypeId[buildproject]):
                if buildinprogress.build_progress < 0.1 and buildproject != 'ASSIMILATOR':
                    unitInfo['phase'] = unitInfo['phase'] + 1
                    return

                
            # Raise the phase if we have assimilators
            hq.assi = 0
            for a in self.units(UnitTypeId.ASSIMILATOR):
                if a.build_progress < 1.0:
                    hq.assi = hq.assi + 1
                    
            if hq.assi == 2 and buildproject == 'ASSIMILATOR':
                unitInfo['phase'] = unitInfo['phase'] + 1
                return
                        

            # Build Order
            # Assimilators are special...
            if buildproject == 'ASSIMILATOR':
                vgs = self.state.vespene_geyser.closer_than(15, hq)
                for vg in vgs:
                    worker = self.select_build_worker(vg.position)
                    if worker is None:
                        break
                    if self.can_afford(UnitTypeId.ASSIMILATOR):
                        err = await self.do(worker.build(UnitTypeId.ASSIMILATOR, vg))
                        if not err:
                            break

            else:
                # We need only one of them
                if buildproject == 'CYBERNETICSCORE':
                    if self.units(UnitTypeId[buildproject]).ready.exists:
                        unitInfo['phase'] = unitInfo['phase'] + 1
                        return
                    
                if buildproject == 'ROBOTICSBAY':
                    if self.units(UnitTypeId[buildproject]).ready.exists:
                        unitInfo['phase'] = unitInfo['phase'] + 1
                        return

                if buildproject == 'TWILIGHTCOUNCIL':
                    if self.units(UnitTypeId[buildproject]).ready.exists:
                        unitInfo['phase'] = unitInfo['phase'] + 1
                        return

                if buildproject == 'DARKSHRINE':
                    if self.units(UnitTypeId[buildproject]).ready.exists:
                        unitInfo['phase'] = unitInfo['phase'] + 1
                        return

                if buildproject == 'FORGE':
                    if self.units(UnitTypeId[buildproject]).ready.exists:
                        unitInfo['phase'] = unitInfo['phase'] + 1
                        return

                if buildrequirement:
                    if not self.units(UnitTypeId[buildrequirement]).ready.exists:
                        break

                if buildsupply:
                    if self.supply_cap < buildsupply:
                        break

                if self.already_pending(UnitTypeId[buildproject]):
                    break

                worker = self.select_build_worker(hq.position)
                if worker is None:
                    break

                if self.can_afford(UnitTypeId[buildproject]):
                    ramp = self.main_base_ramp.top_center
                    if buildproject == 'SHIELDBATTERY' or buildproject == 'PHOTONCANNON':
                        p = ramp.position.towards(hq.position, 5)
                    else:
                        p = hq.position.towards(self.game_info.map_center, 2)
                        for mineral in self.state.mineral_field:
                            distance = mineral.position.distance_to(p)
                            if distance < 2:
                                break

                    await self.build(UnitTypeId[buildproject], near=p)
                    return

 
    async def on_step(self, iteration):
        self.microActions = []
        self.targetunits = []

        if iteration % 100 == 0:
            print("Army: " + str(self.my_armypower))
            print("Enemy Army: " + str(self.enemy_armypower))
            print("Enemy Income: " + str(self.enemy_income))
        if iteration % 2 == 0:
            await self.estimate()
            return

            

        # Kamikaze
        nexus = self.units(UnitTypeId.NEXUS)
        if not nexus.exists:
            target = self.known_enemy_structures.random_or(self.enemy_start_locations[0]).position
            for unit in self.workers | self.units.not_structure:
                await self.do(unit.attack(target))
                return

        if self.enemyrace == "Unknown":
            await self.racecheck()
            print("Enemy Race: " + str(self.enemyrace))
            return

        await self.microroutine()
        await self.dtattack()
        await self.cheesedetection_towerrush()
        await self.scoutroutine()
        await self.buildatramp()
        await self.workerroutine()
        await self.buildroutine()
        await self.buffroutine()
        await self.trainroutine()
        await self.fightroutine()
        await self.defendroutine()
        if self.buildaproxy == True:
            #await self.buildproxy()
            print("Build Proxy")
                    
        await self.do_actions(self.microActions)

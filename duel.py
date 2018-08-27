import sc2, sys
from __init__ import run_ladder_game
from sc2 import Race, Difficulty
from sc2.player import Bot, Computer, Human
import random

# Load bot
from zerg_agent import LingLoverBot
bot = Bot(Race.Zerg, LingLoverBot())

from other_bots.cannon_lover.cannon_lover_bot import CannonLoverBot
oponent = Bot(Race.Protoss, CannonLoverBot())

#from other_bots.mindbot.m1ndb0t import m1ndb0t
#oponent = Bot(Race.Protoss, m1ndb0t())

from other_bots.lucidbot.lucid_bot import LucidBot
oponent = Bot(Race.Protoss, LucidBot())

# Start game
if __name__ == '__main__':
    if "--LadderServer" in sys.argv:
        # Ladder game started by LadderManager
        print("Starting ladder game...")
        run_ladder_game(bot)
    else:
        # Local game
        print("Starting local game...")
        map_name = 'Abyssal Reef LE'
        #map_name = random.choice(["(2)16-BitLE", "(2)AcidPlantLE", "(2)CatalystLE", "(2)DreamcatcherLE", "(2)LostandFoundLE", "(2)RedshiftLE", "(4)DarknessSanctuaryLE"])
        #map_name = random.choice(["ProximaStationLE", "NewkirkPrecinctTE", "OdysseyLE", "MechDepotLE", "AscensiontoAiurLE", "BelShirVestigeLE"])
        #map_name = "(2)16-BitLE"
        sc2.run_game(sc2.maps.get(map_name), [
            #Human(Race.Terran),
            oponent,
            bot,
            #Computer(Race.Random, Difficulty.VeryHard) # CheatInsane VeryHard
        ], realtime=False, save_replay_as="Example.SC2Replay")

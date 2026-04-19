"""Random MLB-flavored persona names for the 'sign replacement' flow.

Used by POST /api/roster/<role>/sign when the operator doesn't supply
a name. Determinism is intentional only at call time — different
process runs produce different names, which is the point.
"""
from __future__ import annotations

import random


_FIRST = (
    "Ace", "Buck", "Cal", "Cy", "Deacon", "Duke", "Earl", "Fritz", "Goose",
    "Hank", "Ichi", "Junior", "Kit", "Lefty", "Mickey", "Nap", "Ozzie",
    "Pete", "Quincy", "Rusty", "Satchel", "Tug", "Ump", "Vance", "Whitey",
    "Yogi", "Zeke", "Babe", "Cliff", "Dizzy", "Eddie", "Frank", "Gus",
    "Harmon", "Iggy", "Jackie", "Kirby", "Lou", "Moe", "Nolan", "Orel",
    "Pee Wee", "Quinn", "Reggie", "Sandy", "Ty", "Urban", "Vic", "Walt",
    "Xander", "Yaz", "Zack", "Brooks", "Carl", "Dale", "Elmer", "Fergie",
    "Gabby", "Harry", "Ivan", "Joe", "Ken", "Luis", "Manny", "Nelson",
    "Omar", "Phil", "Rico", "Sam", "Tony", "Ugueth", "Vlad", "Willie",
    "Yusei", "Zane", "Aaron", "Brandon", "Chuck", "Doc",
)

_LAST = (
    "Aaron", "Bench", "Cobb", "Doby", "Eckersley", "Foxx", "Gehrig",
    "Hornsby", "Irvin", "Jeter", "Kaline", "Lasorda", "Mantle", "Newcombe",
    "Ott", "Paige", "Quisenberry", "Ruth", "Stargell", "Trout", "Uribe",
    "Vincent", "Williams", "Yastrzemski", "Zambrano", "Banks", "Clemente",
    "DiMaggio", "Eckersley", "Feller", "Gibson", "Henderson", "Ichiro",
    "Johnson", "Killebrew", "Larkin", "Maddux", "Niekro", "Ortiz", "Piazza",
    "Quintana", "Rivera", "Schmidt", "Thomas", "Utley", "Verlander", "Wagner",
    "Xochitl", "Young", "Zito", "Berra", "Carter", "Drew", "Encarnacion",
    "Fielder", "Glavine", "Halladay", "Iannetta", "Jackson", "Kershaw",
    "Lincecum", "McCutchen", "Nunez", "Olerud", "Posey", "Ramirez",
    "Sabathia", "Tejada", "Upton", "Votto", "Wright", "Yount", "Zobrist",
    "Soto", "Acuna", "Betts", "Cabrera", "Devers", "Edman", "Fried",
)

_NICKNAMES = (
    "Smoke", "The Kid", "Ice", "Heat", "Splash", "Hammer", "Rocket",
    "Doc", "Scooter", "Rifle", "Slam", "Boom", "Crash", "Dash",
    "Flash", "Glove", "Hit", "Iron", "Jet", "King", "Laser", "Mr. October",
    "Nails", "Outlaw", "Pop", "Quake", "Riot", "Storm", "Thunder", "Vortex",
    "Whip", "Xerxes", "Yard", "Zen", "Bullet", "Chief", "Diesel", "Eagle",
)


def generate_name(*, with_nickname_chance: float = 0.35) -> str:
    """Return a random MLB-style persona name.

    With probability `with_nickname_chance`, formatted as
    `First "Nick" Last`; otherwise `First Last`.
    """
    rng = random.Random()
    first = rng.choice(_FIRST)
    last = rng.choice(_LAST)
    if rng.random() < with_nickname_chance:
        nick = rng.choice(_NICKNAMES)
        return f'{first} "{nick}" {last}'
    return f"{first} {last}"


if __name__ == "__main__":
    # Print 12 sample names for eyeball verification.
    for _ in range(12):
        print(generate_name())

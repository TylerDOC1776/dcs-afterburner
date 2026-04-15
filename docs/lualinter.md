DCS uses Lua version 5.1

starting point:
https://github.com/mpeterv/luacheck

We are going to make a Github Action that checks lua on ingest against known DCS world practices.

DCS Global Variables:

Here are the key, known global tables and singleton objects available in the DCS scripting environment:
Key Global Tables & Singletons

    world: The main singleton for interacting with the game world, used to manage events and query world data.
    coalition: Provides functions to manage coalitions and query data about sides (red/blue).
    timer: Essential for scheduling actions or delaying function calls, as standard Lua loops can freeze the game.
    net: Provides networking information, crucial for multiplayer missions.
    trigger: Allows the script to interact with mission editor triggers, including displaying messages and triggering actions.
    Unit / Weapon / StaticObject / Airbase: Classes used to interact with specific object types in the simulation. 

Accessing Data via Functions
Since true pre-defined variables are rare, you must call functions to get data: 

    coalition.getPlayers(): Returns a table of all active players in the mission.
    Unit.getByName('name'): Gets a unit object based on the name assigned in the Mission Editor.
    Object.inAir(object): Returns true if the specified unit is currently airborne.
    Object.getVelocity(object): Returns the velocity vector of an object. 

Important Notes on Scope

    Persistent Globals: By default, any variable defined in a DO SCRIPT trigger without the local keyword is global and persists throughout the session across different triggers.
    Local Variables: If you use local, the variable only exists within that specific DO SCRIPT container.
    Timing Issues: Variables declared in a trigger might fail if the object they reference (like a late-activated aircraft) does not exist when the script runs. Using timer to delay script execution can solve this. 

For specialized data, developers often use tools like DCS-BIOS for cockpit exports or MOOSE/MIST frameworks which provide higher-level wrapper functions for these native DCS global objects. 


https://wiki.hoggitworld.com/view/Simulator_Scripting_Engine_Documentation

https://flightcontrol-master.github.io/MOOSE_DOCS_DEVELOP/Documentation/DCS.html


I have a clone of the moose github at ~Documents/Projects/MOOSE
I also have Mist clone at ~Documents/Projects/MissionScriptingTools

moose has linting tools in the github actions.

could be good for the linting.  

could we parse moose, mist and any other standard lua that we use into a json just the calls?  would thar be worth it?  Are there any other resources that I haven't found?



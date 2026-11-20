# Held-out questions (Snowdon Towers)

Write **30 questions** (a few extra is fine) the way a project manager would ask
them. Claude writes and runs the gold SQL afterwards; you review the answers.

## Guidelines

- One clear answer each (a number, a name, a short list).
- Answerable from the model: no questions needing outside information.
- Mix easy and hard: roughly a third simple lookups or counts, a third with a
  filter or two (a level, a room, a type), a third that combine things (type
  properties of placed items, rooms by finish and level, systems, materials).
- No repeats of the 85 existing questions (list at the bottom); a different
  question on the same topic is fine.
- Say "in the electrical model" when you mean one discipline; otherwise the
  whole project counts (see `../bim_conventions.md`).
- Please don't look at Claude's answers or the agent's runs while writing.

## What's in the model

- **Rooms**: number, name, level, area, perimeter, volume, occupancy, department,
  occupant, base/wall/floor/ceiling finish, ceiling height, design option.
- **Placed items** by category: doors, windows, walls, floors, furniture,
  casework, lighting fixtures, plumbing fixtures, air terminals, ducts, pipes,
  conduits, structural framing, curtain panels and mullions, specialty equipment, ...
- **Families and types** with parameters (fire rating, width, thickness, ...),
  wall layers and materials, material areas and volumes.
- **Levels** (Parking, L1 - Block 35/37/43, M1, L2-L5, R1-R3, parapets), phases
  (Existing, New Construction, ...), design options.
- **MEP systems** and the elements in them.
- **Documentation**: views, sheets, sheet sets, schedules, warnings.
- **Project info** per discipline model: status, issue date, client, address,
  author, organization, location.

## Your questions

1.
2.
3.
4.
5.
6.
7.
8.
9.
10.
11.
12.
13.
14.
15.
16.
17.
18.
19.
20.
21.
22.
23.
24.
25.
26.
27.
28.
29.
30.

## The 85 existing questions (don't repeat these)

- How many walls are in the building?
- How many doors are in the building?
- How many elements are there in room 200?
- What is the area of room 301?
- What is the volume of room 108?
- How many rooms are in the model?
- How many sheets are in the drawing set?
- Who is the client for this project?
- What is the project's street address?
- Which discipline models are still at the Design Development stage?
- How many warnings are there in the model?
- What is the most frequent warning in the model?
- How many distinct elements are affected by warnings?
- What is the name of the largest room by area?
- Which room contains the most elements?
- How many discipline models make up the Snowdon Towers project?
- What is the project number of the structural model?
- What is the issue date on the project's drawings?
- How many design options are defined in the model?
- How many design options are marked as primary?
- How many families in the model are in-place families?
- How many families are there?
- How many family types are there?
- How many levels are defined across all discipline models?
- In the '301 Iron Bridge Accounting' design option, what is the area of the main conference room?
- What is the perimeter of room 106?
- How many rooms are larger than 1,000 square feet?
- Which room number has the largest volume?
- How many materials are defined in the model?
- How many sheet sets are defined in the model?
- Which disciplines are still in Design Development?
- How many furniture elements are there in room 200?
- What is the elevation of level L3?
- How many instances of the 'Round Elbow' family are placed in the model?
- How many placed elements use the 'Copper' family type?
- How many rooms are on level L3?
- How much office space is there, in square feet?
- How many elements belong to the 'Domestic Cold Water 1' system?
- Which MEP system contains the most elements?
- What is the total volume of 'Concrete, Cast-in-Place gray' in the model, in cubic feet?
- How many elements does the plumbing discipline model contain?
- How many levels does the building have?
- Which level is the highest?
- What is the occupancy type of room 301?
- How many rooms have a 'Residential One Story' occupancy?
- How many rooms are on the Parking level?
- What is the total area of the rooms on level L4?
- Which level has the most rooms?
- How many windows are placed in the model?
- How many lighting fixtures are placed in the electrical model?
- How many rooms have a polished concrete/LVT floor finish?
- How many rooms list Retail as their occupant?
- What is the total gross building area?
- How many sheets are in the 'Arch - Schematic Design' sheet set?
- How many elements were created in the Existing phase?
- Which building material covers the most surface area?
- How many elements contain the material 'Gypsum Wall Board'?
- How many elements belong to the 'Roof Drainage 1' system?
- Which model group has the most placed instances?
- How many 3D views are in the model?
- How many schedules are in the model?
- How many doors open into room 106?
- How many doors are placed on level L4?
- Which level has the most doors placed on it?
- Which door types have a fire rating of 90 minutes?
- How many wall types have a 2-hour fire rating?
- How many doors are installed whose door type has a 90-minute fire rating?
- What is the total length of all pipes in the model?
- What is the name of sheet A101?
- Which structural material is assigned to the most structural elements (ignoring blank and '<By Category>' values)?
- On which level is room 301 located?
- How many family types are fire rated?
- How many plumbing fixtures are placed on level L4?
- How many lighting fixtures are placed on level L3 in the electrical model?
- How many wall types have more than five layers?
- How thick is the 'Solar Wall (L5)' wall type, in inches?
- Which wall type is the thickest?
- How many elements in the structural model are affected by warnings?
- What is the total area of rooms with a 'Residential One Story' occupancy?
- Which occupant type has the largest total room area?
- How many pipe fittings belong to the 'Domestic Cold Water 1' system?
- What is the total length of all ducts in the model?
- How many rooms on level L3 have a painted wall finish?
- What is the name of the largest room on level L4?
- How many door and wall types have a 1-hour fire rating?

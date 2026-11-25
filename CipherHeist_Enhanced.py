"""Cipher Heist: Monster Run — a 2D Pygame adventure for LifeBridgeAI.
Controls: arrow keys/A-D or on-screen arrows; answer with keyboard or tap choices.
Completed/lost runs write a JSON result for the LifeBridgeAI import workflow.
"""
from __future__ import annotations
import json, math, random, time, uuid
from pathlib import Path
import pygame

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "lifebridge_data"
DATA.mkdir(exist_ok=True)
RESULT = DATA / "cipher_heist_result.json"
W, H, FPS = 1000, 680, 60
BG=(7,12,27); WHITE=(241,247,255); MUTED=(150,173,204); CYAN=(73,235,224)
GOLD=(255,203,102); RED=(255,93,119); GREEN=(105,240,166); PURPLE=(166,119,255)
ROOMS = [
 {"name":"THE MOONLIT GATE","monster":"ASHFANG","kind":"ALGEBRA","q":"3(2x − 1) = 21","prompt":"Solve for x.","choices":["3","4","5","6"],"answer":"4","hint":"Expand first: 6x − 3 = 21.","why":"6x − 3 = 21, so 6x = 24 and x = 4."},
 {"name":"THE GLASS BRIDGE","monster":"VEXORA","kind":"GEOMETRY","q":"48° + 67° + x = 180°","prompt":"Find the missing angle.","choices":["55°","65°","75°","85°"],"answer":"65°","hint":"Interior angles of a triangle total 180°.","why":"180° − 48° − 67° = 65°."},
 {"name":"THE IRON VAULT","monster":"MOSSJAW","kind":"NUMBER THEORY","q":"Find the HCF of 84 and 126","prompt":"Choose the greatest common factor.","choices":["14","21","28","42"],"answer":"42","hint":"Use the Euclidean algorithm.","why":"126 − 84 = 42, and both numbers are divisible by 42."},
 {"name":"THE EMBER HALL","monster":"SHARDWING","kind":"SEQUENCES","q":"4, 9, 19, 39, 79, ?","prompt":"What number comes next?","choices":["149","158","159","169"],"answer":"159","hint":"Double each term, then add 1.","why":"79 × 2 + 1 = 159."},
 {"name":"THE SUNKEN ARCHIVE","monster":"DREADCORE","kind":"PERCENTAGES","q":"An ₹800 item is reduced by 15%","prompt":"What is the sale price?","choices":["₹660","₹680","₹690","₹720"],"answer":"₹680","hint":"Find 15% of 800, then subtract it.","why":"15% of 800 is 120; 800 − 120 = ₹680."},
 {"name":"THE RUNE GALLERY","monster":"RUNE WRAITH","kind":"RATIO","q":"a:b = 3:5 and a+b = 64","prompt":"Find b.","choices":["24","32","40","48"],"answer":"40","hint":"There are 8 equal parts altogether.","why":"One part is 64 ÷ 8 = 8; b = 5 × 8 = 40."},
 {"name":"THE THUNDER CHAMBER","monster":"STORM OGRE","kind":"PHYSICS · FORCE","q":"Mass = 2 kg; acceleration = 3 m/s²","prompt":"Calculate the net force.","choices":["1.5 N","5 N","6 N","9 N"],"answer":"6 N","hint":"Newton's second law: F = m × a.","why":"F = 2 × 3 = 6 newtons."},
 {"name":"THE CLOCKWORK ROOM","monster":"GEAR FIEND","kind":"PHYSICS · ENERGY","q":"A 60 W lamp runs for 10 seconds","prompt":"How much energy is used?","choices":["6 J","60 J","600 J","6000 J"],"answer":"600 J","hint":"Energy = power × time.","why":"E = 60 W × 10 s = 600 joules."},
 {"name":"THE ATOM CELLAR","monster":"ION BEAST","kind":"CHEMISTRY","q":"11 protons and 10 electrons","prompt":"What is the net electrical charge?","choices":["−1","0","+1","+2"],"answer":"+1","hint":"Protons are positive; electrons are negative.","why":"11 positive and 10 negative charges give a net +1."},
 {"name":"THE ALCHEMY LAB","monster":"PH WITCH","kind":"CHEMISTRY · pH","q":"Which has the highest pH?","prompt":"Assume typical household substances.","choices":["Lemon juice","Pure water","Soap solution","Vinegar"],"answer":"Soap solution","hint":"Higher pH means more alkaline.","why":"Soap solution is generally alkaline; lemon juice and vinegar are acidic."},
 {"name":"THE GREENHOUSE","monster":"THORN TROLL","kind":"BIOLOGY","q":"Where does most photosynthesis occur?","prompt":"Choose the cell organelle.","choices":["Mitochondrion","Chloroplast","Nucleus","Ribosome"],"answer":"Chloroplast","hint":"It contains chlorophyll.","why":"Chloroplasts contain chlorophyll and are the main site of photosynthesis."},
 {"name":"THE DOUBLE HELIX","monster":"DNA SHADE","kind":"BIOLOGY · GENETICS","q":"Which molecule carries hereditary instructions?","prompt":"Choose the main hereditary material in humans.","choices":["ATP","DNA","Glucose","Starch"],"answer":"DNA","hint":"Its structure is a double helix.","why":"DNA stores hereditary information in its nucleotide sequence."},
 {"name":"THE WATER TEMPLE","monster":"MIST KEEPER","kind":"EARTH SCIENCE","q":"Water vapour changes into liquid droplets","prompt":"Name this stage of the water cycle.","choices":["Evaporation","Condensation","Transpiration","Sublimation"],"answer":"Condensation","hint":"Cloud droplets form by this process.","why":"Cooling water vapour causes condensation into liquid droplets."},
 {"name":"THE WAVE TOWER","monster":"ECHO DEMON","kind":"PHYSICS · WAVES","q":"Frequency = 5 Hz; wavelength = 4 m","prompt":"Calculate the wave speed.","choices":["1.25 m/s","9 m/s","20 m/s","25 m/s"],"answer":"20 m/s","hint":"Wave speed = frequency × wavelength.","why":"v = 5 × 4 = 20 metres per second."},
 {"name":"THE BLOOD CHAMBER","monster":"SCARLET KNIGHT","kind":"BIOLOGY","q":"Which blood cells help fight infection?","prompt":"Choose the correct cell type.","choices":["Red blood cells","White blood cells","Platelets","Plasma"],"answer":"White blood cells","hint":"They are also called leukocytes.","why":"White blood cells help the immune system defend against pathogens."},
 {"name":"THE LOGIC MAZE","monster":"PARADOX","kind":"LOGIC · DEDUCTION","q":"All Zorbs are blue. No blue things are silent.","prompt":"Which conclusion must be true?","choices":["Some Zorbs are silent","No Zorbs are silent","All silent things are Zorbs","All blue things are Zorbs"],"answer":"No Zorbs are silent","hint":"Combine the two statements directly.","why":"Every Zorb is blue, and nothing blue is silent; therefore no Zorb is silent."},
 {"name":"THE NUMBER SPIRE","monster":"SEQUENCE SERPENT","kind":"LOGIC · PATTERN","q":"2, 6, 12, 20, 30, ?","prompt":"Find the next term.","choices":["36","40","42","44"],"answer":"42","hint":"Terms follow n × (n + 1).","why":"The next term is 6 × 7 = 42."},
 {"name":"THE CHANCE CASINO","monster":"DICE DEMON","kind":"LOGIC · PROBABILITY","q":"A fair six-sided die is rolled once","prompt":"Probability of getting a prime number?","choices":["1/6","1/3","1/2","2/3"],"answer":"1/2","hint":"Prime faces are 2, 3 and 5.","why":"3 prime outcomes out of 6 gives 3/6 = 1/2."},
 {"name":"THE TIME CORRIDOR","monster":"CHRONO WRAITH","kind":"LOGIC · REASONING","q":"Yesterday was Monday. What is the day after tomorrow?","prompt":"Track the days carefully.","choices":["Wednesday","Thursday","Friday","Saturday"],"answer":"Thursday","hint":"Today must be Tuesday.","why":"Today Tuesday, tomorrow Wednesday, and the day after tomorrow Thursday."},
 {"name":"THE LETTER SPIRE","monster":"RUNE STALKER","kind":"LOGIC · PATTERN","q":"A, C, F, J, O, ?","prompt":"Which letter comes next?","choices":["T","U","V","W"],"answer":"U","hint":"The jumps are +2, +3, +4, +5.","why":"The next jump is +6: O (15) + 6 = U (21)."},
 {"name":"THE WORD VAULT","monster":"LEXICON","kind":"ENGLISH · VOCABULARY","q":"Closest meaning of 'meticulous'","prompt":"Select the best synonym.","choices":["Careless","Precise","Impatient","Ordinary"],"answer":"Precise","hint":"A meticulous person pays close attention to detail.","why":"Meticulous means very careful and precise about details."},
 {"name":"THE GRAMMAR GATE","monster":"SYNTAX SHADE","kind":"ENGLISH · GRAMMAR","q":"Neither of the answers ___ correct.","prompt":"Choose the standard verb.","choices":["are","were","is","have"],"answer":"is","hint":"'Neither' is singular in this construction.","why":"In formal standard usage, 'neither' takes the singular verb 'is'."},
 {"name":"THE OPPOSITE HALL","monster":"CONTRARY","kind":"ENGLISH · VOCABULARY","q":"The opposite of 'scarce' is…","prompt":"Choose the antonym.","choices":["Rare","Limited","Abundant","Insufficient"],"answer":"Abundant","hint":"Scarce means not enough or hard to find.","why":"Abundant means plentiful, the opposite of scarce."},
 {"name":"THE PYTHON PIT","monster":"BYTE BEAST","kind":"CODING · PYTHON","q":"What does len([4, 7, 9, 2]) return?","prompt":"Choose the Python output.","choices":["2","3","4","9"],"answer":"4","hint":"len() counts the list elements.","why":"The list contains four elements, so len() returns 4."},
 {"name":"THE REMAINDER ROOM","monster":"MODULO MIMIC","kind":"CODING · PYTHON","q":"What is 17 % 5 in Python?","prompt":"The % operator returns the remainder.","choices":["2","3","3.4","12"],"answer":"2","hint":"5 goes into 17 three times, with a remainder.","why":"17 = 5×3 + 2, so the remainder is 2."},
 {"name":"THE LOOP DUNGEON","monster":"ITERATOR","kind":"CODING · LOGIC","q":"Which structure repeats while a condition is true?","prompt":"Choose the control structure.","choices":["if statement","while loop","function","class"],"answer":"while loop","hint":"It checks a condition before each repetition.","why":"A while loop repeats its body while its condition remains true."},
 {"name":"THE BINARY BRIDGE","monster":"BIT BANSHEE","kind":"CODING · BINARY","q":"What is decimal 13 in 4-bit binary?","prompt":"Choose the correct representation.","choices":["1011","1101","1110","1001"],"answer":"1101","hint":"8 + 4 + 1 = 13.","why":"13 = 8 + 4 + 0 + 1, so its 4-bit binary form is 1101."},
 {"name":"THE ALGORITHM HALL","monster":"SORT SPECTRE","kind":"CODING · ALGORITHMS","q":"Which search halves the range on sorted data?","prompt":"Choose the algorithm.","choices":["Linear search","Binary search","Bubble sort","Depth-first search"],"answer":"Binary search","hint":"It repeatedly checks the middle element.","why":"Binary search uses sorted order to discard half the remaining range each step."},
 {"name":"THE CIRCLE SANCTUM","monster":"RADIUS REAPER","kind":"MATHEMATICS · MENSURATION","q":"Circle radius = 7 cm; use π = 22/7","prompt":"Find its circumference.","choices":["22 cm","44 cm","49 cm","154 cm"],"answer":"44 cm","hint":"Circumference = 2πr.","why":"2 × 22/7 × 7 = 44 cm."},
 {"name":"THE FINAL EQUATION","monster":"THE VAULT GUARDIAN","kind":"MATHEMATICS · LINEAR EQUATIONS","q":"5(x − 2) = 3x + 8","prompt":"Solve for x.","choices":["7","8","9","10"],"answer":"9","hint":"Expand: 5x − 10 = 3x + 8.","why":"2x = 18, so x = 9."},

 {"name":"THE QUADRATIC KEEP","monster":"ROOT REVENANT","kind":"MATHEMATICS · QUADRATICS","q":"x² − 7x + 12 = 0","prompt":"Which pair gives both roots?","choices":["2 and 6","3 and 4","−3 and −4","1 and 12"],"answer":"3 and 4","hint":"Find two numbers with product 12 and sum 7.","why":"(x − 3)(x − 4) = 0, so x = 3 or x = 4."},
 {"name":"THE SIMILARITY SANCTUM","monster":"PROPORTION GARGOYLE","kind":"MATHEMATICS · SIMILARITY","q":"Similar triangles have sides in ratio 2:5","prompt":"A smaller side is 8 cm. Find its corresponding larger side.","choices":["12 cm","16 cm","20 cm","24 cm"],"answer":"20 cm","hint":"Multiply the smaller side by 5/2.","why":"Scale factor = 5/2, so 8 × 5/2 = 20 cm."},
 {"name":"THE STATISTICS TOWER","monster":"MEAN MIMIC","kind":"MATHEMATICS · STATISTICS","q":"Mean of 6, 8, 10, 13 and x is 10","prompt":"Find x.","choices":["11","12","13","14"],"answer":"13","hint":"The total of five values must be 50.","why":"6+8+10+13 = 37; x = 50−37 = 13."},
 {"name":"THE ELECTRIC FORGE","monster":"VOLT WRAITH","kind":"PHYSICS · ELECTRICITY","q":"V = 12 V and R = 4 Ω","prompt":"What current flows through the resistor?","choices":["0.33 A","3 A","8 A","48 A"],"answer":"3 A","hint":"Use Ohm’s law: I = V/R.","why":"I = 12/4 = 3 amperes."},
 {"name":"THE RESISTANCE RIFT","monster":"OHM OGRE","kind":"PHYSICS · CIRCUITS","q":"Two 6 Ω resistors are connected in series","prompt":"What is their equivalent resistance?","choices":["3 Ω","6 Ω","12 Ω","36 Ω"],"answer":"12 Ω","hint":"Series resistances add directly.","why":"R = 6 + 6 = 12 Ω."},
 {"name":"THE MIRROR CHAMBER","monster":"REFRACTION SHADE","kind":"PHYSICS · LIGHT","q":"Angle of incidence is 35°","prompt":"What is the angle of reflection on a plane mirror?","choices":["25°","35°","55°","70°"],"answer":"35°","hint":"The law of reflection equates these angles.","why":"Angle of reflection equals angle of incidence: 35°."},
 {"name":"THE CHEMICAL FOUNDRY","monster":"VALENCE BEAST","kind":"CHEMISTRY · BONDING","q":"What is the formula of magnesium chloride?","prompt":"Magnesium forms Mg²⁺ and chlorine forms Cl⁻.","choices":["MgCl","MgCl₂","Mg₂Cl","Mg₂Cl₃"],"answer":"MgCl₂","hint":"Two chloride ions balance one magnesium ion.","why":"One Mg²⁺ requires two Cl⁻ ions, giving MgCl₂."},
 {"name":"THE REACTION VAULT","monster":"OXIDE KNIGHT","kind":"CHEMISTRY · REACTIONS","q":"2Mg + O₂ → 2MgO","prompt":"Which substance is oxidised?","choices":["Magnesium","Oxygen","Magnesium oxide","Both products"],"answer":"Magnesium","hint":"Oxidation here means gain of oxygen.","why":"Magnesium combines with oxygen, so magnesium is oxidised."},
 {"name":"THE CARBON CATACOMB","monster":"CARBON SHADE","kind":"CHEMISTRY · ORGANIC","q":"Which functional group defines alcohols?","prompt":"Choose the characteristic group.","choices":["−COOH","−CHO","−OH","−CO−"],"answer":"−OH","hint":"It is called the hydroxyl group.","why":"Alcohols contain the hydroxyl (−OH) functional group."},
 {"name":"THE HEREDITY HALL","monster":"ALLELE WITCH","kind":"BIOLOGY · GENETICS","q":"Tt × Tt","prompt":"What fraction of offspring is expected to be tt?","choices":["0","1/4","1/2","3/4"],"answer":"1/4","hint":"The genotype ratio is 1 TT : 2 Tt : 1 tt.","why":"One of four equally likely genotype outcomes is tt."},
 {"name":"THE ECOLOGY ABYSS","monster":"FOODWEB TROLL","kind":"BIOLOGY · ECOLOGY","q":"Grass → grasshopper → frog → snake","prompt":"Which organism is the secondary consumer?","choices":["Grass","Grasshopper","Frog","Snake"],"answer":"Frog","hint":"The primary consumer eats the producer.","why":"Grasshopper is primary; the frog eats it and is secondary."},
 {"name":"THE CELL CITADEL","monster":"MITO WARDEN","kind":"BIOLOGY · CELL BIOLOGY","q":"A cell requires large amounts of usable energy","prompt":"Which organelle is especially abundant in such cells?","choices":["Ribosomes","Mitochondria","Vacuoles","Cell wall"],"answer":"Mitochondria","hint":"They release energy through cellular respiration.","why":"Mitochondria generate much of the cell’s ATP."},
 {"name":"THE CLIMATE SPIRE","monster":"GREENHOUSE GIANT","kind":"EARTH SCIENCE","q":"Which gas is a major human-caused greenhouse gas?","prompt":"Select the best answer from these options.","choices":["Oxygen","Carbon dioxide","Argon","Neon"],"answer":"Carbon dioxide","hint":"Burning fossil fuels releases this gas.","why":"Carbon dioxide traps outgoing infrared radiation and contributes to warming."},
 {"name":"THE DATA LABYRINTH","monster":"AVERAGE ABOMINATION","kind":"MATHEMATICS · DATA","q":"Data: 4, 7, 7, 9, 13","prompt":"What is the median?","choices":["4","7","8","9"],"answer":"7","hint":"The median is the middle value after sorting.","why":"The ordered list has 7 in the middle position."},
 {"name":"THE PROBABILITY PIT","monster":"BAYES BEAST","kind":"MATHEMATICS · PROBABILITY","q":"A bag has 3 red and 2 blue balls","prompt":"Two balls are drawn without replacement. P(both red)?","choices":["1/5","3/10","2/5","1/2"],"answer":"3/10","hint":"Multiply 3/5 by 2/4.","why":"(3/5) × (2/4) = 6/20 = 3/10."},
 {"name":"THE PYTHON ARCHIVE","monster":"INDEX PHANTOM","kind":"CODING · PYTHON","q":"What is [10, 20, 30, 40][−2]?","prompt":"Choose the Python result.","choices":["10","20","30","40"],"answer":"30","hint":"Negative index −1 is last; −2 is second-last.","why":"Index −2 selects the second-last element: 30."},
 {"name":"THE FUNCTION FORTRESS","monster":"SCOPE SPECTRE","kind":"CODING · PYTHON","q":"def f(x): return x*2 + 1","prompt":"What does f(4) return?","choices":["8","9","10","12"],"answer":"9","hint":"Substitute x = 4.","why":"4 × 2 + 1 = 9."},
 {"name":"THE COMPLEXITY CAVERN","monster":"BIG-O BEHEMOTH","kind":"CODING · ALGORITHMS","q":"A loop examines each of n items once","prompt":"What is its time complexity?","choices":["O(1)","O(log n)","O(n)","O(n²)"],"answer":"O(n)","hint":"The number of operations grows linearly with n.","why":"One constant-time operation per item gives linear O(n) time."},
 {"name":"THE LOGIC FURNACE","monster":"TRUTH TABLE TITAN","kind":"LOGIC · BOOLEAN","q":"If P is true and Q is false","prompt":"What is P AND NOT Q?","choices":["True","False","Undefined","Both"],"answer":"True","hint":"NOT Q becomes true; then evaluate true AND true.","why":"P=true and NOT Q=true, so their conjunction is true."},
 {"name":"THE LANGUAGE LAB","monster":"CLAUSE CRAWLER","kind":"ENGLISH · GRAMMAR","q":"Identify the clause: 'Although it was raining, we played.'","prompt":"What kind of clause begins with 'Although'?","choices":["Main clause","Adverbial subordinate clause","Noun clause","Relative clause"],"answer":"Adverbial subordinate clause","hint":"It expresses a contrast or concession.","why":"'Although it was raining' is a concessive adverbial subordinate clause."},
]

class Button:
 def __init__(self, rect, label, fill=(24,43,70), edge=(57,91,128), color=WHITE):
  self.rect=pygame.Rect(rect); self.label=label; self.fill=fill; self.edge=edge; self.color=color
 def draw(self, s, font, mouse, disabled=False):
  hover=self.rect.collidepoint(mouse) and not disabled; fill=tuple(min(255,c+12) for c in self.fill) if hover else self.fill
  pygame.draw.rect(s,fill,self.rect,border_radius=13); pygame.draw.rect(s,CYAN if hover else self.edge,self.rect,2,border_radius=13)
  surf=font.render(self.label,True,self.color); s.blit(surf,surf.get_rect(center=self.rect.center))
 def hit(self,p): return self.rect.collidepoint(p)

def txt(s,font,text,pos,color=WHITE,center=False):
 surf=font.render(str(text),True,color); s.blit(surf,surf.get_rect(center=pos) if center else pos)
def rounded(s,rect,color,r=16,edge=None,width=1):
 pygame.draw.rect(s,color,rect,border_radius=r)
 if edge: pygame.draw.rect(s,edge,rect,width,border_radius=r)
def save_result(score,won,room):
 payload={"run_id":uuid.uuid4().hex,"score":score,"total":1000,"fragments":room if won else max(0,room),"completed_at":time.strftime("%Y-%m-%dT%H:%M:%S"),"won":won,"game":"Cipher Heist: Monster Run"}
 try: RESULT.write_text(json.dumps(payload),encoding="utf-8")
 except OSError: pass

def main():
 pygame.init(); pygame.display.set_caption("Cipher Heist: Monster Run | LifeBridgeAI")
 screen=pygame.display.set_mode((W,H),pygame.RESIZABLE); clock=pygame.time.Clock()
 font=lambda size,bold=False: pygame.font.SysFont("segoeui",size,bold=bold)
 f12=font(12,True); f14=font(14); f16=font(16); f18=font(18); f22=font(22,True); f28=font(28,True); f40=font(40,True); f54=font(54,True)
 stars=[(random.randrange(W),random.randrange(H),random.choice([1,1,2])) for _ in range(100)]
 state="intro"; room=0; run_rooms=[]; previous_run_ids=set(); score=0; answer=""; feedback=""; hint=False; hint_text=False; walk=0.0; hero_x=150; hero_y=440; enemy_bob=0; result_saved=False; shake=0; time_left=10.0; attack_t=0.0; attack_kind="hit"; sword_t=0.0
 choices=[]; choice_rects=[]
 def reset():
  nonlocal state,room,run_rooms,previous_run_ids,score,answer,feedback,hint,hint_text,hero_x,result_saved,shake,time_left,attack_t,sword_t
  available=[q for q in ROOMS if q["name"] not in previous_run_ids]
  if len(available)<10: available=ROOMS[:]
  run_rooms=random.sample(available, min(50, len(available)))
  previous_run_ids={q["name"] for q in run_rooms}; room=0; score=0; answer=""; feedback=""; hint=False; hint_text=False; hero_x=150; result_saved=False; shake=0; time_left=10.0; attack_t=0.0; sword_t=0.0; state="play"
 def build_choices():
  source = run_rooms[room] if run_rooms else ROOMS[0]
  return [Button((x,y,205,48),f"{i+1}  {label}",(19,42,67),(49,96,132)) for i,((x,y),label) in enumerate(zip([(290,430),(510,430),(290,490),(510,490)],source["choices"]))]
 choices=build_choices()
 left=Button((40,555,68,58),"◀",(23,47,75),(57,116,145)); right=Button((118,555,68,58),"▶",(23,47,75),(57,116,145))
 jump=Button((830,555,125,58),"DASH  ➜",(25,75,81),(61,201,189))
 start=Button((350,535,300,64),"START HEIST  ➜",(16,105,111),(73,235,224))
 replay=Button((320,520,175,58),"PLAY AGAIN",(16,105,111),(73,235,224))
 back=Button((510,520,175,58),"GO BACK",(28,39,65),(88,108,143))
 hint_btn=Button((50,490,185,44),"USE HINT TOKEN",(49,36,78),(137,105,188))
 running=True
 while running:
  dt=min(clock.tick(FPS)/1000,0.04); mouse=pygame.mouse.get_pos(); enemy_bob+=dt*4; walk+=dt*8; sword_t=max(0.0,sword_t-dt)
  sw,sh=screen.get_size(); sx=sw/W; sy=sh/H
  # draw in fixed virtual resolution, scale for resized windows
  canvas=pygame.Surface((W,H))
  for x,y,r in stars:
   pygame.draw.circle(canvas,(27,53,83),(int(x),int(y)),r)
  for x in range(0,W,50): pygame.draw.line(canvas,(12,23,43),(x,0),(x,H),1)
  # distant tower silhouettes
  for i in range(9):
   x=i*125-15; h=95+(i*37)%95
   pygame.draw.rect(canvas,(12,22,43),(x,330-h,76,h+190))
   pygame.draw.polygon(canvas,(16,30,53),[(x-8,330-h),(x+38,285-h),(x+84,330-h)])
  # HUD
  rounded(canvas,(24,18,952,64),(13,24,44),17,(40,69,101))
  pygame.draw.circle(canvas,CYAN,(56,50),16,2); pygame.draw.circle(canvas,CYAN,(56,50),5)
  txt(canvas,f22,"CIPHER HEIST",(83,28)); txt(canvas,f12,"MONSTER RUN  /  KNOWLEDGE IS YOUR WEAPON",(85,53),MUTED)
  if state=="intro":
   # vault illustration and hero silhouette
   pygame.draw.circle(canvas,(16,37,61),(500,300),142); pygame.draw.circle(canvas,(43,111,135),(500,300),124,6); pygame.draw.circle(canvas,(22,57,82),(500,300),96,4)
   for a in range(0,360,45):
    rad=math.radians(a); pygame.draw.line(canvas,GOLD,(500+math.cos(rad)*55,300+math.sin(rad)*55),(500+math.cos(rad)*90,300+math.sin(rad)*90),7)
   pygame.draw.circle(canvas,GOLD,(500,300),35,5); pygame.draw.circle(canvas,GOLD,(500,300),10)
   txt(canvas,f12,f"{len(ROOMS)} CHALLENGES · 10 PER RUN · NO BACK-TO-BACK REPEATS",(500,450),CYAN,True)
   txt(canvas,f16,"50-question campaign · Answer within 10 seconds. Correct answers trigger a sword attack.",(500,481),MUTED,True)
   txt(canvas,f16,"Wrong answer or timeout ends the run. The monster advances as the clock runs down.",(500,506),MUTED,True)
   start.draw(canvas,f22,mouse)
  elif state=="play":
   data=run_rooms[room]
   if attack_t > 0:
    attack_t=max(0.0,attack_t-dt)
    if attack_t==0:
     if attack_kind=="hit":
      room+=1; hint=False; hint_text=False; feedback=""; time_left=10.0; hero_x=150
      if room>=len(run_rooms): state="won"; save_result(score,True,room); result_saved=True
      else: choices=build_choices()
     else:
      state="lost"; save_result(score,False,room); result_saved=True
   elif state=="play":
    time_left=max(0.0,time_left-dt)
    if time_left<=0:
     feedback="TIME UP! THE MONSTER CAUGHT YOU."; attack_kind="enemy"; attack_t=0.55
   # Smooth keyboard movement (held keys), with predictable boundaries.
   held=pygame.key.get_pressed()
   if attack_t<=0:
    if held[pygame.K_LEFT] or held[pygame.K_a]: hero_x=max(70,hero_x-260*dt)
    if held[pygame.K_RIGHT] or held[pygame.K_d]: hero_x=min(430,hero_x+260*dt)
  # progress & stats
   rounded(canvas,(35,100,900,7),(38,57,80),4)
   rounded(canvas,(35,100,int(900*room/max(1,len(run_rooms))),7),CYAN,4)
   txt(canvas,f14,f"ROOM {room+1}/{len(run_rooms)}  ·  {data['name']}",(40,121),CYAN)
   txt(canvas,f14,f"SCORE  {score:04d}/{len(run_rooms)*20}",(805,121),GOLD)
   timer_color=RED if time_left<3 else GOLD if time_left<5 else CYAN
   rounded(canvas,(690,145,250,14),(34,48,68),7)
   rounded(canvas,(690,145,int(250*max(0,time_left/10)),14),timer_color,7)
   txt(canvas,f22,f"{max(0,math.ceil(time_left)):02d}s",(950,142),timer_color)
   if time_left < 4 and attack_t<=0: txt(canvas,f12,"DANGER · MONSTER CLOSING IN",(815,170),RED,True)
   if time_left < 2.5 and attack_t<=0: pygame.draw.circle(canvas,(255,70,105),(int(835-(1-max(0,time_left/10))*475),374),58,2)
   # stone floor
   pygame.draw.rect(canvas,(20,31,49),(0,510,W,170)); pygame.draw.line(canvas,(54,79,104),(0,510),(W,510),3)
   for x in range(0,W,100): pygame.draw.line(canvas,(30,47,67),(x,510),(x+45,680),2)
   # hero character, head/body/boots/cape, animated stride
   lunge=(1-attack_t/0.82) if attack_t>0 and attack_kind=="hit" else 0
   hx=int(hero_x+115*max(0,min(1,lunge))); hy=int(hero_y+math.sin(walk)*2)
   pygame.draw.ellipse(canvas,(4,8,18),(hx-25,488,hx+28,500))
   pygame.draw.polygon(canvas,(125,62,111),[(hx-10,hy+4),(hx-31,hy+37),(hx-13,hy+33),(hx+4,hy+10)])
   pygame.draw.rect(canvas,(51,111,150),(hx-13,hy+2,27,30),border_radius=7)
   pygame.draw.circle(canvas,(255,207,157),(hx,hy-10),13)
   pygame.draw.arc(canvas,(82,48,38),(hx-14,hy-24,15,20),math.pi,2*math.pi,6)
   pygame.draw.rect(canvas,(232,190,122),(hx-11,hy-14,22,7),border_radius=3)
   pygame.draw.circle(canvas,(14,28,44),(hx+5,hy-10),2)
   if (attack_t>0 and attack_kind=="hit") or sword_t>0:
    pygame.draw.line(canvas,(191,207,224),(hx+13,hy+5),(hx+83,hy-35),6)
    pygame.draw.line(canvas,GOLD,(hx+13,hy+5),(hx+27,hy+15),6)
    pygame.draw.circle(canvas,GOLD,(min(W-10,hx+75),hy-28),8,2)
    pygame.draw.arc(canvas,CYAN,(hx+25,hy-72,110,95),math.radians(205),math.radians(335),5)
    pygame.draw.circle(canvas,(255,225,155),(hx+85,hy-30),15,2)
    for spark_i in range(7):
     spark_a=walk*3+spark_i*math.tau/7
     pygame.draw.line(canvas,GOLD,(hx+90+math.cos(spark_a)*8,hy-28+math.sin(spark_a)*8),(hx+90+math.cos(spark_a)*19,hy-28+math.sin(spark_a)*19),2)
   else:
    pygame.draw.line(canvas,(191,207,224),(hx+13,hy+8),(hx+29,hy-9),4)
    pygame.draw.polygon(canvas,CYAN,[(hx+28,hy-14),(hx+37,hy-8),(hx+28,hy-3)])
   pygame.draw.line(canvas,(35,43,62),(hx-7,hy+30),(hx-14+int(math.sin(walk)*4),hy+45),7)
   pygame.draw.line(canvas,(35,43,62),(hx+6,hy+30),(hx+12-int(math.sin(walk)*4),hy+45),7)
   # monster sprite right side
   ex=int(835-(1-max(0,time_left/10))*475); ey=int(415+math.sin(enemy_bob)*5)
   if attack_t>0 and attack_kind=="enemy": ex=min(470,ex+int((0.55-attack_t)*560))
   pygame.draw.ellipse(canvas,(5,9,19),(ex-52,493,ex+54,509))
   # horns, ears, body, arms
   pygame.draw.polygon(canvas,(118,53,83),[(ex-29,ey-35),(ex-46,ey-60),(ex-13,ey-49)])
   pygame.draw.polygon(canvas,(118,53,83),[(ex+27,ey-35),(ex+46,ey-59),(ex+12,ey-48)])
   pygame.draw.ellipse(canvas,(109,46,76),(ex-43,ey-45,ex+43,ey+47))
   pygame.draw.ellipse(canvas,(153,57,87),(ex-33,ey-37,ex+33,ey+35))
   pygame.draw.circle(canvas,(255,83,115),(ex-15,ey-10),6); pygame.draw.circle(canvas,(255,83,115),(ex+15,ey-10),6)
   pygame.draw.circle(canvas,(255,225,225),(ex-15,ey-10),2); pygame.draw.circle(canvas,(255,225,225),(ex+15,ey-10),2)
   pygame.draw.arc(canvas,(45,17,38),(ex-18,ey+1,36,24),math.pi,2*math.pi,3)
   pygame.draw.line(canvas,(109,46,76),(ex-35,ey+10),(ex-59,ey+34),12); pygame.draw.line(canvas,(109,46,76),(ex+35,ey+10),(ex+59,ey+34),12)
   # panel
   rounded(canvas,(205,158,590,245),(14,27,48),20,(48,78,108))
   txt(canvas,f12,data["kind"],(235,180),GOLD); txt(canvas,f22,data["monster"],(235,202),WHITE)
   txt(canvas,f40,data["q"],(500,278),CYAN,True)
   txt(canvas,f16,data["prompt"],(500,330),MUTED,True)
   # Answer options
   choices=build_choices()
   for b in choices: b.draw(canvas,f18,mouse,disabled=(attack_t>0))
   if feedback:
    txt(canvas,f14,feedback,(500,405),GREEN if (feedback.startswith("CORRECT") or feedback.startswith("DIRECT SWORD")) else RED,True)
   hint_btn.draw(canvas,f12,mouse)
   if hint_text:
    rounded(canvas,(250,555,520,42),(39,32,61),10,(111,87,150)); txt(canvas,f14,"HINT: "+data["hint"],(270,568),(226,210,255))
   txt(canvas,f12,"MOVE: ARROWS / A-D  •  ANSWER: 1–4  •  SPACE: SWORD SWING  •  H: HINT",(500,640),MUTED,True)
   left.draw(canvas,f28,mouse); right.draw(canvas,f28,mouse); jump.draw(canvas,f14,mouse)
  elif state in ("lost","won"):
   # atmospheric end screen
   for i in range(28):
    ang=i*math.pi*2/28+enemy_bob*.15; rr=130+math.sin(enemy_bob+i)*8
    pygame.draw.circle(canvas,GOLD if state=="won" else RED,(int(500+math.cos(ang)*rr),int(310+math.sin(ang)*rr)),3)
   if state=="won":
    pygame.draw.circle(canvas,(22,75,70),(500,280),95); pygame.draw.circle(canvas,GOLD,(500,280),72,5); pygame.draw.circle(canvas,GOLD,(500,280),25,5)
    txt(canvas,f40,"TREASURE SECURED!",(500,405),GOLD,True)
    txt(canvas,f18,"You defeated every monster and unlocked the Knowledge Vault.",(500,450),MUTED,True)
   else:
    # monster eyes and game-over mark
    pygame.draw.circle(canvas,(74,24,48),(500,270),86); pygame.draw.circle(canvas,RED,(470,260),10); pygame.draw.circle(canvas,RED,(530,260),10)
    txt(canvas,f54,"RUN ENDED",(500,390),RED,True)
    txt(canvas,f18,"The monster won this round. Reset, learn, and try again!",(500,440),MUTED,True)
   txt(canvas,f22,f"FINAL SCORE  {score}",(500,485),GOLD,True)
   replay.draw(canvas,f16,mouse); back.draw(canvas,f16,mouse)
  # scale output to current window size
  if (sw,sh)!=(W,H): screen.blit(pygame.transform.smoothscale(canvas,(sw,sh)),(0,0))
  else: screen.blit(canvas,(0,0))
  pygame.display.flip()
  # Events handled after frame is drawn; map mouse to virtual coordinates
  for event in pygame.event.get():
   if event.type==pygame.QUIT: running=False
   elif event.type==pygame.VIDEORESIZE: screen=pygame.display.set_mode((max(600,event.w),max(420,event.h)),pygame.RESIZABLE)
   elif event.type==pygame.KEYDOWN:
    if state=="intro" and event.key in (pygame.K_RETURN, pygame.K_SPACE):
     reset()
    if state=="play" and attack_t<=0:
     if event.key in (pygame.K_1,pygame.K_KP1,pygame.K_2,pygame.K_KP2,pygame.K_3,pygame.K_KP3,pygame.K_4,pygame.K_KP4):
      idx={pygame.K_1:0,pygame.K_KP1:0,pygame.K_2:1,pygame.K_KP2:1,pygame.K_3:2,pygame.K_KP3:2,pygame.K_4:3,pygame.K_KP4:3}[event.key]
      data=run_rooms[room]
      if data["choices"][idx].strip().lower()==data["answer"].strip().lower():
       score+=10 if hint else 20; feedback="DIRECT SWORD HIT! MONSTER DEFEATED  +"+str(10 if hint else 20)
       attack_kind="hit"; attack_t=0.82; sword_t=0.42
      else:
       attack_kind="enemy"; attack_t=0.55; feedback="WRONG ANSWER! THE MONSTER STRIKES."
     elif event.key==pygame.K_SPACE:
      sword_t=0.38
     elif event.key==pygame.K_h:
      hint=True; hint_text=True
    if event.key in (pygame.K_ESCAPE,):
     if state in ("play","lost","won"): state="intro"
     else: running=False

   elif event.type in (pygame.MOUSEBUTTONDOWN,pygame.FINGERDOWN):
    if event.type==pygame.FINGERDOWN: pos=(int(event.x*W),int(event.y*H))
    else: pos=(int(event.pos[0]*W/max(1,sw)),int(event.pos[1]*H/max(1,sh)))
    if state=="intro":
     if start.hit(pos): reset()
    elif state=="play" and attack_t<=0:
     if left.hit(pos): hero_x=max(70,hero_x-36)
     elif right.hit(pos): hero_x=min(400,hero_x+36)
     elif jump.hit(pos): hero_x=min(430,hero_x+55)
     elif hint_btn.hit(pos) and attack_t<=0: hint=True; hint_text=True
     else:
      for idx,b in enumerate(choices):
       if b.hit(pos):
        data=run_rooms[room]
        if data["choices"][idx].strip().lower()==data["answer"].strip().lower():
         score+=10 if hint else 20; feedback="DIRECT SWORD HIT! MONSTER DEFEATED  +"+str(10 if hint else 20)
         attack_kind="hit"; attack_t=0.82
        else:
         attack_kind="enemy"; attack_t=0.55; feedback="WRONG ANSWER! THE MONSTER STRIKES."
        break
    elif state in ("lost","won"):
     if replay.hit(pos): reset()
     elif back.hit(pos): state="intro"
 pygame.quit()
if __name__=="__main__": main()

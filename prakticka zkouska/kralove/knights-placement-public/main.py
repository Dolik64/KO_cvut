#!/usr/bin/env python3

import gurobipy as g   
import sys

with open(sys.argv[1], "r") as f:
    R = int(f.readline())
    pisemny_seznam = []
    for i in range(R):
        policko = str(f.readline())
        pisemny_seznam.append(policko)
        
ciselny_seznam = []
for i in range (R):
    pozice_str = pisemny_seznam[i]
    
    if(pozice_str[0] == "a"):
        dvojice = [0, int(pozice_str[1]) - 1]
    elif(pozice_str[0] == "b"):
        dvojice = [1, int(pozice_str[1])   -1 ]
    elif(pozice_str[0] == "c"):
            dvojice = [2, int(pozice_str[1]) - 1]
    elif(pozice_str[0] == "d"):
            dvojice = [3, int(pozice_str[1]) - 1]
    elif(pozice_str[0] == "e"):
            dvojice = [4, int(pozice_str[1]) - 1]
    elif(pozice_str[0] == "f"):
            dvojice = [5, int(pozice_str[1]) - 1]
    elif(pozice_str[0] == "g"):
            dvojice = [6, int(pozice_str[1]) - 1]
    elif(pozice_str[0] == "h"):
            dvojice = [7, int(pozice_str[1]) - 1]
                                                    
    ciselny_seznam.append(dvojice)
    
print (ciselny_seznam)    

#promenna bude binarni a bude neco ve stylu je tam jezdec neni tam jezdec

model = g.Model()

t = model.addVars(range(8),range(8), vtype=g.GRB.BINARY, name= "t")

model.setObjective(g.quicksum(t[x,y] for x in range(8) for y in range(8)), g.GRB.MAXIMIZE)

for x in range (8):
    for y in range(8):
        if (x + 2 < 8 and y + 1 < 8):
                    model.addConstr(t[x,y] + t[x+2, y+1] <= 1)
        if (x - 2 >= 0 and y + 1 < 8):
                    model.addConstr(t[x,y] + t[x-2, y+1] <= 1)
        if (x - 2 >= 0 and y - 1 >= 0):
                    model.addConstr(t[x,y] + t[x-2, y-1] <= 1)
        if (x + 2 < 8 and y - 1 >= 0):
                    model.addConstr(t[x,y] + t[x+2, y-1] <= 1)
                    
        if (x + 1 < 8 and y + 2 < 8):
                    model.addConstr(t[x,y] + t[x+1, y+2] <= 1)
        if (x - 1 >= 0 and y + 2 < 8):
                    model.addConstr(t[x,y] + t[x-1, y+2] <= 1)
        if (x - 1 >= 0 and y - 2 >= 0):
                    model.addConstr(t[x,y] + t[x-1, y-2] <= 1)
        if (x + 1 < 8 and y - 2 >= 0):
                    model.addConstr(t[x,y] + t[x+1, y-2] <= 1)
                    
for x, y in ciselny_seznam:
    seznam_pokrytych_poli = []
    for i in range(8):
        seznam_pokrytych_poli.append(t[i, y])
    for i in range(8):
        seznam_pokrytych_poli.append(t[x, i])
    model.addConstr(g.quicksum(seznam_pokrytych_poli) == 0) 

model.optimize()

karel = model.ObjVal
karel = round(karel)
karel = int(karel)

print(karel)

with open(sys.argv[2], "w") as f:
    print(karel, file=f)
    for x in range (8):
        for y in range (8):
            if (t[x,y].X > 0.5):
                if (x == 0):
                    print (str("a") + str(y + 1), file=f)
                elif (x == 1):
                    print (str("b") + str(y + 1), file=f)
                elif (x == 2):
                    print (str("c") + str(y + 1), file=f)
                elif (x == 3):
                    print (str("d") + str(y + 1), file=f)
                elif (x == 4):
                    print (str("e") + str(y + 1), file=f)
                elif (x == 5):
                    print (str("f") + str(y + 1), file=f)
                elif (x == 6):
                    print (str("g") + str(y + 1), file=f)
                elif (x == 7):
                    print (str("h") + str(y + 1), file=f)
                    

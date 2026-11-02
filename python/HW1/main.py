#!/usr/bin/env python3

import sys
import gurobipy as g

with open(sys.argv[1], "r") as f:
    d = [int(v) for v in f.readline().split()]
    e = [int(v) for v in f.readline().split()]
    D = int(f.readline().strip())
    
model = g.Model()

#D = 2
#e = [3, 3, 3, 3, 3, 4, 4, 6, 9, 11, 12, 10, 10, 10, 9, 10, 10, 12, 12, 9, 9, 9, 6, 4]
week = (5*d + 2*e)
x = model.addVars(168, vtype=g.GRB.INTEGER, lb=0)

z = model.addVars(168, vtype=g.GRB.INTEGER, lb=0)

for i in range(168):
    model.addConstr(week[i] - g.quicksum(x[j % 168] for j in range (i-7, i+1)) <= z[i])
    model.addConstr(   g.quicksum(x[j % 168] for j in range (i-7, i+1))  - week[i]  <= z[i])
    model.addConstr(z[i] >= 0)
    model.addConstr(week[i] - g.quicksum(x[j % 168] for j in range (i-7, i+1)) <= D)
    

model.setObjective(z.sum(), sense=g.GRB.MINIMIZE)
model.optimize()   


with open(sys.argv[2], "w") as f:
    f.write(f"{int(round(model.ObjVal))}\n")
    f.write(" ".join(str(int(round(x[i].X))) for i in range(168)) + "\n")
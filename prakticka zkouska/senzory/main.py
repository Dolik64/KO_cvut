import gurobipy as g
import sys

with open (sys.argv[1], "r") as f:
    h, w, b = map(int, f.readline().split())
    J = int(f.readline())
    
    
    stroje = []
    for i in range (b):
        x, y = map(int, f.readline().split())
        stroj = [x, y]
        stroje.append(stroj)
        
model = g.Model()


t = model.addVars(range(h), range(w), vtype = g.GRB.BINARY, name="t")


    
#print(stroje0)

for x,y in stroje:
    model.addConstr(t[x,y] == 0)
    
for x,y in (stroje):
    sousedi = []
    if (x-1 >= 0):
        sousedi.append(t[x-1, y])
    if (x+1 < h):
        sousedi.append(t[x+1, y])
    if (y-1 >= 0):
        sousedi.append(t[x, y-1])
    if (y+1 < w):
        sousedi.append(t[x, y+1])
        
    model.addConstr(g.quicksum(sousedi) == 0)
    

for x in range (h):
    for y in range (w):
        sousedi = []
        if (x-1 >= 0):
                model.addConstr(t[x, y] + t[x-1, y] <=1)
        if (x+1 < h):
                model.addConstr(t[x, y] + t[x+1, y] <=1)
        if (y-1 >= 0):
                model.addConstr(t[x, y] + t[x, y-1] <=1)
        if (y+1 < w):
                model.addConstr(t[x, y] + t[x, y+1] <=1)
                
        if(x-1 >= 0 and y-1 >= 0):
            model.addConstr(t[x, y] + t[x-1, y-1] <=1)              
        if(x+1 < h and y-1 >= 0):
            model.addConstr(t[x, y] + t[x+1, y-1] <=1)  
        if(x+1 < h and y+1 < w):
            model.addConstr(t[x, y] + t[x+1, y+1] <=1)  
        if(x-1 >= 0 and y+1 < w):
            model.addConstr(t[x, y] + t[x-1, y+1] <=1)  
            
model.setObjective(g.quicksum(t[a,b] for a in range (h) for b in range(w)), g.GRB.MAXIMIZE)


model.optimize()

karel = model.ObjVal
karel = round(karel)
kerel = int(karel)

with open (sys.argv[2], "w") as f:
    print(str(karel), file=f)
    for x in range(h):
        for y in range(w):
            if (t[x, y].X > 0.5):
                print(str(x) + " " + str(y), file=f)
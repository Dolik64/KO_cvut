import gurobipy as g 
import sys

walls = []
with open(sys.argv[1], "r") as f:
    h, w, b = map(int, f.readline().split())
    for i in range(b):
        
        x, y = map(int, f.readline().split())
        one_wall = [x, y]
        walls.append(one_wall)
        
model = g.Model()

t = model.addVars(range(h),range(w),vtype=g.GRB.BINARY,name = "t")

model.setObjective(g.quicksum(t[x,y] for x in range (h)for y in range (w)), g.GRB.MINIMIZE )

for x,y in walls:
    
    model.addConstr(t[x,y] == 0)
 

for x in range (h):
    for y in range(w):
        
        
        je_zed = 0   
        for a,b in walls:
             if ((x == a) and (y == b)):
                je_zed = 1
                
                
        sousedi = []
        if (x-1 >= 0):    
            sousedi.append(t[x-1, y])
        if (x+1 < h):
            sousedi.append(t[x+1,y])
        if (y-1 >= 0):
            sousedi.append(t[x, y-1])
        if(y+1 < w):
            sousedi.append(t[x,y+1])
        
        sousedi.append(t[x,y])
        
        if (je_zed == 0 ):
            model.addConstr(g.quicksum(sousedi) >= 1)



model.optimize()

karel = model.ObjVal
karel = round(karel)
karel = int(karel)

with open(sys.argv[2], "w") as f:
    print(str(karel), file=f)
    for x in range (h):
        for y in range (w):
            if (t[x,y].X > 0.5):
                print (str(x) + " " + str(y), file=f)
    
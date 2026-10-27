"""Closed height-field stand with a finer central aisle and no internal faces."""
def stepped_stand(center,u,v,length,width,height=3,base=.16,seat_rows=7,aisle_width=2.8):
 n=seat_rows*2;xs=[-length/2,-aisle_width/2,aisle_width/2,length/2];ds=[-width/2+j*width/n for j in range(n+1)];zs=[base+k*height/n for k in range(n+1)];vertices=[];faces=[];lookup={}
 def occupied(i,j,k):
  if not(0<=i<3 and 0<=j<n and k>=0):return False
  return k<(n-j if i==1 else n-(j//2)*2)
 def vertex(i,j,k):
  key=(i,j,k)
  if key not in lookup:lookup[key]=len(vertices);vertices.append(tuple(center[q]+u[q]*xs[i]+v[q]*ds[j]+(zs[k] if q==2 else 0) for q in range(3)))
  return lookup[key]
 patterns=[((-1,0,0),(0,4,7,3)),((1,0,0),(1,2,6,5)),((0,-1,0),(0,1,5,4)),((0,1,0),(3,7,6,2)),((0,0,-1),(0,3,2,1)),((0,0,1),(4,5,6,7))]
 offsets=[(0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,1),(1,0,1),(1,1,1),(0,1,1)]
 for i in range(3):
  for j in range(n):
   for k in range(n):
    if not occupied(i,j,k):continue
    for delta,corners in patterns:
     if occupied(i+delta[0],j+delta[1],k+delta[2]):continue
     faces.append(tuple(vertex(i+offsets[c][0],j+offsets[c][1],k+offsets[c][2]) for c in corners))
 return vertices,faces

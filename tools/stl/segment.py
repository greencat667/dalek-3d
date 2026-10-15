# Split the 1965 Dalek STL (Stryker123, Thingiverse 3163881, CC BY) into the archive's named components and pack them.
import struct, math, sys, json, gzip, base64
from collections import defaultdict, Counter
D=sys.argv[1]; OUT=sys.argv[2]
b=open(D+'/complete.stl','rb').read(); n=struct.unpack('<I',b[80:84])[0]
mask=open(D+'/mask.bin','rb').read()
T=[struct.unpack_from('<12f',b,84+i*50)[3:] for i in range(n)]
YC=4.26; S=0.0525
def cen(t): return ((t[0]+t[3]+t[6])/3,(t[1]+t[4]+t[7])/3,(t[2]+t[5]+t[8])/3)
# skirt seam polygon (ref units) at bottom (z=1.7) and top (z=14.45), 11 loop vertices + 3 split points = 14 seams
SKB=[(0,-8.47),(3.5,-6.46),(6.5,-2.23),(7.48,1.98),(7.48,10.43),(4.48,12.43)]   # measured in the assembled model
SKT=[(0,-3.66),(2.97,-2.66),(5.25,0.1),(6.27,3.14),(6.28,8.75),(3.52,10.75)]
def loop(h): return h+[(-x,y) for x,y in reversed(h[1:])]
LB,LT=loop(SKB),loop(SKT)
SPLIT={3,5,7}
def seams(z):
    t=(z-1.7)/(14.2-1.7); L=[(a[0]+(c[0]-a[0])*t,a[1]+(c[1]-a[1])*t) for a,c in zip(LB,LT)]
    s=[]
    for i in range(11):
        s.append(L[i])
        if i in SPLIT: a,c=L[i],L[(i+1)%11]; s.append(((a[0]+c[0])/2,(a[1]+c[1])/2))
    return s
def segdist(p,a,c):
    ex,ey=c[0]-a[0],c[1]-a[1]; L2=ex*ex+ey*ey; u=max(0,min(1,((p[0]-a[0])*ex+(p[1]-a[1])*ey)/L2))
    return math.hypot(p[0]-a[0]-u*ex,p[1]-a[1]-u*ey)
part=[None]*n
# gun and sucker axes from the parts that are unambiguously ahead of the casing
def axis(sign):
    c=[cen(t) for t in T if cen(t)[1]<-5 and cen(t)[0]*sign>0 and 15<cen(t)[2]<19.5]
    return sum(x for x,_,_ in c)/len(c), sum(z for _,_,z in c)/len(c)
GA,AA=axis(1),axis(-1); print('gun axis',GA,'arm axis',AA)
for i,t in enumerate(T):
    cx,cy,cz=cen(t); r=math.hypot(cx,cy-YC); m=mask[i]
    if m==1: part[i]='globes'; continue
    if cz<1.55: part[i]='fender'; continue
    if cz<14.45:
        s=seams(cz); k=min(range(14),key=lambda j:segdist((cx,cy),s[j],s[(j+1)%14])); part[i]='panel%d'%k; continue
    if cz>14.6 and cy<-2.25 and cx>0 and math.hypot(cx-GA[0],cz-GA[1])<0.95: part[i]='gun'; continue
    if cz>14.6 and cy<-2.25 and cx<0 and math.hypot(cx-AA[0],cz-AA[1])<1.45: part[i]='arm'; continue
    if cz<15.1: part[i]='belt'; continue
    if cz<18.45 and 1.9<abs(cx)<5.3 and cy<0.9 and r>6.4: part[i]='gunMount' if cx>0 else 'armMount'; continue
    if cz<21.45: part[i]='shoulders'; continue
    if cz<25.3 and r>5.2: part[i]='ring0' if cz<22.4 else ('ring1' if cz<24.0 else 'ring2'); continue
    if cz<25.9: part[i]='neck'; continue
    if cz<26.6 and r>4.55: part[i]='collar'; continue
    if cz>26.6 and cy<-0.3 and abs(cx)<1.4: part[i]='eye'; continue
    if cz>27.3 and min(math.hypot(abs(cx)-3.87,cy-4.33),9)<0.8: part[i]='lightL' if cx<0 else 'lightR'; continue
    part[i]='dome'
print(Counter(part))
# pivots (ref units)
def mean(idx,f): return sum(f(cen(T[i])) for i in idx)/len(idx)
def pivot_of(key,sel):
    idx=[i for i in range(n) if part[i]==key and sel(cen(T[i]))]
    return (mean(idx,lambda c:c[0]),mean(idx,lambda c:c[1]),mean(idx,lambda c:c[2]),len(idx))
gp=pivot_of('gun',lambda c:c[1]>-3.6); ap=pivot_of('arm',lambda c:c[1]>-3.6)
ep=pivot_of('eye',lambda c:c[1]>-1.1)
# extents of moving parts
def ext(key):
    vs=[(T[i][j],T[i][j+1],T[i][j+2]) for i in range(n) if part[i]==key for j in (0,3,6)]
    return [round(min(v[k] for v in vs),3) for k in range(3)],[round(max(v[k] for v in vs),3) for k in range(3)]
for k in ['gun','arm','eye','lightL','gunMount','ring0','ring1','ring2','collar','dome','neck','belt','shoulders']: print(k,ext(k))
print('pivots gun',gp,'arm',ap,'eye',ep)
# globe clustering by shared vertices
gidx=[i for i in range(n) if part[i]=='globes']
par={}
def f(a):
    while par[a]!=a: par[a]=par[par[a]]; a=par[a]
    return a
key=lambda x,y,z:(round(x,3),round(y,3),round(z,3))
for i in gidx:
    t=T[i]; ks=[key(*t[j:j+3]) for j in (0,3,6)]
    for k in ks: par.setdefault(k,k)
    r0=f(ks[0])
    for k in ks[1:]: par[f(k)]=r0
groups=defaultdict(list)
for i in gidx: groups[f(key(*T[i][0:3]))].append(i)
gl=sorted(groups.values(),key=lambda g:-len(g))
print('globe clusters',len(gl),[len(g) for g in gl[:3]],[len(g) for g in gl[-3:]])
json.dump({'part':part,'gun':gp,'arm':ap,'eye':ep,'globes':gl},open(OUT+'/seg.json','w'))

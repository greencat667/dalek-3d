import struct, json, gzip, base64, sys, math
D=sys.argv[1]
b=open(D+'/ref-viewer/complete.stl','rb').read(); n=struct.unpack('<I',b[80:84])[0]
mask=open(D+'/ref-viewer/mask.bin','rb').read()
T=[struct.unpack_from('<12f',b,84+i*50)[3:] for i in range(n)]
seg=json.load(open(D+'/seg.json')); part=seg['part']
YC=4.26; S=0.0525; Q=20000
conv=lambda x,y,z:(x*S, z*S, -(y-YC)*S)
PIV={'gun':conv(3.498,-2.2,16.767),'arm':conv(-3.776,-2.1,16.827),'eye':conv(0,-0.65,28.411)}
gid={}
for g,idx in enumerate(seg['globes']):
    for i in idx: gid[i]=g
groups={}
for i in range(n):
    k=part[i]; c=mask[i]
    if k=='globes': k='globe%d'%gid[i]; c=1
    elif k in('lightL','lightR') and (T[i][2]+T[i][5]+T[i][8])/3>28.75: c=3
    elif c==1: c=0
    groups.setdefault((k,c),[]).append(i)
hdr=[]; data=bytearray()
for (k,c),idx in sorted(groups.items()):
    base=k.rstrip('0123456789') if k.startswith('globe') else k
    pv=PIV.get(k,(0,0,0))
    for i in idx:
        t=T[i]
        for j in (0,3,6):
            X,Y,Z=conv(t[j],t[j+1],t[j+2]); data+=struct.pack('<3h',round((X-pv[0])*Q),round((Y-pv[1])*Q),round((Z-pv[2])*Q))
    hdr.append({'k':k,'c':c,'n':len(idx)})
gz=gzip.compress(bytes(data),9)
blob=base64.b64encode(gz).decode()
open(D+'/shell.b64','w').write(blob)
json.dump({'parts':hdr,'pivots':{k:[round(v,5) for v in p] for k,p in PIV.items()},'q':Q},open(D+'/shell.json','w'))
print(len(hdr),'groups; raw',len(data),'gz',len(gz),'b64',len(blob)); print({k:[round(v,4) for v in p] for k,p in PIV.items()})

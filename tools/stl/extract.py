import re, base64, gzip, struct, json, sys
h=open(sys.argv[1]).read()
def blob(i):
    m=re.search(r'<script type="application/octet-stream" id="%s">(.*?)</script>'%i,h,re.S); return gzip.decompress(base64.b64decode(m.group(1).strip()))
meta=json.loads(re.search(r'<script type="application/json" id="fileMetadata">(.*?)</script>',h,re.S).group(1))
open(sys.argv[2]+'/complete.stl','wb').write(blob('stl-complete'))
mask=blob('paint-mask'); open(sys.argv[2]+'/mask.bin','wb').write(mask)
from collections import Counter
print(len(mask), Counter(mask), list(meta.keys()))

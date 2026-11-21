import re,json,sys
def rsc(path):
    t=open(path,encoding='utf-8').read()
    parts=re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)',t,flags=re.S)
    return ''.join(json.loads(p) for p in parts)
def lines(s):
    out={}
    for m in re.finditer(r'^([0-9a-f]+):(.*)$',s,flags=re.M):
        out[m.group(1)]=m.group(2)
    return out
if __name__=='__main__':
    s=rsc(sys.argv[1]); L=lines(s)
    for k,v in L.items():
        if v.startswith('{') or v.startswith('['):
            try:
                d=json.loads(v); print(k,type(d).__name__,len(v), str(d)[:150])
            except Exception as e: pass

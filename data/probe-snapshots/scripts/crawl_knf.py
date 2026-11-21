import json,urllib.request,time
B='https://www.knf.gov.pl/api/podmioty-children'
def get(q):
    req=urllib.request.Request(B+'?'+q,headers={'User-Agent':'Mozilla/5.0 research-probe'})
    for i in range(3):
        try:
            return json.load(urllib.request.urlopen(req,timeout=40))
        except Exception as e: time.sleep(2)
    return {'items':[],'err':True}
subs={}
for p in [1,2,3,4,57467,57468,57469,501688,501689,1390251,2102845,7238697,7238698]:
    d=get(f'parentId={p}&type=SUBCATEGORY&pageSize=100')
    subs[p]=[(s['id'],s['name'],s.get('hasSubSubCategory')) for s in d['items']]
    print(p,len(subs[p]),{k:v for k,v in d.items() if k!='items'})
    time.sleep(.3)
json.dump(subs,open('registers/knf_subcategories.json','w'),ensure_ascii=False,indent=1)

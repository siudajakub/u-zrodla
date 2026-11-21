import json,time,sys
sys.path.insert(0,'.')
exec(open('crawl_knf.py').read().split('subs={}')[0])
targets={19:'domy_maklerskie',8:'banki_maklerskie',57490:'banki_art70',32:'towarowe_dm',44:'oddzialy_zagr_FI',57:'notyfikacje_zagr_FI',5:'agenci_fiz',6:'agenci_prawne',22:'cofniete_zezwolenie',5988205:'FI_historyczne',33:'TFI',1384614:'doradcy_inwest',1384612:'maklerzy',1384613:'maklerzy_doradcy',57480:'rejestr_FI',57485:'rejestr_agentow',57500:'krajowe_DM_oddzial_EOG',57504:'krajowe_DM_EOG',236573:'banki_powiernicze',65039:'ASI',2102846:'oddzialy_bankow_zagr',5355962:'crowdfunding'}
summary={}
for pid,name in targets.items():
    items=[];page=0
    while True:
        d=get(f'parentId={pid}&page={page}&pageSize=100&type=COMPANY')
        it=d['items']
        if not it:
            # try without type (for sub-subcategories)
            if page==0:
                d2=get(f'parentId={pid}&type=SUBCATEGORY&pageSize=100')
                if d2['items']:
                    for s in d2['items']:
                        pg=0
                        while True:
                            dd=get(f'parentId={s["id"]}&page={pg}&pageSize=100&type=COMPANY')
                            if not dd['items']: break
                            items+=dd['items']; pg+=1
                            if len(dd['items'])<100: break
                            time.sleep(.2)
            break
        items+=it;page+=1
        if len(it)<100: break
        time.sleep(.2)
        if page>200: break
    summary[name]=len(items)
    json.dump(items,open(f'registers/knf_{name}.json','w'),ensure_ascii=False)
    print(name,pid,len(items),flush=True)

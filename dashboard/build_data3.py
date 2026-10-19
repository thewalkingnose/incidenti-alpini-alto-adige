import json,csv,re,collections
d=json.load(open("dati_audb.json"))
alt={r['id']:float(r['quota_m']) for r in csv.DictReader(open("quote_incidenti.csv"))}
t=open("main.js",encoding="utf-8",errors="replace").read()
def unesc(s): return re.sub(r"\\x([0-9a-fA-F]{2})",lambda m:chr(int(m.group(1),16)),s)
def lst(name):
    i=t.find(name+"=[");j=t.index("[",i);dep=0
    for k in range(j,len(t)):
        dep+=(t[k]=="[")-(t[k]=="]")
        if dep==0: return t[j:k+1]
def tab(n): return {int(a):unesc(c) for a,b,c in re.findall(r'\{id:(-?\d+),name:"([^"]*)",name2:"([^"]*)"',lst(n))}
disc=tab("disziplinenListe"); caus=tab("unfallursachenListe"); nat=tab("nationalitaetenListe")
# comuni hierarchy
distr=[];comuni=[];cidx={}
for a,b,c in re.findall(r'\{id:(\d+),name:"([^"]*)",name2:"([^"]*)"',lst("gemeindenListe")):
    a=int(a);c=unesc(c)
    if a<100: distr.append(c)
    else: cidx[a]=len(comuni);comuni.append({"n":c,"d":len(distr)-1})
print(distr,len(comuni))
parent=lambda c: 100 if c in(101,102) else 400 if 401<=c<=406 else 800 if 801<=c<=804 else 1100 if 1101<=c<=1104 else 1400 if 1401<=c<=1404 else 1500 if 1501<=c<=1505 else 1600 if 1601<=c<=1603 else 1700 if 1701<=c<=1706 else c
macro={100:'Lavoro',201:'Incidente stradale',301:'Impianti a fune',400:'Volo (parapendio e altro)',501:'Escursionismo',601:'Alta montagna / ghiacciaio',701:'Speleologia',800:'Arrampicata',901:'Parchi avventura',1001:'Ferrata',1100:'Bicicletta',1201:'Slittino',1301:'Sci di fondo',1400:'Sci su pista',1500:'Fuoripista e scialpinismo',1600:'Acque libere',1700:'Altro (funghi, alpeggi, caccia…)',1801:'Falso allarme'}
cap=lambda s:s[0].upper()+s[1:]
P=d['patienten'];E=d['einsaetze'];evidx={e['id']:i for i,e in enumerate(E)}
orgmap={'BRD':0,'CNSAS':1,'TWO_B':2,'TWO_C':2}
PLACEHOLDER=(680631,5152073)   # 57 eventi 2026 di sci/snowboard con le stesse coordinate (segnaposto a Bolzano)
def evrow(e):
    bad=(e['x'],e['y'])==PLACEHOLDER
    return [int(e['einsatzdatum'].replace('-','')),-1 if bad else int(round(alt[e['id']])),e['hubschrauber'],orgmap[e['id'].split('-')[0]],cidx[int(e['gemeinde'])],
            -1 if bad else round((e['x']-600000)/50),-1 if bad else round((e['y']-5150000)/50)]
ev=[evrow(e) for e in E]
print('eventi senza posizione valida:',sum(1 for r in ev if r[1]<0))
# raw index tables sorted by global frequency
def order(vals,force_last=()):
    o=[k for k,_ in collections.Counter(vals).most_common() if k not in force_last]+[k for k in force_last if k in set(vals)]
    return o,{k:i for i,k in enumerate(o)}
det_o,det_i=order([p['disziplin'] for p in P],force_last=(1706,))
caus_o,caus_i=order([p['unfallursache'] for p in P],force_last=(20,))
nat_o,nat_i=order([p['nation'] for p in P],force_last=(8,))
grp_o,grp_i=order([parent(c) for c in [p['disziplin'] for p in P]],force_last=(1700,))
dl=lambda c:('Altro (generico)' if c==1706 else cap(disc[c]))
folg_labels=['Indenne','Lievemente ferito','Gravemente ferito','In pericolo di vita','Deceduto','Non noto']
eta_labels=['0–9','10–19','20–29','30–39','40–49','50–59','60–69','70–79','80 e oltre','Non nota']
eta_raw=lambda a:{1:0,2:1,3:2,4:3,5:4,6:5,7:6,8:7,9:8}.get(a,9)
sesso_labels=['Maschile','Femminile','Non noto']
auf_labels=['Discesa','Salita','Non indicato']
org_labels=['Soccorso Alpino AVS (BRD)','CNSAS','BRD e CNSAS insieme']
pe=[[evidx[p['id-ereignis']],det_i[p['disziplin']],caus_i[p['unfallursache']],p['unfallfolgen']-1,eta_raw(p['alter']),{1:0,2:1}.get(p['geschlecht'],2),nat_i[p['nation']],{2:0,1:1}.get(p['aufabstieg'],2)] for p in P]
# district freq order for 'dist' dimension
dc=collections.Counter(comuni[e[4]]['d'] for e in ev); dist_o=[k for k,_ in dc.most_common()]; dist_map=[dist_o.index(i) for i in range(len(distr))]
fields=dict(
 det=dict(labels=[dl(c) for c in det_o],parent=[grp_i[parent(c)] for c in det_o],groups=[macro[c] for c in grp_o],gray=[det_o.index(1706)]),
 causa=dict(labels=[caus[c] for c in caus_o],gray=[caus_o.index(20)]),
 folg=dict(labels=folg_labels),eta=dict(labels=eta_labels),sesso=dict(labels=sesso_labels),
 naz=dict(labels=['Non nota' if c==8 else nat[c] for c in nat_o],gray=[nat_o.index(8)]),
 auf=dict(labels=auf_labels),org=dict(labels=org_labels),
 comune=dict(labels=[c['n'] for c in comuni],parent=[c['d'] for c in comuni],groups=distr))
dims=[
 dict(key='grp',label='Attività (gruppi)',kind='cat',src='det',map=[grp_i[parent(c)] for c in det_o],cats=[macro[c] for c in grp_o],gray=[grp_o.index(1700)],other='Altre attività'),
 dict(key='det',label='Attività (dettaglio)',kind='cat',src='det',map=None,cats=fields['det']['labels'],gray=fields['det']['gray'],other='Altre attività'),
 dict(key='causa',label='Causa dell’incidente',kind='cat',src='causa',map=None,cats=fields['causa']['labels'],gray=fields['causa']['gray'],other='Altre cause'),
 dict(key='folg',label='Conseguenza',kind='ord',src='folg',map=[0,1,2,2,3,4],cats=['Indenne','Lievemente ferito','Gravemente ferito o in pericolo di vita','Deceduto','Non noto'],gray=[4],other=''),
 dict(key='eta',label='Età',kind='ord',src='eta',map=[0,0,1,1,2,2,3,3,4,5],cats=['0–19','20–39','40–59','60–79','80 e oltre','Non nota'],gray=[5],other=''),
 dict(key='sesso',label='Sesso',kind='cat',src='sesso',map=None,cats=sesso_labels,gray=[2],other=''),
 dict(key='naz',label='Nazionalità',kind='cat',src='naz',map=None,cats=fields['naz']['labels'],gray=fields['naz']['gray'],other='Altre nazionalità'),
 dict(key='auf',label='Salita / discesa',kind='cat',src='auf',map=None,cats=auf_labels,gray=[2],other=''),
 dict(key='dist',label='Distretto',kind='cat',src=None,lvl='e',map=dist_map,cats=[distr[i] for i in dist_o],gray=[],other='Altri distretti'),
 dict(key='heli',label='Elicottero',kind='cat',src=None,lvl='e',map=None,cats=['Con elicottero','Senza elicottero'],gray=[],other=''),
 dict(key='org',label='Organizzazione',kind='cat',src=None,lvl='e',map=None,cats=org_labels,gray=[],other=''),
 dict(key='stag',label='Stagione',kind='cat',src=None,lvl='e',map=None,cats=['Estate (mag–ott)','Inverno (nov–apr)'],gray=[],other='')]
import geo_build
out=dict(ev=ev,pe=pe,fields=fields,dims=dims,geo=geo_build.build(cidx))
js=json.dumps(out,ensure_ascii=False,separators=(',',':'))
open("data3.js","w").write("const DATA="+js+";");print(len(js)//1024,"KB")

import pandas as pd, numpy as np
from scipy import stats
import statsmodels.formula.api as smf
pd.set_option('display.width',220); pd.set_option('display.max_columns',30)
p=pd.read_pickle('p.pkl')
d=p[(p.anno>=2022)&(p.anno<=2025)].copy()   # anni completi e non anomali
h=d[d.attivita=='Escursionismo'].copy()
ev=h.drop_duplicates('id_evento')
print("== eventi escursionismo per giorno settimana (2022-25), atteso uniforme=14.3%")
dow=ev.groupby('dow').size(); print((dow/dow.sum()*100).round(1).to_dict(), 'chi2 p=',stats.chisquare(dow).pvalue)
we=ev[ev.mese.between(6,9)].groupby('dow').size(); print('giu-set:',(we/we.sum()*100).round(1).to_dict())
print("\n== persone-età media per giorno (feriale vs weekend), escursionismo estate")
s=h[h.mese.between(6,9)&h.eta_num.notna()]
s=s.assign(we=s.dow>=5)
print(s.groupby('we').agg(n=('eta_num','size'),eta=('eta_num','mean'),over65=('eta_num',lambda x:(x>=65).mean()*100),Bz=('nazionalita',lambda x:(x=='Italia (Prov. di Bolzano)').mean()*100),Itaaltre=('nazionalita',lambda x:(x=='Italia (altre regioni)').mean()*100)).round(1))
print("\n== MESE: eventi, età, quota media, %grave, %heli, %malore+cuore, %cadute")
g=h[h.conseguenza!='non noto'].groupby('mese')
print(pd.DataFrame({'n':g.size(),'quota':g.quota_m.mean(),'eta':g.eta_num.mean(),'gm%':g.grave_o_morto.mean()*100,'heli%':g.heli.mean()*100,
 'mal+cuo%':g.apply(lambda x:x.causa.isin(['Malore','Cuore/circolazione']).mean()*100),'cadute%':g.apply(lambda x:(x.causa.str.startswith('Caduta,')).mean()*100),
 'sfin%':g.apply(lambda x:(x.causa=='Sfinimento').mean()*100),'orient%':g.apply(lambda x:x.causa.str.startswith('Perdita').mean()*100)}).round(1))
print("\n== QUOTA (hiking): causa mix per fascia")
h['qb']=pd.cut(h.quota_m,[0,1000,1500,2000,2500,4000])
top=['Caduta, inciampo, scivolamento','Malore','Cuore/circolazione','Sfinimento','Perdita orientamento, fuorivia','Attrezzatura inidonea, incapacità']
h['c']=h.causa.where(h.causa.isin(top),'altro')
print(pd.crosstab(h.qb,h.c,normalize='index').mul(100).round(1)[top+['altro']])
print(h.groupby('qb',observed=True).agg(n=('eta_num','size'),eta=('eta_num','mean'),heli=('heli','mean')).round(2))
print("\n== QUOTA x età (hiking, estate): %over65 per fascia")
print(h[h.mese.between(6,9)&h.eta_num.notna()].groupby('qb',observed=True).apply(lambda x:pd.Series({'n':len(x),'over65%':(x.eta_num>=65).mean()*100,'under30%':(x.eta_num<=25).mean()*100})).round(1))
print("\n== Dimensione gruppo (persone per evento) hiking: esito")
ev2=h[h.conseguenza!='non noto'].copy(); ev2['gr']=ev2.persone_ev.clip(upper=4)
print(ev2.groupby('gr').agg(n=('morto','size'),morto=('morto','mean'),gm=('grave_o_morto','mean'),indenne=('indenne','mean'),heli=('heli','mean')).mul([1,100,100,100,100]).round(1))
print("\n== Persone/evento dove >=2: causa (primo)")
print(h[h.persone_ev>=2].c.value_counts(normalize=True).mul(100).round(1).to_dict())
print(h[h.persone_ev==1].c.value_counts(normalize=True).mul(100).round(1).to_dict())
print("\n== Distanza da impianto/malga/rifugio: esito (hiking, estate, eventi) – per persona")
e=h[h.mese.between(6,9)&h.dist_qualsiasi_m.notna()&(h.conseguenza!='non noto')].copy()
e['band']=pd.cut(e.dist_qualsiasi_m,[-1,250,1000,2000,100000],labels=['<=250','250-1000','1-2km','>2km'])
print(e.groupby('band',observed=True).agg(n=('morto','size'),gm=('grave_o_morto','mean'),morto=('morto','mean'),heli=('heli','mean'),eta=('eta_num','mean'),cuore=('causa',lambda x:(x=='Cuore/circolazione').mean()),orient=('causa',lambda x:x.str.startswith('Perdita').mean())).mul([1,100,100,100,1,100,100]).round(1))

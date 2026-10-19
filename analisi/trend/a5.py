import pandas as pd, numpy as np
from scipy import stats
import statsmodels.formula.api as smf
pd.set_option('display.width',220); pd.set_option('display.max_columns',30)
p=pd.read_pickle('p.pkl')
h=p[(p.attivita=='Escursionismo')&(p.anno>=2022)&(p.conseguenza!='non noto')].copy()
cu=h[h.causa=='Cuore/circolazione']
print("== CUORE: n,morti,letalità per sesso / età")
print(cu[cu.sesso!='non noto'].groupby('sesso').agg(n=('morto','size'),morti=('morto','sum'),let=('morto','mean'),eta=('eta_num','mean'),heli=('heli','mean')).round(3))
print(cu[cu.eta_num.notna()].assign(f=lambda x:pd.cut(x.eta_num,[0,50,60,70,100],labels=['<50','50s','60s','70+'])).groupby('f',observed=True).agg(n=('morto','size'),morti=('morto','sum'),let=('morto','mean')).round(3))
print("cuore: quota media",cu.quota_m.mean().round(0),"vs altri",h[h.causa!='Cuore/circolazione'].quota_m.mean().round(0))
print("cuore salita%:",(cu.salita_discesa=='salita').sum(),"su",(cu.salita_discesa!='').sum(), " | altri:", round((h[h.causa!='Cuore/circolazione'].salita_discesa=='salita').sum()/ (h[h.causa!='Cuore/circolazione'].salita_discesa!='').sum(),3))
print("\n== CADUTE: letalità per sesso, età")
f=h[h.causa=='Caduta, inciampo, scivolamento']
print(f[f.sesso!='non noto'].groupby('sesso').agg(n=('morto','size'),morti=('morto','sum'),let=('morto','mean'),gm=('grave_o_morto','mean'),eta=('eta_num','mean')).round(3))
print(f[f.eta_num.notna()].assign(f=lambda x:pd.cut(x.eta_num,[0,30,50,65,100])).groupby('f',observed=True).agg(n=('morto','size'),morti=('morto','sum'),gm=('grave_o_morto','mean'),let=('morto','mean')).round(3))
print("\n== Caduta in SALITA vs DISCESA: gravità")
print(f[f.salita_discesa!=''].groupby('salita_discesa').agg(n=('morto','size'),gm=('grave_o_morto','mean'),let=('morto','mean'),eta=('eta_num','mean'),heli=('heli','mean')).round(3))
print("\n== Sesso: quota% nei vari esiti")
print(pd.crosstab(h[h.sesso!='non noto'].sesso,h[h.sesso!='non noto'].conseguenza,normalize='columns').mul(100).round(1))
print("\n== Locali (BZ) vs altri: causa mix, età, quota, weekend")
h['loc']=np.where(h.nazionalita=='Italia (Prov. di Bolzano)','BZ',np.where(h.nazionalita=='Germania','DE','altri'))
top=['Caduta, inciampo, scivolamento','Malore','Cuore/circolazione','Sfinimento','Perdita orientamento, fuorivia','Attrezzatura inidonea, incapacità']
h['c']=h.causa.where(h.causa.isin(top),'altro')
print(pd.crosstab(h['loc'],h.c,normalize='index').mul(100).round(1)[top+['altro']])
print(h.groupby('loc').agg(n=('eta_num','size'),eta=('eta_num','mean'),quota=('quota_m','mean'),weekend=('dow',lambda x:(x>=5).mean()*100),gm=('grave_o_morto','mean'),heli=('heli','mean')).round(2))
print("\n== Mese: Set-Nov vs Giu-Ago, disorientamento e gravità")
a=h[h.mese.isin([6,7,8])]; b=h[h.mese.isin([9,10,11])]
for lab,fn in [('orient',lambda x:x.causa.str.startswith('Perdita')),('gm',lambda x:x.grave_o_morto==1),('heli',lambda x:x.heli==1),('sfinimento',lambda x:x.causa=='Sfinimento')]:
    x1,n1,x2,n2=fn(a).sum(),len(a),fn(b).sum(),len(b)
    print(f"{lab:11s} estate {x1/n1*100:5.1f}%  set-nov {x2/n2*100:5.1f}%  p={stats.fisher_exact([[x1,n1-x1],[x2,n2-x2]])[1]:.4f}")
print("\n== Giorni con più eventi hiking (2022-25)")
ev=h.drop_duplicates('id_evento'); top=ev.groupby('data').size().sort_values(ascending=False).head(10); print(top)
print("\n== Ferragosto/festivi: media eventi/giorno luglio-agosto feriali vs sab vs dom")
ja=ev[ev.mese.isin([7,8])]; days=ja.groupby('data').size().reset_index(name='n'); days['dow']=pd.to_datetime(days.data).dt.dayofweek
print(days.groupby('dow').n.mean().round(1).to_dict())
print("\n== Trend con correzione (hiking 2022-2026, parziale 2026 escluso per stagionalità)")
hh=p[(p.attivita=='Escursionismo')&(p.anno.between(2022,2025))].copy()
tests={}
hh['naz_altri']=(~hh.nazionalita.isin(['Italia (Prov. di Bolzano)','Italia (altre regioni)','Germania','Austria'])).astype(int)
hh['it_altre']=(hh.nazionalita=='Italia (altre regioni)').astype(int)
hh['sfin']=(hh.causa=='Sfinimento').astype(int); hh['orient']=hh.causa.str.startswith('Perdita').astype(int)
hh['over65']=(hh.eta_num>=65).astype(float).where(hh.eta_num.notna())
hh['cadute']=hh.causa.str.startswith('Caduta,').astype(int); hh['heli_']=hh.heli
hh['malcuo']=hh.causa.isin(['Malore','Cuore/circolazione']).astype(int)
hh['M']=(hh.sesso=='maschile').astype(float).where(hh.sesso!='non noto')
hh['gm']=hh.grave_o_morto.astype(float).where(hh.conseguenza!='non noto')
res=[]
for v in ['naz_altri','it_altre','sfin','orient','over65','cadute','heli_','malcuo','M','gm']:
    dd=hh[['anno',v]].dropna().rename(columns={v:'y'}); m=smf.logit('y~anno',dd).fit(disp=0)
    res.append((v,np.exp(m.params['anno']),m.pvalues['anno'],dd.groupby('anno').y.mean().round(3).to_dict()))
pv=[r[2] for r in res]; order=np.argsort(pv); k=len(pv)
for r in sorted(res,key=lambda r:r[2]): print(f"{r[0]:10s} OR/anno={r[1]:.3f} p={r[2]:.4f}  p_bonf={min(1,r[2]*k):.3f}  {r[3]}")

import pandas as pd, numpy as np
from scipy import stats
pd.set_option('display.width',200); pd.set_option('display.max_columns',30)
p=pd.read_pickle('p.pkl')
d=p[(p.anno>=2021)&(p.conseguenza!='non noto')].copy()
print("n",len(d))
def rate(g,col): 
    t=d.groupby(g)[col].agg(['mean','sum','count']); t['mean']*=100; return t.round(1)
print("\n== esito per attività (morto%, grave+morto%)")
t=d.groupby('attivita').agg(n=('morto','size'),morti=('morto','sum'),morto=('morto','mean'),gm=('grave_o_morto','mean'),indenne=('indenne','mean'),heli=('heli','mean'))
t[['morto','gm','indenne','heli']]*=100; print(t[t.n>=100].sort_values('morto',ascending=False).round(1))
print("\n== esito per causa")
t=d.groupby('causa').agg(n=('morto','size'),morti=('morto','sum'),morto=('morto','mean'),gm=('grave_o_morto','mean'),indenne=('indenne','mean'),heli=('heli','mean'),eta=('eta_num','mean'))
t[['morto','gm','indenne','heli']]*=100; print(t[t.n>=40].sort_values('morto',ascending=False).round(1))
print("\n== età x esito (tutte attività)")
t=d[d.eta!='non noto'].groupby('eta').agg(n=('morto','size'),morti=('morto','sum'),morto=('morto','mean'),gm=('grave_o_morto','mean'),indenne=('indenne','mean'),heli=('heli','mean'))
t[['morto','gm','indenne','heli']]*=100; print(t.round(1))
h=d[d.attivita=='Escursionismo']
print("\n== ESCURSIONISMO età x esito")
t=h[h.eta!='non noto'].groupby('eta').agg(n=('morto','size'),morti=('morto','sum'),morto=('morto','mean'),gm=('grave_o_morto','mean'),indenne=('indenne','mean'),heli=('heli','mean'))
t[['morto','gm','indenne','heli']]*=100; print(t.round(1))
print("\n== ESC. sesso x esito"); 
t=h[h.sesso!='non noto'].groupby('sesso').agg(n=('morto','size'),morti=('morto','sum'),morto=('morto','mean'),gm=('grave_o_morto','mean'),eta=('eta_num','mean'),heli=('heli','mean')); t[['morto','gm','heli']]*=100; print(t.round(1))
print("\n== ESC. salita/discesa x esito, causa")
t=h[h.salita_discesa!=''].groupby('salita_discesa').agg(n=('morto','size'),morti=('morto','sum'),morto=('morto','mean'),gm=('grave_o_morto','mean'),eta=('eta_num','mean')); t[['morto','gm']]*=100; print(t.round(1))
print(pd.crosstab(h[h.salita_discesa!=''].salita_discesa,h[h.salita_discesa!=''].causa,normalize='index').mul(100).round(1).T.sort_values('discesa',ascending=False).head(8))
print("\n== ESC. causa mix per fascia età (%)")
h2=h[h.eta!='non noto'].copy()
top=['Caduta, inciampo, scivolamento','Malore','Cuore/circolazione','Sfinimento','Perdita orientamento, fuorivia','Attrezzatura inidonea, incapacità','Altro']
h2['c']=h2.causa.where(h2.causa.isin(top),'resto')
print(pd.crosstab(h2.eta,h2.c,normalize='index').mul(100).round(1)[top+['resto']])
print("\n== ESC. nazionalità")
t=h.groupby('nazionalita').agg(n=('morto','size'),morto=('morto','mean'),gm=('grave_o_morto','mean'),eta=('eta_num','mean'),heli=('heli','mean')); t[['morto','gm','heli']]*=100; print(t.round(1))
print(pd.crosstab(h.nazionalita,h.c if 'c' in h else h.causa.where(h.causa.isin(top),'resto'),normalize='index').mul(100).round(1)[top[:6]])

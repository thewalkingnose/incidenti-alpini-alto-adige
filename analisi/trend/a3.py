import pandas as pd, numpy as np
from scipy import stats
pd.set_option('display.width',220); pd.set_option('display.max_columns',30)
p=pd.read_pickle('p.pkl')
# confronto a parità di periodo: gen-set (2026 arriva a ottobre?)
print("ultima data:",p.data.max().date())
q=p[(p.anno>=2021)&(p.data.dt.dayofyear<=p[p.anno==2026].data.dt.dayofyear.max())]
print("\n== persone per anno (gen-ott 11 stessa finestra) per attività principali")
act=['Escursionismo','Mountainbike','E-Bike','Sci','Scialpinismo','Ferrata','Arrampicata alpinistica','Parapendio','Downhill']
t=q[q.attivita.isin(act)].groupby(['anno','attivita']).size().unstack(fill_value=0)[act]; print(t)
print("\ntotale:",q.groupby('anno').size().to_dict())
# eventi (non persone)
print("eventi/anno:", q.groupby('anno').id_evento.nunique().to_dict())
print("persone per evento:", q.groupby('anno').apply(lambda g: round(len(g)/g.id_evento.nunique(),3)).to_dict())
h=q[q.attivita=='Escursionismo']
print("\n== ESCURSIONISMO per anno: età media, %>=60, %uomini, %heli, %grave+morto, %morto")
g=h[h.conseguenza!='non noto'].groupby('anno')
print(pd.DataFrame({'n':g.size(),'eta':h[h.eta_num.notna()].groupby('anno').eta_num.mean(),
 'over60%':h[h.eta_num.notna()].groupby('anno').apply(lambda x:(x.eta_num>=65).mean()*100),
 'M%':h[h.sesso!='non noto'].groupby('anno').apply(lambda x:(x.sesso=='maschile').mean()*100),
 'heli%':g.heli.mean()*100,'gm%':g.grave_o_morto.mean()*100,'morti':g.morto.sum(),'morto%':g.morto.mean()*100}).round(1))
print("\n== ESC. mix cause per anno (%)")
top=['Caduta, inciampo, scivolamento','Malore','Cuore/circolazione','Sfinimento','Perdita orientamento, fuorivia','Attrezzatura inidonea, incapacità']
h2=h.copy(); h2['c']=h2.causa.where(h2.causa.isin(top),'altro')
print(pd.crosstab(h2.anno,h2.c,normalize='index').mul(100).round(1)[top+['altro']])
print("\n== ESC. nazionalità per anno (%)")
h2['n']=h2.nazionalita.replace({'Italia (Prov. di Bolzano)':'BZ','Italia (altre regioni)':'IT altre','Germania':'DE'}); h2['n']=h2.n.where(h2.n.isin(['BZ','IT altre','DE']),'altri')
print(pd.crosstab(h2.anno,h2.n,normalize='index').mul(100).round(1))
# trend test: Cochran-Armitage like via logit on anno
import statsmodels.formula.api as smf
for lab,mask,y in [('over65',h.eta_num.notna(),(h.eta_num>=65).astype(int)),('heli',h.index==h.index,h.heli),('malore+cuore',h.index==h.index,h.causa.isin(['Malore','Cuore/circolazione']).astype(int)),('sfinimento',h.index==h.index,(h.causa=='Sfinimento').astype(int)),('uomo',h.sesso!='non noto',(h.sesso=='maschile').astype(int))]:
    dd=pd.DataFrame({'y':y[mask],'a':h.anno[mask]}); m=smf.logit('y~a',dd).fit(disp=0)
    print(f"trend {lab:14s} OR/anno={np.exp(m.params['a']):.3f}  p={m.pvalues['a']:.3f}")
# trend per attività
print("\n== trend annuale persone per attività (var% 2021->2025 stessa finestra)")
for a in act:
    s=t[a]; print(f"{a:25s} {s.loc[2021]:4d} -> {s.loc[2025]:4d}  ({(s.loc[2025]/s.loc[2021]-1)*100:+.0f}%)  2026: {s.loc[2026]}")

import pandas as pd, numpy as np, statsmodels.formula.api as smf, warnings
warnings.filterwarnings('ignore')
p=pd.read_pickle('p.pkl')
h=p[(p.attivita=='Escursionismo')&(p.anno.between(2022,2025))&(p.conseguenza!='non noto')].copy()
IT=['Italia (Prov. di Bolzano)','Italia (altre regioni)']
rng=np.random.default_rng(1)
edges=[0,1000,1500,2000,2500,5000]; labs=['<1000','1000-1500','1500-2000','2000-2500','>2500']
def stats(d,q):
    b=pd.cut(q,edges,labels=labs,right=False)
    dd=d.assign(b=b.values)
    out={}
    o65=dd[dd.eta_num.notna()].groupby('b',observed=False).apply(lambda x:(x.eta_num>=65).mean()*100)
    he=dd.groupby('b',observed=False).heli.mean()*100
    ca=dd.groupby('b',observed=False).apply(lambda x:x.causa.str.startswith('Caduta,').mean()*100)
    return o65,he,ca
base=stats(h,h.quota_m)
# equipment OR per 1000 m among Italians
hi=h[h.nazionalita.isin(IT)&h.eta_num.notna()].copy(); hi['eqp']=(hi.causa=='Attrezzatura inidonea, incapacità').astype(int); hi['eta10']=hi.eta_num/10
def eqcoef(q):
    d=hi.assign(qk=q/1000); m=smf.logit('eqp~qk+eta10',d).fit(disp=0); return np.exp(m.params['qk'])
b0=eqcoef(hi.quota_m)
def scale(q,mode):
    s=np.where(q<2500,1.0,2.0)  # quota alta: errore doppio (test B/C)
    return (20 if mode=='tipico' else 40)*s
for mode in ['tipico','pessimistico']:
    R=[[],[],[]]; E=[]
    for _ in range(300):
        qn=h.quota_m.values+rng.laplace(0,scale(h.quota_m.values,mode)); qn=np.clip(qn,190,3910)
        s=stats(h,pd.Series(qn,index=h.index))
        for i in range(3): R[i].append(s[i].values)
        E.append(eqcoef(pd.Series(np.clip(hi.quota_m.values+rng.laplace(0,scale(hi.quota_m.values,mode)),190,3910),index=hi.index)))
    print(f"\n== Rumore {mode}: Laplace b={20 if mode=='tipico' else 40} m (x2 sopra 2500 m); mediana |errore| ~{(20 if mode=='tipico' else 40)*np.log(2):.0f} m")
    for name,i in [('over65 %',0),('elicottero %',1),('cadute %',2)]:
        arr=np.array(R[i]); print(f"  {name:13s}",' | '.join(f"{labs[j]}: {base[i].values[j]:.0f} → {np.median(arr[:,j]):.0f} [{np.percentile(arr[:,j],5):.0f}-{np.percentile(arr[:,j],95):.0f}]" for j in range(5)))
    E=np.array(E); print(f"  attrezzatura OR per +1000 m (italiani): base {b0:.2f} → mediana {np.median(E):.2f} [5-95%: {np.percentile(E,5):.2f}-{np.percentile(E,95):.2f}]")

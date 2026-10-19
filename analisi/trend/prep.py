import pandas as pd, numpy as np
p = pd.read_csv('incidenti_altoadige_con_quota.csv', sep=';', encoding='utf-8-sig', decimal=',')
v = pd.read_csv('eventi_vicinanza.csv', sep=';', encoding='utf-8-sig', decimal=',')
p['data'] = pd.to_datetime(p['data'])
p['anno'] = p.data.dt.year; p['mese'] = p.data.dt.month; p['dow'] = p.data.dt.dayofweek
p['persone_ev'] = p.groupby('id_evento')['id_evento'].transform('size')
p['morto'] = (p.conseguenza=='deceduto').astype(int)
p['grave_o_morto'] = p.conseguenza.isin(['deceduto','gravemente ferito']).astype(int)
p['indenne'] = (p.conseguenza=='indenne').astype(int)
p['eta_num'] = p.eta.map({'0-9':5,'10-19':15,'20-29':25,'30-39':35,'40-49':45,'50-59':55,'60-69':65,'70-79':75,'80+':85})
p['heli'] = (p.elicottero=='si').astype(int)
p = p.merge(v[['id_evento','dist_impianto_m','dist_rifugio_o_bivacco_m','dist_malga_m','dist_qualsiasi_m']], on='id_evento', how='left')
p.to_pickle('p.pkl')
print(p.shape, p.anno.value_counts().sort_index().to_dict())

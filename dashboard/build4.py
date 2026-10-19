t=open('template4.html',encoding='utf-8').read()
d=open('data3.js',encoding='utf-8').read()
assert '/*DATA*/' in t
open('index.html','w',encoding='utf-8').write(t.replace('/*DATA*/',d))
print('index.html',round(len(t)/1024+len(d)/1024),'KB')

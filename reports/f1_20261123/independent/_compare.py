import json
A=json.load(open('f1_results.json')); B=json.load(open('independent/independent_check.json'))
rows=[];cnt={'match':0,'close':0,'mismatch':0}
def cmp(path,a,b):
    d=abs(a-b); s='match' if d<=1e-6 else 'close' if d<=0.005 else 'mismatch'
    cnt[s]+=1; rows.append({'path':path,'author':a,'independent':b,'abs_diff':d,'status':s})
concl=[]
for c in ('buckeye','timit'):
    ac=A['corpora'][c]; bc=B['corpora'][c]
    for m,bm in bc['modes'].items():
        am=ac['modes'][m]
        cmp(f'{c}.{m}.n_failed_clips',am['n_failed_clips'],bm['n_failed_clips'])
        for k in ('edge20','edge50','ctx20'):
            for f in ('precision','recall','f1'): cmp(f'{c}.{m}.{k}.{f}',am[k][f],bm[k][f])
            for i in (0,1): cmp(f'{c}.{m}.{k}.f1_ci_95[{i}]',am[k]['f1_ci_95'][i],bm[k]['f1_ci_95'][i])
        cmp(f'{c}.{m}.unmatched_cost',am['unmatched_cost_acc20_minus_recall20'],bm['unmatched_cost_acc20_minus_recall20'])
        asf=am['speaker_f1_edge20']
        for s,v in bm['speaker_f1_edge20'].items(): cmp(f'{c}.{m}.speaker_f1_edge20.{s}',asf[s] if not isinstance(asf[s],dict) else asf[s]['f1'],v)
    for t,bt in bc['tests_edge20'].items():
        at=ac['tests_edge20'][t]
        cmp(f'{c}.tests.{t}.mean_difference',at['mean_difference_ms'],bt['mean_difference'])
        cmp(f'{c}.tests.{t}.p_value_raw',at['p_value_raw'],bt['p_value_raw'])
        cmp(f'{c}.tests.{t}.p_value_holm',at['p_value_holm'],bt['p_value_holm'])
        same=(at['mean_difference_ms']>0)==(bt['mean_difference']>0) and (at['p_value_holm']<0.05)==(bt['p_value_holm']<0.05)
        concl.append({'corpus':c,'pair':t,'author_mean':at['mean_difference_ms'],'indep_mean':bt['mean_difference'],'author_holm':at['p_value_holm'],'indep_holm':bt['p_value_holm'],'same_conclusion':same})
out={'tolerance':{'match':1e-6,'close':0.005},'counts':cnt,'non_matches':[r for r in rows if r['status']!='match'],'conclusions':concl,'all_rows':rows}
json.dump(out,open('independent/compare.json','w'),indent=2)
print(cnt); [print(r) for r in out['non_matches'][:40]]; [print(x) for x in concl]

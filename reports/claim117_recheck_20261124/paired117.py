import sys; sys.path.insert(0,'.'); sys.path.insert(0,'src')
import numpy as np
from collections import defaultdict
from scripts.p1_p4_analyses import corpus, ref_matches, run_inputs
from scripts.s1_long_recordings import paired_test
for c in ('buckeye','timit'):
    _,preds,ok,ids=run_inputs(c); u=corpus(c)
    for a,b in (('A2_proposed','B2_proposed'),('A2_brqe','B2_brqe')):
        ea,eb,spk=[],[],[]
        for uid in sorted(ok[a]&ok[b]):
            r=u[uid].ref_words; ma,mb=ref_matches(preds[a][uid],r),ref_matches(preds[b][uid],r)
            for i in range(len(r)):
                for side,j in (('start',i-1),('end',i+1)):
                    if 0<=j<len(r) and i in mb and j in mb and i in ma and j in ma:
                        ea.append(abs(getattr(ma[i][1],side)-getattr(r[i],side))*1000); eb.append(abs(getattr(mb[i][1],side)-getattr(r[i],side))*1000); spk.append(u[uid].speaker_id)
        ea,eb,spk=map(np.array,(ea,eb,spk)); S=sorted(set(spk))
        ra={s:float((ea[spk==s]<=20.0001).mean()) for s in S}; rb={s:float((eb[spk==s]<=20.0001).mean()) for s in S}
        ma_={s:float(ea[spk==s].mean()) for s in S}; mb_={s:float(eb[spk==s].mean()) for s in S}
        t=paired_test(ra,rb); m=paired_test(ma_,mb_)
        print(c,a,b,'n',len(ea),'recall',round((ea<=20.0001).mean(),4),round((eb<=20.0001).mean(),4),'MAE',round(ea.mean(),2),round(eb.mean(),2),'median',round(np.median(ea),2),round(np.median(eb),2),'>100ms',round((ea>100).mean(),4),round((eb>100).mean(),4))
        print('   recall diff p',t['p_value_raw'],'| MAE diff',round(m['mean_difference_ms'],2),'worse',m['n_worse'],'/',m['n_pairs'],'p',m['p_value_raw'])

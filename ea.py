# -*- coding: utf-8 -*-
"""
Created on Wed Jun 22 11:26:36 2022

@author: MOMO
"""
from numpy import array,random
from mpc import evaluate,update_controls,evaluate_parallel

from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import Problem
from pymoo.optimize import minimize
from pymoo.factory import get_sampling,get_crossover,get_mutation

from multiprocessing.pool import ThreadPool
from multiprocessing import Pool
import time

class mpc_problem(Problem):
    def __init__(self,config,eval_file):
        self.config = config
        self.file = eval_file
        self.n_step = config['CTRL_HRZ']//config['TIME_STEP']
        self.n_var = len(config['ACTIONS'])*self.n_step
        # self.n_obj = len(config['TARGET'])
        self.n_obj = 1
        super().__init__(n_var=self.n_var,n_obj=self.n_obj,n_constr=0,
                         xl = array([0 for _ in range(self.n_var)]),
                         xu = array([len(act)-1 for _ in range(self.n_step)
                                     for act in config['ACTIONS'].values()]),
                         type_var=int)
        
    def _evaluate(self,x,out,*args,**kwargs):
        def para_eval(k,y):
            y = y.reshape((self.n_step,len(self.config['ACTIONS']))).tolist()
            eval_file = update_controls(self.file,self.config,k,y)
            return sum(evaluate(eval_file,self.config))
        # out["F"] = zeros((x.shape[0],self.n_obj))
        params = [(k,x[k]) for k in range(x.shape[0])]
        
        pool = ThreadPool(self.config['THREADS'])
        # pool = Pool(self.config['PROCESSES'])
        F = pool.starmap(para_eval,params)
        out['F'] = array(F)

        # TODO Try swmm_api.swmm5_run_parallel
        # eval_inp_files = []
        # for i in range(x.shape[0]):
        #     xi = x[i,:]
        #     y = xi.reshape((self.n_step,len(self.config['ACTIONS']))).tolist()
        #     eval_file = update_controls(self.file,self.config,i,y)
        #     eval_inp_files.append(eval_file)
        # F = evaluate_parallel(eval_inp_files,self.config)
        # out['F'] = array(F).sum(axis=1)

        

def run_ea(config,eval_file,settings):
    t0 = time.time()
    prob = mpc_problem(config,eval_file)
    method = NSGA2(pop_size=32,
                   sampling=get_sampling("int_random"),
                   crossover=get_crossover("int_sbx", prob=1.0, eta=3.0),
                   mutation=get_mutation("int_pm", eta=3.0),
                   eliminate_duplicates=True)
    
    res = minimize(prob,
                   method,
                   termination=('n_gen',5),
                   seed=1,
                   save_history=False)
    print("Best solution found: %s" % res.X)
    print("Function value: %s" % res.F)
    if res.X.ndim == 2:
        X = res.X[:,:4]
        chan = (X-array(settings)).sum(axis=1)
        ctrls = res.X[chan.argmin()]
        # ctrls = res.X[random.randint(0,len(res.X))]
    else:
        ctrls = res.X
    # ctrls = res.X[res.F.argmin()]
    ctrls = ctrls.reshape((prob.n_step,len(config['ACTIONS']))).tolist()
    print('elapsed time: %s'%(time.time()-t0))
    return ctrls[0]
    
    


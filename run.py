# -*- coding: utf-8 -*-
"""
Created on Tue Jun 21 11:33:41 2022

@author: MOMO
"""

from pyswmm import Simulation,Links
from mpc import save_hotstart,create_eval_inp
from ea import run_ea
config = {'TIME_STEP':15,
          'CTRL_HRZ':60,
          'EVAL_HRZ':60,
          'inp_file':'2009-11-03-6.inp',
          'hsf_dir':'hsf',
          'eval_dir':'eval',
          'ACTIONS':{'ORIFICE V2':[0.1075, 0.2366, 1.0],
                     'ORIFICE V3':[0.3159, 0.6508, 1.0],
                     'ORIFICE V4':[0.1894, 0.3523, 1.0],
                     'ORIFICE V6':[0.1687, 0.4303, 1.0]},
          'TARGET':{('node_flooding_summary','Total_Flood_Volume_10^6 ltr','ALL'):
                    {'target':0,'weight':2},
                    ('node_inflow_summary','Total_Inflow_Volume_10^6 ltr','Out_to_WWTP'):
                        {'target':0,'weight':-1}},
          'SUFFIX':'mpc_eval_',
          'THREADS':8,
          'PROCESSES':4}

sim = Simulation(config['inp_file'])
links = Links(sim)
for st in sim:
    sim.step_advance(config['TIME_STEP']*60)
    ct = sim.current_time
    print('Current time: %s'%ct.strftime('%Y-%m-%d %H:%M:%S'))
    # if (sim.current_time-sim.start_time).total_seconds()>3600:
    #     break
    hsf = save_hotstart(sim,config)
    settings = [v.index(links[k.split()[-1]].current_setting)
                for k,v in config['ACTIONS'].items()]
    eval_inp_file = create_eval_inp(ct,config)
    ctrl = run_ea(config,eval_inp_file,settings)
    for i,(k,v) in enumerate(config['ACTIONS'].items()):
        links[k.split()[-1]].target_setting = v[ctrl[i]]
sim.close()   
    
    
    
    # ctrl_grp = run_ea()
    # ctrl_grp = [[[1 for _ in range(4)] for _ in range(4)] for _ in range(20)]
    # for ctrls in ctrl_grp:
        
    




# -*- coding: utf-8 -*-
"""
Created on Thu Jun 16 14:50:14 2022

@author: MOMO
"""

from pyswmm import Nodes,Links,Subcatchments
from struct import pack
def save_hotstart(sim,config):
    filestamp = 'SWMM5-HOTSTART4'
    ct = sim.current_time
    
    links = [link for link in Links(sim)]
    nodes = [node for node in Nodes(sim)]
    subs = [sub for sub in Subcatchments(sim)]
    
    hsf_file = '%s.hsf'%ct.strftime('%Y-%m-%d-%H-%M')
    hsf_file = path.join(path.dirname(config['inp_file']),
                         config['hsf_dir'],hsf_file)
    with open(hsf_file,'wb') as f:
        f.write(bytes(filestamp,encoding='utf-8'))
        f.write(pack('i',len(subs)))
        f.write(pack('i',0))    #nLandUses
        f.write(pack('i',len(nodes)))
        f.write(pack('i',len(links)))
        f.write(pack('i',0))    #nPollutants
        f.write(pack('i',['CFS','GPM','MGD','CMS','LPS','MLD'].index(sim.flow_units)))    #FlowUnits CMS
        
        for sub in subs:
            x = (0.0,0.0,0.0,sub.runoff)  # ponded depths in 3 subareas, runoff
            f.write(pack('dddd',*x))
            x = (0.0,sub.infiltration_loss,0.0,0.0,0.0,0.0)
            f.write(pack('dddddd',*x))
            
        for node in nodes:
            x = (node.depth,node.lateral_inflow)
            f.write(pack('ff',*x))
            if node.is_storage():
                f.write(pack('f',0)) # HRT for storage
        
        for link in links:
            x = (link.flow,link.depth,link.current_setting)
            f.write(pack('fff',*x))
    return hsf_file

from swmm_api import read_inp_file,swmm5_run,swmm5_run_parallel,read_rpt_file
from swmm_api.input_file.sections import FilesSection,Control
from swmm_api.input_file.sections.others import TimeseriesData

import datetime
from os import path
rpt_helper = {('node_flooding_summary','Total_Flood_Volume_10^6 ltr','ALL'):{'target':0,'weight':0.8},
              ('node_inflow_summary','Maximum_Depth_Meters','T1'):{'target':3,'weight':0.2}}


def create_eval_inp(ct,config):
        
    inp = read_inp_file(config['inp_file'])
    inp['OPTIONS']['START_DATE'] = ct.date()
    inp['OPTIONS']['START_TIME'] = ct.time()
    inp['OPTIONS']['REPORT_START_DATE'] = ct.date()
    inp['OPTIONS']['REPORT_START_TIME'] = ct.time()
    inp['OPTIONS']['END_DATE'] = (ct + datetime.timedelta(minutes=config['EVAL_HRZ'])).date()
    inp['OPTIONS']['END_TIME'] = (ct + datetime.timedelta(minutes=config['EVAL_HRZ'])).time()
    inp['FILES'] = FilesSection()
    inp['FILES']['USE HOTSTART'] = path.join(path.dirname(config['inp_file']),
                                             config['hsf_dir'],
                                             '%s.hsf'%ct.strftime('%Y-%m-%d-%H-%M'))
    inp['CONTROLS'] = Control.create_section()
    
    # Use modelated control timeseries
    # for k,v in config['ACTIONS'].items():
    #     name = k.split()[-1]
    #     conditions = [['SIMULATION', 'TIME', '>', '0']]
    #     actions = [k.split() +['SETTING','=','TIMESERIES','TS_'+name]]
    #     inp['CONTROLS'].add_obj(Control('P_'+name,conditions,actions))
    #     data = [((ct+datetime.timedelta(minutes=i*config['TIME_STEP'])).strftime('%m/%d/%Y %H:%M:%S'),v[0])
    #             for i in range(config['CTRL_HRZ']//config['TIME_STEP'])]
    #     inp['TIMESERIES'].add_obj(TimeseriesData(Name='TS_'+name,data=data))
    
    # Use control rules
    for i in range(config['CTRL_HRZ']//config['TIME_STEP']):
        conditions = [['SIMULATION', 'TIME', '<', 
                       str(round(config['TIME_STEP']/60*(i+1),2))]]
        actions = [k.split()+['SETTING','=',str(act[0])]
                   for k,act in config['ACTIONS'].items()]
        actions = [actions[0]]+[['AND']+act for act in actions[1:]]
        inp['CONTROLS'].add_obj(Control('P%s'%(i+1),conditions,actions,priority=5-i))
    
    eval_inp_file = path.join(path.dirname(config['inp_file']),
                              config['eval_dir'],
                             config['SUFFIX']+path.basename(config['inp_file']))
    inp.write_file(eval_inp_file)
    return eval_inp_file
    
def update_controls(eval_inp_file,config,j,ctrls):
    inp = read_inp_file(eval_inp_file)
    
    # Use modelated control timeseries
    # for i,(k,options) in enumerate(config['ACTIONS'].items()):
    #     name = k.split()[-1]
    #     ts = inp['TIMESERIES']['TS_'+name]
    #     data = [(dat[0],options[ctrls[idx][i]])
    #             for idx,dat in enumerate(ts.data)]
    #     ts.data = data
    #     inp['TIMESERIES']['TS_'+name] = ts
    
    # Use control rules
    for idx,k in enumerate(inp['CONTROLS']):
        acts = inp['CONTROLS'][k].actions
        action = [options[ctrls[idx][i]]
                  for i,options in enumerate(config['ACTIONS'].values())]
        acts = [act[:-1] + [str(action[i])]
                for i,act in enumerate(acts)]
        inp['CONTROLS'][k].actions = acts
    eval_inp_file = eval_inp_file.strip('.inp')+'_%s.inp'%j
    inp.write_file(eval_inp_file)
    return eval_inp_file
    
def eval_cost(rpt_file,target):
    rpt = read_rpt_file(rpt_file)
    cost = []
    for k,v in target.items():
        table = getattr(rpt,k[0])
        if table.empty:
            cost.append(abs(0-v['target'])*v['weight'])
            continue
        else:
            series = table[k[1]]
        if k[2] == 'ALL':
            target = series.sum()
        elif k[2] == 'AVERAGE':
            target = series.mean()
        elif k[2] == 'MAX':
            target = series.max()
        elif k[2] == 'MIN':
            target = series.min()     
        else:
            target = series[k[2]]
        cost.append(abs(target-v['target'])*v['weight'])
    return cost

def evaluate(eval_inp_file,config):
    rpt_file,_ = swmm5_run(eval_inp_file,create_out=False)
    cost = eval_cost(rpt_file,config['TARGET'])
    return cost




def evaluate_parallel(eval_inp_files,config):
    swmm5_run_parallel(eval_inp_files,processes = config['PROCESSES'])
    costs = []
    for file in eval_inp_files:
        rpt_file = file.replace('.inp','.rpt')
        cost = eval_cost(rpt_file,config['TARGET'])
        costs.append(cost)
    return costs
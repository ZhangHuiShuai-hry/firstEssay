"""原物理定义下Full-Line-LP可行/IP不可行：两个选择性AND链线。"""
def lp_yes_ip_no():
    lines=[]
    for label in ('A','B'):
        tasks=[]
        for mode in ('H','R'):
            for n in (1,2):
                tasks.append(dict(id=mode+str(n),value=2,weight=int(n==2),
                    modes={mode:dict(time=1,cost=1,beta=0)}))
        lines.append(dict(id=label,cycle_time=1,fatigue_limit=.5,
            stations=[dict(fixed_cost=0,human_cost=0,robot_cost=0) for _ in range(2)],
            tasks=tasks,required_tasks=[],min_recovery=1,precedence=[['H1','H2'],['R1','R2']]))
    return dict(lines=lines,human_limit=3,robot_limit=1)

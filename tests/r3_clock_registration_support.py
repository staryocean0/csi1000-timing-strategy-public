"""Remove only the exact later #345 registration to check historical identities."""
PROFILE='two-wave-r3-clock-evidence-audit-v1'
BROKER='executor/wave_r3_clock_broker_v1.py'

def remove_once(text,part):
    if text.count(part)!=1:
        raise AssertionError('audit route missing, duplicated or altered')
    return text.replace(part,'')

def strip_audit_workflow(text):
    text=remove_once(text,'          - '+PROFILE+'\n')
    cond=" || inputs.profile == '"+PROFILE+"'"
    if text.count(cond)!=2:
        raise AssertionError('audit condition count drift')
    text=text.replace(cond,'')
    for phase in ('prepare','compute','cleanup','publish'):
        part="          elif [ '${{ inputs.profile }}' = '"+PROFILE+"' ]; then\n            python3 "+BROKER+' '+phase+' '+PROFILE+'\n'
        text=remove_once(text,part)
    return text

def strip_audit_controller(text):
    text=remove_once(text,"       github.event.issue.title == 'controller: "+PROFILE+"' ||\n")
    return remove_once(text,"            'controller: "+PROFILE+"')\n              profile='"+PROFILE+"'\n              ;;\n")

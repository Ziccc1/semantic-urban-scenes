"""Exercise the step evaluator using clearly labeled synthetic A/B/C states."""

import argparse
import json
from pathlib import Path

import numpy as np

from evaluate_steps import assemble, write


def main(output):
    sample = output/'sample'
    sample.mkdir(parents=True,exist_ok=False)

    def save(file, data):
        (sample/file).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

    ground = [[100+x*.5,200+y*.5,0.,1] for x in range(4) for y in range(3)]
    defects = [row.copy() for row in ground]
    defects[6][2] = .5
    defects[7][3] = 2
    defects[2][3] = 2
    manifest = dict(schema_version='1.0',method='pritti',sample_id='synthetic-4x3',
                    coordinates=dict(unit='m',up='+Z',handedness='right'),
                    labels=[dict(id=1,name='road'),dict(id=2,name='ground')],states=[],
                    regions=[dict(id='test-window',state_id='before',role='window')])
    for name,cells in (('before',ground),('defects',defects),('repaired',ground)):
        manifest['states'].append(dict(id=name,format='ground_objects_json',path=f'{name}.json'))
        save(f'{name}.json',dict(ground=dict(cell_size_xy=[.5,.5],cells=cells),objects=[]))
    save('manifest.json',manifest)
    protected = np.zeros((4,3),bool)
    protected[:2] = True
    np.save(sample/'protected.npy',protected)
    steps, settings = [], []
    for strategy in 'ABC':
        key = dict(run_id='synthetic',sample_id=manifest['sample_id'],strategy=strategy,step=1)
        first = dict(seed=10,status='success',elapsed_ms=100,output_path='defects.json')
        repeat = dict(seed=11,status='success',elapsed_ms=80,output_path='repaired.json')
        skipped = dict(seed=None,status='skipped',elapsed_ms=None,output_path=None)
        steps.append(dict(**key,parent_state_id='before',first_state_id='defects',
                    adopted_state_id='defects' if strategy=='A' else 'repaired',window_region_id='test-window',
                    issue_region_ids=[],status='success',action={'A':'none','B':'resample','C':'local_repair'}[strategy],
                    elapsed_ms=100 if strategy=='A' else 180,
                    attempts=[first] if strategy=='A' else [first,repeat,skipped]))
        settings.append(dict(**key,seam_axis=0,seam_edge=2,seam_span=[0,3],height_threshold_m=.25,
                             protected_mask_path='protected.npy'))
    skipped_step = dict(steps[-1],step=2,status='skipped',parent_state_id='repaired',first_state_id=None,
                        adopted_state_id=None,window_region_id=None,attempts=[],elapsed_ms=None,reason='fixture')
    steps.append(skipped_step)
    save('steps.json',steps)
    geometry = dict(grid=dict(shape_xy=[4,3],first_center_xy_m=[100.,200.],cell_size_xy_m=[.5,.5]),
                    road_ids=[1],attempts_record='all_calls',steps=settings)
    save('geometry.json',geometry)
    result = assemble(sample.resolve(),sample/'steps.json',sample/'geometry.json','synthetic')
    a,b,c,skipped = result['rows']
    assert [a['additional_calls'],b['additional_calls'],c['additional_calls']]==[0,1,1]
    assert skipped['unassessed_reason']=='fixture' and not skipped['assessments']
    damaged = a['assessments']['first']
    assert {issue['kind'] for issue in damaged['issues']}=={
        'road_discontinuity','ground_height_jump','protected_ground_change'}
    road = next(issue for issue in damaged['issues'] if issue['kind']=='road_discontinuity')
    assert road['centers_xy_m']==[[100.5,200.5],[101.,200.5]]
    assert road['suggested_xy_bounds_m']==[[100.25,200.25],[101.25,200.75]]
    assert not b['assessments']['adopted']['issues'] and not c['assessments']['adopted']['issues']
    # A generated state must be the next step's registered parent.
    bad = list(steps[:-1])+[dict(skipped_step,parent_state_id='before')]
    save('invalid-steps.json',bad)
    try:
        assemble(sample.resolve(),sample/'invalid-steps.json',sample/'geometry.json','synthetic')
    except ValueError as error:
        if 'preceding adopted state' not in str(error):
            raise
    else:
        raise AssertionError('Invalid chain was accepted')
    write(output/'report',result)
    print('PASS: synthetic A/B/C localization, optional skipped state, call counts, and chain validation')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    main(parser.parse_args().output)

"""Evaluate registered PrITTI steps and write JSON plus a human-readable comparison."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from 检查扩展接缝 import evaluate


KEYS = ('run_id', 'sample_id', 'strategy', 'step')
STATE_FIELDS = ('parent_state_id', 'first_state_id', 'adopted_state_id')
STATUSES = {'success', 'failed', 'skipped'}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def within(root, name):
    if not isinstance(name, str) or Path(name).is_absolute():
        raise ValueError(f'Expected a relative sample path: {name!r}')
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f'Path is missing or outside the sample: {name}')
    return path


def keyed(rows):
    items = {}
    for row in rows:
        key = tuple(row[k] for k in KEYS)
        run, sample, strategy, step = key
        if (not all(isinstance(v, str) and v for v in (run, sample)) or strategy not in ('A','B','C')
                or type(step) is not int or step < 1 or key in items):
            raise ValueError(f'Invalid or repeated step: {key}')
        items[key] = row
    return items


def sequence(items):
    previous = {}
    for key in sorted(items):
        step = items[key]
        group, number = key[:3], key[3]
        if step['status'] not in STATUSES:
            raise ValueError(f'Invalid step status: {key}')
        last = previous.get(group)
        if number != (last[0] + 1 if last else 1) or (
                last and (last[1] is None or last[1] != step['parent_state_id'])):
            raise ValueError(f'Step does not continue from the preceding adopted state: {key}')
        previous[group] = number, step['adopted_state_id']


def raster(state, origin, spacing, shape, path, label_ids):
    data = read_json(path)
    ground = data['ground']
    if not np.allclose(ground['cell_size_xy'], spacing, atol=1e-8, rtol=0):
        raise ValueError(f'Ground cell sizes do not match the shared grid: {state}')
    raw = np.asarray(ground['cells'], dtype=float)
    if not len(raw):
        raw = np.empty((0,4))
    if raw.ndim != 2 or raw.shape[1] != 4:
        raise ValueError(f'Expected [x,y,z,label_id] cells: {state}')
    q = (raw[:,:2] - origin) / spacing
    if (not np.isfinite(raw).all() or not np.allclose(q, np.rint(q), atol=1e-5, rtol=0)
            or (q < -1e-5).any() or (np.rint(q) >= shape).any()
            or not set(raw[:,3]) <= label_ids):
        raise ValueError(f'Ground cells do not align with the shared grid or use undeclared labels: {state}')
    xy = np.rint(q).astype(int)
    if len(np.unique(xy,axis=0)) != len(xy):
        raise ValueError(f'Duplicate ground cells: {state}')
    idx = tuple(xy.T)
    cells = dict(labels=np.zeros(shape,np.int64), z_m=np.zeros(shape), valid=np.zeros(shape,bool))
    cells['labels'][idx], cells['z_m'][idx], cells['valid'][idx] = raw[:,3], raw[:,2], True
    return cells


def anomalies(diagnosis, origin, spacing):
    axis, edge = diagnosis['seam_axis'], diagnosis['seam_edge']
    items = []

    def add(kind, xy):
        indices = np.asarray(xy)
        positions = origin + indices * spacing
        items.append(dict(kind=kind, candidate_xy=indices.tolist(), centers_xy_m=positions.tolist(),
                          review='pending', suggested_xy_bounds_m=[
                              (positions.min(axis=0) - spacing / 2).tolist(),
                              (positions.max(axis=0) + spacing / 2).tolist()]))

    for name, field in (('road_discontinuity','road_mismatch_along_seam'),
                        ('ground_height_jump','height_jump_along_seam')):
        for p in diagnosis[field]:
            indices = [[p, edge - 1],[p,edge]] if axis else [[edge - 1,p],[edge,p]]
            add(name, indices)
    for pos in diagnosis['protected_changed_xy']:
        add('protected_ground_change', [pos])
    return items


def milliseconds(value):
    if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or value < 0):
        raise ValueError(f'Invalid elapsed time: {value}')
    return value


def assemble(sample, steps_path, geometry_path, input_kind):
    manifest_path = sample/'manifest.json'
    manifest = read_json(manifest_path)
    if (manifest['schema_version'] != '1.0' or manifest['method'] != 'pritti'
            or any(manifest['coordinates'].get(k) != v for k,v in (('unit','m'),('up','+Z'),('handedness','right')))):
        raise ValueError('Expected PrITTI v1 states in right-handed, metric, +Z-up coordinates.')
    states = {s['id']:s for s in manifest['states']}
    regions = {r['id']:r for r in manifest.get('regions',[])}
    if len(states) != len(manifest['states']) or len(regions) != len(manifest.get('regions',[])):
        raise ValueError('Duplicate state or region IDs')
    label_ids = {r['id'] for r in manifest['labels']}
    steps, geometry = keyed(read_json(steps_path)), read_json(geometry_path)
    grid = geometry['grid']
    shape, origin, spacing = tuple(grid['shape_xy']), np.asarray(grid['first_center_xy_m']), np.asarray(grid['cell_size_xy_m'])
    if (len(shape) != 2 or not all(type(n) is int and n > 0 for n in shape)
            or origin.shape != (2,) or spacing.shape != (2,) or not np.isfinite([origin,spacing]).all() or (spacing <= 0).any()):
        raise ValueError('Invalid metric grid geometry')
    road_ids = geometry['road_ids']
    if not road_ids or not set(road_ids) <= label_ids:
        raise ValueError('Road labels must be mapped to manifest IDs')
    specifics = keyed(geometry['steps'])
    if not steps or not set(specifics) <= set(steps):
        raise ValueError('Geometry must refer to registered steps')
    sequence(steps)
    inputs = {}
    rows = []
    for key, step in sorted(steps.items()):
        if step['sample_id'] != manifest['sample_id']:
            raise ValueError(f'Step belongs to a different sample: {key}')
        for region in (step['window_region_id'], *step['issue_region_ids']):
            if region is None and step['status'] != 'success':
                continue
            if region not in regions:
                raise ValueError(f'Unknown region {region!r}: {key}')
        outputs = {f:step[f] for f in STATE_FIELDS}
        if any(v is not None and v not in states for v in outputs.values()) or (
                step['status'] == 'success' and None in outputs.values()):
            raise ValueError(f'Unknown or incomplete successful states: {key}')
        attempts = step['attempts']
        if not isinstance(attempts,list):
            raise ValueError(f'Invalid attempts list: {key}')
        for attempt in attempts:
            if attempt['status'] not in STATUSES or (type(attempt['seed']) is not int and
                    not (attempt['status'] == 'skipped' and attempt['seed'] is None)):
                raise ValueError(f'Invalid attempt record: {key}')
            milliseconds(attempt['elapsed_ms'])
            if attempt['output_path'] is not None:
                track = within(sample,attempt['output_path'])
                inputs[track.relative_to(sample).as_posix()] = digest(track)
        config = specifics.get(key)
        counting = (config or {}).get('attempts_record', geometry.get('attempts_record'))
        if counting not in (None,'all_calls','extra_calls'):
            raise ValueError(f'Unexpected attempt accounting convention: {key}')
        calls = sum(a['status'] != 'skipped' for a in attempts)
        if counting == 'all_calls' and calls == 0 and outputs['first_state_id'] is not None:
            raise ValueError(f'The first generated state has no attempt entry: {key}')
        extra = calls if counting == 'extra_calls' else max(0,calls-1) if counting == 'all_calls' else None
        row = dict(**{k:v for k,v in zip(KEYS,key)}, **outputs, action=step['action'], status=step['status'],
                   elapsed_ms=milliseconds(step['elapsed_ms']), attempts=attempts,
                   recorded_calls=calls, additional_calls=extra,
                   window_region_id=step['window_region_id'], assessments={})
        if config is None or outputs['parent_state_id'] is None:
            if step['status'] == 'success':
                raise ValueError(f'Successful step needs explicit evaluation geometry: {key}')
            row['unassessed_reason'] = step.get('reason') or '缺少可比较状态或评价区域'
            rows.append(row)
            continue
        mask = within(sample,config['protected_mask_path'])
        inputs[mask.relative_to(sample).as_posix()] = digest(mask)
        grids = {}
        for state in dict.fromkeys(v for v in outputs.values() if v is not None):
            info = states[state]
            if info['format'] != 'ground_objects_json':
                raise ValueError(f'Unsupported state format: {state}')
            path = within(sample,info['path'])
            inputs[path.relative_to(sample).as_posix()] = digest(path)
            grids[state] = raster(state,origin,spacing,shape,path,label_ids)
        old = dict(grids[outputs['parent_state_id']], protected=np.load(mask,allow_pickle=False))
        for tag,state in (('first',outputs['first_state_id']),('adopted',outputs['adopted_state_id'])):
            if state is None:
                row['assessments'][tag] = None
                continue
            diagnostic = evaluate(old,grids[state],road_ids,config['seam_axis'],config['seam_edge'],
                                  config['height_threshold_m'],seam_span=config.get('seam_span'),
                                  protected_height_limit_m=config.get('protected_height_tolerance_m',0.))
            row['assessments'][tag] = dict(ground=diagnostic, issues=anomalies(diagnostic,origin,spacing),
                                          object_preservation='pending_stable_id_review')
        rows.append(row)
    return dict(input_kind=input_kind, human_review_status='pending',
                source_sha256=dict(manifest=digest(manifest_path),steps=digest(steps_path),geometry=digest(geometry_path)),
                referenced_files=inputs, rows=rows)


def write(output, result):
    output.mkdir(parents=True,exist_ok=False)
    (output/'evaluation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    table = ['# PrITTI 逐步评价', '',
             f"数据来源为 `{result['input_kind']}`，异常范围待人工复核。", '',
             '| 运行 | 样例 | 方案 | 步号 | 状态 | 阶段 | 道路匹配率 | 高差 P95（m） | 保留地面变化率 | 耗时（ms） | 额外调用 |',
             '|---|---|---|---:|---|---|---:|---:|---:|---:|---:|']
    def value(v):
        return '—' if v is None else f'{v:.4g}' if isinstance(v,(int,float)) else str(v).replace('|','\\|').replace('\n',' ')
    for item in result['rows']:
        for phase, assessment in item['assessments'].items() or [('—',None)]:
            ground = assessment['ground'] if assessment else {}
            columns = ([item[k] for k in KEYS]+[item['status'],phase]
                       +[ground.get(k) for k in ('road_match_fraction','height_p95_m','protected_changed_fraction')]
                       +[item['elapsed_ms'],item['additional_calls']])
            table.append('| ' + ' | '.join(map(value,columns))+' |')
    (output/'evaluation.md').write_text('\n'.join(table)+'\n',encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sample',type=Path)
    parser.add_argument('--steps',required=True,type=Path)
    parser.add_argument('--geometry',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--input-kind',required=True,choices=('synthetic','pritti'))
    args = parser.parse_args()
    result = assemble(args.sample.resolve(),args.steps,args.geometry,args.input_kind)
    write(args.output,result)
    print(f"{len(result['rows'])} steps written to {args.output}")


if __name__ == '__main__':
    main()

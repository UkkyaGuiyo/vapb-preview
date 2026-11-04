# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt in exact generated Skin revisions to pre-import weight preservation."""
import hashlib
import json
import math
import re
from .staging import StagedUnityAsset


def _policy_asset(guid, value):
    path = f'Assets/VAPBExport/SkinWeightPolicy_{guid}.json'
    identity = hashlib.sha256(('VAPB_SKIN_WEIGHT_POLICY_V1:' + path).encode()).hexdigest()[:32]
    return StagedUnityAsset(identity, path, json.dumps(value, sort_keys=True).encode(),
                           f'fileFormatVersion: 2\nguid: {identity}\n'.encode(), operation='CREATE',
                           asset_type='GENERATED_EXPORT_SUPPORT')


def first_shape_policy_asset(task, recipe):
    if (task.get('kind') != 'RESTORE_DIRECT_SKIN_VARIANT_V1'
            or not recipe.get('realization_id')
            or recipe['realization_id'] != task.get('realization_id')
            or (task.get('first_shape_normals_sha256') and
                recipe.get('content_sha256') != task['first_shape_normals_sha256'])
            or not recipe.get('geometry_uid') or not recipe.get('shape_geometry_uid')):
        raise ValueError('First Shape normal policy identity is unproven')
    guid, sha = task['model_guid'], task['model_sha256']
    if not re.fullmatch('[0-9a-f]{32}', guid) or not re.fullmatch('[0-9a-f]{64}', sha):
        raise ValueError('Skin import policy requires exact generated model revision')
    version = recipe.get('policy_version', 2)
    if version not in (2, 3, 4):
        raise ValueError('First Shape policy version is unsupported')
    content = recipe.get('content_json')
    content_value = None
    if version in (3, 4) or content is not None:
        if (not isinstance(content, str)
                or hashlib.sha256(content.encode()).hexdigest() != recipe.get('content_sha256')
                or json.loads(content).get('policy_version', 2) != version):
            raise ValueError('First Shape policy version or content binding mismatch')
        content_value = json.loads(content)
    if version == 4:
        sample_positions = content_value.get('sample_positions') if content_value else None
        sample_normals = content_value.get('sample_normals') if content_value else None
        basis_positions = content_value.get('base_positions') if content_value else None
        basis_normals = content_value.get('base_normals') if content_value else None
        corners = content_value.get('corner_indices') if content_value else None
        normal_sample_weight = content_value.get('normal_sample_weight') if content_value else None
        def valid_vectors(values, count):
            return (isinstance(values, list) and len(values) == count and
                    all(isinstance(row, dict) and set(row) == {'x', 'y', 'z'} and
                        all(isinstance(value, (int, float)) and not isinstance(value, bool)
                            and math.isfinite(value) for value in row.values())
                        for row in values))
        if (normal_sample_weight != 50.0 or
                not valid_vectors(basis_positions, len(basis_positions or ())) or
                not valid_vectors(basis_normals, len(basis_normals or ())) or
                not valid_vectors(sample_positions, len(basis_positions or ())) or
                not valid_vectors(sample_normals, len(basis_normals or ())) or
                not isinstance(corners, list) or
                any(not isinstance(index, int) or isinstance(index, bool) or index < 0
                    for index in corners)):
            raise ValueError('First Shape finite-normal sample is invalid')
        if content_value.get('policy_version') != version:
            raise ValueError('First Shape finite-normal content version mismatch')
    return _policy_asset(guid, dict(version=version, model_guid=guid, model_sha256=sha, first_shape=recipe))


def skin_weight_policy_assets(tasks, *, staged_assets=()):
    tasks = tuple(tasks)
    revisions = {}
    for task in tasks:
        if task.get('kind') not in {'REBIND_SKINNED_RENDERER_V1',
                'RESTORE_MODEL_SKIN_VARIANT_V1', 'RESTORE_DIRECT_SKIN_VARIANT_V1',
                'RESTORE_SOURCE_MODEL_SKIN_VARIANT_V1'}:
            continue
        guid, sha = task.get('model_guid', ''), task.get('model_sha256', '')
        if not re.fullmatch('[0-9a-f]{32}', guid) or not re.fullmatch('[0-9a-f]{64}', sha):
            raise ValueError('Skin import policy requires exact generated model revision')
        if guid in revisions and revisions[guid] != sha:
            raise ValueError('Skin import policy model revisions conflict')
        revisions[guid] = sha
    assets = []
    for guid, sha in sorted(revisions.items()):
        path = f'Assets/VAPBExport/SkinWeightPolicy_{guid}.json'
        existing = [asset for asset in staged_assets if asset.pathname == path]
        if existing:
            if len(existing) != 1:
                raise ValueError('Duplicate generated Skin import policy')
            value = json.loads(existing[0].asset_bytes)
            matches = [task for task in tasks if task.get('model_guid') == guid]
            if (value.get('version') not in (2, 3, 4) or value.get('model_guid') != guid
                    or value.get('model_sha256') != sha
                    or not matches or any(first_shape_policy_asset(task, value.get('first_shape', {}))
                                          != existing[0] for task in matches)):
                raise ValueError('Staged Skin normal policy revision or identity mismatch')
            assets.append(existing[0])
        else:
            if any(task.get('model_guid') == guid and task.get('first_shape_normals_sha256') for task in tasks):
                raise ValueError('Required first Shape normal policy is missing')
            assets.append(_policy_asset(guid, dict(version=1, model_guid=guid, model_sha256=sha)))
    return tuple(assets)

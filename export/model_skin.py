"""Build a deferred model-skin task from confirmed source and instance evidence."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import PurePosixPath
import re

from ..unity.yaml_parser import parse_unity_yaml
from ..unity.prefab_parser import ref_file_id, ref_guid


_GUID = re.compile(r"[0-9a-fA-F]{32}\Z")
_SHA = re.compile(r"[0-9a-fA-F]{64}\Z")
_SIGNED_ID = re.compile(r"-?(?:0|[1-9][0-9]*)\Z")


def group_model_skin_tasks(tasks):
    """Give already prepared skins of one Prefab a single deterministic Variant."""
    if not tasks:
        raise ValueError('No skin tasks selected')
    result = deepcopy(list(tasks))
    source_tasks = [task for task in result if task.get('kind') == 'RESTORE_SOURCE_MODEL_SKIN_VARIANT_V1']
    if source_tasks:
        if len(result) != 1:
            raise ValueError('Source-model Skin requires one task')
        task = source_tasks[0]
        _guid(task['source_model_guid'])
        _sha(task['source_model_sha256'])
        edited_guid = _guid(task['model_guid'])
        if edited_guid == task['source_model_guid'] or not task.get('realization_id'):
            raise ValueError('Source and edited model identities must differ')
        if task.get('prefab_guid') or task.get('instance_edges') or task.get('renderer_candidates'):
            raise ValueError('Source-model Skin cannot carry Prefab evidence')
        return tuple(result)
    prefabs, realizations, models = set(), set(), set()
    for task in result:
        try:
            if task['kind'] not in ('RESTORE_MODEL_SKIN_VARIANT_V1', 'RESTORE_DIRECT_SKIN_VARIANT_V1'):
                raise ValueError('Unsupported skin task kind')
            prefabs.add((_guid(task['prefab_guid']), _sha(task['prefab_source_sha256'])))
            realization, model = task['realization_id'], _guid(task['model_guid'])
            if not isinstance(realization, str) or not realization or realization in realizations or model in models:
                raise ValueError('Skin realization or edited model is missing or duplicated')
            realizations.add(realization)
            models.add(model)
        except (KeyError, TypeError) as exc:
            raise ValueError('Skin task identity is incomplete') from exc
    if len(prefabs) != 1:
        raise ValueError('Selected skins must belong to the same Prefab revision')
    result.sort(key=lambda task: task['realization_id'])
    if len(result) > 1:
        identity = {'prefab_guid': result[0]['prefab_guid'], 'skins': [
            {key: task[key] for key in ('kind', 'realization_id', 'instance_edges')}
            for task in result]}
        suffix = hashlib.sha256(('MODEL_SKIN_SET_V1:' + json.dumps(
            identity, sort_keys=True, separators=(',', ':'))).encode()).hexdigest()
        for task in result:
            task['variant_path'] = f'Assets/VAPBExport/EditedVariant_{suffix}.prefab'
    return tuple(result)


def _guid(value):
    if not isinstance(value, str) or not _GUID.fullmatch(value):
        raise ValueError("Asset GUID is incomplete")
    return value.lower()


def _sha(value):
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError("Source revision is incomplete")
    return value.lower()


def _id(value):
    if not isinstance(value, str) or not _SIGNED_ID.fullmatch(value):
        raise ValueError("Signed local ID is incomplete")
    number = int(value)
    if number == 0 or number < -(1 << 63) or number >= (1 << 63):
        raise ValueError("Signed local ID is out of range")
    return value


def model_skin_material_bindings(materials, *, source_model_guid='', source_model_sha256='', source_model_uid=''):
    """Explicit Unity assets or pending source UIDs, never inferred slot identity."""
    result = []
    for material in materials:
        if material is None:
            raise ValueError('Unassigned slots are unsupported by model Material transport')
        if 'source_material_uid' in material:
            if set(material) != {'source_material_uid'}:
                raise ValueError('Source Material and Unity asset identities cannot be mixed')
            uid = _id(material['source_material_uid'])
            identity = ':'.join((_guid(source_model_guid), _sha(source_model_sha256), _id(source_model_uid), uid))
            label = 'VAPB-MAT-' + hashlib.sha256(('MODEL_SKIN_SOURCE_MATERIAL_V1:' + identity).encode('ascii')).hexdigest()[:32]
            result.append(dict(transport_id=label, source_material_uid=uid))
            continue
        guid, file_id = _guid(material.get('guid')), _id(material.get('file_id'))
        label = 'VAPB-MAT-' + hashlib.sha256(
            ('MODEL_SKIN_MATERIAL_V1:' + guid + ':' + file_id).encode('ascii')).hexdigest()[:32]
        result.append(dict(transport_id=label, guid=guid, file_id=file_id))
    return result


def model_skin_rig_meta(meta):
    """Use Generic for a generated geometry carrier copied from Humanoid metadata.

    The restored Prefab retains the original Avatar/Animator. This carrier has no
    baked animation; None is unsuitable because Unity discards its Skin binding.
    Preserve other modes, the original schema, and every unrelated byte.
    """
    importer = re.search(
        rb'(?m)^ModelImporter[ \t]*:[ \t]*\r?\n'
        rb'((?:(?:[ \t]+|#)[^\r\n]*(?:\r?\n|$)|\r?\n)*)', meta)
    if importer is None or len(re.findall(rb'(?m)^ModelImporter[ \t]*:', meta)) != 1:
        raise ValueError('Generated Skin transport requires unique ModelImporter settings')
    body = importer.group(1)
    if len(re.findall(rb'(?m)^  animationType[ \t]*:', body)) != 1:
        raise ValueError('Generated Skin rig settings are missing or ambiguous')
    value = re.search(rb'(?m)^  animationType[ \t]*:[ \t]*([0-3])[ \t]*\r?$', body)
    if value is None:
        raise ValueError('Generated Skin rig settings are unsupported')
    if value.group(1) != b'3':
        return meta
    start = importer.start(1) + value.start(1)
    return meta[:start] + b'2' + meta[start + 1:]


def model_skin_material_meta(meta, bindings):
    """Keep generated FBX carrier Materials embedded when transport is required."""
    if not bindings:
        return meta
    importer = re.search(rb'(?m)^ModelImporter[ \t]*:[ \t]*\r?\n'
                         rb'((?:(?:[ \t]+|#)[^\r\n]*(?:\r?\n|$)|\r?\n)*)', meta)
    if importer is None or len(re.findall(rb'(?m)^ModelImporter[ \t]*:', meta)) != 1:
        raise ValueError('Generated Material transport requires unique ModelImporter settings')
    body = importer.group(1)
    materials = re.search(rb'(?m)^  materials[ \t]*:[ \t]*\r?\n'
                          rb'((?:(?: {4}|[ \t]*#)[^\r\n]*(?:\r?\n|$)|[ \t]*\r?\n)*)', body)
    if materials is None or len(re.findall(rb'(?m)^  materials[ \t]*:', body)) != 1:
        raise ValueError('Generated Material transport requires unique material settings')
    settings = materials.group(1)
    # Preserve the source schema on the generated copy; legacy importMaterials
    # is a Boolean, modern materialImportMode uses ImportStandard=1. InPrefab=1.
    import_keys = re.findall(rb'(?m)^    (materialImportMode|importMaterials)[ \t]*:', settings)
    if len(import_keys) != 1:
        raise ValueError('Generated Material transport settings are ambiguous')
    import_key = import_keys[0]
    import_values = b'[01]' if import_key == b'importMaterials' else b'[012]'
    for key, values in ((import_key, import_values), (b'materialLocation', b'[01]')):
        if len(re.findall(rb'(?m)^    ' + key + rb'[ \t]*:', settings)) != 1:
            raise ValueError('Generated Material transport settings are ambiguous')
        settings, count = re.subn(rb'(?m)^(    ' + key + rb'[ \t]*:[ \t]*)' + values + rb'([ \t]*\r?)$',
                                  rb'\g<1>1\g<2>', settings)
        if count != 1:
            raise ValueError('Generated Material transport settings are unsupported')
    start = importer.start(1) + materials.start(1)
    end = importer.start(1) + materials.end(1)
    return meta[:start] + settings + meta[end:]


def _asset(by_guid, guid, extension, sha):
    source = by_guid.get(guid)
    if source is None or PurePosixPath(source.pathname).suffix.lower() != extension:
        raise ValueError("Source asset is missing or has the wrong type")
    if hashlib.sha256(source.asset_bytes).hexdigest() != sha:
        raise ValueError("Source asset revision changed")
    return source


def _bone_rows(bone_mappings):
    if not isinstance(bone_mappings, list) or not bone_mappings:
        raise ValueError("Bone mappings are incomplete")
    bones = []
    seen_edits, seen_sources = set(), set()
    for row in bone_mappings:
        try:
            edited = row['edited_bone_realization_id']
            source_uid = _id(row['source_model_uid'])
        except (KeyError, TypeError) as exc:
            raise ValueError("Bone mapping is incomplete") from exc
        if not isinstance(edited, str) or not edited or edited in seen_edits or source_uid in seen_sources:
            raise ValueError("Bone mapping identity is missing or duplicated")
        seen_edits.add(edited)
        seen_sources.add(source_uid)
        bones.append({'edited_bone_realization_id': edited, 'source_model_uid': source_uid})
    return sorted(bones, key=lambda row: int(row['source_model_uid']))


def model_skin_task(metadata, bone_mappings, assets):
    """Verify the ordered class1001 path; leave FBX and Unity ID mapping to witnesses."""
    try:
        prefab_guid = _guid(metadata['prefab_guid'])
        prefab_sha = _sha(metadata['prefab_source_sha256'])
        model_guid = _guid(metadata['source_model_guid'])
        model_sha = _sha(metadata['source_model_sha256'])
        model_uid = _id(metadata['source_model_uid'])
        geometry_uid = _id(metadata['source_geometry_uid'])
        realization_id = metadata['realization_id']
        raw_edges = metadata['instance_edges']
    except (KeyError, TypeError) as exc:
        raise ValueError("Model skin metadata is incomplete") from exc
    if not isinstance(realization_id, str) or not realization_id or not isinstance(raw_edges, list) or not raw_edges:
        raise ValueError("Model occurrence is incomplete")

    by_guid = {}
    for source in assets:
        guid = _guid(source.guid)
        if guid in by_guid:
            raise ValueError("Source asset GUID is duplicated")
        by_guid[guid] = source
    _asset(by_guid, prefab_guid, '.prefab', prefab_sha)
    _asset(by_guid, model_guid, '.fbx', model_sha)

    edges = []
    expected_container = prefab_guid
    for raw in raw_edges:
        try:
            container = _guid(raw['container_guid'])
            revision = _sha(raw['container_sha256'])
            instance_id = _id(raw['instance_file_id'])
            source_guid = _guid(raw['source_guid'])
        except (KeyError, TypeError) as exc:
            raise ValueError("Prefab instance edge is incomplete") from exc
        if container != expected_container:
            raise ValueError("Prefab instance edge chain is broken")
        source = _asset(by_guid, container, '.prefab', revision)
        docs = parse_unity_yaml(source.asset_bytes.decode('utf-8-sig'))
        if len({doc.file_id for doc in docs}) != len(docs):
            raise ValueError("Prefab document local ID is duplicated")
        match = next((doc for doc in docs if doc.file_id == int(instance_id)), None)
        reference = match.data.get('m_SourcePrefab') if match is not None and match.class_id == 1001 else None
        if not isinstance(reference, dict) or _guid(reference.get('guid')) != source_guid:
            raise ValueError("Prefab instance source does not match serialized edge")
        edges.append({'container_guid': container, 'container_sha256': revision,
                      'instance_file_id': instance_id, 'source_guid': source_guid})
        expected_container = source_guid
    if expected_container != model_guid:
        raise ValueError("Prefab instance path does not end at the source FBX")

    bones = _bone_rows(bone_mappings)

    identity = {'prefab_guid': prefab_guid, 'instance_edges': edges, 'realization_id': realization_id}
    suffix = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {
        'kind': 'RESTORE_MODEL_SKIN_VARIANT_V1',
        'prefab_guid': prefab_guid, 'prefab_source_sha256': prefab_sha,
        'source_model_guid': model_guid, 'source_model_sha256': model_sha,
        'source_model_uid': model_uid, 'source_geometry_uid': geometry_uid,
        'realization_id': realization_id, 'instance_edges': edges, 'bone_mappings': bones,
        'variant_path': f'Assets/VAPBExport/EditedVariant_{suffix}.prefab',
    }


def direct_skin_task(metadata, bone_mappings, assets):
    """Carry serialized candidates; Unity witnesses must resolve exactly one."""
    try:
        prefab_guid = _guid(metadata['prefab_guid'])
        prefab_sha = _sha(metadata['prefab_source_sha256'])
        model_guid = _guid(metadata['source_model_guid'])
        model_sha = _sha(metadata['source_model_sha256'])
        model_uid = _id(metadata['source_model_uid'])
        geometry_uid = _id(metadata['source_geometry_uid'])
        realization = metadata['realization_id']
    except (KeyError, TypeError) as exc:
        raise ValueError('Direct skin metadata is incomplete') from exc
    if not isinstance(realization, str) or not realization or metadata.get('instance_edges'):
        raise ValueError('Direct skin context is incomplete or inherited')
    by_guid = {}
    for asset in assets:
        guid = _guid(asset.guid)
        if guid in by_guid:
            raise ValueError('Source asset GUID is duplicated')
        by_guid[guid] = asset
    prefab = _asset(by_guid, prefab_guid, '.prefab', prefab_sha)
    _asset(by_guid, model_guid, '.fbx', model_sha)
    docs = parse_unity_yaml(prefab.asset_bytes.decode('utf-8-sig'))
    if len({doc.file_id for doc in docs}) != len(docs):
        raise ValueError('Prefab document local ID is duplicated')
    transforms = {str(doc.file_id) for doc in docs if doc.class_id == 4}
    candidates = []
    for doc in docs:
        reference = doc.data.get('m_Mesh')
        if doc.class_id != 137 or ref_guid(reference) != model_guid:
            continue
        references = doc.data.get('m_Bones')
        root = doc.data.get('m_RootBone')
        if (not isinstance(references, list) or not references or not isinstance(root, dict)
                or any(not isinstance(ref, dict) or ref_guid(ref) not in (None, '', '0' * 32)
                       for ref in references + [root])):
            raise ValueError('Direct skin bone references are incomplete or external')
        # Validate before integer conversion can alias a fractional reference to another ID.
        bones = ['0' if str(ref.get('fileID')) == '0' else _id(str(ref.get('fileID')))
                 for ref in references]
        root_id = _id(str(root.get('fileID')))
        nonnull = [bone for bone in bones if bone != '0']
        if len(set(nonnull)) != len(nonnull) or not set(nonnull + [root_id]) <= transforms:
            raise ValueError('Direct skin bone Transform is missing or duplicated')
        candidates.append({'renderer_file_id': _id(str(doc.file_id)),
                           'source_mesh_file_id': _id(str(reference.get('fileID'))),
                           'bone_transform_file_ids': bones, 'root_bone_transform_file_id': root_id})
    if not candidates:
        raise ValueError('No direct skin references the source FBX')
    candidates.sort(key=lambda row: int(row['renderer_file_id']))
    suffix = hashlib.sha256(('DIRECT_SKIN_V1:' + prefab_guid + ':' + realization).encode()).hexdigest()
    return {'kind': 'RESTORE_DIRECT_SKIN_VARIANT_V1',
            'prefab_guid': prefab_guid, 'prefab_source_sha256': prefab_sha,
            'source_model_guid': model_guid, 'source_model_sha256': model_sha,
            'source_model_uid': model_uid, 'source_geometry_uid': geometry_uid,
            'realization_id': realization, 'instance_edges': [],
            'renderer_candidates': candidates, 'bone_mappings': _bone_rows(bone_mappings),
            'variant_path': f'Assets/VAPBExport/EditedVariant_{suffix}.prefab'}


def source_model_skin_task(metadata, bone_mappings, assets):
    """One real source FBX root; Unity witnesses resolve its native identities."""
    if metadata.get('prefab_guid') or metadata.get('prefab_source_sha256') or metadata.get('instance_edges'):
        raise ValueError('Source-model Skin cannot carry Prefab evidence')
    model_guid = _guid(metadata.get('source_model_guid'))
    model_sha = _sha(metadata.get('source_model_sha256'))
    model_uid = _id(metadata.get('source_model_uid'))
    geometry_uid = _id(metadata.get('source_geometry_uid'))
    realization = metadata.get('realization_id')
    if not isinstance(realization, str) or not realization:
        raise ValueError('Source-model realization is incomplete')
    by_guid = {}
    for source in assets:
        guid = _guid(source.guid)
        if guid in by_guid or PurePosixPath(source.pathname).suffix.lower() == '.prefab':
            raise ValueError('Source-model asset identity is duplicated or has Prefab context')
        by_guid[guid] = source
    _asset(by_guid, model_guid, '.fbx', model_sha)
    identity = f'SOURCE_MODEL_SKIN_V1:{model_guid}:{model_sha}:{realization}'
    suffix = hashlib.sha256(identity.encode()).hexdigest()
    task = dict(kind='RESTORE_SOURCE_MODEL_SKIN_VARIANT_V1', source_model_guid=model_guid,
                source_model_sha256=model_sha, source_model_uid=model_uid,
                source_geometry_uid=geometry_uid, realization_id=realization,
                instance_edges=[], bone_mappings=_bone_rows(bone_mappings),
                variant_path=f'Assets/VAPBExport/EditedVariant_{suffix}.prefab')

    if 'parent_transform_mapping' in metadata:
        row = metadata['parent_transform_mapping']
        if not isinstance(row, dict) or set(row) != {'source_model_uid', 'edited_transform_realization_id'}:
            raise ValueError('Parent Transform receipt is incomplete')
        uid = _id(row['source_model_uid'])
        receipt = row['edited_transform_realization_id']
        if (uid == model_uid or uid in {b['source_model_uid'] for b in task['bone_mappings']}
                or not isinstance(receipt, str) or not receipt or receipt == realization
                or receipt in {b['edited_bone_realization_id'] for b in task['bone_mappings']}):
            raise ValueError('Parent Transform receipt has a conflicting role')
        task['parent_transform_mapping'] = dict(source_model_uid=uid, edited_transform_realization_id=receipt)
    return task

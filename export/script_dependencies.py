# SPDX-License-Identifier: GPL-3.0-or-later
"""Exact external MonoScript references from selected Prefabs and Controllers."""
import hashlib
from pathlib import PurePosixPath
import re

from ..unity.yaml_parser import parse_unity_yaml


_KINDS = {'RESTORE_MODEL_SKIN_VARIANT_V1', 'RESTORE_DIRECT_SKIN_VARIANT_V1',
          'REBIND_SKINNED_RENDERER_V1'}


def _guid(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-fA-F]{32}', value):
        raise ValueError('Script dependency GUID is invalid')
    return value.lower()


def _signed(value):
    text = str(value)
    if not re.fullmatch(r'-?(?:0|[1-9][0-9]*)', text):
        raise ValueError('Script dependency signed fileID is invalid')
    number = int(text)
    if not number or not -(1 << 63) <= number < (1 << 63):
        raise ValueError('Script dependency signed fileID is out of range')
    return str(number)


def _references(value):
    if isinstance(value, dict):
        if 'fileID' in value:
            yield value
        for child in value.values():
            yield from _references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _references(child)


def script_dependencies_for_tasks(tasks, assets):
    """Preserve references, without guessing a provider or traversing unused Prefabs."""
    by_guid = {}
    for asset in assets:
        guid = _guid(asset.guid)
        if guid in by_guid:
            raise ValueError('Script dependency closure has duplicated asset GUIDs')
        by_guid[guid] = asset
    records, visited, active = {}, set(), set()

    def visit(guid, controller_root=None):
        if guid in active and controller_root is None:
            raise ValueError('Script dependency Prefab source cycle')
        asset = by_guid.get(guid)
        suffix = '.controller' if controller_root is not None else '.prefab'
        if asset is None or PurePosixPath(asset.pathname).suffix.lower() != suffix:
            raise ValueError('Script dependency Prefab source is unavailable')
        revision = hashlib.sha256(asset.asset_bytes).hexdigest()
        docs = parse_unity_yaml(asset.asset_bytes.decode('utf-8-sig'))
        if len({doc.file_id for doc in docs}) != len(docs):
            raise ValueError('Script dependency Prefab component identity is duplicated')
        if controller_root is not None:
            roots = [doc for doc in docs if doc.class_id == 91]
            if len(roots) != 1 or _signed(roots[0].file_id) != _signed(controller_root):
                raise ValueError('Script dependency Controller root identity is invalid')
            by_id = {_signed(doc.file_id): doc for doc in docs}
            pending, reached = [_signed(controller_root)], set()
            while pending:
                local_id = pending.pop()
                if local_id in reached:
                    continue
                if local_id not in by_id:
                    raise ValueError('Script dependency Controller local reference is unresolved')
                reached.add(local_id)
                for reference in _references(by_id[local_id].data):
                    if not reference.get('guid') and str(reference['fileID']) != '0':
                        pending.append(_signed(reference['fileID']))
            docs = [doc for doc in docs if _signed(doc.file_id) in reached]
        if guid in visited or guid in active:
            return
        active.add(guid)
        for doc in docs:
            if doc.class_id == 114:
                reference = doc.data.get('m_Script')
                if isinstance(reference, dict) and reference == {'fileID': 0}:
                    continue  # Unassigned script remains an unexplained missing script.
                if not isinstance(reference, dict):
                    raise ValueError('Script dependency reference is malformed')
                provider = _guid(reference.get('guid'))
                file_id = _signed(reference.get('fileID'))
                component = _signed(doc.file_id)
                if provider in by_guid:
                    continue
                key = (provider, file_id)
                record = records.setdefault(key, dict(
                    classification='UNRESOLVED_BUT_PRESERVED', kind='UNITY_SCRIPT',
                    reference_id='VAPB-REF-' + hashlib.sha256(
                        f'UNITY_SCRIPT:{provider}:{file_id}'.encode('ascii')).hexdigest()[:32],
                    guid=provider, file_id=file_id, status='EXTERNAL_DEPENDENCY_REQUIRED',
                    required_by=[]))
                record['required_by'].append(dict(asset_guid=guid, asset_sha256=revision,
                                                  component_file_id=component))
            elif doc.class_id == 1001:
                reference = doc.data.get('m_SourcePrefab')
                if not isinstance(reference, dict):
                    raise ValueError('Script dependency Prefab source reference is malformed')
                source_guid = _guid(reference.get('guid'))
                source = by_guid.get(source_guid)
                if source is None:
                    raise ValueError('Script dependency Prefab source is outside the closure')
                if PurePosixPath(source.pathname).suffix.lower() == '.prefab':
                    visit(source_guid)
        for doc in docs:
            for reference in _references(doc.data):
                candidate = reference.get('guid')
                controller = by_guid.get(candidate.lower()) if isinstance(candidate, str) else None
                if controller is not None and PurePosixPath(controller.pathname).suffix.lower() == '.controller':
                    visit(_guid(candidate), _signed(reference['fileID']))
        active.remove(guid)
        visited.add(guid)

    for task in tasks:
        if task.get('kind') not in _KINDS:
            continue
        guid = _guid(task.get('prefab_guid'))
        source = by_guid.get(guid)
        if source is None or hashlib.sha256(source.asset_bytes).hexdigest() != task.get('prefab_source_sha256'):
            raise ValueError('Script dependency selected Prefab revision is stale')
        visit(guid)
    for record in records.values():
        record['required_by'].sort(key=lambda row: (row['asset_guid'], int(row['component_file_id'])))
    return tuple(records[key] for key in sorted(records))


def missing_material_shader_dependencies_for_tasks(tasks, assets):
    """Declare absent providers for exact bound serialized Materials; never repair them.

    Provider presence is not proof of Shader compatibility or rendering. Embedded
    model Materials are outside this serialized .mat diagnostic.
    """
    by_guid = {}
    for asset in assets:
        guid = _guid(asset.guid)
        if guid in by_guid:
            raise ValueError('Shader dependency closure has duplicated asset GUIDs')
        by_guid[guid] = asset
    records, visited = {}, set()
    for task in tasks:
        if task.get('kind') not in _KINDS:
            continue
        bindings = list(task.get('material_bindings') or ())
        if any('source_material_uid' in row for row in bindings):
            # Native Apply chooses the exact occurrence later. Preserve diagnostics
            # for original candidate Materials now; do not invent a raw UID mapping.
            if task.get('kind') != 'RESTORE_DIRECT_SKIN_VARIANT_V1':
                raise ValueError('Pending source Materials require a direct receiver')
            prefab = by_guid.get(_guid(task.get('prefab_guid')))
            if prefab is None or hashlib.sha256(prefab.asset_bytes).hexdigest() != task.get('prefab_source_sha256'):
                raise ValueError('Pending source Material receiver revision is stale')
            docs = parse_unity_yaml(prefab.asset_bytes.decode('utf-8-sig'))
            bindings = [row for row in bindings if 'source_material_uid' not in row]
            candidates = task.get('renderer_candidates') or ()
            if not candidates:
                raise ValueError('Pending source Material receiver candidates are missing')
            for candidate in candidates:
                found = [d for d in docs if d.class_id == 137 and str(d.file_id) == candidate['renderer_file_id']]
                if len(found) != 1:
                    raise ValueError('Pending source Material receiver is ambiguous')
                mesh = found[0].data.get('m_Mesh', {})
                if mesh.get('guid') != task.get('source_model_guid') or str(mesh.get('fileID')) != candidate['source_mesh_file_id']:
                    raise ValueError('Pending source Material receiver Mesh changed')
                for ref in found[0].data.get('m_Materials', ()):
                    if ref == {'fileID': 0}:
                        continue
                    bindings.append(dict(guid=ref.get('guid'), file_id=str(ref.get('fileID'))))
        for binding in bindings:
            material_guid, material_id = _guid(binding.get('guid')), _signed(binding.get('file_id'))
            key = (material_guid, material_id)
            if key in visited:
                continue
            visited.add(key)
            material = by_guid.get(material_guid)
            if material is None:
                raise ValueError('Shader dependency bound Material is unavailable')
            if PurePosixPath(material.pathname).suffix.lower() != '.mat':
                continue
            docs = [doc for doc in parse_unity_yaml(material.asset_bytes.decode('utf-8-sig'))
                    if doc.class_id == 21 and str(doc.file_id) == material_id]
            if len(docs) != 1:
                raise ValueError('Shader dependency Material identity is unresolved')
            reference = docs[0].data.get('m_Shader')
            if not isinstance(reference, dict):
                raise ValueError('Shader dependency reference is malformed')
            guid, file_id = _guid(reference.get('guid')), _signed(reference.get('fileID'))
            if guid == '0' * 32:
                raise ValueError('Shader dependency GUID is null')
            if guid == '0000000000000000f000000000000000' and file_id == '46':
                continue
            if guid in by_guid:
                continue
            record = records.setdefault((guid, file_id), dict(
                classification='UNRESOLVED_BUT_PRESERVED', kind='SHADER',
                reference_id='VAPB-REF-' + hashlib.sha256(
                    f'SHADER:{guid}:{file_id}'.encode('ascii')).hexdigest()[:32],
                guid=guid, file_id=file_id, status='UNRESOLVED_BUT_PRESERVED', required_by=[]))
            record['required_by'].append(dict(asset_guid=material_guid,
                asset_sha256=hashlib.sha256(material.asset_bytes).hexdigest(),
                component_file_id=material_id))
    for record in records.values():
        record['required_by'].sort(key=lambda row: (row['asset_guid'], int(row['component_file_id'])))
    return tuple(records[key] for key in sorted(records))

# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture one authored Shape's polygon normals on the disposable export copy."""
import math
import struct
import hashlib
from collections import Counter


def _capture_uv0_tangents(mesh):
    """Read endpoint tangents; retain quads when splitting unsupported N-gons."""
    if not mesh.uv_layers:
        raise ValueError('SHAPE_TANGENT_UV0_MISSING')
    uv0 = [tuple(value.uv) for value in mesh.uv_layers[0].data]
    if any(not math.isfinite(x) for uv in uv0 for x in uv):
        raise ValueError('SHAPE_TANGENT_UV0_NONFINITE')
    proxy = None
    try:
        tangent_mesh = mesh
        source_loops = list(range(len(mesh.loops)))
        if any(p.loop_total > 4 for p in mesh.polygons):
            import bpy
            mesh.calc_loop_triangles()
            faces, source_loops = [], []
            triangles = mesh.loop_triangles
            index = 0
            while index < len(triangles):
                tri = triangles[index]
                polygon = mesh.polygons[tri.polygon_index]
                if polygon.loop_total == 4:
                    if (index + 1 >= len(triangles) or
                            triangles[index + 1].polygon_index != polygon.index):
                        raise ValueError('SHAPE_TANGENT_QUAD_DOMAIN_INVALID')
                    loops = tuple(polygon.loop_indices)
                    index += 2
                else:
                    loops = tuple(tri.loops)
                    index += 1
                source_loops.extend(loops)
                faces.append(tuple(mesh.loops[loop].vertex_index for loop in loops))
            proxy = bpy.data.meshes.new('VAPB tangent endpoint')
            proxy.from_pydata([tuple(v.co) for v in mesh.vertices], [], faces)
            for polygon in proxy.polygons:
                polygon.use_smooth = True
            normal = proxy.attributes.new('custom_normal', 'FLOAT_VECTOR', 'CORNER')
            if normal.name != 'custom_normal':
                raise ValueError('SHAPE_TANGENT_NORMAL_DOMAIN_INVALID')
            layer = proxy.uv_layers.new(name='UV0')
            for target, source in enumerate(source_loops):
                normal.data[target].vector = mesh.corner_normals[source].vector
                layer.data[target].uv = uv0[source]
            proxy.update()
            if (len(proxy.loops) != len(source_loops) or
                    any(struct.pack('<3f', *value.vector) !=
                        struct.pack('<3f', *mesh.corner_normals[source].vector)
                        for value, source in zip(proxy.corner_normals, source_loops, strict=True))):
                raise ValueError('SHAPE_TANGENT_NORMAL_INPUT_CHANGED')
            tangent_mesh = proxy
        tangent_mesh.calc_tangents(uvmap=tangent_mesh.uv_layers[0].name)
        tangents = [None] * len(mesh.loops)
        for loop, source in zip(tangent_mesh.loops, source_loops, strict=True):
            value = (*loop.tangent, loop.bitangent_sign)
            if (not all(math.isfinite(x) for x in value) or
                    not any(value[:3]) or abs(value[3]) != 1):
                raise ValueError('SHAPE_TANGENT_ENDPOINT_INVALID')
            previous = tangents[source]
            if previous is not None and struct.pack('<4f', *previous) != struct.pack('<4f', *value):
                raise ValueError('SHAPE_TANGENT_CORNER_CONFLICT')
            tangents[source] = value
        if any(value is None for value in tangents):
            raise ValueError('SHAPE_TANGENT_CORNER_MISSING')
        return ([dict(zip('xy', uv)) for uv in uv0],
                [dict(zip('xyzw', value)) for value in tangents])
    finally:
        if proxy is not None:
            bpy.data.meshes.remove(proxy)


def capture_first_shape_normals(context, obj, *, include_tangents=False,
                                finite_normal_candidate=False):
    """Return Mesh-local endpoints before triangulation, without applying skin pose."""
    keys = obj.data.shape_keys
    if (keys is None or not keys.use_relative or len(keys.key_blocks) != 2
            or not obj.get('_vapb_fbx_realization_id')):
        raise ValueError('SHAPE_NORMAL_CAPTURE_SCOPE_UNSUPPORTED')
    basis, shape = keys.key_blocks
    unsupported = [name for name, failed in (
        ('relative_key', shape.relative_key != basis), ('default_weight', shape.value != 0),
        ('muted', shape.mute), ('vertex_group', bool(shape.vertex_group)),
        ('animation', keys.animation_data is not None and
         (keys.animation_data.action is not None or keys.animation_data.drivers
          or keys.animation_data.nla_tracks))) if failed]
    if unsupported:
        raise ValueError('SHAPE_NORMAL_CAPTURE_SCOPE_UNSUPPORTED:' + ','.join(unsupported))
    obj.data.calc_loop_triangles()
    triangles = [index for tri in obj.data.loop_triangles for index in tri.vertices]
    corners = [index for tri in obj.data.loop_triangles for index in tri.loops]
    triangle_membership = Counter(tuple(sorted(tri.loops)) for tri in obj.data.loop_triangles)
    loop_vertices = [loop.vertex_index for loop in obj.data.loops]
    polygons = [tuple(p.vertices) for p in obj.data.polygons]
    armatures = [(modifier, modifier.show_viewport) for modifier in obj.modifiers
                 if modifier.type == 'ARMATURE']
    frames = []

    def vector(value):
        values = tuple(float(x) for x in value)
        if not all(math.isfinite(x) for x in values):
            raise ValueError('SHAPE_NORMAL_CAPTURE_NONFINITE')
        return dict(zip(('x', 'y', 'z'), values))

    try:
        for modifier, _ in armatures:
            modifier.show_viewport = False
        weights = (0.0, 0.5, 1.0) if finite_normal_candidate else (0.0, 1.0)
        for weight in weights:
            shape.value = weight
            context.view_layer.update()
            graph = context.evaluated_depsgraph_get()
            evaluated = obj.evaluated_get(graph)
            mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=graph)
            try:
                if ([loop.vertex_index for loop in mesh.loops] != loop_vertices
                        or [tuple(p.vertices) for p in mesh.polygons] != polygons
                        or len(mesh.vertices) != len(obj.data.vertices)):
                    raise ValueError('SHAPE_NORMAL_CAPTURE_DOMAIN_CHANGED')
                mesh.calc_loop_triangles()
                if Counter(tuple(sorted(tri.loops)) for tri in mesh.loop_triangles) != triangle_membership:
                    raise ValueError('SHAPE_NORMAL_CAPTURE_TESSELLATION_CHANGED')
                normals = []
                for normal in mesh.corner_normals:
                    if normal.vector.length_squared == 0:
                        raise ValueError('SHAPE_NORMAL_CAPTURE_ZERO_NORMAL')
                    normals.append(vector(normal.vector if include_tangents
                                          else normal.vector.normalized()))
                tangent_data = _capture_uv0_tangents(mesh) if include_tangents else None
                frames.append(([vector(v.co) for v in mesh.vertices], normals, tangent_data))
            finally:
                evaluated.to_mesh_clear()
    finally:
        shape.value = 0
        for modifier, visible in armatures:
            modifier.show_viewport = visible
        context.view_layer.update()
    endpoint = frames[-1]
    recipe = dict(realization_id=obj['_vapb_fbx_realization_id'], shape_name=shape.name,
                frame_weight=100.0, base_positions=frames[0][0], shape_positions=endpoint[0],
                base_normals=frames[0][1], shape_normals=endpoint[1],
                triangles=triangles, corner_indices=corners,
                coordinate_space='BLENDER_MESH_LOCAL_WITHOUT_ARMATURE')
    if include_tangents:
        for frame in frames[1:]:
            if any(struct.pack('<2f', a['x'], a['y']) != struct.pack('<2f', b['x'], b['y'])
                   for a, b in zip(frames[0][2][0], frame[2][0], strict=True)):
                raise ValueError('SHAPE_TANGENT_UV0_CHANGED')
        if finite_normal_candidate:
            for frame in frames[1:]:
                if any(struct.pack('<f', base['w']) != struct.pack('<f', sample['w'])
                       for base, sample in zip(frames[0][2][1], frame[2][1], strict=True)):
                    raise ValueError('SHAPE_FINITE_NORMAL_TANGENT_HANDEDNESS_CHANGED')
        recipe.update(policy_version=3, uv0=frames[0][2][0],
                      base_tangents=frames[0][2][1], shape_tangents=endpoint[2][1])
    if finite_normal_candidate:
        if not include_tangents:
            raise ValueError('SHAPE_FINITE_NORMAL_REQUIRES_TANGENT_SCOPE')
        recipe.update(policy_version=4, normal_sample_weight=50.0,
                      sample_positions=frames[1][0], sample_normals=frames[1][1])
    return recipe


def bind_first_shape_fbx(recipe, path):
    """Bind the captured domains to the actual generated FBX OO graph and arrays."""
    version = recipe.get('policy_version', 2)
    if version not in (2, 3, 4):
        raise ValueError('SHAPE_NORMAL_POLICY_VERSION_UNSUPPORTED')
    if version == 4:
        positions, normals = recipe.get('sample_positions'), recipe.get('sample_normals')
        count = len(recipe.get('base_positions', ()))
        loop_count = len(recipe.get('base_normals', ()))
        def valid_vectors(values, expected):
            return (isinstance(values, list) and len(values) == expected and
                    all(isinstance(row, dict) and set(row) == {'x', 'y', 'z'} and
                        all(isinstance(value, (int, float)) and not isinstance(value, bool)
                            and math.isfinite(value) for value in row.values())
                        for row in values))
        if (recipe.get('normal_sample_weight') != 50.0 or
                not valid_vectors(positions, count) or
                not valid_vectors(normals, loop_count)):
            raise ValueError('SHAPE_NORMAL_SAMPLE_DOMAIN_INVALID')
    from io_scene_fbx import parse_fbx
    root, _ = parse_fbx.parse(str(path), use_namedtuple=True)
    objects = next(n for n in root.elems if n.id == b'Objects')
    nodes = {n.props[0]: n for n in objects.elems}
    if len(nodes) != len(objects.elems):
        raise ValueError('SHAPE_NORMAL_DUPLICATE_FBX_UID')
    children = {}
    for edge in next(n for n in root.elems if n.id == b'Connections').elems:
        if edge.id == b'C' and len(edge.props) == 3 and edge.props[0] == b'OO':
            children.setdefault(edge.props[2], []).append(edge.props[1])

    def property_values(node, name):
        return [p.props[-1] for container in node.elems if container.id == b'Properties70'
                for p in container.elems if p.id == b'P' and p.props and p.props[0] == name]

    models = [node for node in objects.elems if node.id == b'Model'
              and property_values(node, b'_vapb_fbx_realization_id') ==
              [recipe['realization_id'].encode()]]
    content_sha = hashlib.sha256(recipe['content_json'].encode()).hexdigest()
    if (len(models) != 1 or property_values(models[0], b'_vapb_shape_normal_policy_required') !=
            [(str(version) + ':' + content_sha).encode()]):
        raise ValueError('SHAPE_NORMAL_GENERATED_MODEL_IDENTITY_UNPROVEN')

    def unique_child(parent, element, subtype):
        candidates = [nodes[uid] for uid in children.get(parent.props[0], [])
                      if uid in nodes and nodes[uid].id == element
                      and nodes[uid].props[-1] == subtype]
        if len(candidates) != 1:
            raise ValueError('SHAPE_NORMAL_GENERATED_GRAPH_UNPROVEN')
        return candidates[0]

    mesh = unique_child(models[0], b'Geometry', b'Mesh')
    blend = unique_child(mesh, b'Deformer', b'BlendShape')
    channel = unique_child(blend, b'Deformer', b'BlendShapeChannel')
    shape = unique_child(channel, b'Geometry', b'Shape')
    fields = lambda node: {n.id: n.props[0] for n in node.elems if n.props}
    mf, sf = fields(mesh), fields(shape)
    full_weights = list(fields(channel).get(b'FullWeights', []))
    if not full_weights or any(weight != 100.0 for weight in full_weights):
        raise ValueError('SHAPE_NORMAL_FRAME_UNSUPPORTED')
    xyz = lambda v: tuple(v[k] for k in ('x', 'y', 'z'))
    if list(mf[b'Vertices']) != [x for v in recipe['base_positions'] for x in xyz(v)]:
        raise ValueError('SHAPE_NORMAL_GENERATED_CONTROL_POINTS_CHANGED')
    raw = [~v if v < 0 else v for v in mf[b'PolygonVertexIndex']]
    if (len(raw) % 3 or any((v < 0) != (i % 3 == 2)
                            for i, v in enumerate(mf[b'PolygonVertexIndex']))
            or Counter(tuple(sorted(raw[i:i+3])) for i in range(0, len(raw), 3)) !=
               Counter(tuple(sorted(recipe['triangles'][i:i+3]))
                       for i in range(0, len(recipe['triangles']), 3))):
        raise ValueError('SHAPE_NORMAL_GENERATED_TRIANGLES_CHANGED')
    deltas = [dict(x=0.0, y=0.0, z=0.0) for _ in recipe['base_positions']]
    indices, values = list(sf[b'Indexes']), list(sf[b'Vertices'])
    if len(set(indices)) != len(indices) or len(values) != 3 * len(indices):
        raise ValueError('SHAPE_NORMAL_FRAME_DOMAIN_INVALID')
    for j, index in enumerate(indices):
        if not 0 <= index < len(deltas):
            raise ValueError('SHAPE_NORMAL_FRAME_DOMAIN_INVALID')
        deltas[index] = dict(zip(('x', 'y', 'z'), values[j*3:j*3+3]))
    f32 = lambda value: struct.unpack('<f', struct.pack('<f', value))[0]
    for base, target, delta in zip(recipe['base_positions'], recipe['shape_positions'], deltas):
        if any(f32(t-b) != f32(d) for b, t, d in zip(xyz(base), xyz(target), xyz(delta))):
            raise ValueError('SHAPE_NORMAL_GENERATED_POSITION_DELTA_CHANGED')
    bound = dict(realization_id=recipe['realization_id'], model_uid=str(models[0].props[0]),
                geometry_uid=str(mesh.props[0]), shape_geometry_uid=str(shape.props[0]),
                shape_channel_uid=str(channel.props[0]), content_json=recipe['content_json'],
                content_sha256=content_sha)
    if version in (3, 4):
        bound['policy_version'] = version
    return bound

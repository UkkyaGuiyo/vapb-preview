"""Conservative presentation hints, never authoritative anatomy or asset identity."""

import math
import re


def shoe_candidate(obj):
    """Suggest footwear only when names, actual bindings and rest geometry agree.

    Bare feet named shoes can satisfy this heuristic. The caller must require
    human confirmation and preserve every existing user classification.
    """
    names = [obj.name, obj.data.name] + [s.material.name for s in obj.material_slots if s.material]
    text = ' '.join(re.sub(r'([a-z])([A-Z])', r'\1 \2', name) for name in names).casefold()
    words = set(re.findall(r'[a-z]+', text))
    if not (words & {'shoe', 'shoes'} or '靴' in text):
        return False
    if words & {'body', 'head', 'face', 'hair', 'sock', 'socks'}:
        return False
    modifiers = [m for m in obj.modifiers if m.show_viewport]
    if (len(modifiers) != 1 or modifiers[0].type != 'ARMATURE'
            or not modifiers[0].use_vertex_groups or modifiers[0].use_bone_envelopes):
        return False
    rig = modifiers[0].object
    if rig is None or rig.type != 'ARMATURE' or not obj.data.vertices:
        return False
    matrices = (obj.matrix_world, rig.matrix_world)
    if any(not all(math.isfinite(v) for row in matrix for v in row)
           or matrix.determinant() == 0 for matrix in matrices):
        return False
    to_rig = rig.matrix_world.inverted() @ obj.matrix_world
    normalize = lambda name: re.sub(r'[^a-z0-9]', '', name.casefold())
    chains = []
    foot_names, leg_names = set(), set()
    for side, letter in (('left', 'l'), ('right', 'r')):
        feet = [b for b in rig.data.bones if normalize(b.name) in
                {side + 'foot', 'foot' + side, letter + 'foot', 'foot' + letter}]
        if len(feet) != 1:
            return False
        foot = feet[0]
        toes = [b for b in foot.children if normalize(b.name) in
                {side + 'toe', 'toe' + side, letter + 'toe', 'toe' + letter,
                 side + 'toes', 'toes' + side}]
        if len(toes) != 1 or foot.parent is None:
            return False
        toe, leg = toes[0], foot.parent
        if not all(b.use_deform for b in (foot, toe, leg)):
            return False
        ankle, tip, knee = foot.head_local, toe.tail_local, leg.head_local
        if not all(math.isfinite(v) for point in (ankle, tip, knee) for v in point):
            return False
        span, shin = tip - ankle, knee - ankle
        if any(not math.isfinite(length) or length <= 0
               for length in (span.length_squared, shin.length_squared)):
            return False
        # The ankle is above the sole. Compare horizontal extent in the plane
        # perpendicular to the shin, rather than treating that height as width.
        span = span - shin * (span.dot(shin) / shin.length_squared)
        if not math.isfinite(span.length_squared) or span.length_squared <= 0:
            return False
        chains.append((ankle, span, shin))
        foot_names.update((foot.name, toe.name))
        leg_names.add(leg.name)
    if len(leg_names) != 2 or len(foot_names) != 4 or foot_names & leg_names:
        return False
    if ((chains[0][0] - chains[1][0]).length == 0
            or chains[0][1].dot(chains[1][1]) <= 0
            or chains[0][2].dot(chains[1][2]) <= 0):
        return False
    by_index = {g.index: g.name for g in obj.vertex_groups}
    foot_weight = total_weight = 0.0
    for vertex in obj.data.vertices:
        positive = 0.0
        for group in vertex.groups:
            weight = group.weight
            if not math.isfinite(weight) or weight < 0:
                return False
            if weight == 0:
                continue
            bone = by_index.get(group.group)
            if bone not in foot_names | leg_names:
                return False
            positive += weight
            if bone in foot_names:
                foot_weight += weight
        if positive == 0:
            return False
        total_weight += positive
        point = to_rig @ vertex.co
        if not all(math.isfinite(v) for v in point):
            return False
        localized = False
        for ankle, span, shin in chains:
            relative = point - ankle
            height = relative.dot(shin) / shin.length
            horizontal = relative - shin * (height / shin.length)
            along = max(0.0, min(1.0, horizontal.dot(span) / span.length_squared))
            # Whole-Mesh footprint: half a foot-span around either segment.
            # Height: one foot-span below ankle to ankle/knee midpoint.
            if ((horizontal - along * span).length <= span.length * 0.5
                    and -span.length <= height <= shin.length * 0.5):
                localized = True
                break
        if not localized:
            return False
    return foot_weight > total_weight * 0.5


def hair_candidate(obj):
    """Hint only for hair-branch-driven parts, never rigid Head-only surfaces.

    Rest-space locality uses one Neck-to-Head separation around the actually
    weighted hair branches and their hair ancestors. This is a fixed heuristic,
    not a skull-size measurement or proof of anatomy; confirmation is required.
    """
    text = ' '.join(re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
                    for name in (obj.name, obj.data.name)).casefold()
    words = set(re.findall(r'[a-z]+', text))
    if not ('hair' in words or '髪' in text):
        return False
    if words & {'body', 'head', 'face', 'eye', 'eyes', 'ear', 'ears', 'earring',
                'earrings', 'hat', 'accessory', 'accessories', 'shoe', 'shoes'}:
        return False
    modifiers = [m for m in obj.modifiers if m.show_viewport]
    if (len(modifiers) != 1 or modifiers[0].type != 'ARMATURE'
            or not modifiers[0].use_vertex_groups or modifiers[0].use_bone_envelopes):
        return False
    rig = modifiers[0].object
    if rig is None or rig.type != 'ARMATURE' or not obj.data.vertices:
        return False
    if any(not all(math.isfinite(v) for row in matrix for v in row)
           or matrix.determinant() == 0 for matrix in (obj.matrix_world, rig.matrix_world)):
        return False
    to_rig = rig.matrix_world.inverted() @ obj.matrix_world
    normalize = lambda name: re.sub(r'[^a-z0-9]', '', name.casefold())
    heads = [b for b in rig.data.bones if normalize(b.name) == 'head']
    necks = [b for b in rig.data.bones if normalize(b.name) == 'neck']
    if len(heads) != 1 or len(necks) != 1 or heads[0].parent != necks[0]:
        return False
    head, neck = heads[0], necks[0]
    if not head.use_deform or not neck.use_deform:
        return False
    radius = (head.head_local - neck.head_local).length
    if not math.isfinite(radius) or radius <= 0:
        return False
    branches = {}
    for bone in rig.data.bones:
        if not bone.use_deform or not normalize(bone.name).startswith('hair'):
            continue
        chain, ancestor = [], bone
        while ancestor is not None and ancestor != head:
            if not normalize(ancestor.name).startswith('hair'):
                break
            chain.append(ancestor)
            ancestor = ancestor.parent
        if ancestor == head:
            branches[bone.name] = chain
    if not branches:
        return False
    by_index = {g.index: g.name for g in obj.vertex_groups}
    head_weight = hair_weight = 0.0
    used = {}
    for vertex in obj.data.vertices:
        positive = 0.0
        for group in vertex.groups:
            weight = group.weight
            if not math.isfinite(weight) or weight < 0:
                return False
            if weight == 0:
                continue
            bone_name = by_index.get(group.group)
            if bone_name == head.name:
                head_weight += weight
            elif bone_name in branches:
                hair_weight += weight
                used.update((b.name, b) for b in branches[bone_name])
            else:
                return False
            positive += weight
        if positive == 0:
            return False
    if hair_weight <= head_weight:
        return False
    segments = [(head.head_local, head.head_local)] + [
        (b.head_local, b.tail_local) for b in used.values()]
    if not all(math.isfinite(v) for segment in segments for point in segment for v in point):
        return False
    for vertex in obj.data.vertices:
        point = to_rig @ vertex.co
        if not all(math.isfinite(v) for v in point):
            return False
        localized = False
        for start, end in segments:
            span = end - start
            along = max(0.0, min(1.0, (point - start).dot(span) / span.length_squared)) if span.length_squared else 0.0
            if (point - start - span * along).length <= radius:
                localized = True
                break
        if not localized:
            return False
    return True

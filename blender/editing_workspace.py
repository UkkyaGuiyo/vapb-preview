"""Presentation-only part collections; Unity identity and parenting stay intact."""

import bpy
from itertools import count


# Native search copies RNA properties and executes a new operator instance.
# Retain strings and captured references per popup, with at most one per window.
_part_searches = {}
_part_search_sequence = count()


PART_LABELS = {
    'BODY': 'Body / 身体', 'HEAD': 'Head / 頭部', 'FACE': 'Face / 顔・表情',
    'HAIR': 'Hair / 髪', 'CLOTHING': 'Clothing / 衣装', 'SHOES': 'Shoes / 靴',
    'ACCESSORIES': 'Accessories / 装飾品', 'ARMATURE': 'Armature / 骨格',
    'OTHER': 'Other / 未分類', 'INTERNAL': '内部参照・階層',
}


def _category_collection(member, category):
    scope = member['_vapb_workspace_root_context_id']
    for collection in member.children:
        if (collection.get('_vapb_workspace_root_context_id') == scope
                and collection.get('_vapb_part_category') == category):
            return collection
    collection = bpy.data.collections.new(PART_LABELS[category])
    collection['_vapb_workspace_root_context_id'] = scope
    collection['_vapb_part_category'] = category
    member.children.link(collection)
    return collection


def organize_member(member, root_context_id):
    """Only called on the current import's newly constructed member Collection."""
    member['_vapb_workspace_root_context_id'] = root_context_id
    for obj in tuple(member.objects):
        category = ('ARMATURE' if obj.type == 'ARMATURE' else
                    'OTHER' if obj.type == 'MESH' else 'INTERNAL')
        obj['_vapb_workspace_root_context_id'] = root_context_id
        obj['_vapb_part_category'] = category
        obj['_vapb_part_evidence'] = 'UNCLASSIFIED' if category == 'OTHER' else 'OBJECT_TYPE'
        _category_collection(member, category).objects.link(obj)
        member.objects.unlink(obj)


def member_for_object(scene, obj):
    if obj is None:
        return None
    scope = obj.get('_vapb_workspace_root_context_id')
    members = [c for c in scene.collection.children_recursive
               if c.get('_vapb_workspace_root_context_id')
               and (not scope or c.get('_vapb_workspace_root_context_id') == scope)
               and c.get('unity_composition_member_id')
               and obj.name in c.all_objects]
    return members[0] if len(members) == 1 else None


def show_imported_members(context, members):
    """Best-effort foreground handoff using only this import's new Collections."""
    if bpy.app.background or context.window is None or context.mode != 'OBJECT' or not members:
        return False
    area = context.area
    if area is None or area.type != 'VIEW_3D':
        area = next((a for a in context.window.screen.areas if a.type == 'VIEW_3D'), None)
    if area is None or area.spaces.active.local_view is not None:
        return False
    region = next((r for r in area.regions if r.type == 'WINDOW'), None)
    if region is None or region.data is None or region.data.view_perspective == 'CAMERA':
        # Frame Selected can move a locked scene Camera. Never take over camera view.
        return False
    with context.temp_override(area=area, region=region):
        selectable = set(context.selectable_objects)
        targets = list(dict.fromkeys(obj for member in members for obj in member.all_objects
                       if obj.type == 'MESH' and obj in selectable
                       and member_for_object(context.scene, obj) == member))
        if not targets or not bpy.ops.view3d.view_selected.poll():
            return False
        layer = context.view_layer
        previous = {obj for obj in layer.objects if obj.select_get()}
        active = layer.objects.active
        try:
            for obj in previous | set(targets):
                obj.select_set(obj in targets)
            layer.objects.active = targets[0]
            if 'FINISHED' not in bpy.ops.view3d.view_selected(use_all_regions=False):
                raise RuntimeError('Imported Mesh framing was unavailable')
        except (RuntimeError, ReferenceError):
            for obj in previous | set(targets):
                obj.select_set(obj in previous)
            layer.objects.active = active
            return False
        area.spaces.active.show_region_ui = True
        sidebar = next((r for r in area.regions if r.type == 'UI'), None)
        if sidebar is not None:
            try:
                sidebar.active_panel_category = 'VAPB編集'
            except (AttributeError, TypeError, RuntimeError):
                # Category activation also requires an already drawn sidebar in current Blender.
                pass
    try:
        _defer_imported_part_reveal(context)
    except (RuntimeError, ReferenceError):
        # A closed or unavailable Outliner must not turn a completed Import into failure.
        pass
    return True


def _defer_imported_part_reveal(context):
    # The newly imported tree is unavailable until Blender returns to its UI loop.
    window, screen = context.window, context.window.screen
    scene, layer = context.scene, context.view_layer
    active = layer.objects.active
    member = member_for_object(scene, active)

    def reveal():
        try:
            current = bpy.context
            if (not VAPB_OT_reveal_part.is_registered
                    or window not in tuple(current.window_manager.windows)
                    or window.screen != screen or window.scene != scene
                    or window.view_layer != layer or layer.objects.active != active):
                return None
            with current.temp_override(window=window):
                if (current.mode == 'OBJECT'
                        and member_for_object(current.scene, active) == member):
                    _show_active_in_outliner(current)
        except (RuntimeError, ReferenceError):
            # Closing a window, undoing Import or changing editors cancels this view hint.
            pass
        return None

    # Best effort, exactly once; no retry, persistent callback or forced redraw.
    bpy.app.timers.register(reveal, first_interval=0.1)


def classify_mesh(scene, obj, category):
    member = member_for_object(scene, obj)
    if (member is None or obj.type != 'MESH'
            or category not in PART_LABELS or category in {'ARMATURE', 'INTERNAL'}):
        raise ValueError('分類するPrefab内のMeshを選択してください')
    target = _category_collection(member, category)
    previous = [c for c in obj.users_collection if c in tuple(member.children)
                and c.get('_vapb_workspace_root_context_id') == member['_vapb_workspace_root_context_id']
                and c.get('_vapb_part_category') in PART_LABELS and c != target]
    if obj.name not in target.objects:
        target.objects.link(obj)
    if obj.name in member.objects:
        member.objects.unlink(obj)
    for collection in previous:
        collection.objects.unlink(obj)
        # Never remove a user's objects, child Collections or additional links.
        if not collection.objects and not collection.children and collection.users == 1:
            bpy.data.collections.remove(collection)
    obj['_vapb_part_category'] = category
    obj['_vapb_part_evidence'] = 'USER'
    obj['_vapb_workspace_root_context_id'] = member['_vapb_workspace_root_context_id']


def _classification_targets(context, apply_selected, category):
    """Validate the entire explicit selection before moving any Collection links."""
    if context.mode != 'OBJECT' or category not in PART_LABELS or category in {'ARMATURE', 'INTERNAL'}:
        raise ValueError('ObjectモードでMeshの分類を指定してください')
    member = member_for_object(context.scene, context.active_object)
    targets = tuple(context.selected_objects) if apply_selected else (context.active_object,)
    if member is None or not targets:
        raise ValueError('分類するPrefab内のMeshを選択してください')
    members = [c for c in context.scene.collection.children_recursive
               if c.get('unity_composition_member_id') and c.get('_vapb_workspace_root_context_id')]
    for obj in targets:
        if (obj is None or obj.type != 'MESH' or member_for_object(context.scene, obj) != member
                or [c for c in members if obj.name in c.all_objects] != [member]):
            raise ValueError('同じPrefabのMeshだけを選択してください。別Prefab・所属不明の部品はまとめて分類できません')
        affected = [obj, member] + [c for c in member.children
            if c.get('_vapb_workspace_root_context_id') == member['_vapb_workspace_root_context_id']
            and c.get('_vapb_part_category') in PART_LABELS
            and (c in obj.users_collection or c.get('_vapb_part_category') == category)]
        if any(collection.users != 1 for collection in affected[2:]):
            raise ValueError('分類用Collectionが他の場所と共有されています。共有を確認してから分類してください')
        if any(not item.is_editable or item.library is not None or item.override_library is not None
               for item in affected):
            raise ValueError('リンク・オーバーライド等の編集できない部品やCollectionは分類できません')
    return targets


class VAPB_OT_classify_part(bpy.types.Operator):
    bl_idname = 'vapb.classify_part'
    bl_label = '選択した部品の分類を変更'
    bl_description = '選択中のMeshの表示分類を指定します。元の階層やUnity設定は変更しません'
    bl_options = {'REGISTER', 'UNDO'}

    category: bpy.props.EnumProperty(
        name='部品の分類', default='OTHER',
        items=[(key, label, '') for key, label in PART_LABELS.items()
               if key not in {'ARMATURE', 'INTERNAL'}],
    )
    apply_selected: bpy.props.BoolProperty(
        name='選択中のMeshへまとめて適用', default=False, options={'SKIP_SAVE'},
        description='同じPrefab内で選択したMeshすべてを、利用者が確認した分類へ移します',
    )
    part_suggestion: bpy.props.StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (context.mode == 'OBJECT' and obj is not None and obj.type == 'MESH'
                and member_for_object(context.scene, obj) is not None)

    def invoke(self, context, event):
        self.apply_selected = False
        self.part_suggestion = ''
        self._suggestion_target = None
        current = context.active_object.get('_vapb_part_category', 'OTHER')
        self.category = current if current in PART_LABELS and current not in {'ARMATURE', 'INTERNAL'} else 'OTHER'
        if self.category == 'OTHER' and context.active_object.get('_vapb_part_evidence') != 'USER':
            try:
                _classification_targets(context, False, self.category)
                from .part_suggestion import shoe_candidate, hair_candidate
                if shoe_candidate(context.active_object):
                    self.part_suggestion = 'SHOES'
                elif hair_candidate(context.active_object):
                    self.part_suggestion = 'HAIR'
            except (ValueError, ReferenceError, ZeroDivisionError):
                self.part_suggestion = ''
            if self.part_suggestion:
                self._suggestion_target = context.active_object
                self.category = self.part_suggestion
        return context.window_manager.invoke_props_dialog(self)

    def _validate_suggestion_target(self, context):
        if not self.part_suggestion:
            return
        target = getattr(self, '_suggestion_target', None)
        try:
            valid = target is not None and target == context.active_object
        except ReferenceError:
            valid = False
        if not valid:
            raise ValueError('対象が変わりました。部品を選び直し、分類画面を開き直してください')

    def draw(self, context):
        try:
            self._validate_suggestion_target(context)
        except ValueError as exc:
            self.layout.label(text=str(exc), icon='ERROR')
            return
        if self.part_suggestion:
            self.layout.label(text=f'候補: {PART_LABELS[self.part_suggestion]}（確認して適用）', icon='INFO')
            self.layout.label(text='名前・骨の接続・ウェイト・形状から推定')
            self.layout.label(text='見た目を確認して適用してください')
            self.layout.label(text='候補はこの部品だけに適用します')
        self.layout.prop(self, 'category')
        row = self.layout.row()
        row.enabled = not self.part_suggestion
        row.prop(self, 'apply_selected')
        try:
            targets = _classification_targets(context, self.apply_selected, self.category)
            self.layout.label(text=f'変更対象: {len(targets)} Mesh')
            if not self.apply_selected:
                self.layout.label(text=context.active_object.name)
        except ValueError as exc:
            self.layout.label(text=str(exc), icon='ERROR')

    def execute(self, context):
        if self.part_suggestion and self.apply_selected:
            self.report({'ERROR'}, '分類候補は選択中の部品だけに適用してください')
            return {'CANCELLED'}
        try:
            self._validate_suggestion_target(context)
            targets = _classification_targets(context, self.apply_selected, self.category)
        except ValueError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        for obj in targets:
            classify_mesh(context.scene, obj, self.category)
        return {'FINISHED'}


class VAPB_OT_focus_prefab(bpy.types.Operator):
    bl_idname = 'vapb.focus_prefab'
    bl_label = 'Prefabの集中表示を切り替え'
    bl_description = 'この3DビューだけをPrefabの表示に切り替えます。もう一度押すと元の全体表示へ戻ります'
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return (context.area is not None and context.area.type == 'VIEW_3D'
                and context.mode == 'OBJECT'
                and (context.space_data.local_view is not None
                     or member_for_object(context.scene, context.active_object) is not None))

    def execute(self, context):
        region = next((r for r in context.area.regions if r.type == 'WINDOW'), None)
        if region is None:
            return {'CANCELLED'}
        if context.space_data.local_view is not None:
            with context.temp_override(region=region):
                return bpy.ops.view3d.localview(frame_selected=True)

        member = member_for_object(context.scene, context.active_object)
        targets = {obj for obj in member.all_objects if obj.visible_get()}
        if not any(obj.type == 'MESH' for obj in targets):
            self.report({'WARNING'}, 'Prefab内のMeshを表示してから実行してください')
            return {'CANCELLED'}
        layer = context.view_layer
        selected = {obj for obj in layer.objects if obj.select_get()}
        active = layer.objects.active
        try:
            for obj in selected | targets:
                obj.select_set(obj in targets)
            with context.temp_override(region=region):
                result = bpy.ops.view3d.localview(frame_selected=True)
        finally:
            for obj in selected | targets:
                obj.select_set(obj in selected)
            layer.objects.active = active
        return result


def _show_active_in_outliner(context):
    for area in context.window.screen.areas:
        if (area.type != 'OUTLINER' or area.spaces.active.display_mode != 'VIEW_LAYER'
                or area.spaces.active.filter_text):
            continue
        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
        if region is None:
            continue
        with context.temp_override(area=area, region=region):
            try:
                if bpy.ops.outliner.show_active.poll():
                    if 'FINISHED' in bpy.ops.outliner.show_active():
                        return True
            except RuntimeError:
                pass
    return False


class VAPB_OT_reveal_part(bpy.types.Operator):
    bl_idname = 'vapb.reveal_part'
    bl_label = 'Outlinerで部品を表示'
    bl_description = '編集中の部品の行へ移動します。検索条件や元の階層は変更しません'

    @classmethod
    def poll(cls, context):
        return (context.window is not None
                and member_for_object(context.scene, context.active_object) is not None)

    def execute(self, context):
        if not self.poll(context):
            return {'CANCELLED'}
        if _show_active_in_outliner(context):
            return {'FINISHED'}
        self.report({'WARNING'}, '部品を表示できません。OutlinerをView Layer表示にし、検索や表示フィルターを確認してください')
        return {'CANCELLED'}


class VAPB_OT_find_part(bpy.types.Operator):
    bl_idname = 'vapb.find_part'
    bl_label = '編集するMeshを探す'
    bl_description = '表示中のPrefabから部品を検索し、選択して画面中央に表示します'
    bl_property = 'target'

    def _items(self, context):
        search = _part_searches.get(self.search_session)
        return search[1] if search else []

    target: bpy.props.EnumProperty(name='編集する部品', items=_items)
    search_session: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def unregister(cls):
        _part_searches.clear()

    @classmethod
    def poll(cls, context):
        return (context.area is not None and context.area.type == 'VIEW_3D'
                and context.mode == 'OBJECT')

    def invoke(self, context, event):
        window = context.window.as_pointer()
        live_windows = {w.as_pointer() for w in context.window_manager.windows}
        # Escape/click-away has no operator cancel callback. Replace that window's
        # abandoned snapshot on its next search and discard closed-window entries.
        for key, search in tuple(_part_searches.items()):
            if search[0] == window or search[0] not in live_windows:
                del _part_searches[key]
        choices = []
        for obj in context.selectable_objects:
            if obj.type != 'MESH':
                continue
            member = member_for_object(context.scene, obj)
            if member is not None:
                category = PART_LABELS.get(obj.get('_vapb_part_category'), PART_LABELS['OTHER'])
                choices.append((f'{member.name} / {category} / {obj.name}', obj, member))
        choices.sort(key=lambda choice: choice[0].casefold())
        # The index only addresses this invocation's captured object references.
        targets = {str(i): (obj, member) for i, (_, obj, member) in enumerate(choices)}
        if not choices:
            self.report({'WARNING'}, '検索できるMeshがありません。Prefabを読み込み、部品を表示してください')
            return {'CANCELLED'}
        self.search_session = str(next(_part_search_sequence))
        items = [(str(i), label, '') for i, (label, _, _) in enumerate(choices)]
        _part_searches[self.search_session] = (window, items, targets)
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}

    def execute(self, context):
        search = _part_searches.get(self.search_session)
        if search is None or search[0] != context.window.as_pointer():
            return {'CANCELLED'}
        captured = search[2].get(self.target)
        del _part_searches[self.search_session]
        if captured is None or not self.poll(context):
            return {'CANCELLED'}
        obj, member = captured
        try:
            valid = (obj.type == 'MESH'
                     and member_for_object(context.scene, obj) == member
                     and obj in context.selectable_objects)
        except ReferenceError:
            valid = False
        if not valid:
            self.report({'WARNING'}, '部品の状態が変わりました。表示状態を確認して、もう一度検索してください')
            return {'CANCELLED'}
        region = next((r for r in context.area.regions if r.type == 'WINDOW'), None)
        if region is None or region.data is None:
            return {'CANCELLED'}
        if region.data.view_perspective == 'CAMERA':
            # Frame Selected moves a view-locked Camera, not just the viewport.
            self.report({'WARNING'}, 'カメラ表示を解除してから、もう一度部品を検索してください')
            return {'CANCELLED'}
        layer = context.view_layer
        selected = tuple(context.selected_objects)
        active = layer.objects.active
        try:
            for previous in selected:
                previous.select_set(False)
            obj.select_set(True)
            layer.objects.active = obj
            with context.temp_override(region=region):
                result = bpy.ops.view3d.view_selected(use_all_regions=False)
            if 'FINISHED' not in result:
                raise RuntimeError('表示範囲を変更できませんでした')
        except RuntimeError as exc:
            obj.select_set(False)
            for previous in selected:
                previous.select_set(True)
            layer.objects.active = active
            self.report({'WARNING'}, str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}


CLASSES = (VAPB_OT_classify_part, VAPB_OT_focus_prefab, VAPB_OT_reveal_part, VAPB_OT_find_part)

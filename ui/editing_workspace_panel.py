"""Small editing entry point next to existing import results."""

import bpy

from ..blender.editing_workspace import PART_LABELS, member_for_object


def _prefab_layers(layer, blocked=False):
    """Pair each actual View Layer occurrence with its inherited restrictions."""
    restricted = blocked or layer.exclude or layer.collection.hide_viewport
    if (layer.collection.get('unity_composition_member_id')
            and layer.collection.get('_vapb_workspace_root_context_id')):
        yield layer, restricted
    for child in layer.children:
        yield from _prefab_layers(child, restricted or layer.hide_viewport)


class VAPB_PT_editing_workspace(bpy.types.Panel):
    bl_label = '編集する部品'
    bl_idname = 'VAPB_PT_editing_workspace'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VAPB編集'
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        members = tuple(_prefab_layers(context.view_layer.layer_collection))
        if members:
            header, visibility = layout.panel('vapb_workspace_prefab_visibility', default_closed=True)
            header.label(text=f'Prefabの表示（{len(members)}件）')
            if visibility is not None:
                visibility.label(text='目のボタンで表示を切り替えます')
                local = context.space_data.local_view is not None
                for layer, restricted in members:
                    row = visibility.row()
                    row.label(text=layer.collection.name, icon='OUTLINER_COLLECTION')
                    control = row.row()
                    control.enabled = not restricted and not local and context.mode == 'OBJECT'
                    control.prop(layer, 'hide_viewport', text='', toggle=True,
                                 icon='HIDE_ON' if layer.hide_viewport else 'HIDE_OFF')
                    if restricted:
                        visibility.label(text='上位階層などで非表示です')
                        visibility.label(text='Outlinerの表示・除外を確認してください')
                if local:
                    visibility.label(text='先に「全体表示へ戻す」を押します')
                elif context.mode != 'OBJECT':
                    visibility.label(text='表示切替はObjectモードで行います')
                visibility.label(text='このView Layerの表示だけを変更します')
        row = layout.row()
        row.enabled = context.mode == 'OBJECT'
        row.operator('vapb.find_part', icon='VIEWZOOM')
        layout.label(text='表示中の部品を名前や分類で検索')
        obj = context.active_object
        member = member_for_object(context.scene, obj)
        if context.space_data.local_view is not None or member is not None:
            row = layout.row()
            row.enabled = context.mode == 'OBJECT'
            row.operator('vapb.focus_prefab', text=(
                '全体表示へ戻す' if context.space_data.local_view is not None
                else 'このPrefabに集中表示'))
            if context.mode != 'OBJECT':
                layout.label(text='表示切替はObjectモードで行います')
        if members:
            header, overlays = layout.panel('vapb_workspace_overlays', default_closed=True)
            header.label(text='骨格・補助物の表示')
            if overlays is not None:
                overlay = context.space_data.overlay
                controls = overlays.column()
                controls.enabled = overlay.show_overlays
                controls.prop(overlay, 'show_bones', text='骨格を表示')
                controls.prop(overlay, 'show_extras', text='補助物（Empty等）を表示')
                if not overlay.show_overlays:
                    overlays.label(text='オーバーレイがオフです')
                overlays.label(text='この3Dビューの表示だけを変更')
                overlays.label(text='データ・変形・出力は保持します')
        if member is None:
            layout.label(text='OutlinerからPrefab内の部品を選択')
            layout.label(text='未分類の部品はOtherにあります')
            return
        layout.label(text=member.name, icon='OUTLINER_COLLECTION')
        layout.label(text=obj.name, icon='OBJECT_DATA')
        layout.operator('vapb.reveal_part', icon='OUTLINER')
        layout.label(text=PART_LABELS.get(obj.get('_vapb_part_category'), 'Other / 未分類'))
        if obj.get('_vapb_part_evidence') == 'USER':
            layout.label(text='利用者が指定した分類')
        elif obj.type == 'MESH':
            layout.label(text='役割を確認して分類できます')
        row = layout.row()
        row.enabled = obj.type == 'MESH' and context.mode == 'OBJECT'
        row.operator('vapb.classify_part')
        if obj.type != 'MESH':
            layout.label(text='分類変更はMeshを選択してください')
        elif context.mode != 'OBJECT':
            layout.label(text='分類変更はObjectモードで行います')

        header, details = layout.panel('vapb_workspace_outliner', default_closed=True)
        header.label(text='Outlinerの表示設定')
        if details is not None:
            outliners = [area.spaces.active for area in context.window.screen.areas
                         if area.type == 'OUTLINER' and area.spaces.active.display_mode == 'VIEW_LAYER']
            if len(outliners) == 1:
                details.prop(outliners[0], 'use_filter_children', text='親子階層を表示')
                details.prop(outliners[0], 'use_filter_object_content', text='Mesh・骨などの内部詳細を表示')
                details.label(text='表示だけの変更です。データは保持します')
                details.label(text='内部参照は矢印で折りたためます')
            else:
                details.label(text='各Outlinerのフィルターで表示を調整してください')


CLASSES = (VAPB_PT_editing_workspace,)

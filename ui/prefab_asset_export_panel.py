"""Panel for the isolated imported-Prefab asset export operator."""

import bpy

from ..blender.editing_workspace import member_for_object


class VAPB_PT_prefab_asset_export(bpy.types.Panel):
    bl_label = "Prefab\u7d20\u6750Export"
    bl_idname = "VAPB_PT_prefab_asset_export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "VAPB編集"
    bl_parent_id = "VAPB_PT_editing_workspace"

    @classmethod
    def poll(cls, context):
        return (context.mode == "OBJECT" and context.active_object is not None
                and member_for_object(context.scene, context.active_object) is not None)

    def draw(self, context):
        layout = self.layout
        member = member_for_object(context.scene, context.active_object)
        layout.label(text=f"\u5bfe\u8c61: {member.name}", icon="OUTLINER_COLLECTION")
        layout.operator("vapb.export_prefab_assets", text="\u7d20\u6750\u3092\u66f8\u304d\u51fa\u3059", icon="EXPORT")


CLASSES = (VAPB_PT_prefab_asset_export,)

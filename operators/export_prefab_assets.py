"""UI entry point for extracting assets from one imported Prefab member."""

import bpy
from bpy.props import BoolProperty, StringProperty

from ..blender.editing_workspace import member_for_object
from ..export.prefab_assets import export_prefab_assets, partial_export_message


class VAPB_OT_export_prefab_assets(bpy.types.Operator):
    bl_idname = "vapb.export_prefab_assets"
    bl_label = "Prefab\u7d20\u6750\u3092\u66f8\u304d\u51fa\u3059"
    bl_description = "\u8aad\u307f\u8fbc\u307f\u6e08\u307fPrefab 1\u4ef6\u306eUV\u30fb\u5143Texture\u30fbFBX\u3092\u66f8\u304d\u51fa\u3057\u307e\u3059"
    bl_options = {"REGISTER"}

    destination: StringProperty(name="\u4fdd\u5b58\u5148\u30d5\u30a9\u30eb\u30c0\u30fc", subtype="DIR_PATH")
    export_uv: BoolProperty(name="UV\u30ec\u30a4\u30a2\u30a6\u30c8\uff08PNG + SVG\uff09", default=True)
    export_textures: BoolProperty(name="\u5143Texture", default=True)
    export_fbx: BoolProperty(name="FBX", default=True)
    target_name: StringProperty(options={"HIDDEN"})
    target_member_id: StringProperty(options={"HIDDEN"})
    target_root_id: StringProperty(options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return (context.mode == "OBJECT" and context.active_object is not None
                and member_for_object(context.scene, context.active_object) is not None)

    def invoke(self, context, event):
        self.destination = bpy.path.abspath("//")
        member = member_for_object(context.scene, context.active_object)
        self.target_name = member.name if member else ""
        self.target_member_id = str(member.get("unity_composition_member_id", "")) if member else ""
        self.target_root_id = str(member.get("_vapb_workspace_root_context_id", "")) if member else ""
        return context.window_manager.invoke_props_dialog(self, width=480)

    def draw(self, context):
        layout = self.layout
        layout.label(text=f"\u5bfe\u8c61Prefab: {self.target_name}", icon="OUTLINER_COLLECTION")
        layout.prop(self, "destination")
        layout.label(text="既存の保存先に、新しい出力フォルダーを作ります", icon="INFO")
        layout.separator()
        layout.prop(self, "export_uv")
        layout.prop(self, "export_textures")
        layout.prop(self, "export_fbx")
        enabled = self.export_uv or self.export_textures or self.export_fbx
        layout.operator_context = "EXEC_DEFAULT"
        if not enabled:
            layout.label(text="\u5c11\u306a\u304f\u3068\u30821\u7a2e\u985e\u306e\u51fa\u529b\u3092\u9078\u629e\u3057\u3066\u304f\u3060\u3055\u3044", icon="ERROR")
        else:
            layout.label(text="\u65e2\u5b58\u30d5\u30a9\u30eb\u30c0\u30fc\u306f\u4e0a\u66f8\u304d\u3057\u307e\u305b\u3093", icon="INFO")

    def execute(self, context):
        member = member_for_object(context.scene, context.active_object)
        if member is None:
            self.report({"ERROR"}, "\u8aad\u307f\u8fbc\u307f\u6e08\u307fPrefab\u306b\u5c5e\u3059\u308b\u30aa\u30d6\u30b8\u30a7\u30af\u30c8\u3092\u9078\u629e\u3057\u3066\u304f\u3060\u3055\u3044")
            return {"CANCELLED"}
        if (str(member.get("unity_composition_member_id", "")) != self.target_member_id
                or str(member.get("_vapb_workspace_root_context_id", "")) != self.target_root_id):
            self.report({"ERROR"}, "\u5bfe\u8c61Prefab\u304c\u5909\u308f\u308a\u307e\u3057\u305f\u3002\u5bfe\u8c61\u3092\u9078\u3073\u76f4\u3057\u3066\u5b9f\u884c\u3057\u3066\u304f\u3060\u3055\u3044")
            return {"CANCELLED"}
        if not (self.export_uv or self.export_textures or self.export_fbx):
            self.report({"ERROR"}, "\u5c11\u306a\u304f\u3068\u30821\u7a2e\u985e\u306e\u51fa\u529b\u3092\u9078\u629e\u3057\u3066\u304f\u3060\u3055\u3044")
            return {"CANCELLED"}
        try:
            path, manifest = export_prefab_assets(
                context, member, self.destination,
                uv=self.export_uv, textures=self.export_textures, fbx=self.export_fbx,
            )
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            self.report({"ERROR"}, f"Prefab\u7d20\u6750\u306e\u66f8\u304d\u51fa\u3057\u306b\u5931\u6557\u3057\u307e\u3057\u305f: {exc}")
            return {"CANCELLED"}
        if manifest["status"] == "COMPLETE":
            self.report({"INFO"}, f"{member.name}: 書き出しました ({path})")
        else:
            self.report({"WARNING"}, partial_export_message(member.name, path, manifest))
        return {"FINISHED"}


CLASSES = (VAPB_OT_export_prefab_assets,)

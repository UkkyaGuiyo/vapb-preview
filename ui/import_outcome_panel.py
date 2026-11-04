"""Persistent Blender view of existing import projection and dependency state."""

from __future__ import annotations

from collections import Counter

import bpy

from ..blender.import_outcome import scene_import_outcome
from ..blender.dependency_resolver import resolve_after_import

_CATEGORY_LABELS = {
    "UNRESOLVED_IDENTITY": "Mesh対応未解決",
    "MISSING_DEPENDENCY": "未解決の素材参照",
    "AMBIGUOUS": "候補が複数",
    "UNSUPPORTED": "未対応",
    "ERROR": "エラー",
    "PARTIAL": "一部未確認",
}


def _label_lines(layout, value, *, icon="NONE"):
    # Blender labels do not wrap. Keep every line short in the narrow N panel.
    remaining = value
    first = True
    while remaining:
        end = min(17, len(remaining))
        if end < len(remaining) and remaining[end - 1].isascii() and remaining[end - 1].isalnum() and remaining[end].isascii() and remaining[end].isalnum():
            word_start = end - 1
            while word_start > 0 and remaining[word_start - 1].isascii() and remaining[word_start - 1].isalnum():
                word_start -= 1
            if word_start >= 7:
                end = word_start
        layout.label(text=remaining[:end], icon=icon if first else "NONE")
        remaining = remaining[end:]
        first = False


class VAPB_OT_resolve_import_dependencies(bpy.types.Operator):
    bl_idname = "vapb.resolve_import_dependencies"
    bl_label = "Scene内の依存を再解決"
    bl_description = "読み込み済みの素材と元の参照を照合します。ファイル探索や編集済み素材の上書きは行いません"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        resolve_after_import(context.scene)
        outcome = scene_import_outcome(context.scene)
        if outcome["overall"] == "SUCCESS":
            self.report({"INFO"}, "素材の照合を更新しました。形状やUnity復帰の検証は別です")
        else:
            self.report({"WARNING"}, "照合を更新しました。未解決・未確認の項目はImport結果に残しています")
        return {"FINISHED"}


class VAPB_PT_import_outcome(bpy.types.Panel):
    bl_label = "Import結果"
    bl_idname = "VAPB_PT_import_outcome"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "VAPB編集"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        outcome = scene_import_outcome(context.scene)
        counts = outcome["counts"]
        if outcome["overall"] == "UNVERIFIED":
            layout.label(text="このSceneにImport判定記録はありません")
            return
        actions = layout.column(align=True)
        actions.operator_context = "INVOKE_DEFAULT"
        actions.operator("import_scene.unitypackage", text="UnityPackageを追加...")
        _label_lines(actions, "同じPackageから別のPrefabも選んで追加できます")
        actions.operator("vapb.resolve_import_dependencies")
        if outcome["overall"] == "SUCCESS":
            _label_lines(layout, "記録されたMaterialと参照の未解決項目はありません", icon="CHECKMARK")
            _label_lines(layout, "形状・Skin・Exportは別判定です")
            return

        layout.label(text="一部の復元を保留しました", icon="ERROR")
        for category, label in _CATEGORY_LABELS.items():
            if counts[category]:
                layout.label(text=f"{label}: {counts[category]}件")
        header, details = layout.panel("vapb_import_outcome_details", default_closed=True)
        header.label(text="保留理由と対処方法")
        if details is None:
            return
        layout = details
        layout.label(text="未証明の対応を推測していません")
        layout.label(text="白い見た目だけでは原因を判断しません")
        layout.label(text=f"結合済みMaterial依存: {counts['RESOLVED']}件")
        _label_lines(layout, "件数は証拠記録数です（Mesh数ではありません）")
        groups = Counter((item["category"], item["scope"], item["reason"], item["action"])
                         for item in outcome["items"])
        for (category, scope, reason, action), count in groups.items():
            box = layout.box()
            box.label(text=f"{_CATEGORY_LABELS[category]}: {count}件")
            _label_lines(box, f"範囲: {scope}")
            _label_lines(box, f"理由: {reason}")
            _label_lines(box, f"次: {action}")
            if category == "UNRESOLVED_IDENTITY":
                _label_lines(box, "対象Objectは証拠だけでは特定できません")
        if counts["UNRESOLVED_IDENTITY"]:
            layout.label(text="通常ImportにはUnityは不要です")
            layout.label(text="witness作成は現在開発者向けです")


CLASSES = (VAPB_OT_resolve_import_dependencies, VAPB_PT_import_outcome)

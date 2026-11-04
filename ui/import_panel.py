"""Shared UI helpers for the import operator."""


def draw_import_options(layout, operator) -> None:
    layout.prop(operator, "import_mode")
    if operator.import_mode == "RECONSTRUCT":
        layout.label(text="複数のPrefabは、解析後に選べます")
    layout.label(text="原本は一時展開先とは別に保管します")
    layout.prop(operator, "show_import_details")
    if not operator.show_import_details:
        return
    options = layout.box()
    options.label(text="読み込むデータ")
    options.prop(operator, "use_armatures")
    options.prop(operator, "use_bone_weights")
    options.prop(operator, "use_shape_keys")
    options.prop(operator, "use_materials")
    options.prop(operator, "use_textures")
    options.prop(operator, "apply_prefab_transforms")
    options.prop(operator, "keep_extracted")
    options.prop(operator, "source_storage_directory")
    options.prop(operator, "model_witness_path")

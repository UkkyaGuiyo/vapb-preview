"""Scoped extraction of UV layouts, original Textures and one imported Prefab FBX."""

from __future__ import annotations

import hashlib
import json
import math
import re
from array import array
from pathlib import Path


def partial_export_message(member_name, path, manifest):
    """Explain independent output issues without calling references missing files."""
    missing = manifest["missing"]
    message = f"{member_name}: 一部出力 ({path})。未解決項目 {len(missing)} 件。"
    no_uv = sum(item.get("status") == "NO_UV_MAPS" for item in missing)
    if no_uv:
        message += (f" UVマップのないMesh {no_uv} 個のUV画像は出力していません。"
                    "必要な場合はBlenderでUVマップを作成して再出力してください。")
    unproven = sum(item.get("status") == "CURRENT_MATERIAL_SOURCE_UNPROVEN" for item in missing)
    if unproven:
        message += (f" 元Texture: 対応未確認のMaterialスロット {unproven} 件。"
                    "素材ファイルの有無は未判定です。元Prefabとの対応を確認してください。")
    unresolved_textures = sum(item.get("status") == "MISSING_OR_AMBIGUOUS_TEXTURE" for item in missing)
    if unresolved_textures:
        message += (f" 元Texture: 未解決の参照 {unresolved_textures} 件。"
                    "素材Packageや参照先を確認し、再解決後に再出力してください。")
    empty_png = sum(item.get("status") == "UV_PNG_EMPTY_WITH_SOURCE_CORNER" for item in missing)
    if empty_png:
        message += (f" UV座標があるのに透明なPNG {empty_png} 枚。"
                    "微小なUVは画像に描画されない場合があります。保持したSVGで座標を確認してください。")
    fbx = manifest["outputs"].get("fbx", {})
    if fbx.get("status") == "FAILED":
        message += f" FBXは未出力: {fbx['reason']}。"
    return message + " 詳細は保存先のmanifest.jsonに記録しました。"


def selected_member_objects(member, scene):
    """Return objects uniquely owned by this Scene member plus proven dependencies."""
    member_id = str(member.get("unity_composition_member_id", ""))
    root_id = str(member.get("_vapb_root_context_id", member.get("_vapb_workspace_root_context_id", "")))
    if not member_id or not root_id:
        raise ValueError("Prefab member/root identity is unavailable")
    scene_members = [collection for collection in scene.collection.children_recursive
                     if collection.get("unity_composition_member_id")]
    if sum(collection == member for collection in scene_members) != 1:
        raise ValueError("Prefab member is not uniquely present in the current Scene")
    if any(collection != member and collection.get("unity_composition_member_id") == member_id
           and collection.get("_vapb_root_context_id", collection.get("_vapb_workspace_root_context_id", "")) == root_id
           for collection in scene_members):
        raise ValueError("Prefab member identity is duplicated in the current Scene")
    members = {obj for obj in member.all_objects}
    if not members:
        raise ValueError("Prefab has no member objects")
    def validate_ownership(obj, *, closure=False):
        object_member = str(obj.get("unity_composition_member_id", ""))
        object_roots = {str(obj.get(key, "")) for key in
                        ("_vapb_root_context_id", "_vapb_workspace_root_context_id") if obj.get(key, "")}
        if object_member and object_member != member_id:
            raise ValueError("Prefab contains an object with another member identity")
        if object_roots and object_roots != {root_id}:
            raise ValueError("Prefab contains an object with a conflicting root identity")
        owners = [collection for collection in scene_members
                  if any(candidate == obj for candidate in collection.all_objects)]
        if any(collection != member for collection in owners):
            raise ValueError("Prefab object is shared with or owned by another member")
        if not closure and not owners:
            raise ValueError("Prefab object has no current Scene member ownership")
        return owners
    for obj in members:
        validate_ownership(obj)
    result = set(members)
    queue = list(members)
    while queue:
        obj = queue.pop()
        refs = ([obj.parent] if obj.parent is not None else [])
        refs.extend(mod.object for mod in obj.modifiers
                    if mod.type == "ARMATURE" and mod.object is not None)
        for ref in refs:
            if ref in result:
                continue
            # A direct relationship proves dependency, but a different imported
            # Prefab identity makes the closure ambiguous and unsafe to export.
            validate_ownership(ref, closure=True)
            result.add(ref)
            queue.append(ref)
    return tuple(sorted(result, key=lambda item: (item.name, item.as_pointer())))


def _safe_stem(value):
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return stem[:80] or "Prefab"


def uv_polygons(mesh, layer):
    return tuple(tuple(tuple(layer.data[loop].uv) for loop in poly.loop_indices)
                 for poly in mesh.polygons)


_MAX_SIGNED_UV_TILES = 64


def _blender_uv_tiles(polygons):
    signed = any(u < 0 or v < 0 for poly in polygons for u, v in poly)
    tiles = set()
    for poly in polygons:
        polygon_tiles = set()
        for u, v in poly:
            x, y = math.floor(u), math.floor(v)
            if not signed and x > 0 and u < x + 1e-6:
                x -= 1
            if not signed and y > 0 and v < y + 1e-6:
                y -= 1
            polygon_tiles.add((x, y))
        if poly:
            min_x = min(x for x, _ in polygon_tiles)
            max_x = max(x for x, _ in polygon_tiles)
            min_y = min(y for _, y in polygon_tiles)
            max_y = max(y for _, y in polygon_tiles)
            bounds_count = (max_x - min_x + 1) * (max_y - min_y + 1)
            if signed:
                # Renderers draw complete faces into each tile viewport. Cover
                # intermediate tiles too, but refuse excessive work before output.
                if bounds_count > _MAX_SIGNED_UV_TILES:
                    raise ValueError("UV画像は1マップ64タイルまでです。このマップは出力していません")
                tiles.update((x, y) for x in range(min_x, max_x + 1)
                             for y in range(min_y, max_y + 1))
                if len(tiles) > _MAX_SIGNED_UV_TILES:
                    raise ValueError("UV画像は1マップ64タイルまでです。このマップは出力していません")
                continue
            # Blender emits tiles containing UV corners, not clipped polygon
            # fragments. Refuse if the polygon bounds cross an unlisted tile;
            # polygon clipping is outside this focused exporter.
            if bounds_count > len(polygon_tiles):
                raise ValueError("UV polygon crosses tiles Blender's layout exporter would omit")
            tiles.update(polygon_tiles)
    return tiles or {(0, 0)}


def _png_has_visible_alpha(path, bpy):
    """Inspect the generated file without reusing or changing a working Image."""
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        width, height = image.size
        if width <= 0 or height <= 0 or image.channels != 4:
            raise RuntimeError("UV PNG could not be decoded as an RGBA image")
        pixels = array("f", [0.0]) * (width * height * 4)
        image.pixels.foreach_get(pixels)
        return any(pixels[i] > 0 for i in range(3, len(pixels), 4))
    finally:
        bpy.data.images.remove(image)


def write_uv_layout(context, obj, layer_index, directory: Path, stem: str, *, bpy_module=None):
    """Draw original UV coordinates with Blender's layout exporters."""
    if bpy_module is None:
        import bpy as bpy_module
    mesh = obj.data
    layer = mesh.uv_layers[layer_index]
    polygons = uv_polygons(mesh, layer)
    for poly in polygons:
        if any(not math.isfinite(c) for uv in poly for c in uv):
            raise ValueError("UV map contains non-finite coordinates")
    coords = [uv for poly in polygons for uv in poly]
    tiles = _blender_uv_tiles(polygons)
    negative = any(u < 0 or v < 0 for u, v in coords)
    needs_tiles = negative or any(u > 1 or v > 1 for u, v in coords)
    if negative:
        # The standard operator discards negative tiles. Its renderers accept
        # signed viewport origins directly, without translating stored UVs.
        try:
            from io_mesh_uv_layout import ExportUVLayout, export_uv_png, export_uv_svg
            renderers = {"PNG": export_uv_png.export, "SVG": export_uv_svg.export}
            color_for = ExportUVLayout.get_polygon_color
            if not all(callable(fn) for fn in (*renderers.values(), color_for)):
                raise AttributeError("UV renderer contract unavailable")
        except (ImportError, AttributeError) as exc:
            raise RuntimeError("Blender signed-tile UV layout exporters are unavailable") from exc
        faces = [(uvs, color_for(mesh, poly)) for uvs, poly in zip(polygons, mesh.polygons)]
        colors = {color for _, color in faces}
    copy = None if negative else mesh.copy()
    old_data = obj.data
    try:
        if copy is not None:
            obj.data = copy
            copy.uv_layers.active_index = layer_index
        outputs = []
        for mode, extension in (("PNG", ".png"), ("SVG", ".svg")):
            base = directory / (stem + extension)
            if negative:
                for u, v in sorted(tiles):
                    path = directory / (stem + f".u{u + 1}_v{v + 1}" + extension)
                    renderers[mode](str(path), (u, v), faces, colors, 1024, 1024, 0.25)
            else:
                with context.temp_override(
                    active_object=obj, object=obj, selected_objects=[obj],
                    selected_editable_objects=[obj]):
                    result = bpy_module.ops.uv.export_layout(
                        filepath=str(base), export_all=True,
                        export_tiles="UV" if needs_tiles else "NONE",
                        modified=False, mode=mode, size=(1024, 1024), opacity=0.25,
                        check_existing=False,
                    )
                if result != {"FINISHED"}:
                    raise RuntimeError(f"Blender UV {mode} export was cancelled")
            expected = [stem + f".u{u + 1}_v{v + 1}" + extension for u, v in sorted(tiles)] if needs_tiles else [stem + extension]
            actual = {path.name for path in directory.glob(stem + "*" + extension)
                      if path.name == stem + extension
                       or re.fullmatch(re.escape(stem) + r"\.u-?\d+_v-?\d+" + re.escape(extension), path.name)}
            if actual != set(expected):
                raise RuntimeError(f"Blender UV tile output mismatch: expected {sorted(expected)}, found {sorted(actual)}")
            for name in expected:
                if name not in outputs:
                    outputs.append(name)
        pngs = [name for name in outputs if name.endswith(".png")]
        svgs = [name for name in outputs if name.endswith(".svg")]
        if not pngs or not svgs:
            raise RuntimeError("Blender UV exporter produced incomplete PNG/SVG output")
        tile_files = []
        for tile in sorted(tiles):
            suffix = f".u{tile[0] + 1}_v{tile[1] + 1}" if needs_tiles else ""
            tile_files.append({"tile": list(tile),
                               "png": stem + suffix + ".png",
                               "svg": stem + suffix + ".svg"})
        interior_tiles = set()
        for u, v in coords:
            x, y = math.floor(u), math.floor(v)
            if x < u < x + 1 and y < v < y + 1:
                interior_tiles.add((x, y))
        # This detects wholly empty rasters with source corners, not fidelity of
        # individual islands or polygons crossing tiles without an interior corner.
        issues = [{"status": "UV_PNG_EMPTY_WITH_SOURCE_CORNER",
                   "tile": tile["tile"], "png": tile["png"]}
                  for tile in tile_files if tuple(tile["tile"]) in interior_tiles
                  and not _png_has_visible_alpha(directory / tile["png"], bpy_module)]
        return {"png": pngs, "svg": svgs, "tiles": tile_files, "issues": issues,
                "tile_mode": "UV" if needs_tiles else "NONE"}
    finally:
        if copy is not None:
            obj.data = old_data
            if copy.users == 0:
                bpy_module.data.meshes.remove(copy)


def _texture_exports(scene, objects, texture_dir):
    from .final_state_package import _material_data, _resolve_source_asset, _source_assets
    packages = {}
    references, missing = [], []
    for obj in objects:
        if obj.type != "MESH":
            continue
        raw_by_slot = {}
        raw_records = []
        try:
            bindings = json.loads(str(obj.get("_vapb_renderer_bindings", "{}")))
            member_id = str(obj.get("unity_composition_member_id", ""))
            for renderer in bindings.get("renderers", []):
                if renderer.get("member_id") != member_id or not renderer.get("renderer_file_id"):
                    continue
                semantic_id = str(obj.get("_vapb_semantic_id", ""))
                if (semantic_id and renderer.get("game_object_semantic_id")
                        and renderer.get("game_object_semantic_id") != semantic_id):
                    continue
                raw_records.append(renderer)
                for raw in renderer.get("material_slots", []):
                    slot_index = raw.get("slot")
                    guid = str(raw.get("effective_material_guid", "")).lower()
                    file_id = str(raw.get("effective_material_file_id", ""))
                    if isinstance(slot_index, int) and slot_index >= 0:
                        raw_by_slot.setdefault(slot_index, []).append({
                            "guid": guid, "file_id": file_id,
                            "renderer_file_id": str(renderer.get("renderer_file_id", "")),
                            "renderer_source_kind": renderer.get("renderer_source_kind", ""),
                        })
        except (TypeError, ValueError, AttributeError):
            pass
        slot_count = max(len(obj.material_slots), max(raw_by_slot, default=-1) + 1)
        for slot_index in range(slot_count):
            mat = obj.material_slots[slot_index].material if slot_index < len(obj.material_slots) else None
            current_guid = str(mat.get("unity_material_guid", "")).lower() if mat else ""
            current_file_id = str(mat.get("unity_material_file_id", "")) if mat else ""
            current_package = str(mat.get("unity_source_package_id", "")) if mat else ""
            has_current_identity = bool(current_guid or current_file_id or current_package)
            raw_items = raw_by_slot.get(slot_index, [])
            raw_keys = {(item["guid"], item["file_id"]) for item in raw_items if item["guid"] and item["file_id"]}
            if len(raw_keys) > 1:
                missing.append({"mesh": obj.name, "slot": slot_index,
                                "status": "CONFLICTING_RAW_RENDERER_MATERIAL_REFERENCES",
                                "references": sorted([{"guid": g, "file_id": f} for g, f in raw_keys], key=lambda x: (x["guid"], x["file_id"]))})
            if mat is not None and not has_current_identity:
                missing.append({"mesh": obj.name, "slot": slot_index,
                                "material": mat.name,
                                "status": "CURRENT_MATERIAL_SOURCE_UNPROVEN"})
                continue
            if has_current_identity:
                if not (current_guid and current_file_id and current_package):
                    missing.append({"mesh": obj.name, "slot": slot_index,
                                    "status": "CURRENT_MATERIAL_IDENTITY_INCOMPLETE"})
                    continue
                guid, file_id, package_id, renderer_ids = current_guid, current_file_id, current_package, []
                source_kind = "CURRENT_MATERIAL"
            elif len(raw_keys) == 1 and raw_items:
                guid, file_id = next(iter(raw_keys))
                package_id = str(obj.get("unity_source_package_id", ""))
                renderer_ids = sorted({item["renderer_file_id"] for item in raw_items if item["guid"] == guid and item["file_id"] == file_id})
                source_kind = "RAW_RENDERER_FALLBACK"
            elif len(raw_keys) > 1:
                continue
            else:
                missing.append({"mesh": obj.name, "slot": slot_index, "status": "MATERIAL_SOURCE_UNRESOLVED"})
                continue
            if not package_id or not guid or not file_id:
                missing.append({"mesh": obj.name, "slot": slot_index,
                                "material": getattr(mat, "name", None), "renderer_file_ids": renderer_ids,
                                "status": "SOURCE_MATERIAL_IDENTITY_MISSING"})
                continue
            manifest_material = {"mesh": obj.name, "slot": slot_index,
                                 "current": {"guid": current_guid, "file_id": current_file_id,
                                             "provider": current_package, "name": getattr(mat, "name", None)},
                                 "raw_renderer": raw_items, "selected_source": source_kind,
                                 "material_guid": guid, "material_file_id": file_id,
                                 "renderer_file_ids": renderer_ids}
            try:
                if package_id not in packages:
                    packages[package_id] = _source_assets(scene, package_id)
                material = _resolve_source_asset(scene, package_id, guid, packages)
                material_provider = next((pid for pid, assets in packages.items()
                                          if assets.get(guid) is material), None)
                if (material is None or not material.pathname.lower().endswith(".mat")
                        or not re.search(rb"(?m)^---\s+!u!21\s+&" + re.escape(file_id.encode()) + rb"\b", material.asset_bytes)):
                    raise ValueError("source Material bytes unavailable")
                if material_provider is None:
                    raise ValueError("Material provider identity is unavailable")
                parsed = _material_data(material.asset_bytes)
            except (OSError, ValueError, KeyError) as exc:
                manifest_material.update(status="SOURCE_MATERIAL_UNRESOLVED", reason=str(exc))
                references.append(manifest_material)
                missing.append({"mesh": obj.name, "slot": slot_index, "material_guid": guid,
                                "renderer_file_id": file_id, "status": "SOURCE_MATERIAL_UNRESOLVED", "reason": str(exc)})
                continue
            manifest_material.update(status="RESOLVED", provider=material_provider,
                                     pathname=material.pathname)
            references.append(manifest_material)
            for prop, ref in parsed.textures.items():
                entry = {"mesh": obj.name, "slot": slot_index, "material_guid": guid,
                         "material_file_id": file_id, "renderer_file_ids": renderer_ids,
                         "property": prop, "guid": ref.guid, "file_id": str(ref.file_id),
                         "provider": material_provider, "renderer_package": package_id}
                if not ref.guid or ref.file_id == 0:
                    entry["status"] = "NULL_REFERENCE"
                    references.append(entry)
                    continue
                try:
                    tex = _resolve_source_asset(scene, material_provider, ref.guid, packages)
                    if tex is None:
                        raise ValueError("provider unresolved")
                    if (ref.file_id != 2800000
                            or not re.search(rb"(?m)^TextureImporter:\s*$", tex.meta_bytes)):
                        raise ValueError("source reference is not a supported Texture2D asset")
                    # Resolve provider by exact package archive asset identity.
                    provider = next((pid for pid, assets in packages.items()
                                     if assets.get(tex.guid) is tex), None)
                    if provider is None:
                        raise ValueError("Texture provider identity unavailable")
                    suffix = Path(tex.pathname).suffix or ".bin"
                    name = _safe_stem(Path(tex.pathname).stem)[:40]
                    key = (provider, tex.guid)
                    provider_tag = hashlib.sha256(provider.encode("utf-8")).hexdigest()
                    disk = texture_dir / f"{name}_{tex.guid}_{provider_tag}{suffix}"
                    prior = next((x for x in references if x.get("_key") == key), None)
                    if prior:
                        if prior["sha256"] != hashlib.sha256(tex.asset_bytes).hexdigest():
                            raise ValueError("same GUID has differing source bytes")
                        entry.update(file=prior["file"], sha256=prior["sha256"], status="EXPORTED_SHARED")
                    else:
                        entry.update(file=disk.name, sha256=hashlib.sha256(tex.asset_bytes).hexdigest(), status="EXPORTED")
                        try:
                            with disk.open("xb") as stream:
                                stream.write(tex.asset_bytes)
                        except FileExistsError as collision:
                            raise ValueError("Texture output filename collision; existing file preserved") from collision
                    entry.update(provider=provider, pathname=tex.pathname, source="RAW_UNITYPACKAGE")
                    entry["_key"] = key
                except (OSError, ValueError, KeyError, StopIteration) as exc:
                    entry["status"] = "MISSING_OR_AMBIGUOUS"
                    entry["reason"] = str(exc)
                    missing.append({"mesh": obj.name, "slot": slot_index, "material_guid": guid,
                                    "property": prop, "texture_guid": ref.guid,
                                    "status": "MISSING_OR_AMBIGUOUS_TEXTURE", "reason": str(exc)})
                references.append(entry)
    for item in references:
        item.pop("_key", None)
    return references, missing


def _export_fbx_with_slots(context, objects, output, *, bpy_module):
    """Retain repeated slots on disposable copies, including unused occurrences."""
    from .fbx_export import FBX_EXPORT_PRESET
    from .triangle_staging import triangle_export_scene
    for obj in objects:
        if obj.type == "MESH":
            for modifier in obj.modifiers:
                if modifier.type != "ARMATURE" and (modifier.show_viewport or modifier.show_render):
                    raise ValueError(
                        f"{obj.name}: モディファイア「{modifier.name}」をFBXに反映できません。"
                        "元データを残した作業コピーで形状を確定してから再出力してください。"
                        "UV・元テクスチャは個別に出力できます")
    carriers, slot_map = [], []
    try:
        with triangle_export_scene(context, objects, bpy_module=bpy_module) as (_, copies):
            for source, copy in zip(objects, copies):
                if source.type != "MESH":
                    continue
                triangles = {}
                for face in copy.data.polygons:
                    key = tuple(sorted(face.vertices))
                    if key in triangles:
                        raise ValueError(
                            f"{source.name}: 頂点を共有する重複面（{triangles[key]}, {face.index}）があり、"
                            "BlenderへのFBX再読込で面が失われます。重複面を確認してください。"
                            "UV・元Textureは個別に出力できます")
                    triangles[key] = face.index
                seen = set()
                for index, slot in enumerate(copy.material_slots):
                    material = slot.material
                    if material is None:
                        raise ValueError("FBX cannot preserve an empty Material slot; UV and Texture outputs remain available")
                    pointer = material.as_pointer()
                    if pointer in seen:
                        carrier = material.copy()
                        carriers.append(carrier)
                        carrier.name = f"{material.name}_slot_{index}"
                        slot.material = carrier
                    seen.add(pointer)
                    slot_map.append({"mesh": source.name, "slot": index,
                                     "source_material": material.name,
                                     "fbx_material": slot.material.name})
            options = dict(FBX_EXPORT_PRESET, filepath=str(output), use_selection=True)
            if bpy_module.ops.export_scene.fbx(**options) != {"FINISHED"}:
                raise RuntimeError("FBX export was cancelled")
    finally:
        for carrier in carriers:
            if carrier.users == 0:
                bpy_module.data.materials.remove(carrier)
    return slot_map


def export_prefab_assets(context, member, destination, *, uv=True, textures=True, fbx=True):
    """Write requested data to a new directory; all changes are disposable copies."""
    if not any((uv, textures, fbx)):
        raise ValueError("Select at least one output")
    import bpy
    parent = Path(destination).expanduser().resolve()
    if not parent.is_dir():
        raise ValueError("保存先フォルダーが見つかりません。作成するか、既存のフォルダーを選んでください。")
    objects = selected_member_objects(member, context.scene)
    meshes = [obj for obj in objects if obj.type == "MESH"]
    if not meshes:
        raise ValueError("選択したPrefabには出力対象のMeshがありません。Meshを含むPrefabを選び直してください。")
    target = parent / (_safe_stem(member.name) + "_assets")
    if target.exists():
        raise FileExistsError(f"output folder already exists: {target.name}")
    staging = parent / ("." + target.name + ".tmp")
    if staging.exists():
        raise FileExistsError("temporary output path already exists")
    staging.mkdir()
    manifest = {"schema": "vapb-prefab-assets-1", "root_context_id": member.get("_vapb_root_context_id", member.get("_vapb_workspace_root_context_id", "")),
                "package_id": member.get("unity_source_package_id", context.scene.get("unitypackage_source_package_id", "")),
                "member_id": member.get("unity_composition_member_id"),
                "member_name": member.name, "outputs": {"uv": bool(uv), "textures": bool(textures), "fbx": {"requested": bool(fbx), "status": "NOT_REQUESTED"}},
                "meshes": [], "textures": [], "missing": []}
    try:
        for mesh_index, obj in enumerate(meshes):
            record = {"object": obj.name, "source_mesh": obj.data.name, "uv_layers": []}
            record["identity"] = {key: obj.get(key, "") for key in (
                "unity_source_package_id", "unity_source_prefab_guid", "unity_prefab_file_id",
                "_vapb_fbx_source_asset_guid", "_vapb_fbx_model_uid", "_vapb_fbx_geometry_uid",
                "unity_guid", "unity_asset_path")}
            try:
                binding_payload = json.loads(str(obj.get("_vapb_renderer_bindings", "{}")))
                member_id = str(obj.get("unity_composition_member_id", ""))
                record["raw_renderer_materials"] = [
                    {"renderer_file_id": r.get("renderer_file_id"), "renderer_source_kind": r.get("renderer_source_kind"),
                     "mesh_guid": r.get("mesh_guid"), "slot": s.get("slot"),
                     "material_guid": s.get("effective_material_guid"),
                     "material_file_id": s.get("effective_material_file_id")}
                    for r in binding_payload.get("renderers", []) if r.get("member_id") == member_id
                    for s in r.get("material_slots", [])]
            except (TypeError, ValueError, AttributeError):
                record["raw_renderer_materials"] = []
            record["polygon_material_slots"] = [{"polygon": p.index, "material_index": p.material_index,
                                                   "slot": p.material_index}
                                                  for p in obj.data.polygons]
            record["slots"] = [{"index": i, "material": slot.material.name if slot.material else None,
                                "guid": slot.material.get("unity_material_guid") if slot.material else None,
                                "file_id": slot.material.get("unity_material_file_id") if slot.material else None,
                                "provider": slot.material.get("unity_source_package_id") if slot.material else None}
                               for i, slot in enumerate(obj.material_slots)]
            manifest["meshes"].append(record)
        if uv:
            folder = staging / "UV"
            folder.mkdir()
            for mesh_index, obj in enumerate(meshes):
                record = manifest["meshes"][mesh_index]
                if not obj.data.uv_layers:
                    manifest["missing"].append({"mesh": obj.name, "kind": "UV", "status": "NO_UV_MAPS"})
                for i, layer in enumerate(obj.data.uv_layers):
                    stem = f"mesh_{mesh_index}_{_safe_stem(obj.name)}_uv_{i}_{_safe_stem(layer.name)}"
                    try:
                        files = write_uv_layout(context, obj, i, folder, stem, bpy_module=bpy)
                    except (OSError, RuntimeError, ValueError) as exc:
                        # UV is an independent selection; report this map as
                        # unsupported while continuing Texture/FBX output.
                        for path in folder.glob(stem + "*"):
                            if path.is_file():
                                path.unlink()
                        manifest["missing"].append({"mesh": obj.name, "kind": "UV",
                                                    "layer": layer.name,
                                                    "status": "UV_EXPORT_UNSUPPORTED",
                                                    "reason": str(exc)})
                        continue
                    for issue in files.pop("issues", []):
                        manifest["missing"].append({**issue, "kind": "UV", "mesh": obj.name,
                                                    "layer": layer.name, "png": "UV/" + issue["png"]})
                    files.update({"name": layer.name,
                                  "png": ["UV/" + name for name in files["png"]],
                                  "svg": ["UV/" + name for name in files["svg"]],
                                  "tiles": [{**tile, "png": "UV/" + tile["png"],
                                             "svg": "UV/" + tile["svg"]}
                                            for tile in files["tiles"]],
                                  "polygons": len(obj.data.polygons)})
                    record["uv_layers"].append(files)
        if textures:
            folder = staging / "Textures"
            folder.mkdir()
            manifest["textures"], unresolved = _texture_exports(context.scene, objects, folder)
            manifest["missing"].extend(unresolved)
        if fbx:
            folder = staging / "FBX"
            folder.mkdir()
            fbx_path = folder / (_safe_stem(member.name) + ".fbx")
            try:
                slot_map = _export_fbx_with_slots(context, objects, fbx_path, bpy_module=bpy)
                if not fbx_path.is_file() or fbx_path.stat().st_size == 0:
                    raise RuntimeError("FBX export reported success without a nonempty file")
                manifest["outputs"]["fbx"] = {"requested": True, "status": "EXPORTED",
                                                "file": "FBX/" + fbx_path.name,
                                                "material_slots": slot_map,
                                                "limitations": ["Existing VAPB FBX preset; no Unity/VRC component serialization"]}
            except Exception as exc:
                # Do not publish a file left incomplete by a failed writer.
                # Failure to remove it aborts publication through outer cleanup.
                fbx_path.unlink(missing_ok=True)
                manifest["outputs"]["fbx"] = {"requested": True, "status": "FAILED", "reason": str(exc)}
                manifest["missing"].append({"kind": "FBX", "status": "FBX_EXPORT_FAILED", "reason": str(exc)})
        manifest["status"] = "PARTIAL" if manifest["missing"] or manifest["outputs"]["fbx"].get("status") == "FAILED" else "COMPLETE"
        (staging / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        staging.rename(target)
    except Exception:
        # The staging directory is exclusively ours and target is never replaced.
        import shutil
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return target, manifest

# Current Alpha snapshot: 14ef77e

This is a bounded Development Preview, not whole-product acceptance.

- Public source: `14ef77e5b756a8f202f1faad4717c41d7476fd19` in this independent history.
- Selected development source: `1d6b8a454c8371dabefd022fe650fc2f64df4a6d`; its history and private data are not included.
- ZIP: `VAPB-alpha-14ef77e.zip`, 424,045 bytes, 119 files including eight first-party Unity helpers.
- SHA-256: `02fe16fcead943022b75f49fb558f10f08986d10c3413cf88e927e42943caff4`.
- Tested on Windows / Blender 5.2.3 LTS, 2026-11-05 UTC.

## What this update changes

Japanese partial-export guidance distinguishes unresolved Texture references from
missing files, identifies absent UV maps and source-unproven Material slots, and
reports wholly transparent PNGs for a bounded set of UV conditions. It preserves
SVG coordinates rather than changing UVs. Failed FBX writes leave no incomplete
FBX in the published output folder. Prefab detail display and Material-slot counts
are corrected. Proven helper-only Prefabs avoid an unrelated lone-FBX fallback.
Dependency discovery traverses renderer references in source Prefabs; this does
not prove full Nested Prefab occurrence restoration or remove its refusal gates.

## New ZIP verification

| Boundary | Observed result |
|---|---|
| Source and ZIP | All 119 file bytes equal the fixed public source; CRC passed. All eight helper sources retain complete MIT notices. |
| Installation API | Standard Preferences operators installed, enabled, disabled and re-enabled the exact ZIP. All 119 files matched; Import/UnityPackage Export hooks and asset Export classes registered. This remains separate API evidence. |
| Ordinary GUI installation | A separate operator used Preferences > Add-ons > Install from Disk on this exact ZIP, with automatic enable unchecked, then enabled, disabled and re-enabled it. All 119 installed files matched by SHA-256. Two owned GUI sessions are described below; the second used isolated temporary storage. |
| GUI menus and paths | Import and Export registrations, disappearance while disabled and restoration were observed. Import and Mesh/Skin Export pickers were opened and cancelled without real assets. Disabled-menu disappearance and picker cancellation were checked in the first session; the second repeated installation/checkbox lifecycle and final menus. This is not a real-data GUI round trip. |
| Import | Normal import operators selected one Prefab from a permitted real clothing package. Current selected member scope contained two Meshes and one rig. |
| Asset Export | Native operations wrote two PNG/SVG pairs, two original Texture files, one FBX and the correspondence manifest. Manifest COMPLETE/no missing entries means completion of these requested outputs, not whole-product acceptance. |
| UV | Both PNGs decoded as nonempty 1024x1024 images. Both SVG polygon multisets matched original UVs at Blender's own three-decimal pixel serialization. Individual raster-island fidelity was not established. |
| Texture | Both output files exactly matched GUID-addressed original bytes. Eight Material property references were checked against raw source Material data. |
| Fresh FBX process | Two current Mesh identities matched bijectively; ordered triangle indices, coupled UV/Material-slot order, slots and weights matched. Vertex counts were 553 and 8,209. This sample has no Shape Keys, so it provides no Shape Key preservation proof. |
| FBX residuals | Maximum world-position delta was 1.30385160446167e-7. Bone names and parent relations matched, but rig identity was incomplete, rest-matrix maximum element delta was 5.543231964111328e-6, and rig world matrices differed. These are measured residuals, not an accepted new tolerance or complete deformation/FBX fidelity. |
| UnityPackage Export | Normal operator completed a 31,463,452-byte package. Six included helper sources matched the public source and retained MIT notices. The generated package was not newly applied in Unity. |
| Preservation | Asset Export's captured Scene fingerprint was unchanged. Original/protected package hashes and fresh-reader inputs were checked unchanged. Both owned Blender processes exited normally and returned their leases. |

The new ordinary-GUI installation condition was subsequently completed on the
same ZIP by a separate operator. Previous snapshot GUI results remain scoped to
their earlier ZIPs. The current real-data Import/Export and fresh-FBX results above
remain API evidence; no new real-data GUI round trip is claimed.
No new Unity Apply, VRChat SDK build, VRChat runtime, arbitrary Shader fidelity or
whole-avatar restoration is established. Source/runtime safety refusals remain.

### GUI isolation correction and limits

The first GUI session isolated Blender user directories but inherited shared
temporary storage. On exit, Blender wrote its default `quit.blend` recovery file.
Its prior existence/content had not been captured; preservation or restoration of
that earlier recovery state is UNKNOWN. No guessed restoration or deletion was
attempted. A launch-only unsupported flag also produced a warning; it was removed
before the separately recorded corrected run. Neither event was an add-on install
failure, and neither is hidden by the later success.

The second GUI session used fresh Blender user directories and isolated
TEMP/TMP/TMPDIR, factory startup and disabled auto-execution. Its installation,
enable/disable/re-enable and final Import/Export menus passed. All 119 installed
files matched the fixed ZIP. The five pre-existing user-config files and shared
recovery file matched before/after, including the latter's size and timestamp.
New recovery data was written only inside the second session's isolated Temp.
Minimum two-second-sampled available RAM was 4.72 GiB. The owned process exited
normally and returned its lease/mutex. No original avatar or existing blend was
loaded in either GUI session. The second run proves corrected isolation; it does
not prove restoration of unknown pre-first-run recovery content.

### Known original-Prefab scope boundary

For direct Mesh references the importer can realize a whole referenced FBX inside
the current Blender member. Current member ownership is not proof that every Mesh
belongs to the original Unity Prefab. A later diagnostic found this distinction;
exact original mesh-fileID to FBX modelUID mapping remains unverified. Do not
infer extra or missing Meshes from names or counts. The current ZIP's COMPLETE
asset-export status means requested outputs completed, not original-Prefab scope
or complete Unity/VRChat fidelity. A later development-only reporting correction
is not included in this fixed ZIP. Users should inspect the member's contents.

The independent private campaign has 32 of 165 conditions attempted: zero
whole-case PASS, 25 PARTIAL, five UNVERIFIED, two SAFE_REFUSAL and 133 untested.
The GUI installation checks and repeated distribution example add no new corpus
condition. Raw assets, identifiers, local paths and GUI transcripts are not shipped.

## Publication inspection

The update uses an independent public history and approved GitHub noreply identities.
Primary selected-source checks and a separate adversarial review cover source,
metadata, histories/refs, licenses, ZIP members and test claims. Private originals,
purchased assets, raw logs, paths and identity tables are excluded. The scope of
source licensing is in LICENSES.md. Fresh source/privacy/license inspection and independent adversarial review are
required for this republication; the earlier withdrawn publication decision is
not automatically reused.


## Earlier snapshot records retained

# Current Alpha snapshot: 6317c05

This is a bounded development-preview check, not whole-product acceptance.

- Source commit: `6317c059b1a5da33a2a55a8f642a964533e9bdc6` in this independent public history.
- Selected development commit: `c95a431110602a168f574b59954c006307712335`.
- ZIP: `VAPB-alpha-6317c05.zip`, **422,231 bytes**, 119 files, eight Unity helper sources.
- SHA-256: `da489a18e98237be2041239f654f2d31244e6d6b7457bd74cfcea3df61c3f9c7`.
- Windows / Blender **5.2.3 LTS**, isolated preferences; 2026-11-05 UTC.

## Changes and separate development evidence

Only Import Assistant and Model Skin Finalizer runtime sources changed from the
previous snapshot. All addon Python and other helper sources remain byte-identical.
The update adds bounded direct leaf-renderer translation restoration and Japanese
feedback for refused Apply. It does not enable arbitrary Object/Bone frame edits,
rotation/scale, Shape/Action combinations or general SDK behavior.

The selected development implementation has first-party counterexamples,
independent technical review and a protected real clothing GUI Apply. Sibling,
bone and material state remained unchanged. A separate Unity 2022.3.22f1 process
reopened the saved Variant and confirmed exact GUID/fileID references and position.
That Apply was PARTIAL because a Shader was unavailable. This development evidence
is not a new Unity Apply of the package generated by the ZIP validation below.

## Current ZIP observations

| Boundary | Result and scope |
|---|---|
| Fixed source / ZIP | Clean CRC; all 119 file bytes exactly equal the fixed source commit. All eight helpers contain complete MIT notices. |
| Ordinary GUI installation | Install from Disk, enable, disable and re-enable succeeded. All 119 installed files matched the archive. Import, UnityPackage Export and asset Export registrations checked. |
| Ordinary GUI Import | One of eight Prefabs selected from a permitted real clothing package. The selected clothing and accessory were visible in the viewport and editing panel. No missing-visual-dependency prompt for this case. |
| Ordinary GUI asset Export | All three options selected: two PNG and two SVG UV layouts, two original texture files, one FBX and a correspondence manifest. Manifest: COMPLETE, two Meshes, no missing entries. One generated UV PNG was visually inspected. |
| Original texture check | Both files matched the GUID-addressed original package asset bytes exactly; repeated references shared the same two outputs. |
| Ordinary GUI UnityPackage Export | Mesh / Skin export produced a 33,320,087-byte package. Its six helper sources matched the selected public sources exactly and contained full MIT notices. This generated package has not been newly applied in Unity. |
| Preservation | Scene saved to a new blend file. Original package, protected copy and earlier source blend hashes unchanged. Owned Blender exited normally; lease and mutex returned. |
| Earlier evidence reused | The previous snapshot's fresh-process FBX comparison remains evidence for identical Python implementation. The newly generated FBX was not separately reimported for this update. |

Two operator mistakes were retained in the private record: an initial installation
attempt without a filename failed before installation; selecting the explicit ZIP
succeeded. Asset Export safely rejected a nonexistent destination; after creating
the destination, the same GUI export succeeded. Neither failure was hidden as a pass.

These checks do not establish general avatar compatibility, every output-option
combination, all Blender versions, exact Shader appearance, complete Unity/VRChat
restoration, VRChat SDK build or client runtime acceptance. Preserve originals.
The test assets, generated clothing exports and raw private logs are not distributed.

## Update inspection

Independent source inspection (SOL) and independent adversarial publication audit
(Astra) inspected the selected public source, Git objects/references and identities,
licenses and archive. No concrete privacy/secret/license/history blocker was found
in that bounded inspection. Final documentation, runtime evidence and delivery are
subject to the final audit before public push; this file alone is not proof of push.
All commits use the approved GitHub noreply identity. There is no copied private
Git history or automatic development-to-public synchronization.

The README inside the fixed ZIP is a build-time record. The current
repository documentation adds the subsequent runtime results without changing ZIP bytes.

---

# Previous snapshot: b3f141d

This is a bounded development-preview check, not whole-product acceptance.

- ZIP source: `b3f141d601dc59964332275669b9be72e3bb9b2b` in this independent repository.
- Development source selected: `ca8156bb6e53403c2bc75a07e813cbc10300e7cf`.
- Publication-only changes: documentation and complete MIT notices in five Unity helper headers. Runtime bodies were unchanged.
- Later development change excluded from this snapshot: improved Japanese feedback after a rejected Unity Apply. The rejection safety check is already present here.
- File: `VAPB-alpha-b3f141d.zip`, 419,333 bytes, 119 files, eight Unity helper sources.
- SHA-256: `414173627d984d6a710cf9d9812cd88d6457a88510f2154e29c6443c38fbb5b2`.
- Tested on Windows with Blender **5.2.3 LTS**, using isolated preferences.
- Validation date: 2026-11-04 UTC.

## Observed results

| Boundary | Result and scope |
|---|---|
| ZIP structure and revision | CRC and all 119 packaged files checked against the fixed source commit; no mixed revisions. |
| Ordinary GUI installation | Install from Disk, enable, disable and re-enable succeeded. All installed files matched the ZIP. Import, UnityPackage Export and Prefab asset Export registration checked. |
| Ordinary UnityPackage Import | A permitted real clothing package with eight Prefabs was imported through the GUI; one Prefab selected, two Meshes and one Armature instantiated. Nonselected package data retained. No missing-visual-dependency prompt appeared for this input. |
| Prefab asset Export | All three output options enabled through the GUI: two PNG and two SVG UV layouts, two original texture files, one FBX and a correspondence manifest produced. Manifest reported complete with no missing entries for this input. One PNG was visually inspected. |
| Original textures | Both exported images matched the corresponding original package asset bytes exactly. Shared references did not create duplicate image files. |
| Saved Blender state | The imported scene was saved through the GUI. A separate process reopened it to capture the source for FBX comparison. |
| Fresh-process GUI FBX import | The newly exported FBX was imported through Blender's normal FBX menu in a separate process. The two Mesh identities, Prefab scope, one Armature's bone/parent sets, vertex counts, triangle counts, Material slots, UV layer names and triangle UV values, per-vertex weights and Shape Key names/coordinates matched the saved source in this case. No unrelated Mesh appeared. |
| FBX visual inspection | Clothing and accessory Meshes were visible. Numerous retained auxiliary objects initially obscured inspection; disabling viewport overlays made the shape readable. This is a usability limitation, not a claim that the helpers can be deleted safely. |
| Numerical observation | Maximum per-vertex world-position component residual was about `1.31e-7` Blender world units. This is a diagnostic of this case, not an approved general error tolerance or an independent vertex-correspondence proof. |
| Ordinary UnityPackage Export | Mesh / Skin GUI export produced a package and success notification. Its six included helper sources retained full MIT notices. This package was not newly applied in Unity during this snapshot validation. |
| Preservation and cleanup | Original package, protected input and prior saved source hashes remained unchanged. Both owned Blender processes exited normally. |

## Not established

- General compatibility with all avatars, Prefab Variant/Nested Prefab structures or multi-package dependencies.
- Correct visual reconstruction of arbitrary Unity shaders in Blender.
- Arbitrary Object/Bone rest-frame edits or enabled non-Armature modifiers through the asset FBX path.
- Complete evaluated deformation, animation, normals/tangents or every Unity/VRChat component after FBX round-trip.
- New Unity Apply/restart proof for this exact ZIP-generated package, VRChat SDK build, upload or client runtime acceptance.
- Every listed UI feature, every combination of output options or Blender versions other than the one listed above.

The private test assets and raw logs are not distributed. The repository contains the addon, first-party validation scripts, documentation, licenses and this addon ZIP only. Do not use the sample's success as a guarantee for a different asset. Keep originals and review the generated package before applying it.

## Publication checks

The selected source received independent source/privacy/license inspection and an independent adversarial audit. A missing complete MIT notice in five helper headers was corrected and independently rechecked. The independent initial Git history, all objects/references, approved GitHub noreply Author/Committer identity and ZIP contents/metadata were inspected. Final repository visibility and download verification are recorded by the delivery report; the existence of this document alone does not prove publication.

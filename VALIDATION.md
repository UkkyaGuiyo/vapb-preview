# Alpha snapshot validation

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

## Next candidate (not yet published)

Selected development commit: `c95a431110602a168f574b59954c006307712335`.
Only Import Assistant and Model Skin Finalizer runtime sources changed relative
to the published source. All addon Python and other helper bodies remain unchanged.
The changes add bounded direct leaf-renderer translation restoration and Japanese
feedback for refused Apply. The existing translation guards and limitations apply;
this does not enable arbitrary Object/Bone frame edits or general SDK behavior.

Development verification includes first-party counterexamples, independent technical
review, a protected real clothing GUI Apply, unchanged sibling/bone/material state,
and exact references/position after separate-process Unity2022.3.22f1 reopen.
The real Apply remains PARTIAL because of an unavailable Shader. VRChat is untested.
A new fixed-source ZIP and candidate-specific installation/representative-function
checks and publication audits are pending. Prior snapshot results above do not
establish those new gates.

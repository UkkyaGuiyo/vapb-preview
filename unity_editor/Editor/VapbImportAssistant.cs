// SPDX-License-Identifier: MIT
/*
MIT License

Copyright (c) 2026 UkkyaGuiyo and VAPB contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/

using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEngine;

// Detection and presentation only. Providers retain their own strict validators
// and restoration code; this class never imports, repairs, or saves an Asset.
public sealed class VapbImportAssistant : EditorWindow
{
    public sealed class Inspection
    {
        public string target, output, changes, warning, details;
        public string[] animationClips;
        public int count;
        public bool partial;
    }
    private sealed class Provider
    {
        public Func<string, Inspection> inspect;
        public Func<string, bool> apply;
        public Func<bool> partialResult;
        public Func<string> failureReason;
    }
    [Serializable] private sealed class Manifest { public string schema_version; public Task[] reference_rebind_tasks; public string[] warnings; }
    [Serializable] private sealed class Task { public string kind; }
    private sealed class Entry
    {
        public string path, identity, error, warning;
        public string[] missingScripts;
        public Inspection inspection;
        public Provider provider;
        public bool details, recognized, applied, appliedPartial;
    }
    private static readonly Dictionary<string, Provider> providers = new Dictionary<string, Provider>();
    private readonly List<Entry> entries = new List<Entry>();
    private static bool pending;
    private static double stableSince;
    private Vector2 scroll;
    private static string StatePath { get { return Path.Combine(Directory.GetParent(Application.dataPath).FullName,
        "Library", "VapbApplyAssistant.state"); } }

    public static void Register(string kind, Func<string, Inspection> inspect, Func<string, bool> apply,
        Func<bool> partialResult = null, Func<string> failureReason = null)
    {
        providers[kind] = new Provider { inspect = inspect, apply = apply, partialResult = partialResult,
            failureReason = failureReason };
        Schedule();
    }
    [InitializeOnLoadMethod]
    private static void Initialize()
    {
        if (Application.isBatchMode || AssetDatabase.IsAssetImportWorkerProcess()) return;
        EditorApplication.projectChanged -= Schedule;
        EditorApplication.projectChanged += Schedule;
        Schedule();
    }
    private void OnEnable()
    {
        // Unity restores the utility Window across assembly reload but not its
        // transient Entry/provider objects. Rehydrate only a displayed prompt.
        EditorApplication.update -= RestoreDisplayedPrompt;
        EditorApplication.update += RestoreDisplayedPrompt;
    }
    private void OnDisable() { EditorApplication.update -= RestoreDisplayedPrompt; }
    private void RestoreDisplayedPrompt()
    {
        if (entries.Count != 0) { EditorApplication.update -= RestoreDisplayedPrompt; return; }
        if (EditorApplication.isCompiling || EditorApplication.isUpdating ||
            EditorApplication.timeSinceStartup - stableSince < 1) return;
        EditorApplication.update -= RestoreDisplayedPrompt;
        Open(false, null, true);
    }
    private static void Schedule()
    {
        if (Application.isBatchMode || AssetDatabase.IsAssetImportWorkerProcess()) return;
        stableSince = EditorApplication.timeSinceStartup;
        if (pending) return;
        pending = true;
        EditorApplication.update += WaitForStableEditor;
    }
    private static void WaitForStableEditor()
    {
        if (EditorApplication.isCompiling || EditorApplication.isUpdating || EditorApplication.isPlayingOrWillChangePlaymode)
        { stableSince = EditorApplication.timeSinceStartup; return; }
        if (EditorApplication.timeSinceStartup - stableSince < 1) return;
        pending = false;
        EditorApplication.update -= WaitForStableEditor;
        // A manual prompt can precede provider initialization. Registration must
        // invalidate that cached rejection without reopening cancelled prompts.
        foreach (var window in Resources.FindObjectsOfTypeAll<VapbImportAssistant>())
        {
            foreach (Entry entry in window.entries)
                if (entry.error != null && entry.error.StartsWith("TASK_UNSUPPORTED", StringComparison.Ordinal))
                    window.RefreshEntry(entry);
            window.Repaint();
        }
        Open(false, null);
    }
    [MenuItem("Tools/VAPB/編集内容を確認")]
    private static void OpenManually() { Open(true, null); }
    public static void Show(string path) { Open(true, path); }

    private static Entry Inspect(string path)
    {
        Entry entry = InspectManifest(path);
        if (entry.error == null)
            try { entry.inspection = entry.provider.inspect(path); }
            catch (Exception error)
            {
                entry.error = error.Message;
                if (entry.error == "EXTERNAL_DEPENDENCY_REQUIRED")
                    entry.missingScripts = error.Data["VapbMissingScripts"] as string[];
            }
        return entry;
    }
    private static Entry InspectManifest(string path)
    {
        var entry = new Entry { path = path };
        try
        {
            if (String.IsNullOrEmpty(path) || !path.StartsWith("Assets/VAPBExport/", StringComparison.Ordinal) ||
                path.Contains("..") || !path.EndsWith(".json", StringComparison.OrdinalIgnoreCase) ||
                AssetDatabase.LoadAssetAtPath<TextAsset>(path) == null)
                throw new InvalidOperationException("MANIFEST_UNAVAILABLE");
            // Match the finalizers: imported TextAsset content can retain a previous
            // manifest after package replacement. Inspect and fingerprint the same
            // on-disk bytes that strict Apply will validate, without reimporting.
            string text = File.ReadAllText(Path.Combine(Directory.GetParent(Application.dataPath).FullName, path));
            using (var sha = SHA256.Create())
            {
                byte[] hash = sha.ComputeHash(Encoding.UTF8.GetBytes(path + "\n" + text));
                entry.identity = BitConverter.ToString(hash).Replace("-", "").ToLowerInvariant();
            }
            Manifest manifest = JsonUtility.FromJson<Manifest>(text);
            if (manifest == null || manifest.schema_version != "vapb-export-manifest-1" ||
                manifest.reference_rebind_tasks == null || manifest.reference_rebind_tasks.Length == 0)
                throw new InvalidOperationException("MANIFEST_UNSUPPORTED");
            entry.recognized = true;
            if (manifest.warnings != null)
            {
                if (Array.IndexOf(manifest.warnings, "FIRST_SHAPE_TANGENTS_UNVERIFIED") >= 0)
                    entry.warning = "このShape Keyの接線と、中間値での陰影はUnityへの復帰が未検証です。";
                else if (Array.IndexOf(manifest.warnings, "FIRST_SHAPE_INTERMEDIATE_SHADING_UNVERIFIED") >= 0)
                    entry.warning = "このShape Keyの中間値での陰影はUnityへの復帰が未検証です。";
            }
            foreach (Task task in manifest.reference_rebind_tasks)
            {
                if (task == null || String.IsNullOrEmpty(task.kind))
                    throw new InvalidOperationException("TASK_UNSUPPORTED:KIND_MISSING");
                if (!providers.TryGetValue(task.kind, out Provider provider))
                    throw new InvalidOperationException("TASK_UNSUPPORTED:PROVIDER_NOT_REGISTERED:" + task.kind);
                if (entry.provider != null && entry.provider.inspect != provider.inspect)
                    throw new InvalidOperationException("TASK_UNSUPPORTED:MIXED_PROVIDERS");
                entry.provider = provider;
            }
        }
        catch (Exception error) { entry.error = error.Message; }
        return entry;
    }
    private static void Remember(Entry entry, string state)
    {
        if (entry.identity == null) return;
        // Library is project-local and not an Asset. Asset bytes stay unchanged on cancel.
        var lines = File.Exists(StatePath) ? new List<string>(File.ReadAllLines(StatePath)) : new List<string>();
        lines.RemoveAll(line => line.StartsWith(entry.identity + " ", StringComparison.Ordinal));
        lines.Add(entry.identity + " " + state);
        Directory.CreateDirectory(Path.GetDirectoryName(StatePath));
        File.WriteAllLines(StatePath, lines.ToArray());
    }
    private static void Open(bool manual, string selected, bool restoreDisplayed = false)
    {
        if (Application.isBatchMode || AssetDatabase.IsAssetImportWorkerProcess() ||
            EditorApplication.isCompiling || EditorApplication.isUpdating) return;
        var found = new List<Entry>();
        var remembered = new Dictionary<string, string>();
        try
        {
            if (File.Exists(StatePath)) foreach (string line in File.ReadAllLines(StatePath))
            {
                string[] fields = line.Split(' ');
                if (fields.Length == 2) remembered[fields[0]] = fields[1];
            }
            var paths = new List<string>();
            if (selected != null) paths.Add(selected);
            else if (AssetDatabase.IsValidFolder("Assets/VAPBExport"))
                foreach (string guid in AssetDatabase.FindAssets("t:TextAsset", new[] { "Assets/VAPBExport" }))
                {
                    string path = AssetDatabase.GUIDToAssetPath(guid);
                    if (path.EndsWith(".json", StringComparison.OrdinalIgnoreCase)) paths.Add(path);
                }
            paths.Sort(StringComparer.Ordinal);
            foreach (string path in paths)
            {
                Entry entry = InspectManifest(path);
                // Other JSON files aren't VAPB export manifests.
                if (selected == null && !entry.recognized) continue;
                bool known = remembered.TryGetValue(entry.identity ?? "", out string state);
                if (restoreDisplayed ? !known || state != "prompted" : !manual && known) continue;
                // Suppressed prompts need only a fresh manifest fingerprint.
                // Displayed entries and Apply still perform full fresh inspection.
                entry = Inspect(path);
                Remember(entry, "prompted");
                found.Add(entry);
            }
        }
        catch (Exception error)
        { Debug.LogWarning("VAPB_ASSISTANT_STATE_UNAVAILABLE=" + error.GetType().Name); return; }
        if (found.Count == 0)
        {
            if (manual) EditorUtility.DisplayDialog("VAPB", "確認する編集データがありません。Unity用PackageをImportしてください。", "閉じる");
            return;
        }
        var window = GetWindow<VapbImportAssistant>(true, "VAPB：編集内容を確認", true);
        window.entries.Clear(); window.entries.AddRange(found);
        window.minSize = new Vector2(520, 400);
        window.Show();
    }
    private static string Reason(string error)
    {
        if (error == null) return "";
        if (error == "EDITED_REST_MISMATCH")
            return "編集したMeshと元の骨格の基準位置を一致させられませんでした。\n" +
                "Objectの位置・回転・拡大縮小や骨の基準姿勢を変えた場合は、変更前の保存コピーから確認してください。\n" +
                "この組み合わせの復元は未対応のため、適用を停止しました。";
        if (error.Contains("HASH") || error.Contains("STALE") || error.Contains("REVISION"))
            return "原本または編集データの版が一致しません。対象のPackageを確認してください。";
        if (error.Contains("OCCUPIED") || error.Contains("ALREADY")) return "保存先が別の内容で使用されています。上書きは行いません。";
        if (error.Contains("DEPENDENCY") || error.Contains("MISSING_SCRIPT")) return "必要な外部依存またはScriptが不足しています。元アバターで使用していたSDKやアドオンの導入を確認し、再確認してください。参照IDだけでは製品名や必要な版は特定できません。";
        if (error.Contains("MATERIAL") || error.Contains("TEXTURE")) return "素材の対応を確認できません。名前から推測して割り当てません。";
        if (error.Contains("UNAVAILABLE") || error.Contains("NOT_FOUND")) return "必要な対象Assetが見つかりません。PackageのImport結果を確認してください。";
        return "この編集データの構造または参照は確認できませんでした。詳細を確認し、対応する経路で書き出してください。";
    }
    private static void DrawAnimationOutputs(Inspection view)
    {
        if (view.animationClips == null || view.animationClips.Length == 0) return;
        EditorGUILayout.LabelField("適用後のAnimation（手動割当）", EditorStyles.boldLabel);
        GameObject variant = AssetDatabase.LoadAssetAtPath<GameObject>(view.output);
        using (new EditorGUI.DisabledScope(variant == null))
            if (GUILayout.Button("割当先Variantを選択"))
            { Selection.activeObject = variant; EditorGUIUtility.PingObject(variant); }
        for (int i = 0; i < view.animationClips.Length; i++)
        {
            AnimationClip clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(view.animationClips[i]);
            using (new EditorGUI.DisabledScope(clip == null))
                if (GUILayout.Button("編集Clip " + (i + 1) + " を選択"))
                { Selection.activeObject = clip; EditorGUIUtility.PingObject(clip); }
        }
    }
    private void OnGUI()
    {
        EditorGUILayout.HelpBox("原本を保持し、確認した編集内容だけを適用します。適用時にも既存Finalizerが出所・参照を再検証します。", MessageType.Info);
        scroll = EditorGUILayout.BeginScrollView(scroll);
        foreach (Entry entry in entries)
        {
            EditorGUILayout.BeginVertical("box");
            Inspection view = entry.inspection;
            EditorGUILayout.LabelField(entry.applied ? (entry.appliedPartial ? "適用済み（部分対応）" : "適用済み") :
                entry.error != null ? "適用不可" : view.partial ? "部分対応" : "適用可能（事前確認済み）", EditorStyles.boldLabel);
            if (entry.error != null)
            {
                if (view != null) EditorGUILayout.LabelField("対象", view.target, EditorStyles.wordWrappedLabel);
                EditorGUILayout.HelpBox(Reason(entry.error), MessageType.Error);
                if (entry.missingScripts != null && entry.missingScripts.Length != 0)
                    EditorGUILayout.LabelField("不足しているScript参照", entry.missingScripts.Length + "件（参照IDは詳細に表示）");
            }
            else
            {
                EditorGUILayout.LabelField("対象", view.target, EditorStyles.wordWrappedLabel);
                EditorGUILayout.LabelField(entry.applied ? "適用した内容" : "更新予定", view.count + " Mesh/Skin", EditorStyles.wordWrappedLabel);
                EditorGUILayout.LabelField("保存先", view.output, EditorStyles.wordWrappedLabel);
                EditorGUILayout.HelpBox(view.changes, MessageType.Info);
                if (!String.IsNullOrEmpty(entry.warning)) EditorGUILayout.HelpBox(entry.warning, MessageType.Warning);
                if (!String.IsNullOrEmpty(view.warning)) EditorGUILayout.HelpBox(view.warning, MessageType.Warning);
                DrawAnimationOutputs(view);
            }
            entry.details = EditorGUILayout.Foldout(entry.details, "詳細");
            if (entry.details)
            {
                EditorGUILayout.SelectableLabel(entry.path, GUILayout.Height(35));
                if (entry.error != null) EditorGUILayout.SelectableLabel(entry.error, GUILayout.Height(35));
                if (entry.missingScripts != null)
                    foreach (string missing in entry.missingScripts)
                        EditorGUILayout.SelectableLabel(missing, EditorStyles.wordWrappedLabel, GUILayout.Height(40));
                if (view != null && !String.IsNullOrEmpty(view.details))
                    EditorGUILayout.HelpBox(view.details, MessageType.None);
            }
            EditorGUILayout.BeginHorizontal();
            if (entry.applied)
            {
                GameObject output = AssetDatabase.LoadAssetAtPath<GameObject>(view.output);
                using (new EditorGUI.DisabledScope(output == null))
                    if (GUILayout.Button("生成したPrefabを表示")) EditorGUIUtility.PingObject(output);
            }
            else if (GUILayout.Button("再確認"))
            {
                RefreshEntry(entry);
            }
            using (new EditorGUI.DisabledScope(entry.applied || entry.error != null || view == null || EditorApplication.isCompiling || EditorApplication.isUpdating || EditorApplication.isPlayingOrWillChangePlaymode))
                if (GUILayout.Button(entry.applied ? "適用済み" : "適用")) ApplyEntry(entry);
            if (GUILayout.Button(entry.applied ? "閉じる" : "キャンセル"))
            {
                CancelEntry(entry); GUIUtility.ExitGUI();
            }
            EditorGUILayout.EndHorizontal();
            EditorGUILayout.EndVertical();
        }
        EditorGUILayout.EndScrollView();
    }
    private void RefreshEntry(Entry entry)
    {
        Entry refreshed = Inspect(entry.path);
        entry.identity = refreshed.identity; entry.provider = refreshed.provider;
        entry.inspection = refreshed.inspection; entry.error = refreshed.error;
        entry.warning = refreshed.warning; entry.missingScripts = refreshed.missingScripts;
    }
    private void CancelEntry(Entry entry)
    {
        if (!entry.applied)
            try { Remember(entry, "cancelled"); } catch (Exception error) { Debug.LogWarning(error.GetType().Name); }
        entries.Remove(entry);
        if (entries.Count == 0) Close();
        else Repaint();
    }
    private static string ApplyResultMessage(bool applied, bool inspectionPartial, bool providerPartial, string failureReason)
    {
        if (applied ? inspectionPartial : providerPartial)
            return "部分対応：Prefabを生成しました。未解決項目が残っています。確認画面の警告を確認してください。";
        if (applied) return "適用が完了しました。出力Prefabを開いて確認してください。";
        return String.IsNullOrEmpty(failureReason) ? "適用できませんでした。Consoleの理由を確認してください。" :
            "適用できませんでした。\n" + Reason(failureReason);
    }

    private void ApplyEntry(Entry entry)
    {
        if (entry.applied) return;
        if (EditorApplication.isCompiling || EditorApplication.isUpdating || EditorApplication.isPlayingOrWillChangePlaymode) return;
        Entry fresh = Inspect(entry.path);
        if (fresh.error != null || fresh.identity != entry.identity)
        {
            entry.error = fresh.error ?? "MANIFEST_CHANGED";
            entry.missingScripts = fresh.missingScripts;
            EditorUtility.DisplayDialog("VAPB：再確認が必要です", Reason(entry.error), "閉じる"); return;
        }
        bool complete = fresh.provider.apply(fresh.path);
        bool partial = !complete && fresh.provider.partialResult != null && fresh.provider.partialResult();
        if (!complete && !partial && fresh.provider.failureReason != null)
            entry.error = fresh.provider.failureReason();
        if (complete || partial)
        {
            entry.applied = true;
            entry.appliedPartial = complete ? fresh.inspection.partial : partial;
            entry.inspection = fresh.inspection;
            entry.warning = fresh.warning;
            GameObject output = AssetDatabase.LoadAssetAtPath<GameObject>(fresh.inspection.output);
            // Selecting a Prefab can run third-party inspectors that rewrite
            // serialized settings after the finalizer has verified them.
            if (output != null) EditorGUIUtility.PingObject(output);
            try { Remember(fresh, "applied"); } catch (Exception error) { Debug.LogWarning(error.GetType().Name); }
        }
        EditorUtility.DisplayDialog("VAPB：適用結果",
            ApplyResultMessage(complete, fresh.inspection.partial, partial, entry.error), "閉じる");
    }
}

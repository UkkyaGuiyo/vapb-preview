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
using System.IO;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Security.Cryptography;
using UnityEditor;
using UnityEngine;

// First-party public API helper. Only exact generated Skin revisions opt in.
public sealed class VapbSkinWeightImporter : AssetPostprocessor
{
    [Serializable] private sealed class Policy { public int version; public string model_guid, model_sha256; public FirstShape first_shape; }
    [Serializable] private sealed class FirstShape { public int policy_version; public string realization_id, geometry_uid, shape_geometry_uid, content_json, content_sha256; }
    [Serializable] private sealed class NormalContent
    {
        public string realization_id,shape_name,coordinate_space;
        public float frame_weight;
        public int policy_version;
        public Vector3[] base_positions,shape_positions,base_normals,shape_normals;
        public Vector4[] base_tangents,shape_tangents;
        public Vector2[] uv0;
        public int[] triangles,corner_indices;
        public float normal_sample_weight;
        public Vector3[] sample_positions,sample_normals;
    }
    private readonly Dictionary<GameObject,string> realizations = new Dictionary<GameObject,string>();
    private readonly Dictionary<GameObject,string> requiredNormals = new Dictionary<GameObject,string>();
    private bool invalidRealization,invalidRequiredMarker,normalRequiredSeen;
    public override int GetPostprocessOrder() { return 1000; }
    public override uint GetVersion() { return 4; }
    private static string Digest(byte[] bytes)
    {
        using(var sha = SHA256.Create())
            return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
    }
    private Policy LoadPolicy()
    {
        string guid = AssetDatabase.AssetPathToGUID(assetPath);
        if(String.IsNullOrEmpty(guid)) return null;
        string policyPath = "Assets/VAPBExport/SkinWeightPolicy_" + guid + ".json";
        if(!File.Exists(policyPath)) return null;
        context.DependsOnSourceAsset(policyPath);
        return ReadPolicy(assetPath,guid,policyPath);
    }
    private static Policy ReadPolicy(string modelPath,string guid,string policyPath)
    {
        Policy policy = JsonUtility.FromJson<Policy>(File.ReadAllText(policyPath));
        if(policy == null || (policy.version != 1 && policy.version != 2 && policy.version != 3 && policy.version != 4) || policy.model_guid != guid ||
           policy.model_sha256 != Digest(File.ReadAllBytes(modelPath)) ||
           (policy.version >= 2 && policy.first_shape == null) ||
           (policy.version >= 3 && policy.first_shape.policy_version != policy.version))
            throw new InvalidOperationException("VAPB_SKIN_WEIGHT_REVISION_MISMATCH");
        return policy;
    }
    private void OnPreprocessModel()
    {
        Policy policy = LoadPolicy();
        if(policy == null) return;
        var importer = (ModelImporter)assetImporter;
        importer.skinWeights = ModelImporterSkinWeights.Custom;
        importer.maxBonesPerVertex = 255;
        // The post-import getter clamps to .001 in 2022.3.22f1. Set at this stage
        // on every import; stored .meta or a setter after import is insufficient.
        importer.minBoneWeight = 0;
        importer.weldVertices = false;
        if(policy.version >= 2)
        {
            importer.importNormals = ModelImporterNormals.Import;
            importer.importBlendShapeNormals = ModelImporterNormals.Import;
            using(var serialized = new SerializedObject(importer))
            {
                var legacy = serialized.FindProperty("legacyComputeAllNormalsFromSmoothingGroupsWhenMeshHasBlendShapes");
                if(legacy == null) throw new InvalidOperationException("VAPB_SHAPE_NORMAL_IMPORT_POLICY_UNSUPPORTED");
                legacy.boolValue = false;
                serialized.ApplyModifiedPropertiesWithoutUndo();
            }
        }
    }
    private void OnPostprocessGameObjectWithUserProperties(GameObject node,string[] names,object[] values)
    {
        if(names == null || values == null || names.Length != values.Length) return;
        for(int i=0;i<names.Length;i++)
        {
            if(names[i] == "_vapb_fbx_realization_id")
            {
                if(!(values[i] is string) || realizations.ContainsKey(node))
                    invalidRealization=true;
                else realizations.Add(node,(string)values[i]);
            }
            if(names[i] == "_vapb_shape_normal_policy_required")
            {
                normalRequiredSeen=true;
                if(!(values[i] is string) || requiredNormals.ContainsKey(node))
                    invalidRequiredMarker=true;
                else requiredNormals.Add(node,(string)values[i]);
            }
        }
    }
    private static bool Finite(Vector3 v)
    {
        return !Single.IsNaN(v.x) && !Single.IsNaN(v.y) && !Single.IsNaN(v.z) &&
               !Single.IsInfinity(v.x) && !Single.IsInfinity(v.y) && !Single.IsInfinity(v.z);
    }
    private static bool SameBits(float a,float b)
    {
        return BitConverter.ToInt32(BitConverter.GetBytes(a),0)==BitConverter.ToInt32(BitConverter.GetBytes(b),0);
    }
    private static bool SameBits(Vector3 a,Vector3 b) {return SameBits(a.x,b.x)&&SameBits(a.y,b.y)&&SameBits(a.z,b.z);}
    private static bool SameBits(Vector4 a,Vector4 b) {return SameBits(a.x,b.x)&&SameBits(a.y,b.y)&&SameBits(a.z,b.z)&&SameBits(a.w,b.w);}
    private static Vector4 SourceTangent(Vector4 value)
    {
        Vector3 xyz=new Vector3(value.x,value.y,value.z);
        if(!Finite(xyz)||!Mathf.Approximately(xyz.sqrMagnitude,1f)||Math.Abs(value.w)!=1f)
            throw new InvalidOperationException("VAPB_SHAPE_TANGENT_TARGET_INVALID");
        return new Vector4(-value.x,value.y,value.z,-value.w);
    }
    private static string TriangleKey(int a,int b,int c)
    {
        if(a == b || a == c || b == c) throw new InvalidOperationException("VAPB_SHAPE_NORMAL_AMBIGUOUS_GEOMETRY");
        int[] values = {a,b,c}; Array.Sort(values); return values[0]+"/"+values[1]+"/"+values[2];
    }
    private static void ApplyFiniteSample(Mesh mesh,Vector3[] basisPositions,Vector3[] basisNormals,Vector4[] basisTangents,
        Vector3[] endpointPositions,Vector3[] endpointNormals,Vector3[] endpointTangents,NormalContent data,
        int[] cpGroups,int[] nativeGroups,int[] indices,Func<Vector3,Vector3> point)
    {
        int vertexCount=basisPositions.Length;
        if(data.normal_sample_weight!=50f || data.sample_positions==null || data.sample_positions.Length!=data.base_positions.Length ||
           data.sample_normals==null || data.sample_normals.Length!=data.shape_normals.Length ||
           endpointPositions.Length!=vertexCount || endpointNormals.Length!=vertexCount || endpointTangents.Length!=vertexCount ||
           basisNormals.Length!=vertexCount || basisTangents.Length!=vertexCount)
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_SAMPLE_DOMAIN_INVALID");
        if(data.sample_positions.Any(position=>!Finite(position))||
           data.sample_normals.Any(normal=>!Finite(normal)||!Mathf.Approximately(normal.sqrMagnitude,1f)))
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_SAMPLE_INVALID");
        var faces=new Dictionary<string,int>();
        for(int offset=0;offset<data.triangles.Length;offset+=3)
        {
            string key=TriangleKey(cpGroups[data.triangles[offset]],cpGroups[data.triangles[offset+1]],cpGroups[data.triangles[offset+2]]);
            if(faces.ContainsKey(key)) throw new InvalidOperationException("VAPB_SHAPE_NORMAL_AMBIGUOUS_GEOMETRY");
            faces.Add(key,offset);
        }
        var seenFaces=new HashSet<string>();var assigned=new bool[vertexCount];var vertexCp=new int[vertexCount];
        var normalAssigned=new bool[vertexCount];var sampleNormal=new Vector3[vertexCount];
        for(int offset=0;offset<indices.Length;offset+=3)
        {
            string key=TriangleKey(nativeGroups[indices[offset]],nativeGroups[indices[offset+1]],nativeGroups[indices[offset+2]]);
            int expected;
            if(!faces.TryGetValue(key,out expected)||!seenFaces.Add(key))
                throw new InvalidOperationException("VAPB_SHAPE_NORMAL_AMBIGUOUS_GEOMETRY");
            for(int j=0;j<3;j++)
            {
                int vertex=indices[offset+j],corner=-1;
                for(int k=0;k<3;k++) if(cpGroups[data.triangles[expected+k]]==nativeGroups[vertex]) corner=expected+k;
                if(corner<0) throw new InvalidOperationException("VAPB_SHAPE_NORMAL_CORNER_UNMATCHED");
                int cp=data.triangles[corner],loop=data.corner_indices[corner];
                if(loop<0||loop>=data.sample_normals.Length||cp<0||cp>=data.sample_positions.Length)
                    throw new InvalidOperationException("VAPB_SHAPE_NORMAL_CORNER_DOMAIN_INVALID");
                Vector3 sample=data.sample_normals[loop];
                if(!Finite(sample)||!Mathf.Approximately(sample.sqrMagnitude,1f))
                    throw new InvalidOperationException("VAPB_SHAPE_NORMAL_SAMPLE_INVALID");
                sample.x=-sample.x;
                if(assigned[vertex]&&vertexCp[vertex]!=cp)
                    throw new InvalidOperationException("VAPB_SHAPE_NORMAL_SAMPLE_POSITION_CONFLICT");
                if(normalAssigned[vertex]&&!SameBits(sampleNormal[vertex],sample))
                    throw new InvalidOperationException("VAPB_SHAPE_NORMAL_SAMPLE_CORNER_CONFLICT");
                assigned[vertex]=true;vertexCp[vertex]=cp;normalAssigned[vertex]=true;sampleNormal[vertex]=sample;
            }
        }
        if(seenFaces.Count!=faces.Count||assigned.Any(value=>!value))
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_CORNERS_INCOMPLETE");
        var sampleDelta=new Vector3[vertexCount];var normalDelta=new Vector3[vertexCount];var tangentDelta=new Vector3[vertexCount];
        for(int vertex=0;vertex<vertexCount;vertex++)
        {
            int cp=vertexCp[vertex];Vector3 sourceSample=data.sample_positions[cp];
            if(!Finite(data.base_positions[cp])||!Finite(sourceSample)||!Finite(endpointPositions[vertex])||
               !Finite(endpointNormals[vertex])||!Finite(endpointTangents[vertex])||!Finite(basisNormals[vertex])||
               !Finite(basisPositions[vertex])||
               !Finite(new Vector3(basisTangents[vertex].x,basisTangents[vertex].y,basisTangents[vertex].z)))
                throw new InvalidOperationException("VAPB_SHAPE_NORMAL_NONFINITE");
            Vector3 halfDelta=endpointPositions[vertex]*0.5f;
            Vector3 declaredDelta=point(sourceSample)-point(data.base_positions[cp]);
            Vector3 samplePoint=point(sourceSample);
            if(!Finite(halfDelta)||!Finite(declaredDelta)||!Finite(samplePoint)||
               !halfDelta.Equals(declaredDelta)||!(basisPositions[vertex]+halfDelta).Equals(samplePoint))
                throw new InvalidOperationException("VAPB_SHAPE_NORMAL_SAMPLE_POSITION_MISMATCH");
            sampleDelta[vertex]=halfDelta;
            normalDelta[vertex]=sampleNormal[vertex]-basisNormals[vertex];
            tangentDelta[vertex]=endpointTangents[vertex]*0.5f;
        }
        mesh.ClearBlendShapes();
        mesh.AddBlendShapeFrame(data.shape_name,50f,sampleDelta,normalDelta,tangentDelta);
        mesh.AddBlendShapeFrame(data.shape_name,100f,endpointPositions,endpointNormals,endpointTangents);
        if(mesh.blendShapeCount!=1||mesh.GetBlendShapeFrameCount(0)!=2||
           mesh.GetBlendShapeFrameWeight(0,0)!=50f||mesh.GetBlendShapeFrameWeight(0,1)!=100f)
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_SAMPLE_LAYOUT_INVALID");
        var p=new Vector3[vertexCount];var n=new Vector3[vertexCount];var t=new Vector3[vertexCount];
        mesh.GetBlendShapeFrameVertices(0,0,p,n,t);
        if(!sampleDelta.SequenceEqual(p)||!normalDelta.SequenceEqual(n)||!tangentDelta.SequenceEqual(t))
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_SAMPLE_STORAGE_CHANGED");
        mesh.GetBlendShapeFrameVertices(0,1,p,n,t);
        if(!endpointPositions.SequenceEqual(p)||!endpointNormals.SequenceEqual(n)||!endpointTangents.SequenceEqual(t)||
           !basisPositions.SequenceEqual(mesh.vertices)||!basisNormals.SequenceEqual(mesh.normals)||!basisTangents.SequenceEqual(mesh.tangents))
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_ENDPOINT_STORAGE_CHANGED");
    }
    private void OnPostprocessModel(GameObject root)
    {
        Policy policy = LoadPolicy();
        if(policy == null || policy.version == 1)
        {
            if(normalRequiredSeen)
            {
                context.DependsOnSourceAsset("Assets/VAPBExport/SkinWeightPolicy_"+AssetDatabase.AssetPathToGUID(assetPath)+".json");
                throw new InvalidOperationException("VAPB_SHAPE_NORMAL_POLICY_MISSING");
            }
            return;
        }
        if(invalidRealization || invalidRequiredMarker)
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_PROPERTY_INVALID");
        FirstShape section = policy.first_shape;
        if(String.IsNullOrEmpty(section.content_json) || String.IsNullOrEmpty(section.realization_id) ||
           String.IsNullOrEmpty(section.geometry_uid) || String.IsNullOrEmpty(section.shape_geometry_uid) ||
           section.content_sha256 != Digest(Encoding.UTF8.GetBytes(section.content_json)) || requiredNormals.Count != 1)
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_POLICY_INVALID");
        GameObject owner = requiredNormals.Keys.Single();
        if(requiredNormals[owner] != policy.version+":"+section.content_sha256 || !realizations.ContainsKey(owner) ||
           realizations[owner] != section.realization_id || realizations.Count(pair=>pair.Value == section.realization_id) != 1)
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_CONTENT_BINDING_MISMATCH");
        var skins = owner.GetComponents<SkinnedMeshRenderer>();
        if(skins.Length != 1 || skins[0].GetBlendShapeWeight(0) != 0)
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_RENDERER_UNPROVEN");
        ApplyNormalContent(section,skins[0].sharedMesh,(ModelImporter)assetImporter,policy.version);
    }
    private static void ApplyNormalContent(FirstShape section,Mesh mesh,ModelImporter importer,int version=2)
    {
        if(section.content_sha256 != Digest(Encoding.UTF8.GetBytes(section.content_json)))
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_CONTENT_BINDING_MISMATCH");
        NormalContent data = JsonUtility.FromJson<NormalContent>(section.content_json);
        if(data == null || (version != 2 && version != 3 && version != 4) ||
           (version >= 3 ? data.policy_version != version : data.policy_version != 0 && data.policy_version != 2) ||
           data.realization_id != section.realization_id ||
           data.coordinate_space != "BLENDER_MESH_LOCAL_WITHOUT_ARMATURE" || data.frame_weight != 100f ||
           data.base_positions == null || data.base_positions.Length == 0 || data.shape_positions == null ||
           data.shape_positions.Length != data.base_positions.Length || data.shape_normals == null ||
           data.triangles == null || data.triangles.Length == 0 || data.triangles.Length % 3 != 0 ||
           data.corner_indices == null || data.corner_indices.Length != data.triangles.Length)
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_DOMAIN_INVALID");
        float scale = importer.fileScale * importer.globalScale;
        if(importer.bakeAxisConversion || !Finite(new Vector3(scale,0,0)) || scale <= 0)
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_COORDINATE_POLICY_UNSUPPORTED");
        if(mesh == null || mesh.blendShapeCount != 1 || mesh.GetBlendShapeFrameCount(0) != 1 ||
           mesh.GetBlendShapeFrameWeight(0,0) != data.frame_weight || mesh.GetBlendShapeName(0) != data.shape_name)
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_FRAME_UNPROVEN");
        Vector3[] vertices = mesh.vertices, basisNormals = mesh.normals;
        if(basisNormals.Length != vertices.Length) throw new InvalidOperationException("VAPB_SHAPE_NORMAL_BASE_NORMALS_MISSING");
        bool sourceTangents=version >= 3;
        Vector2[] uv=mesh.uv;
        if(sourceTangents && (section.policy_version != version || data.base_normals == null ||
           data.base_normals.Length != data.shape_normals.Length || data.base_tangents == null ||
           data.base_tangents.Length != data.shape_normals.Length || data.shape_tangents == null ||
           data.shape_tangents.Length != data.shape_normals.Length || data.uv0 == null ||
           data.uv0.Length != data.shape_normals.Length || uv.Length != vertices.Length))
            throw new InvalidOperationException("VAPB_SHAPE_TANGENT_DOMAIN_INVALID");
        var positions = new Vector3[vertices.Length];var normals = new Vector3[vertices.Length];var tangents = new Vector3[vertices.Length];
        mesh.GetBlendShapeFrameVertices(0,0,positions,normals,tangents);
        Func<Vector3,Vector3> point = p=>new Vector3(-p.x*scale,p.y*scale,p.z*scale);
        var pointGroups = new Dictionary<Vector3,int>(); var cpGroups = new int[data.base_positions.Length];
        for(int cp=0;cp<cpGroups.Length;cp++)
        {
            if(!Finite(data.base_positions[cp]) || !Finite(data.shape_positions[cp]))
                throw new InvalidOperationException("VAPB_SHAPE_NORMAL_NONFINITE");
            Vector3 p = point(data.base_positions[cp]);int group;
            if(!pointGroups.TryGetValue(p,out group)) {group=pointGroups.Count;pointGroups.Add(p,group);}
            cpGroups[cp]=group;
        }
        var expectedFaces = new Dictionary<string,int>();
        for(int offset=0;offset<data.triangles.Length;offset+=3)
        {
            for(int j=0;j<3;j++)
                if(data.triangles[offset+j] < 0 || data.triangles[offset+j] >= cpGroups.Length ||
                   data.corner_indices[offset+j] < 0 || data.corner_indices[offset+j] >= data.shape_normals.Length)
                    throw new InvalidOperationException("VAPB_SHAPE_NORMAL_CORNER_DOMAIN_INVALID");
            string key=TriangleKey(cpGroups[data.triangles[offset]],cpGroups[data.triangles[offset+1]],cpGroups[data.triangles[offset+2]]);
            if(expectedFaces.ContainsKey(key)) throw new InvalidOperationException("VAPB_SHAPE_NORMAL_AMBIGUOUS_GEOMETRY");
            expectedFaces.Add(key,offset);
        }
        var nativeGroups = new int[vertices.Length];
        for(int v=0;v<vertices.Length;v++)
            if(!Finite(vertices[v]) || !pointGroups.TryGetValue(vertices[v],out nativeGroups[v]))
                throw new InvalidOperationException("VAPB_SHAPE_NORMAL_POSITION_UNMATCHED");
        int[] indices=mesh.triangles;var matchedFaces=new HashSet<string>();var assigned=new bool[vertices.Length];var targets=new Vector3[vertices.Length];
        var sourceBasisNormals=new Vector3[vertices.Length];var sourceBasisTangents=new Vector4[vertices.Length];var sourceTargetTangents=new Vector4[vertices.Length];
        if(indices.Length != data.triangles.Length) throw new InvalidOperationException("VAPB_SHAPE_NORMAL_TRIANGLES_INCOMPLETE");
        for(int offset=0;offset<indices.Length;offset+=3)
        {
            string key=TriangleKey(nativeGroups[indices[offset]],nativeGroups[indices[offset+1]],nativeGroups[indices[offset+2]]);int expected;
            if(!expectedFaces.TryGetValue(key,out expected) || !matchedFaces.Add(key))
                throw new InvalidOperationException("VAPB_SHAPE_NORMAL_AMBIGUOUS_GEOMETRY");
            var order=new int[3];
            for(int j=0;j<3;j++)
            {
                int vertex=indices[offset+j];int corner=-1;
                for(int k=0;k<3;k++) if(cpGroups[data.triangles[expected+k]] == nativeGroups[vertex]) corner=expected+k;
                if(corner < 0) throw new InvalidOperationException("VAPB_SHAPE_NORMAL_CORNER_UNMATCHED");
                order[j]=corner-expected;
                int cp=data.triangles[corner];
                // Match the imported float positions before taking their frame delta.
                if(!positions[vertex].Equals(point(data.shape_positions[cp])-point(data.base_positions[cp])))
                    throw new InvalidOperationException("VAPB_SHAPE_NORMAL_POSITION_DELTA_MISMATCH");
                Vector3 normal=data.shape_normals[data.corner_indices[corner]];
                if(!Finite(normal) || !Mathf.Approximately(normal.sqrMagnitude,1f))
                    throw new InvalidOperationException("VAPB_SHAPE_NORMAL_TARGET_INVALID");
                normal.x = -normal.x;
                if(assigned[vertex] && !targets[vertex].Equals(normal))
                    throw new InvalidOperationException("VAPB_SHAPE_NORMAL_CORNER_CONFLICT");
                if(sourceTangents)
                {
                    int loop=data.corner_indices[corner];Vector2 expectedUv=data.uv0[loop];
                    if(!Finite(new Vector3(expectedUv.x,expectedUv.y,0)) ||
                       !SameBits(uv[vertex].x,expectedUv.x)||!SameBits(uv[vertex].y,expectedUv.y))
                        throw new InvalidOperationException("VAPB_SHAPE_TANGENT_UV0_MISMATCH");
                    Vector3 basis=data.base_normals[loop];basis.x=-basis.x;
                    if(!Finite(basis)||!Mathf.Approximately(basis.sqrMagnitude,1f))
                        throw new InvalidOperationException("VAPB_SHAPE_TANGENT_BASE_NORMAL_INVALID");
                    Vector4 basisT=SourceTangent(data.base_tangents[loop]);
                    Vector4 targetT=SourceTangent(data.shape_tangents[loop]);
                    if(basisT.w!=targetT.w)
                        throw new InvalidOperationException("VAPB_SHAPE_TANGENT_ANIMATED_HANDEDNESS_UNSUPPORTED");
                    if(assigned[vertex] && (!SameBits(sourceBasisNormals[vertex],basis)||
                       !SameBits(targets[vertex],normal)||!SameBits(sourceBasisTangents[vertex],basisT)||
                       !SameBits(sourceTargetTangents[vertex],targetT)))
                        throw new InvalidOperationException("VAPB_SHAPE_TANGENT_CORNER_CONFLICT");
                    sourceBasisNormals[vertex]=basis;sourceBasisTangents[vertex]=basisT;sourceTargetTangents[vertex]=targetT;
                }
                assigned[vertex]=true;targets[vertex]=normal;
            }
            if(sourceTangents && (order[1]!=(order[0]+2)%3 || order[2]!=(order[0]+1)%3))
                throw new InvalidOperationException("VAPB_SHAPE_TANGENT_WINDING_MISMATCH");
        }
        if(matchedFaces.Count != expectedFaces.Count || assigned.Any(value=>!value))
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_CORNERS_INCOMPLETE");
        if(sourceTangents) {basisNormals=sourceBasisNormals;mesh.normals=basisNormals;mesh.tangents=sourceBasisTangents;}
        // V4 builds and reads back the same authenticated 100% V3 endpoint first;
        // the finite sample is derived only from those native stored deltas.
        var requested=targets.Select((target,index)=>target-basisNormals[index]).ToArray();
        var requestedTangents=sourceTangents ? sourceTargetTangents.Select((target,index)=>new Vector3(
            target.x-sourceBasisTangents[index].x,target.y-sourceBasisTangents[index].y,target.z-sourceBasisTangents[index].z)).ToArray() : tangents;
        mesh.ClearBlendShapes();mesh.AddBlendShapeFrame(data.shape_name,data.frame_weight,positions,requested,requestedTangents);
        var checkPositions=new Vector3[vertices.Length];var checkNormals=new Vector3[vertices.Length];var checkTangents=new Vector3[vertices.Length];
        mesh.GetBlendShapeFrameVertices(0,0,checkPositions,checkNormals,checkTangents);
        if(!positions.SequenceEqual(checkPositions) || (!sourceTangents && !tangents.SequenceEqual(checkTangents)) ||
           !vertices.SequenceEqual(mesh.vertices) || !basisNormals.SequenceEqual(mesh.normals) ||
           (sourceTangents && !sourceBasisTangents.SequenceEqual(mesh.tangents)))
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_REBUILD_CHANGED_OTHER_DATA");
        if(version == 4)
            ApplyFiniteSample(mesh,vertices,basisNormals,sourceBasisTangents,positions,checkNormals,checkTangents,
                data,cpGroups,nativeGroups,indices,point);
        int changed=0;float maximum=0;
        for(int v=0;v<requested.Length;v++) if(!requested[v].Equals(checkNormals[v]))
        {
            changed++;Vector3 difference=requested[v]-checkNormals[v];
            maximum=Math.Max(maximum,Math.Max(Math.Abs(difference.x),Math.Max(Math.Abs(difference.y),Math.Abs(difference.z))));
        }
        if(changed != 0) Debug.Log("VAPB Shape normal storage readback: "+changed+" differing vectors, maximum component difference "+maximum.ToString("R",System.Globalization.CultureInfo.InvariantCulture));
    }
    private static bool SameVectors(Vector3[] a,Vector3[] b)
    {return a!=null&&b!=null&&a.Length==b.Length&&a.Zip(b,(x,y)=>SameBits(x,y)).All(equal=>equal);}
    private static bool SameVectors(Vector4[] a,Vector4[] b)
    {return a!=null&&b!=null&&a.Length==b.Length&&a.Zip(b,(x,y)=>SameBits(x,y)).All(equal=>equal);}
    internal static bool VerifyAppliedNormalPolicy(string modelPath,string guid,string modelSha,string contentSha,Mesh mesh)
    {
        string path="Assets/VAPBExport/SkinWeightPolicy_"+guid+".json";
        if(!File.Exists(path)) throw new InvalidOperationException("VAPB_SHAPE_NORMAL_POLICY_MISSING");
        Policy policy=ReadPolicy(modelPath,guid,path);
        if((policy.version != 2 && policy.version != 3 && policy.version != 4) || policy.model_sha256 != modelSha || policy.first_shape.content_sha256 != contentSha ||
           AssetDatabase.AssetPathToGUID(modelPath) != guid)
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_POLICY_BINDING_MISMATCH");
        // Applied V4 is [50,100]. Rebuild both frames from a verification clone's
        // endpoint. Raw post-import application enters ApplyNormalContent as one 100 frame.
        bool finiteProfile=policy.version==4;
        if(mesh==null) throw new InvalidOperationException("VAPB_SHAPE_NORMAL_FRAME_UNPROVEN");
        int expectedFrames=finiteProfile?2:1;
        if(mesh.blendShapeCount!=1||mesh.GetBlendShapeFrameCount(0)!=expectedFrames||
           (finiteProfile&&String.IsNullOrEmpty(mesh.GetBlendShapeName(0))))
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_FRAME_UNPROVEN");
        float firstExpectedWeight=finiteProfile?50f:100f;
        if(mesh.GetBlendShapeFrameWeight(0,0)!=firstExpectedWeight||
           (finiteProfile&&mesh.GetBlendShapeFrameWeight(0,1)!=100f))
            throw new InvalidOperationException("VAPB_SHAPE_NORMAL_FRAME_UNPROVEN");
        Mesh candidate=UnityEngine.Object.Instantiate(mesh);
        try
        {
            Vector3[] storedP=new Vector3[mesh.vertexCount],storedN=new Vector3[mesh.vertexCount],storedT=new Vector3[mesh.vertexCount];
            Vector3[] expectedP=new Vector3[mesh.vertexCount],expectedN=new Vector3[mesh.vertexCount],expectedT=new Vector3[mesh.vertexCount];
            if(finiteProfile)
            {
                mesh.GetBlendShapeFrameVertices(0,1,storedP,storedN,storedT);
                candidate.ClearBlendShapes();
                candidate.AddBlendShapeFrame(mesh.GetBlendShapeName(0),100f,storedP,storedN,storedT);
            }
            ApplyNormalContent(policy.first_shape,candidate,(ModelImporter)AssetImporter.GetAtPath(modelPath),policy.version);
            if(finiteProfile)
            {
                for(int frame=0;frame<2;frame++)
                {
                    mesh.GetBlendShapeFrameVertices(0,frame,storedP,storedN,storedT);
                    candidate.GetBlendShapeFrameVertices(0,frame,expectedP,expectedN,expectedT);
                    if(!SameVectors(storedP,expectedP)||!SameVectors(storedN,expectedN)||!SameVectors(storedT,expectedT))
                        throw new InvalidOperationException("VAPB_SHAPE_NORMAL_IMPORT_INCOMPLETE");
                }
            }
            else
            {
                mesh.GetBlendShapeFrameVertices(0,0,storedP,storedN,storedT);
                candidate.GetBlendShapeFrameVertices(0,0,expectedP,expectedN,expectedT);
                bool normalsEqual=policy.version==2 ? storedN.SequenceEqual(expectedN) : SameVectors(storedN,expectedN);
                if(!normalsEqual)
                    throw new InvalidOperationException("VAPB_SHAPE_NORMAL_IMPORT_INCOMPLETE");
                if(policy.version==3&&(!SameVectors(mesh.normals,candidate.normals)||
                   !SameVectors(mesh.tangents,candidate.tangents)||!SameVectors(storedT,expectedT)))
                    throw new InvalidOperationException("VAPB_SHAPE_TANGENT_IMPORT_INCOMPLETE");
                return false;
            }
            if(!SameVectors(mesh.vertices,candidate.vertices)||!SameVectors(mesh.normals,candidate.normals)||
               !SameVectors(mesh.tangents,candidate.tangents)||!mesh.triangles.SequenceEqual(candidate.triangles)||
               !mesh.uv.SequenceEqual(candidate.uv))
                throw new InvalidOperationException("VAPB_SHAPE_NORMAL_BASIS_IMPORT_INCOMPLETE");
        }
        finally {UnityEngine.Object.DestroyImmediate(candidate);}
        return finiteProfile;
    }
}

# VAPB Development Preview

VAPB は、Unity の `.unitypackage` のうち対応するアセットを Blender に読み込み、Blender で編集した対応データを Unity へ戻すための実験的なアドオンです。この配布候補は開発プレビューです。すべての VRChat アバターや Unity 状態を往復できることを保証する正式リリースではありません。

## 今回の更新

選択したSkin MeshのObjectを平行移動してUnityへ戻す限定対応と、Unityの適用拒否後に原因・対処を表示する改善を収録しました。骨格が変わらず、移動対象が末端のRendererで、既存のbounds内に収まり、他Componentが対象を動かしていないことなどを確認できる場合だけ適用します。回転・拡縮・ShapeやActionとの組み合わせを一般対応するものではありません。

## 開発版ZIPの入手

[VAPB-alpha-6317c05.zip をダウンロード](https://github.com/UkkyaGuiyo/vapb-preview/raw/refs/heads/preview/downloads/VAPB-alpha-6317c05.zip)

**Development Preview / Alpha**。422,231 bytes。ZIP元コミットは `6317c059b1a5da33a2a55a8f642a964533e9bdc6`、SHA-256 は `da489a18e98237be2041239f654f2d31244e6d6b7457bd74cfcea3df61c3f9c7` です。GitHubの「Code → Download ZIP」はソース一式なので、上記のアドオンZIPを使ってください。

このZIPで通常インストール、有効化・無効化・再有効化、実衣装のPrefab選択Import、UV・元テクスチャ・FBX抽出、UnityPackage書き出しを実GUI確認しました。今回出力したFBXの別プロセス再読込と、今回出力したUnityPackageのUnity適用は未実施です。同一Python実装の旧版でのFBX再読込実証と、選定した開発ソースのUnity実証は、今回のZIP検証とは区別しています。対象と未検証範囲は [検証記録](VALIDATION.md) を参照してください。Unityへの完全復元やVRChat動作を保証するものではありません。

以前の `VAPB-alpha-b3f141d.zip` は変更せず残しています。今回の限定平行移動復元と拒否理由表示の改善は旧ZIPに含まれません。

## インストール

1. 別途用意された VAPB アドオン ZIP を取得します。
2. Blender の **編集 → プリファレンス → アドオン → ディスクからインストール** で ZIP を選び、**Unity Package / VRChat Avatar Importer** を有効にします。
3. **ファイル → インポート → Unity Package / VRChat Avatar (.unitypackage)** から UnityPackage を読み込みます。元の Unity プロジェクトとパッケージはバックアップしておいてください。

FBX の読み書きには Blender に付属する FBX 機能を使います。書き出したパッケージの読み込みと適用には Unity が必要です。Unity、VRChat SDK、Shader、その他の Unity パッケージは同梱しません。

## Prefabを選んで編集する

Import時に編集したいPrefabを選択します。読み込み後は3Dビューのサイドバー（Nキー）の **VAPB編集 → 編集する部品** で部品検索・集中表示・Prefabの表示切替を利用できます。判別できない部品はOther／未分類に残ります。分類の候補は利用者が確認して決定してください。

通常のBlender操作で編集し、別名の `.blend` として保存してください。後から別のPrefabを読み込むには、Import結果パネルの **UnityPackageを追加...** から同じPackageを選び、追加したいPrefabを指定します。

## UV・元テクスチャ・FBXを取り出す

1. Objectモードで、読み込み済みPrefabの部品を一つ選択します。
2. **VAPB編集 → 編集する部品 → Prefab素材Export** の対象名を確認し、**素材を書き出す** を押します。
3. UVレイアウト（PNGとSVG）、元テクスチャ、FBXを個別にON／OFFにし、既存の保存先フォルダーを指定して実行します。初期状態はすべてONで、少なくとも一項目の選択が必要です。その中にPrefab名を含む新しい出力フォルダーが作られます。
4. 出力先の `manifest.json` でMesh・UV・Material・Textureの対応と不足項目を確認します。一部の出力に失敗した場合は部分結果として報告します。

対象は選択部品の属するPrefab一つです。必要なArmatureは含めますが、無関係なPrefabは混ぜません。UVの自動展開は行いません。元テクスチャは参照先の元ファイルを取得し、存在しないPSDレイヤーなどは作りません。FBXにはUnity／VRChat固有Componentの完全な設定を格納できません。既存ファイルの上書きを避けるため、空の新しい保存先を使ってください。

## Unityへ戻す

対応するMeshを選択し、**ファイル → エクスポート → VAPB UnityPackage（Mesh / Skin）** を使います。別の **VAPB UnityPackage（Blender完成形）** は、対応する静的Meshを現在の完成形から新規Packageへ出力する経路です。Avatar全体の復元とは異なります。

出力Packageを保護コピーのUnity ProjectへImportし、VAPBの確認画面で警告と対象を確認して **適用** を押します。生成されたPrefab／Variantの形状と設定を確認してください。拒否された入力を無理に適用したり、確認前に原本を置き換えたりしないでください。

## 対応する作業範囲

UnityPackage のアセットを Blender に読み込み、対応する Prefab / モデルを選んで編集し、対応する Mesh / Skin または Prefab アセットの経路から UnityPackage を書き出せます。テクスチャ編集用操作、ウェイト転送、セマンティッククリーンアップ、Bone Merge、限定的な物理プレビューも含みます。UI に操作が表示されても、すべてのアセットや組み合わせが対応済みとは限りません。

Unity 側では VAPB の確認画面で内容を確認し、明示的に適用してください。出力は別の Unity プロジェクトに読み込んで確認する運用を想定しています。元データを保持してください。

## 既知の制限

- 直接参照された Skin の Object 座標フレーム変更は、対応する変換を証明できない場合に拒否します。
- Asset FBX 入力に有効な非 Armature モディファイアがある場合、そのアセット経路は拒否されます。
- Blender 上の Shader 表現は一部のみで、近似表示です。Unity 固有の Shader 描画を忠実には再現しません。
- VRChat SDK のビルドとクライアント内の実行時動作は、このプレビューでは未検証です。
- Avatar 全体、すべての Prefab 構成、Unity コンポーネント復元、任意のアニメーション、すべてのアセット組み合わせについて、完全な対応は確認されていません。
- Blender でのインストール、UnityPackage の通常書き出し、Unity Editor の適用、VRChat 実行時確認は別々の検証項目です。一つの成功で他の項目は証明されません。

## バージョンと検証記録

アドオンの Blender 最小バージョン表示は 5.2.0、製品仕様は Blender 5.2.1 LTS を対象にしています。この固定ZIPは Blender 5.2.3 LTS で通常インストールと代表操作を確認しました。ZIP内READMEはビルド時点の記録で、検証後の結果はこのREADMEと検証記録に記載しています。これら以外の Blender バージョンは未検証です。Unity 側ヘルパーは Unity Editor API を使います。既存の限定的な記録には Unity 2022.3.22f1 が含まれますが、全 Unity バージョンや全プロジェクトでの互換性を示すものではありません。VRChat SDK と実行時互換性は未検証です。

## ライセンス

Blender アドオン、ドキュメント、テストは GPL-3.0-or-later です（`LICENSE`）。`unity_editor/` 内の独立した Unity Editor ヘルパーは MIT です（`unity_editor/LICENSE`）。対象範囲と外部依存関係は `LICENSES.md` を参照してください。これらのライセンスは、VAPB で扱うアバター、テクスチャ、Shader などのアセット利用権を与えるものではありません。

# VAPB Development Preview

VAPB は、Unity の `.unitypackage` のうち対応するアセットを Blender に読み込み、Blender で編集した対応データを Unity へ戻すための実験的なアドオンです。この配布候補は開発プレビューです。すべての VRChat アバターや Unity 状態を往復できることを保証する正式リリースではありません。

## 支援 / Support

### 日本語

VAPBは無料のオープンソースとして開発しています。役に立った場合は、[GitHub Sponsors](https://github.com/sponsors/UkkyaGuiyo) から任意で開発を支援できます。支援は開発・検証環境の維持に使用します。支援の有無や金額によって、機能、個別サポート、開発優先順位が変わることはありません。

### English

VAPB is developed as free and open-source software. If VAPB is useful to you, you can optionally support development through [GitHub Sponsors](https://github.com/sponsors/UkkyaGuiyo). Sponsorship helps maintain the development and validation environment. Sponsorship status or amount does not grant feature access, individual support, or development priority.

## このソースの更新内容

- 素材Exportの部分成功を日本語で説明し、未解決のTexture参照と不足ファイル数を混同しないようにしました。
- UV座標があるのにPNGが透明になる一部の条件を検出し、保持したSVGでの確認を案内します。すべてのUV Islandの描画精度を保証する検査ではありません。
- FBX書き出し失敗時の不完全なファイルを出力結果から除き、UVと元Textureの独立出力を保ちます。
- 非表示の補助Prefabだけを選択した場合に無関係な単一FBXを読み込む処理を、構造を確認できる限定条件で抑止しました。
- Prefab詳細表示とMaterialスロット数を修正し、参照先Prefab内のMesh・Material依存関係を追跡します。Nested Prefabの編集対象を正確に復元できない場合の拒否は維持します。

## 開発版ZIPの入手

[VAPB-alpha-14ef77e.zip をダウンロード](https://github.com/UkkyaGuiyo/vapb-preview/raw/refs/heads/preview/downloads/VAPB-alpha-14ef77e.zip)

**Development Preview / Alpha**。424,045 bytes。元ソースは `14ef77e5b756a8f202f1faad4717c41d7476fd19`、SHA-256 は `02fe16fcead943022b75f49fb558f10f08986d10c3413cf88e927e42943caff4` です。GitHubの「Code → Download ZIP」ではなく、このアドオンZIPを使ってください。

Blender 5.2.3 LTSで、この同じZIPを「ディスクからインストール」し、有効化・無効化・再有効化とImport／Exportメニューを実GUI確認しました。119ファイルがZIPと一致しています。別のAPI検証では実衣装1体のImport、UV・元Texture・FBX・UnityPackage出力とFBXの別プロセス再読込を確認しました。これらの実データ操作は今回のGUIインストール検証とは別です。位置と骨のRest Poseには数値差が残り、新ZIPからのUnity適用とVRChat動作は未検証です。初回GUI試行のTemp分離漏れと、修正後の再検証も [検証記録](VALIDATION.md) に記載しています。

以前の [6317c05版](https://github.com/UkkyaGuiyo/vapb-preview/raw/refs/heads/preview/downloads/VAPB-alpha-6317c05.zip) と b3f141d版は上書きせず残しています。それらのGUI実証を新ZIPのGUI検証とは扱いません。

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

出力対象は選択部品の属する現在のBlenderメンバーと、必要なArmatureです。元PrefabがFBX内の一部だけを参照していても、FBX全体がそのメンバーへ読み込まれる場合があります。元Prefabだけの正確なMesh範囲は未確認であり、出力前に部品を確認してください。manifestのCOMPLETEは要求した出力処理の完了を示し、元Prefabとの完全一致を保証しません。UVの自動展開は行いません。元テクスチャは参照先の元ファイルを取得し、存在しないPSDレイヤーなどは作りません。FBXにはUnity／VRChat固有Componentの完全な設定を格納できません。既存ファイルの上書きを避けるため、空の新しい保存先を使ってください。

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

アドオンの Blender 最小バージョン表示は 5.2.0、製品仕様は Blender 5.2.1 LTS を対象にしています。この固定ZIPは Blender 5.2.3 LTS で通常インストールとメニュー操作を実GUI確認しました。実データの代表操作は別のAPI検証です。ZIP内READMEはビルド時点の記録で、検証後の結果はこのREADMEと検証記録に記載しています。これら以外の Blender バージョンは未検証です。Unity 側ヘルパーは Unity Editor API を使います。既存の限定的な記録には Unity 2022.3.22f1 が含まれますが、全 Unity バージョンや全プロジェクトでの互換性を示すものではありません。VRChat SDK と実行時互換性は未検証です。

## ライセンス

Blender アドオン、ドキュメント、テストは GPL-3.0-or-later です（`LICENSE`）。`unity_editor/` 内の独立した Unity Editor ヘルパーは MIT です（`unity_editor/LICENSE`）。対象範囲と外部依存関係は `LICENSES.md` を参照してください。これらのライセンスは、VAPB で扱うアバター、テクスチャ、Shader などのアセット利用権を与えるものではありません。
